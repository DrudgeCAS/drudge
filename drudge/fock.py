"""
Drudge classes for working with operators on Fock spaces.

In this module, several drudge instances are defined for working with creation
and annihilation operators acting on fermion or boson Fock spaces.
"""

import functools
import typing
import warnings

from pyspark import RDD
from sympy import (
    KroneckerDelta,
    IndexedBase,
    Expr,
    Symbol,
    Rational,
    symbols,
    conjugate,
    factorial,
)

from ._tceparser import parse_tce_out
from .canon import NEG, IDENT
from .canonpy import Perm
from .drudge import Tensor, TensorDef
from .term import Vec, Range, try_resolve_range, Term
from .utils import sympy_key, ensure_expr, EnumSymbs
from .wick import WickDrudge


#
# General fermion/boson algebra
# -----------------------------
#


class CranChar(EnumSymbs):
    """Transformation characters of creation/annihilation operators.

    It values, which can be accessed as the class attributes ``CR`` and ``AN``
    also forwarded to module scope, should be used as the first index to vectors
    representing creation and annihilation operators.
    """

    _symbs_ = [("CR", r"\dagger"), ("AN", "")]


CR = CranChar.CR
AN = CranChar.AN

FERMI = -1
BOSE = 1


class FockDrudge(WickDrudge):
    """Drudge for doing fermion/boson operator algebra on Fock spaces.

    This is the general base class for drudges working on fermion/boson operator
    algebras.  Here general methods are defined for working on these algebraic
    systems, but no problem specific information, like ranges or operator base,
    is defined.  Generally, operators for Fock space problems has either
    :py:data:`CR` or :py:data:`AN` as the first index to give their creation or
    annihilation character.

    To customize the details of the commutation rules, properties
    :py:attr:`op_parser` and :py:attr:`ancr_contractor` can be overridden.

    """

    def __init__(self, *args, exch=FERMI, **kwargs):
        """Initialize the drudge.

        Parameters
        ----------

        exch : {1, -1}

            The exchange symmetry for the Fock space.  Constants
            :py:data:`FERMI` and :py:data:`BOSE` can be used.

        """

        super().__init__(*args, **kwargs)
        if exch == FERMI or exch == BOSE:
            self._exch = exch
        else:
            raise ValueError(
                f"Invalid exchange: {exch}, expecting plus/minus 1"
            )

        self.set_tensor_method("eval_vev", self.eval_vev)
        self.set_tensor_method("eval_phys_vev", self.eval_phys_vev)
        self.set_tensor_method("dagger", self.dagger)

    @property
    def contractor(self):
        """Get the contractor for the algebra.

        The operations are read here on-the-fly so that possibly customized
        behaviour from the subclasses can be read.
        """

        ancr_contractor = self.ancr_contractor
        op_parser = self.op_parser

        return functools.partial(
            _contr_field_ops,
            ancr_contractor=ancr_contractor,
            op_parser=op_parser,
        )

    @property
    def phase(self):
        """Get the phase for the commutation rules."""
        return self._exch

    @property
    def comparator(self):
        """Get the comparator for the normal ordering operation."""

        op_parser = self.op_parser

        return functools.partial(_compare_field_ops, op_parser=op_parser)

    @property
    def vec_colour(self):
        """Get the vector colour evaluator."""

        op_parser = self.op_parser

        return functools.partial(_get_field_op_colour, op_parser=op_parser)

    OP_PARSER = typing.Callable[
        [Vec, Term], typing.Tuple[typing.Any, CranChar, typing.Sequence[Expr]]
    ]

    @property
    def op_parser(self) -> OP_PARSER:
        """Get the parser for field operators.

        The result should be a callable taking an vector and return a triple of
        operator base, operator character, and the actual indices to the
        operator.  This can be helpful for cases where the interpretation of the
        operators needs to be tweaked.
        """
        return parse_field_op

    ANCR_CONTRACTOR = typing.Callable[
        [typing.Any, typing.Sequence[Expr], typing.Any, typing.Sequence[Expr]],
        Expr,
    ]

    @property
    def ancr_contractor(self) -> ANCR_CONTRACTOR:
        """Get the contractor for annihilation and creation operators.

        In this drudge, the contraction between creation/creation,
        annihilation/annihilation, and creation/annihilation operators are
        fixed.  By this property, a callable for contracting annihilation
        operators with a creation operator can be given.  It will be called with
        the base and indices (excluding the character) of the annihilation
        operators and the base and indices of the creation operator.  A simple
        SymPy expression is expected in the result.

        By default, the result will be a simple delta.
        """

        return _contr_ancr_by_delta

    def eval_vev(self, tensor: Tensor, contractor):
        """Evaluate vacuum expectation value.

        The contractor needs to be given as a callable accepting two operators.
        And this function is also set as a tensor method by the same name.
        """

        return Tensor(
            self,
            self.normal_order(
                tensor.terms, comparator=None, contractor=contractor
            ),
        )

    def eval_phys_vev(self, tensor: Tensor):
        """Evaluate expectation value with respect to the physical vacuum.

        Here the contractor from normal-ordering will be used.  And this
        function is also set as a tensor method by the same name.
        """

        return Tensor(self, self.normal_order(tensor.terms, comparator=None))

    def normal_order(self, terms: RDD, **kwargs):
        """Normal order the field operators.

        Here the normal-ordering operation of general Wick drudge will be
        invoked twice to ensure full simplification.
        """

        step1 = super().normal_order(terms, **kwargs)
        res = super().normal_order(step1, **kwargs)
        if self._exch == FERMI:
            res = res.filter(_is_not_zero_by_nilp)
        return res

    @staticmethod
    def dagger(tensor: Tensor, real=False):
        """Get the Hermitian adjoint of the given operator.

        This method is also set to be a tensor method with the same name.

        Parameters
        ----------

        tensor
            The operator to take the Hermitian adjoint for.

        real
            If the amplitude is assumed to be real.  Note that this need not be
            set if the amplitude is concrete real numbers.

        """

        return tensor.apply(
            lambda terms: terms.map(functools.partial(_get_dagger, real=real))
        )

    def set_n_body_base(self, base: IndexedBase, n_body: int):
        """Set an indexed base as an n-body interaction.

        The symmetry of an n-body interaction has full permutation symmetry
        among the corresponding slots in the first and second half.

        When the body count if less than two, no symmetry is added.  And the
        added symmetry is for the given valence only.

        """

        # Normalize the type of n_body.
        n_body = int(n_body)

        # No symmetry going to be added for less than two body.
        if n_body < 2:
            return

        begin1 = 0
        end1 = n_body
        begin2 = end1
        end2 = 2 * n_body

        cycl = Perm(
            self._form_cycl(begin1, end1) + self._form_cycl(begin2, end2)
        )
        transp = Perm(
            self._form_transp(begin1, end1) + self._form_transp(begin2, end2)
        )

        self.set_symm(base, cycl, transp, valence=2 * n_body)

        return

    def set_dbbar_base(self, base: IndexedBase, n_body: int, n_body2=None):
        """Set an indexed base as a double-bar interaction.

        A double barred interaction has full permutation symmetry among its
        first half of slots and its second half individually.  For fermion
        field, the permutation is assumed to be anti-commutative.

        The size of the second half can be given by another optional argument,
        or it is assumed to have the same size as the first half.  It can also
        be zero, which gives one chunk of symmetric slots only.
        """

        n_body = int(n_body)

        n_body2 = n_body if n_body2 is None else int(n_body2)
        n_slots = n_body + n_body2

        transp_acc = NEG if self._exch == FERMI else IDENT
        cycl_accs = [
            NEG if self._exch == FERMI and i % 2 == 0 else IDENT
            for i in [n_body, n_body2]
        ]  # When either body is zero, this value is kinda wrong but not used.

        gens = []

        if n_body > 1:
            second_half = list(range(n_body, n_slots))
            gens.append(
                Perm(self._form_cycl(0, n_body) + second_half, cycl_accs[0])
            )
            gens.append(
                Perm(self._form_transp(0, n_body) + second_half, transp_acc)
            )

        if n_body2 > 1:
            first_half = list(range(0, n_body))
            gens.append(
                Perm(
                    first_half + self._form_cycl(n_body, n_slots), cycl_accs[1]
                )
            )
            gens.append(
                Perm(
                    first_half + self._form_transp(n_body, n_slots), transp_acc
                )
            )

        self.set_symm(base, gens, valence=n_slots)

        return

    @staticmethod
    def _form_cycl(begin, end):
        """Form the pre-image for a cyclic permutation over the given range."""
        before_end = end - 1
        res = [before_end]
        res.extend(range(begin, before_end))
        return res

    @staticmethod
    def _form_transp(begin, end):
        """Form a pre-image array with the first two points transposed."""
        res = list(range(begin, end))
        res[0], res[1] = res[1], res[0]
        return res

    def _latex_vec(self, vec):
        """Get the LaTeX form of field operators."""

        head = r"{}^{{{}}}".format(
            vec.label, self._latex_sympy(vec.indices[0])
        )
        indices = ", ".join(self._latex_sympy(i) for i in vec.indices[1:])
        return r"{}_{{{}}}".format(head, indices)

    _latex_vec_mul = " "


def parse_field_op(op: Vec, _: Term):
    """Get the operator label, character and actual indices.

    ValueError will be raised if the given operator does not satisfy the format
    for field operators.
    """

    indices = op.indices
    if len(indices) < 1 or (indices[0] != CR and indices[0] != AN):
        raise ValueError(
            "Invalid field operator", op, "expecting operator character"
        )

    return op.label, indices[0], indices[1:]


def _compare_field_ops(
    op1: Vec, op2: Vec, term: Term, op_parser: FockDrudge.OP_PARSER
):
    """Compare the given field operators.

    Here we try to emulate physicists' convention as much as possible.  The
    annihilation operators are ordered in reversed direction.
    """

    label1, char1, indices1 = op_parser(op1, term)
    label2, char2, indices2 = op_parser(op2, term)

    if char1 == CR and char2 == AN:
        return True
    elif char1 == AN and char2 == CR:
        return False

    key1 = (label1, [sympy_key(i) for i in indices1])
    key2 = (label2, [sympy_key(i) for i in indices2])

    # Equal key are always true for stable insert sort.
    if char1 == CR:
        return key1 <= key2
    else:
        return key1 >= key2


def _contr_field_ops(
    op1: Vec,
    op2: Vec,
    term: Term,
    ancr_contractor: FockDrudge.ANCR_CONTRACTOR,
    op_parser: FockDrudge.OP_PARSER,
):
    """Contract two field operators.

    Here we work by the fermion-boson commutation rules.  The contractor is only
    going to be called for annihilation creation pairs, with all others implied
    by the algebra.

    """

    label1, char1, indices1 = op_parser(op1, term)
    label2, char2, indices2 = op_parser(op2, term)

    if char1 == char2 or char1 == CR:
        return 0

    return ancr_contractor(label1, indices1, label2, indices2)


def _contr_ancr_by_delta(label1, indices1, label2, indices2):
    """Contract an annihilation and a creation operator by delta."""

    # For the delta contraction, some additional checking is needed for it to
    # make sense.

    err_header = "Invalid field operators to contract by delta"

    # When the operators are on different base, it is likely that delta is not
    # what is intended.

    if label1 != label2:
        raise ValueError(
            err_header, (label1, label2), "expecting the same base"
        )

    if len(indices1) != len(indices2):
        raise ValueError(
            err_header,
            (indices1, indices2),
            "expecting same number of indices",
        )

    res = 1
    for i, j in zip(indices1, indices2):
        # TODO: Maybe support continuous indices here.
        res *= KroneckerDelta(i, j)

    return res


def _get_field_op_colour(idx, vec, term, op_parser: FockDrudge.OP_PARSER):
    """Get the colour of field operators.

    Here the annihilation part is specially treated for better compliance with
    conventions in physics.
    """

    char = vec.indices[0]
    assert char == CR or char == AN
    return char, idx if char == CR else -idx


def _get_dagger(term: Term, real: bool):
    """Take the dagger of a term."""

    new_vecs = []
    for vec in reversed(term.vecs):
        base = vec.base
        indices = vec.indices
        if indices[0] == CR:
            new_char = AN
        elif indices[0] == AN:
            new_char = CR
        else:
            raise ValueError(
                "Invalid vector to take Hermitian adjoint",
                vec,
                "expecting CR/AN character in first index",
            )
        new_vecs.append(base[(new_char,) + indices[1:]])

    return term.map(
        lambda x: x if real else conjugate(x),
        vecs=tuple(new_vecs),
        skip_vecs=True,
    )


def _is_not_zero_by_nilp(term: Term):
    """Test if a term is not zero by nilpotency of the operators."""
    vecs = term.vecs
    return all(vecs[i] != vecs[i + 1] for i in range(0, len(vecs) - 1))


#
# Detailed problems
# -----------------
#


def conserve_spin(*spin_symbs):
    """Get a callback giving true only if the given spin values are conserved.

    Here by conserving the spin, we mean the very strict sense that the values
    of the first half of the symbols in the given dictionary exactly matches the
    corresponding values in the second half.
    """

    n_symbs = len(spin_symbs)
    if n_symbs % 2 == 1:
        raise ValueError(
            "Invalid spin symbols",
            spin_symbs,
            "expecting a even number of them",
        )
    n_particles = n_symbs // 2

    outs = spin_symbs[0:n_particles]
    ins = spin_symbs[n_particles:n_symbs]

    def test_conserve(symbs_dict):
        """Test if the spin values from the dictionary is conserved."""
        return all(symbs_dict[i] == symbs_dict[j] for i, j in zip(ins, outs))

    return test_conserve


class GenMBDrudge(FockDrudge):
    """Drudge for general many-body problems.

    In a general many-body problem, a state for the particle is given by a
    symbolic **orbital** quantum numbers for the external degrees of freedom and
    optionally a concrete **spin** quantum numbers for the internal states of
    the particles.  Normally, there is just one orbital quantum number and one
    or no spin quantum number.

    In this model, a default Hamiltonian of the model is constructed from a
    one-body and two-body interaction, both of them are assumed to be spin
    conserving.

    Also Einstein summation convention is assumed for this drudge in drudge
    scripts.

    .. attribute:: op

        The vector base for the field operators.

    .. attribute:: cr

        The base for the creation operator.

    .. attribute:: an

        The base for the annihilation operator.

    .. attribute:: orb_ranges

        A list of all the ranges for the orbital quantum number.

    .. attribute::  spin_vals

        A list of all the explicit spin values.  None if spin values are not
        given.

    .. attribute:: spin_range

        The symbolic range for spin values.  None if it is not given.

    .. attribute:: orig_ham

        The original form of the Hamiltonian without any simplification.

    .. attribute:: ham

        The simplified form of the Hamiltonian.

    """

    def __init__(
        self,
        *args,
        exch=FERMI,
        op_label="c",
        orb=((Range("L"), "abcdefghijklmnopq"),),
        spin=(),
        one_body=IndexedBase("t"),
        two_body=IndexedBase("u"),
        dbbar=False,
        **kwargs,
    ):
        """Initialize the drudge object.

        Parameters
        ----------

        exch
            The exchange symmetry of the identical particle.

        op_label
            The label for the field operators.  The creation operator will be
            registered in the names archive by name of this label with ``_dag``
            appended.  And the annihilation operator will be registered with a
            single trailing underscore.

        orb
            An iterable of range and dummies pairs for the orbital quantum
            number, which is considered to be over the **direct sum** of all the
            ranges given.  All the ranges and dummies will be registered to the
            names archive by :py:meth:`Drudge.set_dumms`.

        spin
            The explicit spin quantum number.  It can be an empty sequence to
            disable explicit spin.  Or it can be a sequence of SymPy expressions
            to give explicit spin values, or a range and dummies pair for
            symbolic spin.

        one_body
            The indexed base for the amplitude in the one-body part of the
            Hamiltonian.  It will also be added to the name archive.

            For developers: if it is given as None, the Hamiltonian will not be
            built.

        two_body
            The indexed base for the two-body part of the Hamiltonian.  It will
            also be added to the name archive.

        dbbar : bool
            If the two-body part of the Hamiltonian is double-bared.

        """

        super().__init__(*args, exch=exch, **kwargs)

        #
        # Setting configuration.
        #

        self.default_einst = True

        #
        # Create the field operator
        #

        op = Vec(op_label)
        cr = op[CR]
        an = op[AN]
        self.op = op
        self.cr = cr
        self.an = an

        self.set_name(
            **{str(op) + "_": an, str(op) + "_dag": cr, str(op) + "dag_": cr}
        )

        #
        # Ranges, dummies, and spins.
        #

        orb_ranges = []
        for range_, dumms in orb:
            self.set_dumms(range_, dumms)
            orb_ranges.append(range_)
        self.orb_ranges = orb_ranges

        spin = list(spin)
        if len(spin) == 0:
            has_spin = False
            spin_range = None

            self.spin_vals = None
            self.spin_range = None

        elif isinstance(spin[0], Range):
            has_spin = True
            if len(spin) != 2:
                raise ValueError(
                    "Invalid spin specification",
                    spin,
                    "expecting range/dummies pair.",
                )
            self.set_dumms(spin[0], spin[1])
            spin_range = spin[0]

            self.spin_vals = None
            self.spin_range = spin_range

        else:
            has_spin = True
            spin_vals = [ensure_expr(i) for i in spin]
            if len(spin_vals) == 1:
                warnings.warn(
                    "Just one spin value is given: "
                    "consider dropping it for better performance"
                )
            spin_range = spin_vals

            self.spin_vals = spin_vals
            self.spin_range = None

        self.add_resolver_for_dumms()

        # These dummies are used temporarily and will soon be reset.  They are
        # here, rather than the given dummies directly, because we might need to
        # dummy for multiple orbital ranges.
        #
        # They are created as tuple so that they can be easily used for
        # indexing.

        orb_dumms = tuple(
            Symbol("internalOrbitPlaceholder{}".format(i)) for i in range(4)
        )
        spin_dumms = tuple(
            Symbol("internalSpinPlaceholder{}".format(i)) for i in range(2)
        )

        orb_sums = [(i, orb_ranges) for i in orb_dumms]
        spin_sums = [(i, spin_range) for i in spin_dumms]

        #
        # Actual Hamiltonian building.
        #
        # It is disabled by a None one-body part.  Nothing should come after
        # this.
        #

        if one_body is None:
            return

        self.one_body = one_body
        self.set_name(one_body)  # No symmetry for it.

        one_body_sums = orb_sums[:2]
        if has_spin:
            one_body_sums.append(spin_sums[0])

        if has_spin:
            one_body_ops = (
                cr[orb_dumms[0], spin_dumms[0]]
                * an[orb_dumms[1], spin_dumms[0]]
            )
        else:
            one_body_ops = cr[orb_dumms[0]] * an[orb_dumms[1]]

        one_body_ham = self.sum(
            *one_body_sums, one_body[orb_dumms[:2]] * one_body_ops
        )

        if dbbar:
            two_body_coeff = Rational(1, 4)
            self.set_dbbar_base(two_body, 2)
        else:
            two_body_coeff = Rational(1, 2)
            self.set_n_body_base(two_body, 2)
        self.two_body = two_body

        two_body_sums = orb_sums
        if has_spin:
            two_body_sums.extend(spin_sums[:2])

        if has_spin:
            two_body_ops = (
                cr[orb_dumms[0], spin_dumms[0]]
                * cr[orb_dumms[1], spin_dumms[1]]
                * an[orb_dumms[3], spin_dumms[1]]
                * an[orb_dumms[2], spin_dumms[0]]
            )
        else:
            two_body_ops = (
                cr[orb_dumms[0]]
                * cr[orb_dumms[1]]
                * an[orb_dumms[3]]
                * an[orb_dumms[2]]
            )

        two_body_ham = self.sum(
            *two_body_sums, two_body_coeff * two_body[orb_dumms] * two_body_ops
        )

        # We need to at lease remove the internal symbols.
        orig_ham = (one_body_ham + two_body_ham).reset_dumms()
        self.orig_ham = orig_ham

        simpled_ham = orig_ham.simplify()
        self.ham = simpled_ham


class PartHoleDrudge(GenMBDrudge):
    """Drudge for the particle-hole problems.

    This is a shallow subclass of :py:class:`GenMBDrudge` for the particle-hole
    problems.  It contains different forms of the Hamiltonian.

    .. attribute:: orig_ham

        The original form of the Hamiltonian, written in terms of bare one-body
        and two-body interaction tensors without normal-ordering with respect to
        the Fermion vacuum.

    .. attribute:: full_ham

        The full form of the Hamiltonian in terms of the bare interaction
        tensors, normal-ordered with respect to the Fermi vacuum.

    .. attribute:: ham_energy

        The zero energy inside the full Hamiltonian.

    .. attribute:: one_body_ham

        The one-body part of the full Hamiltonian, written in terms of the bare
        interaction tensors.

    .. attribute:: ham

        The most frequently used form of the Hamiltonian, written in terms of
        Fock matrix and the two-body interaction tensor.


    """

    DEFAULT_PART_DUMMS = tuple(Symbol(i) for i in "abcd") + tuple(
        Symbol("a{}".format(i)) for i in range(50)
    )
    DEFAULT_HOLE_DUMMS = tuple(Symbol(i) for i in "ijkl") + tuple(
        Symbol("i{}".format(i)) for i in range(50)
    )
    DEFAULT_ORB_DUMMS = tuple(Symbol(i) for i in "pqrs") + tuple(
        Symbol("p{}".format(i)) for i in range(50)
    )

    def __init__(
        self,
        *args,
        op_label="c",
        part_orb=(Range("V", 0, Symbol("nv")), DEFAULT_PART_DUMMS),
        hole_orb=(Range("O", 0, Symbol("no")), DEFAULT_HOLE_DUMMS),
        all_orb_dumms=DEFAULT_ORB_DUMMS,
        spin=(),
        one_body=IndexedBase("t"),
        two_body=IndexedBase("u"),
        fock=IndexedBase("f"),
        dbbar=True,
        **kwargs,
    ):
        """Initialize the particle-hole drudge."""

        self.part_range = part_orb[0]
        self.hole_range = hole_orb[0]

        super().__init__(
            *args,
            exch=FERMI,
            op_label=op_label,
            orb=(part_orb, hole_orb),
            spin=spin,
            one_body=one_body,
            two_body=two_body,
            dbbar=dbbar,
            **kwargs,
        )

        self.all_orb_dumms = tuple(all_orb_dumms)
        self.set_name(*self.all_orb_dumms)
        self.add_resolver(
            {i: (self.part_range, self.hole_range) for i in all_orb_dumms}
        )

        full_ham = self.ham
        full_ham.cache()
        self.full_ham = full_ham

        self.ham_energy = full_ham.filter(lambda term: term.is_scalar)

        self.one_body_ham = full_ham.filter(lambda term: len(term.vecs) == 2)
        two_body_ham = full_ham.filter(lambda term: len(term.vecs) == 4)

        # We need to rewrite the one-body part in terms of Fock matrices.
        self.fock = fock
        one_body_terms = []
        for i in self.one_body_ham.local_terms:
            if i.amp.has(one_body):
                one_body_terms.append(i.subst({one_body: fock}))
        rewritten_one_body_ham = self.create_tensor(one_body_terms)

        ham = rewritten_one_body_ham + two_body_ham
        ham.cache()
        self.ham = ham

        self.set_tensor_method("eval_fermi_vev", self.eval_fermi_vev)

        self.set_name(no=self.hole_range.size)
        self.set_name(nv=self.part_range.size)

    @property
    def op_parser(self):
        """Get the special operator parser for particle-hole problems.

        Here when the first index to the operator is resolved to be a hole
        state, the creation/annihilation character of the operator will be
        flipped.
        """

        resolvers = self.resolvers
        hole_range = self.hole_range

        def parse_parthole_ops(op: Vec, term: Term):
            """Parse the operator for particle/hole field operator."""
            label, char, indices = parse_field_op(op, term)
            orb_range = try_resolve_range(
                indices[0], dict(term.sums), resolvers.value
            )
            if orb_range is None:
                raise ValueError(
                    "Invalid orbit value",
                    indices[0],
                    "expecting particle or hole",
                )
            if orb_range == hole_range:
                char = AN if char == CR else CR
            return label, char, indices

        return parse_parthole_ops

    def eval_fermi_vev(self, tensor: Tensor):
        """Evaluate expectation value with respect to Fermi vacuum.

        This is just an alias to the actual :py:meth:`FockDrudge.eval_phys_vev`
        method to avoid confusion about the terminology in particle-hole
        problems.  And it is set as a tensor method by the same name.
        """
        return self.eval_phys_vev(tensor)

    def parse_tce(
        self, tce_out: str, cc_bases: typing.Mapping[int, IndexedBase]
    ):
        """Parse TCE output into a tensor.

        The CC amplitude bases should be given as a dictionary mapping from the
        excitation order to the actual base.
        """

        def range_cb(label):
            """The range call-back."""
            return self.part_range if label[0] == "p" else self.hole_range

        def base_cb(name, indices):
            """Get the indexed base for a name in TCE output."""
            if name == "f":
                return self.fock
            elif name == "v":
                return self.two_body
            elif name == "t":
                return cc_bases[len(indices) // 2]
            else:
                raise ValueError("Invalid base", name, "in TCE output.")

        terms, free_vars = parse_tce_out(tce_out, range_cb, base_cb)

        # Here we assume that the symbols from directly conversion from TCE
        # output will not conflict with the canonical dummies.
        substs = {}
        for range_, symbs in free_vars.items():
            for i, j in zip(
                sorted(symbs, key=lambda x: int(x.name[1:])),
                self.dumms.value[range_],
            ):
                substs[i] = j

        return self.create_tensor([i.subst(substs) for i in terms])


class SpinOneHalf(EnumSymbs):
    """Labels for an orthogonal basis for a spin one-half particle.

    It values, which can be accessed as the class or module attributes ``UP``
    and ``DOWN``, can optionally be used to denote the direction of a spin
    one-half particle.

    """

    _symbs_ = [("UP", r"\uparrow"), ("DOWN", r"\downarrow")]


UP = SpinOneHalf.UP
DOWN = SpinOneHalf.DOWN


class SpinOneHalfGenDrudge(GenMBDrudge):
    """Drudge for many-body problems of particles with explicit 1/2 spin.

    This is just a shallow subclass of the drudge for general many-body
    problems, with exchange set to fermi and has explicit spin values of
    :py:data:`UP` and :py:data:`DOWN`.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the drudge object."""

        super().__init__(*args, exch=FERMI, spin=[UP, DOWN], **kwargs)


class SpinOneHalfPartHoleDrudge(PartHoleDrudge):
    """Drudge for the particle-hole problems with explicit one-half spin.

    This is a shallow subclass over the general particle-hole drudge without
    explicit spin.  The spin values are given explicitly, which are set to
    :py:data:`UP` and :py:data:`DOWN` by default.  And the double-bar of the
    two-body interaction is disabled.  And some additional dummies traditional
    in the field are also added.

    """

    def __init__(
        self,
        *args,
        part_orb=(
            Range("V", 0, Symbol("nv")),
            PartHoleDrudge.DEFAULT_PART_DUMMS + symbols("beta gamma"),
        ),
        hole_orb=(
            Range("O", 0, Symbol("no")),
            PartHoleDrudge.DEFAULT_HOLE_DUMMS + symbols("u v"),
        ),
        spin=(UP, DOWN),
        **kwargs,
    ):
        """Initialize the particle-hole drudge."""

        super().__init__(
            *args,
            spin=spin,
            dbbar=False,
            part_orb=part_orb,
            hole_orb=hole_orb,
            **kwargs,
        )


class RestrictedPartHoleDrudge(SpinOneHalfPartHoleDrudge):
    """Drudge for the particle-hole problems on restricted reference.

    Similar to :py:class:`SpinOneHalfPartHoldDrudge`, this drudge deals with
    particle-hole problems with explicit one-half spin.  However, here the spin
    quantum number is summed symbolically.  This gives **much** faster
    derivations for theories based on restricted reference, but offers less
    flexibility.

    .. attribute:: spin_range

        The symbolic range for spin values.

    .. attribute:: spin_dumms

        The dummies for the spin quantum number.

    .. attribute:: e_

        Tensor definition for the unitary group generators.  It should be
        indexed with the upper and lower indices to the :math:`E` operator.  It
        is also registered in the name archive as ``e_``.

    """

    def __init__(
        self,
        *args,
        spin_range=Range(r"\uparrow\downarrow", 0, 2),
        spin_dumms=tuple(Symbol("sigma{}".format(i)) for i in range(50)),
        **kwargs,
    ):
        """Initialize the restricted particle-hole drudge."""

        super().__init__(*args, spin=(spin_range, spin_dumms), **kwargs)
        self.add_resolver({UP: spin_range, DOWN: spin_range})

        self.spin_range = spin_range
        self.spin_dumms = self.dumms.value[spin_range]

        sigma = self.dumms.value[spin_range][0]
        p = Symbol("p")
        q = Symbol("q")
        self.e_ = TensorDef(
            Vec("E"),
            (p, q),
            self.sum(
                (sigma, spin_range), self.cr[p, sigma] * self.an[q, sigma]
            ),
        )
        self.set_name(e_=self.e_)


class BogoliubovDrudge(GenMBDrudge):
    r"""Drudge for general Bogoliubov problems.

    Based on :py:class:`GenMBDrudge`, this class performs the Bogoliubov
    transformation to the Hamiltonian as defined in [RS1980]_.  Here the
    creation and annihilation operators of bare fermions :math:`c` and
    :math:`c^\dagger` are going to be substituted as

    .. math::

        c^\dagger_l &= \sum_k u^*_{lk} \beta^\dagger_k + v_{lk} \beta_k \\
        c_l &= \sum_k u_{lk} \beta_k + v^*_{lk} \beta^\dagger_k \\

    which comes from the inversion of

    .. math::

        \beta^\dagger_k = \sum_l u_{lk} c^\dagger_l + v_{lk} c_l

    Then the Hamiltonian is going to be rewritten with matrix elements formatted
    according to the given format.  During the rewritten, the new matrix
    elements follows the normalization convention as in [SDHJ2015]_.

    .. [RS1980] P Ring and P Schuck, The Nuclear Many-Body Problem,
       Springer-Verlag 1980

    .. [SDHJ2015] A Signoracci, T Duguet, G Hagen, and G R Jansen, Ab initio
       Bogoliubov coupled cluster theory for open-shell nuclei, Phys Rev C 91
       (2015), 064320

    Parameters
    ----------

    ctx
        The Spark context.

    u_base
        The indexed base for the :math:`U` part of the Bogoliubov
        transformation.

    v_base
        The indexed base for the :math:`V` part.

    one_body
        The indexed base for the one-body part of the original Hamiltonian.

    two_body
        The indexed base for the two-body part of the original Hamiltonian.

    qp_op_label
        The label for the quasi-particle operators.

    ham_me_format
        The format for the matrix elements of the rewritten Hamiltonian.  It is
        going to be formatted with the creation and annihilation order of the
        quasi-particles to get the name for the indexed base of the Hamiltonian
        matrix elements.

    kwargs
        All the rest of the keyword arguments are given to the base class.

    """

    DEFAULT_P_DUMMS = tuple(Symbol("l{}".format(i)) for i in range(1, 100))
    DEFAULT_QP_DUMMS = tuple(Symbol("k{}".format(i)) for i in range(1, 100))

    def __init__(
        self,
        ctx,
        p_range=Range("L"),
        p_dumms=DEFAULT_P_DUMMS,
        qp_range=Range("Q", 0, Symbol("N")),
        qp_dumms=DEFAULT_QP_DUMMS,
        u_base=IndexedBase("u"),
        v_base=IndexedBase("v"),
        one_body=IndexedBase("epsilon"),
        two_body=IndexedBase("vbar"),
        dbbar=True,
        qp_op_label=r"\beta",
        ham_me_format="H^{{{}{}}}",
        ham_me_name_format="H{}{}",
        **kwargs,
    ):
        """Initialize the drudge object."""

        super().__init__(
            ctx,
            orb=((p_range, p_dumms),),
            one_body=one_body,
            two_body=two_body,
            dbbar=dbbar,
            **kwargs,
        )
        self.set_dumms(qp_range, qp_dumms)
        self.add_resolver_for_dumms()
        self.p_range = p_range
        self.p_dumms = p_dumms
        self.qp_range = qp_range
        self.qp_dumms = qp_dumms

        qp_op = Vec(qp_op_label)
        qp_cr = qp_op[CR]
        qp_an = qp_op[AN]
        self.qp_op = qp_op
        self.qp_cr = qp_cr
        self.qp_an = qp_an

        qp_op_str = str(qp_op).replace("\\", "")
        self.set_name(
            **{
                qp_op_str + "_": qp_an,
                qp_op_str + "_dag": qp_cr,
                qp_op_str + "dag_": qp_cr,
            }
        )

        self.u_base = u_base
        self.v_base = v_base

        cr = self.cr
        an = self.an
        l = p_dumms[0]
        k = qp_dumms[0]
        self.f_in_qp = [
            self.define(
                cr[l],
                self.einst(
                    conjugate(u_base[l, k]) * qp_cr[k]
                    + v_base[l, k] * qp_an[k]
                ),
            ),
            self.define(
                an[l],
                self.einst(
                    u_base[l, k] * qp_an[k]
                    + conjugate(v_base[l, k]) * qp_cr[k]
                ),
            ),
        ]

        orig_ham = self.ham
        rewritten, ham_mes = self.write_in_qp(
            orig_ham, ham_me_format, name_format=ham_me_name_format
        )
        self.orig_ham = orig_ham
        self.ham = rewritten
        self.ham_mes = ham_mes

        self.set_tensor_method("eval_bogoliubov_vev", self.eval_bogoliubov_vev)

    def write_in_qp(
        self, tensor: Tensor, format_: str, name_format=None, set_symms=True
    ):
        """Write the given expression in terms of quasi-particle operators.

        The given expression will be rewritten in terms of the quasi-particle
        operators.  Then the possibly complex matrix elements are all going to
        be replaced by simple tensors, whose names can be tuned.

        Note that for a term with creation order :math:`m` and annihilation
        order :math:`n`, the term carries a normalization of division over
        :math:`m! n!`.

        Parameters
        ----------

        tensor
            The expression to be rewritten.  It should be an expression in terms
            of the physical fermion operators.

        format_
            The format string to be used for the new matrix elements, which is
            going to be formatted with the quasi-particle creation and
            annihilation orders.

        name_format
            With the same usage as ``format_``, when it is given as a string, it
            will be used to add the new indexed bases into the name archive.

        set_symms
            If automatic symmetries are going to be set for the new matrix
            elements.

        Return
        ------

        The rewritten form of the expression, as well as a list of tensor
        definitions for the new matrix elements.

        """

        terms = tensor.subst_all(self.f_in_qp).simplify().local_terms

        # Internal book keeping, maps the cr/an order to lhs and the rhs terms
        # of the definition of the new matrix element.
        transf = {}

        rewritten_terms = []

        for term in terms:
            cr_order = 0
            an_order = 0
            indices = []
            for i in term.vecs:
                if len(i.indices) != 2:
                    raise ValueError(
                        "Invalid operator to rewrite, one index expected", i
                    )
                char, index = i.indices
                if char == CR:
                    assert an_order == 0
                    cr_order += 1
                elif char == AN:
                    an_order += 1
                else:
                    assert False

                indices.append(index)

            norm = factorial(cr_order) * factorial(an_order)
            order = (cr_order, an_order)
            tot_order = cr_order + an_order

            base = IndexedBase(format_.format(*order))
            if name_format is not None:
                base_name = name_format.format(*order)
                self.set_name(**{base_name: base})

            indices[cr_order:tot_order] = reversed(indices[cr_order:tot_order])
            if tot_order > 0:
                new_amp = base[tuple(indices)]
            else:
                new_amp = base.label
            orig_amp = term.amp

            new_sums = []
            wrapped_sums = []
            for i in term.sums:
                if new_amp.has(i[0]):
                    new_sums.append(i)
                else:
                    wrapped_sums.append(i)

            def_term = Term(
                sums=tuple(wrapped_sums), amp=orig_amp * norm, vecs=()
            )

            if order in transf:
                entry = transf[order]
                assert entry[0] == new_amp
                entry[1].append(def_term)
            else:
                transf[order] = (new_amp, [def_term])
                rewritten_terms.append(
                    Term(
                        sums=tuple(new_sums),
                        amp=new_amp / norm,
                        vecs=term.vecs,
                    )
                )
                if set_symms and (cr_order > 1 or an_order > 1):
                    self.set_dbbar_base(base, cr_order, an_order)

        defs = [
            self.define(lhs, self.create_tensor(rhs_terms))
            for lhs, rhs_terms in transf.values()
        ]

        return self.create_tensor(rewritten_terms), defs

    def eval_bogoliubov_vev(self, tensor: Tensor):
        """Evaluate expectation value with respect to Bogoliubov vacuum.

        This is just an alias to the actual :py:meth:`FockDrudge.eval_phys_vev`
        method to avoid confusion.  And it is set as a tensor method by the same
        name.
        """
        return self.eval_phys_vev(tensor)


class MixDrudge(FockDrudge):
    """Drudge for independent fermion and boson operator algebras.

    Fermion operators are kept to the left of boson operators.  Operators from
    the two sectors commute and have no cross contractions.  Normal ordering
    is performed independently in the fermion and boson sectors.
    """

    def __init__(self, *args, fermion_labels, boson_labels, **kwargs):
        super().__init__(*args, exch=BOSE, **kwargs)

        self.fermion_labels = frozenset(fermion_labels)
        self.boson_labels = frozenset(boson_labels)

        overlap = self.fermion_labels & self.boson_labels
        if overlap:
            raise ValueError(
                "Operator labels cannot be both fermionic and bosonic",
                overlap,
            )

        self._mixed_labels = self.fermion_labels | self.boson_labels

    @property
    def ancr_contractor(self):
        """Contract equal operator species and reject cross contractions."""

        return functools.partial(
            _contr_mixed_ancr_by_delta, known_labels=self._mixed_labels
        )

    def normal_order(self, terms: RDD, **kwargs):
        """Normal order fermions and bosons in separate Wick passes."""

        if len(kwargs) != 0:
            raise ValueError("Invalid arguments to mixed normal order", kwargs)

        op_parser = self.op_parser
        fermion_labels = self.fermion_labels
        boson_labels = self.boson_labels

        terms = terms.map(
            functools.partial(
                _partition_mixed_ops,
                fermion_labels=fermion_labels,
                boson_labels=boson_labels,
                op_parser=op_parser,
            )
        )

        contractor = self.contractor
        fermion_comparator = functools.partial(
            _compare_mixed_sector_ops,
            sector_labels=fermion_labels,
            op_parser=op_parser,
        )
        boson_comparator = functools.partial(
            _compare_mixed_sector_ops,
            sector_labels=boson_labels,
            op_parser=op_parser,
        )

        terms = WickDrudge.normal_order(
            self,
            terms,
            comparator=fermion_comparator,
            contractor=contractor,
            phase=FERMI,
        )
        terms = WickDrudge.normal_order(
            self,
            terms,
            comparator=boson_comparator,
            contractor=contractor,
            phase=BOSE,
        )

        return terms.filter(
            functools.partial(
                _is_not_zero_by_mixed_nilp,
                fermion_labels=fermion_labels,
                op_parser=op_parser,
            )
        )

    def eval_phys_vev(self, tensor: Tensor):
        """Evaluate the vacuum expectation value of mixed field operators."""

        terms = self.normal_order(tensor.terms)
        return Tensor(self, terms.filter(lambda term: term.is_scalar))


class GenEPhDrudge(MixDrudge):
    """Drudge for general systems containing fermions and bosons.

    This class configures independent fermion and boson field operators and
    their orbital ranges.  Fermion spin can be disabled, given by explicit
    values, or represented by a symbolic range.

    .. attribute:: fermi_op

        The vector base for fermion field operators.

    .. attribute:: fermi_cr

        The base for fermion creation operators.

    .. attribute:: fermi_an

        The base for fermion annihilation operators.

    .. attribute:: bose_op

        The vector base for boson field operators.

    .. attribute:: bose_cr

        The base for boson creation operators.

    .. attribute:: bose_an

        The base for boson annihilation operators.

    .. attribute:: fermi_density

        The one-fermion density matrix used by :meth:`eval_mf_vev`.

    .. attribute:: H1e

        The one-electron part of the Hamiltonian.

    .. attribute:: H2e

        The two-electron part of the Hamiltonian.

    .. attribute:: Hb

        The free-boson part of the Hamiltonian.

    .. attribute:: Heph

        The electron-boson coupling part of the Hamiltonian.
    """

    DEFAULT_FERMI_DUMMS = symbols("p q r s") + tuple(
        Symbol("p{}".format(i)) for i in range(21)
    )
    DEFAULT_BOSE_DUMMS = symbols("x y z") + tuple(
        Symbol("x{}".format(i)) for i in range(21)
    )
    DEFAULT_SPIN_DUMMS = tuple(
        Symbol("sigma{}".format(i)) for i in range(50)
    )

    def __init__(
        self,
        *args,
        fermi_op_label="c",
        bose_op_label="b",
        fermi_orb=((Range("F"), DEFAULT_FERMI_DUMMS),),
        bose_orb=((Range("B"), DEFAULT_BOSE_DUMMS),),
        spin=(),
        fermi_density=IndexedBase("rho"),
        one_body=IndexedBase("h"),
        two_body=IndexedBase("u"),
        dbbar=True,
        boson_energy=IndexedBase("w"),
        eph_coupling=IndexedBase("g"),
        **kwargs,
    ):
        """Initialize a general mixed fermion-boson drudge.

        Parameters
        ----------

        fermi_op_label
            The label for fermion field operators.

        bose_op_label
            The label for boson field operators.

        fermi_orb
            An iterable of range and dummy pairs for fermion orbital indices.

        bose_orb
            An iterable of range and dummy pairs for boson orbital indices.

        spin
            The fermion spin specification.  An empty sequence disables spin.
            Explicit spin values or a symbolic range and dummy pair can also
            be given, as in :class:`GenMBDrudge`.

        fermi_density
            The indexed base for the one-fermion density matrix.

        one_body
            The indexed base for the one-electron matrix elements.

        two_body
            The indexed base for the two-electron interaction tensor.

        dbbar
            If the two-electron interaction is antisymmetrized.  The default
            antisymmetrized form is odd under exchange within either index
            pair and has a coefficient of one quarter.  The Coulomb form
            obeys ``u[p, q, r, s] = u[r, s, p, q]`` and has a coefficient of
            one half.

        boson_energy
            The indexed base for the boson energies.

        eph_coupling
            The indexed base for the electron-boson coupling tensor.

        """

        super().__init__(
            *args,
            fermion_labels=(fermi_op_label,),
            boson_labels=(bose_op_label,),
            **kwargs,
        )

        self.default_einst = True

        fermi_op = Vec(fermi_op_label)
        fermi_cr = fermi_op[CR]
        fermi_an = fermi_op[AN]
        self.fermi_op_label = fermi_op_label
        self.fermi_op = fermi_op
        self.fermi_cr = fermi_cr
        self.fermi_an = fermi_an

        bose_op = Vec(bose_op_label)
        bose_cr = bose_op[CR]
        bose_an = bose_op[AN]
        self.bose_op_label = bose_op_label
        self.bose_op = bose_op
        self.bose_cr = bose_cr
        self.bose_an = bose_an

        self.set_name(
            **{
                str(fermi_op) + "_": fermi_an,
                str(fermi_op) + "_dag": fermi_cr,
                str(fermi_op) + "dag_": fermi_cr,
                str(bose_op) + "_": bose_an,
                str(bose_op) + "_dag": bose_cr,
                str(bose_op) + "dag_": bose_cr,
            }
        )

        fermi_orb_ranges = []
        for range_, dumms in fermi_orb:
            self.set_dumms(range_, dumms)
            fermi_orb_ranges.append(range_)
        self.fermi_orb_ranges = fermi_orb_ranges

        bose_orb_ranges = []
        for range_, dumms in bose_orb:
            self.set_dumms(range_, dumms)
            bose_orb_ranges.append(range_)
        self.bose_orb_ranges = bose_orb_ranges

        spin = list(spin)
        if len(spin) == 0:
            has_spin = False
            spin_range = None
            self.spin_vals = None
            self.spin_range = None
            self.spin_dumms = None
        elif isinstance(spin[0], Range):
            has_spin = True
            if len(spin) != 2:
                raise ValueError(
                    "Invalid spin specification",
                    spin,
                    "expecting range/dummies pair.",
                )
            spin_range = spin[0]
            self.spin_dumms = self.set_dumms(spin_range, spin[1])
            self.spin_vals = None
            self.spin_range = spin_range
        else:
            has_spin = True
            spin_vals = [ensure_expr(i) for i in spin]
            if len(spin_vals) == 1:
                warnings.warn(
                    "Just one spin value is given: "
                    "consider dropping it for better performance"
                )
            spin_range = spin_vals
            self.spin_vals = spin_vals
            self.spin_range = None
            self.spin_dumms = None

        self.fermi_density = fermi_density
        self.set_name(fermi_density)

        self.add_resolver_for_dumms()

        # Temporary dummies allow the fermion orbital space to be a direct sum
        # of multiple ranges.  They are reset to conventional dummies after the
        # Hamiltonian terms have been formed.
        orb_dumms = tuple(
            Symbol("internalFermiOrbitPlaceholder{}".format(i))
            for i in range(4)
        )
        spin_dumms = tuple(
            Symbol("internalSpinPlaceholder{}".format(i)) for i in range(2)
        )

        orb_sums = [(i, fermi_orb_ranges) for i in orb_dumms]
        spin_sums = [(i, spin_range) for i in spin_dumms]
        bose_orb_dumm = Symbol("internalBosonOrbitPlaceholder")
        bose_orb_sum = (bose_orb_dumm, bose_orb_ranges)

        self.one_body = one_body
        self.set_name(one_body)
        one_body_sums = orb_sums[:2]
        if has_spin:
            one_body_sums.append(spin_sums[0])
            one_body_ops = (
                fermi_cr[orb_dumms[0], spin_dumms[0]]
                * fermi_an[orb_dumms[1], spin_dumms[0]]
            )
        else:
            one_body_ops = (
                fermi_cr[orb_dumms[0]] * fermi_an[orb_dumms[1]]
            )
        self.H1e = self.sum(
            *one_body_sums,
            one_body[orb_dumms[:2]] * one_body_ops,
        ).reset_dumms()

        self.two_body = two_body
        self.dbbar = bool(dbbar)
        if self.dbbar:
            two_body_coeff = Rational(1, 4)
            self.set_symm(
                two_body,
                Perm([1, 0, 2, 3], NEG),
                Perm([0, 1, 3, 2], NEG),
                valence=4,
            )
        else:
            two_body_coeff = Rational(1, 2)
            self.set_symm(
                two_body,
                Perm([2, 3, 0, 1], IDENT),
                valence=4,
            )
        two_body_sums = list(orb_sums)
        if has_spin:
            two_body_sums.extend(spin_sums)
            if self.dbbar:
                two_body_ops = (
                    fermi_cr[orb_dumms[0], spin_dumms[0]]
                    * fermi_cr[orb_dumms[1], spin_dumms[1]]
                    * fermi_an[orb_dumms[3], spin_dumms[1]]
                    * fermi_an[orb_dumms[2], spin_dumms[0]]
                )
            else:
                two_body_ops = (
                    fermi_cr[orb_dumms[0], spin_dumms[0]]
                    * fermi_cr[orb_dumms[2], spin_dumms[1]]
                    * fermi_an[orb_dumms[3], spin_dumms[1]]
                    * fermi_an[orb_dumms[1], spin_dumms[0]]
                )
        else:
            if self.dbbar:
                two_body_ops = (
                    fermi_cr[orb_dumms[0]]
                    * fermi_cr[orb_dumms[1]]
                    * fermi_an[orb_dumms[3]]
                    * fermi_an[orb_dumms[2]]
                )
            else:
                two_body_ops = (
                    fermi_cr[orb_dumms[0]]
                    * fermi_cr[orb_dumms[2]]
                    * fermi_an[orb_dumms[3]]
                    * fermi_an[orb_dumms[1]]
                )
        self.H2e = self.sum(
            *two_body_sums,
            two_body_coeff * two_body[orb_dumms] * two_body_ops,
        ).reset_dumms()

        self.boson_energy = boson_energy
        self.set_name(boson_energy)
        self.Hb = self.sum(
            bose_orb_sum,
            boson_energy[bose_orb_dumm]
            * bose_cr[bose_orb_dumm]
            * bose_an[bose_orb_dumm],
        ).reset_dumms()

        self.eph_coupling = eph_coupling
        self.set_name(eph_coupling)
        eph_sums = [bose_orb_sum, *orb_sums[:2]]
        if has_spin:
            eph_sums.append(spin_sums[0])
            eph_fermi_ops = (
                fermi_cr[orb_dumms[0], spin_dumms[0]]
                * fermi_an[orb_dumms[1], spin_dumms[0]]
            )
        else:
            eph_fermi_ops = (
                fermi_cr[orb_dumms[0]] * fermi_an[orb_dumms[1]]
            )
        self.Heph = self.sum(
            *eph_sums,
            eph_coupling[
                bose_orb_dumm, orb_dumms[0], orb_dumms[1]
            ]
            * eph_fermi_ops
            * (bose_cr[bose_orb_dumm] + bose_an[bose_orb_dumm]),
        ).reset_dumms()

        orig_ham = (self.H1e + self.H2e + self.Hb + self.Heph).reset_dumms()
        self.orig_ham = orig_ham

        simpled_ham = orig_ham.simplify()
        self.ham = simpled_ham

        self.set_tensor_method("eval_mf_vev", self.eval_mf_vev)

    def eval_mf_vev(self, tensor: Tensor):
        """Evaluate a mean-field VEV over the boson vacuum.

        Bosons are contracted with the physical-vacuum contractor.  Fermions
        are contracted by the one-body density matrix.  For spin-free
        operators, ``<c_dag[p] c[q]>`` is ``rho[q, p]``.  Additional fermion
        indices are matched by Kronecker deltas.
        """

        terms = self.normal_order(tensor.terms)
        terms = terms.filter(
            functools.partial(
                _has_eph_op_counts,
                fermion_labels=self.fermion_labels,
                boson_labels=self.boson_labels,
                n_bosons=0,
            )
        )

        contractor = functools.partial(
            _contr_fermi_density,
            fermion_labels=self.fermion_labels,
            density=self.fermi_density,
            op_parser=self.op_parser,
        )
        terms = WickDrudge.normal_order(
            self,
            terms,
            comparator=None,
            contractor=contractor,
            phase=FERMI,
        )
        return Tensor(self, terms)


class RestrictedGenEPhDrudge(GenEPhDrudge):
    """General electron-phonon drudge with symbolic restricted spin."""

    def __init__(
        self,
        *args,
        spin_range=Range(r"\uparrow\downarrow", 0, 2),
        spin_dumms=GenEPhDrudge.DEFAULT_SPIN_DUMMS,
        dbbar=False,
        **kwargs,
    ):
        """Initialize the restricted general electron-phonon drudge."""

        super().__init__(
            *args,
            spin=(spin_range, spin_dumms),
            dbbar=dbbar,
            **kwargs,
        )
        self.add_resolver({UP: spin_range, DOWN: spin_range})

        self.spin_range = spin_range
        self.spin_dumms = self.dumms.value[spin_range]


class PartHoleEPhDrudge(GenEPhDrudge):
    """Electron-phonon drudge using a fermion particle-hole convention.

    Only fermion operators are interpreted relative to the Fermi vacuum.
    Boson operators retain their ordinary creation and annihilation characters.

    .. attribute:: orig_ham

        The Hamiltonian before particle-hole normal ordering.

    .. attribute:: full_ham

        The full Hamiltonian normal-ordered relative to the fermion and boson
        vacua and written in terms of the bare matrix elements.

    .. attribute:: ham_energy

        The scalar reference energy in the full Hamiltonian.

    .. attribute:: one_body_ham

        The fermion one-body part written in terms of bare matrix elements.

    .. attribute:: ham

        The non-scalar Hamiltonian with its fermion one-body part written in
        terms of the Fock matrix.
    """

    DEFAULT_PART_DUMMS = PartHoleDrudge.DEFAULT_PART_DUMMS
    DEFAULT_HOLE_DUMMS = PartHoleDrudge.DEFAULT_HOLE_DUMMS
    DEFAULT_ORB_DUMMS = PartHoleDrudge.DEFAULT_ORB_DUMMS

    def __init__(
        self,
        *args,
        fermi_op_label="c",
        part_orb=(Range("V", 0, Symbol("nv")), DEFAULT_PART_DUMMS),
        hole_orb=(Range("O", 0, Symbol("no")), DEFAULT_HOLE_DUMMS),
        all_orb_dumms=DEFAULT_ORB_DUMMS,
        spin=(),
        one_body=IndexedBase("h"),
        two_body=IndexedBase("u"),
        fock=IndexedBase("f"),
        dbbar=True,
        **kwargs,
    ):
        """Initialize the particle-hole electron-phonon drudge."""

        self.part_range = part_orb[0]
        self.hole_range = hole_orb[0]

        super().__init__(
            *args,
            fermi_op_label=fermi_op_label,
            fermi_orb=(part_orb, hole_orb),
            spin=spin,
            one_body=one_body,
            two_body=two_body,
            dbbar=dbbar,
            **kwargs,
        )

        self.all_orb_dumms = tuple(all_orb_dumms)
        self.set_name(*self.all_orb_dumms)
        self.add_resolver(
            {i: (self.part_range, self.hole_range) for i in all_orb_dumms}
        )

        full_ham = self.ham
        full_ham.cache()
        self.full_ham = full_ham

        self.ham_energy = full_ham.filter(lambda term: term.is_scalar)

        count_args = {
            "fermion_labels": self.fermion_labels,
            "boson_labels": self.boson_labels,
        }
        self.one_body_ham = full_ham.filter(
            functools.partial(
                _has_eph_op_counts,
                n_fermions=2,
                n_bosons=0,
                **count_args,
            )
        )
        self.two_body_ham = full_ham.filter(
            functools.partial(
                _has_eph_op_counts,
                n_fermions=4,
                n_bosons=0,
                **count_args,
            )
        )
        self.boson_ham = full_ham.filter(
            functools.partial(
                _has_eph_op_counts,
                n_fermions=0,
                n_bosons=2,
                **count_args,
            )
        )
        self.eph_ham = full_ham.filter(
            functools.partial(
                _has_eph_op_counts,
                n_bosons=1,
                **count_args,
            )
        )

        # Rewrite the electronic one-body part in terms of Fock matrices.  As
        # in PartHoleDrudge, the one-body terms generated from the two-body
        # interaction are absorbed into the Fock matrix.
        self.fock = fock
        one_body_terms = []
        for term in self.one_body_ham.local_terms:
            if term.amp.has(one_body):
                one_body_terms.append(term.subst({one_body: fock}))
        rewritten_one_body_ham = self.create_tensor(one_body_terms)

        other_ham = full_ham.filter(
            functools.partial(
                _keep_eph_ham_term,
                **count_args,
            )
        )
        ham = rewritten_one_body_ham + other_ham
        ham.cache()
        self.ham = ham

        self.set_name(no=self.hole_range.size)
        self.set_name(nv=self.part_range.size)

    @property
    def op_parser(self):
        """Parse particle-hole characters for fermion operators only."""

        resolvers = self.resolvers
        hole_range = self.hole_range
        fermion_labels = self.fermion_labels

        def parse_parthole_eph_ops(op: Vec, term: Term):
            """Parse a fermion or boson field operator."""

            label, char, indices = parse_field_op(op, term)
            if label not in fermion_labels:
                return label, char, indices

            orb_range = try_resolve_range(
                indices[0], dict(term.sums), resolvers.value
            )
            if orb_range is None:
                raise ValueError(
                    "Invalid fermion orbit value",
                    indices[0],
                    "expecting particle or hole",
                )
            if orb_range == hole_range:
                char = AN if char == CR else CR
            return label, char, indices

        return parse_parthole_eph_ops


class SpinOneHalfPartHoleEPhDrudge(PartHoleEPhDrudge):
    """Particle-hole electron-phonon drudge with explicit spin one-half.

    The electronic interaction uses the Coulomb form inherited from
    :class:`GenEPhDrudge`, with explicit spin indices.
    """

    def __init__(
        self,
        *args,
        part_orb=(
            Range("V", 0, Symbol("nv")),
            PartHoleEPhDrudge.DEFAULT_PART_DUMMS + symbols("beta gamma"),
        ),
        hole_orb=(
            Range("O", 0, Symbol("no")),
            PartHoleEPhDrudge.DEFAULT_HOLE_DUMMS + symbols("u v"),
        ),
        spin=(UP, DOWN),
        dbbar=False,
        **kwargs,
    ):
        """Initialize the explicit-spin electron-phonon drudge."""

        super().__init__(
            *args,
            part_orb=part_orb,
            hole_orb=hole_orb,
            spin=spin,
            dbbar=dbbar,
            **kwargs,
        )


class RestrictedPartHoleEPhDrudge(SpinOneHalfPartHoleEPhDrudge):
    """Particle-hole electron-phonon drudge on a restricted reference."""

    def __init__(
        self,
        *args,
        spin_range=Range(r"\uparrow\downarrow", 0, 2),
        spin_dumms=GenEPhDrudge.DEFAULT_SPIN_DUMMS,
        **kwargs,
    ):
        """Initialize the restricted electron-phonon drudge."""

        super().__init__(
            *args,
            spin=(spin_range, spin_dumms),
            **kwargs,
        )
        self.add_resolver({UP: spin_range, DOWN: spin_range})

        self.spin_range = spin_range
        self.spin_dumms = self.dumms.value[spin_range]

        sigma = self.spin_dumms[0]
        p = Symbol("p")
        q = Symbol("q")
        self.e_ = TensorDef(
            Vec("E"),
            (p, q),
            self.sum(
                (sigma, spin_range),
                self.fermi_cr[p, sigma] * self.fermi_an[q, sigma],
            ),
        )
        self.set_name(e_=self.e_)


def _partition_mixed_ops(
    term: Term, fermion_labels, boson_labels, op_parser: FockDrudge.OP_PARSER
):
    """Stably place all fermion operators before all boson operators."""

    fermions = []
    bosons = []

    for op in term.vecs:
        label, _, _ = op_parser(op, term)
        if label in fermion_labels:
            fermions.append(op)
        elif label in boson_labels:
            bosons.append(op)
        else:
            raise ValueError(
                "Unknown operator label in mixed Fock algebra", label
            )

    return term.map(
        vecs=tuple(fermions + bosons),
        skip_vecs=True,
    )


def _compare_mixed_sector_ops(
    op1: Vec,
    op2: Vec,
    term: Term,
    sector_labels,
    op_parser: FockDrudge.OP_PARSER,
):
    """Compare operators only when both belong to the selected sector."""

    label1, _, _ = op_parser(op1, term)
    label2, _, _ = op_parser(op2, term)
    if label1 in sector_labels and label2 in sector_labels:
        return _compare_field_ops(op1, op2, term, op_parser=op_parser)

    # Mixed operators have already been stably partitioned.  Operators in the
    # other sector are intentionally left untouched during this pass.
    return True


def _has_eph_op_counts(
    term: Term,
    fermion_labels,
    boson_labels,
    n_fermions=None,
    n_bosons=None,
):
    """Test the fermion and boson operator counts in a term."""

    fermion_count = 0
    boson_count = 0
    for op in term.vecs:
        if op.label in fermion_labels:
            fermion_count += 1
        elif op.label in boson_labels:
            boson_count += 1
        else:
            raise ValueError(
                "Unknown operator label in electron-phonon Hamiltonian",
                op.label,
            )

    return (n_fermions is None or fermion_count == n_fermions) and (
        n_bosons is None or boson_count == n_bosons
    )


def _keep_eph_ham_term(term: Term, fermion_labels, boson_labels):
    """Keep non-scalar terms outside the bare fermion one-body part."""

    if term.is_scalar:
        return False
    return not _has_eph_op_counts(
        term,
        fermion_labels=fermion_labels,
        boson_labels=boson_labels,
        n_fermions=2,
        n_bosons=0,
    )


def _contr_fermi_density(
    op1: Vec,
    op2: Vec,
    term: Term,
    fermion_labels,
    density: IndexedBase,
    op_parser: FockDrudge.OP_PARSER,
):
    """Contract a creation-annihilation pair by a fermion density."""

    label1, char1, indices1 = op_parser(op1, term)
    label2, char2, indices2 = op_parser(op2, term)

    if label1 not in fermion_labels or label2 not in fermion_labels:
        return 0
    if label1 != label2 or char1 != CR or char2 != AN:
        return 0
    if len(indices1) != len(indices2) or len(indices1) == 0:
        raise ValueError(
            "Invalid fermion operators to contract by density",
            (indices1, indices2),
        )

    result = density[indices2[0], indices1[0]]
    for index1, index2 in zip(indices1[1:], indices2[1:]):
        result *= KroneckerDelta(index1, index2)
    return result


def _contr_mixed_ancr_by_delta(
    label1, indices1, label2, indices2, known_labels
):
    """Contract equal mixed-field labels and return zero across labels."""

    if label1 not in known_labels or label2 not in known_labels:
        raise ValueError(
            "Unknown operator label in mixed Fock contraction",
            (label1, label2),
        )
    if label1 != label2:
        return 0
    return _contr_ancr_by_delta(label1, indices1, label2, indices2)


def _is_not_zero_by_mixed_nilp(
    term: Term, fermion_labels, op_parser: FockDrudge.OP_PARSER
):
    """Test nilpotency only for repeated identical fermion operators."""

    vecs = term.vecs
    for i in range(len(vecs) - 1):
        if vecs[i] != vecs[i + 1]:
            continue
        label, _, _ = op_parser(vecs[i], term)
        if label in fermion_labels:
            return False
    return True
