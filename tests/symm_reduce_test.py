"""Tests for the symmetry reduction of tensor definitions."""

import pytest
from sympy import IndexedBase, Rational, Symbol

from drudge import Drudge, Perm, NEG, CONJ, IDENT, PartHoleDrudge


@pytest.fixture(scope="module")
def parthole(spark_ctx):
    """Initialize the particle-hole drudge for the tests."""
    dr = PartHoleDrudge(spark_ctx)
    return dr


@pytest.fixture
def dbbar_res(parthole):
    """A doubly-antisymmetric residual definition mimicking CCD.

    The right-hand side is formed by explicit antisymmetrization of a few
    representative terms with different stabilizers, so that the expected
    result of the reduction is known.
    """

    dr = parthole
    p = dr.names
    a, b, c, d = p.V_dumms[:4]
    i, j, k, l = p.O_dumms[:4]
    u = dr.two_body
    t = IndexedBase("t")
    dr.set_dbbar_base(t, 2)
    r = IndexedBase("r")
    dr.set_symm(r, Perm([1, 0, 2, 3], NEG), Perm([0, 1, 3, 2], NEG), valence=4)

    # Fully symmetric term, ring term without any stabilizer, and quadratic
    # ring term with the simultaneous swap as its stabilizer.
    full = u[a, b, i, j]
    ring = t[a, c, i, k] * u[k, b, c, j]
    quad = t[a, c, i, k] * t[b, d, j, l] * u[k, l, c, d]

    def antisymm(expr):
        """Antisymmetrize the expression over the external indices."""
        swap_ab = expr.xreplace({a: b, b: a})
        return (
            expr
            - swap_ab
            - expr.xreplace({i: j, j: i})
            + swap_ab.xreplace({i: j, j: i})
        )

    rhs = dr.einst(full + antisymm(ring) + antisymm(quad) / 2).simplify()
    return dr.define(r[a, b, i, j], rhs)


def test_get_symm_follows_canonicalization_lookup(spark_ctx):
    """Test the lookup precedence for the symmetries of bases."""

    dr = Drudge(spark_ctx)
    x = IndexedBase("x")
    y = IndexedBase("y")

    swap2 = Perm([1, 0], NEG)
    swap4 = Perm([1, 0, 2, 3], NEG)
    dr.set_symm(x, swap2)
    dr.set_symm(x, swap4, valence=4)
    dr.set_symm(y, swap2)
    dr.set_symm(y, None, valence=4)

    # Valence-specific symmetry takes precedence.
    assert len(dr.get_symm(x, 4)) == 2
    assert all(len(i) == 4 for i in dr.get_symm(x, 4).elements())
    # Other valences fall back to the valence-free symmetry.
    assert all(len(i) == 2 for i in dr.get_symm(x, 3).elements())
    assert all(len(i) == 2 for i in dr.get_symm(x).elements())
    # Symmetries set by the label are found for the indexed base.
    dr.set_symm(Symbol("w"), swap2)
    assert all(
        len(i) == 2 for i in dr.get_symm(IndexedBase("w"), 3).elements()
    )
    # Explicit None disables the symmetry for that valence only.
    assert dr.get_symm(y, 4) is None
    assert all(len(i) == 2 for i in dr.get_symm(y, 2).elements())
    # Unknown bases have no symmetry.
    assert dr.get_symm(IndexedBase("z"), 2) is None


def test_term_permutes_external_indices(parthole):
    """Test the permutation of external indices of terms."""

    dr = parthole
    p = dr.names
    a, b, c = p.V_dumms[:3]
    x = IndexedBase("x")

    term = dr.einst(x[a, c] * x[c, b]).local_terms[0]

    swapped = term.permute_exts(Perm([1, 0], NEG), (a, b))
    expected = dr.einst(-x[b, c] * x[c, a]).local_terms[0]
    assert swapped == expected

    ident = term.permute_exts(Perm([0, 1]), (a, b))
    assert ident == term

    with pytest.raises(ValueError):
        term.permute_exts(Perm([1, 0], CONJ), (a, b))
    with pytest.raises(ValueError):
        term.permute_exts(Perm([1, 0]), (a, c))  # c is a dummy.
    with pytest.raises(ValueError):
        term.permute_exts(Perm([1, 0, 2]), (a, b))


def test_term_orbit_representative(parthole):
    """Test the canonical orbit representative of terms.

    Terms in the same orbit should give the same representative, with
    coefficients differing by the sign of the relating permutation, and a
    signed stabilizer should annihilate the term.
    """

    dr = parthole
    p = dr.names
    a, b, c = p.V_dumms[:3]
    i, j, k = p.O_dumms[:3]
    u = dr.two_body
    t = IndexedBase("t")
    dr.set_dbbar_base(t, 2)

    group = [Perm([0, 1]), Perm([1, 0], NEG)]
    symms = dr.symms.value
    dumms = dr.dumms.value

    term = dr.einst(2 * t[a, c, i, k] * u[k, b, c, j]).local_terms[0]
    # The same term with the external indices swapped and a different dummy.
    partner = dr.einst(-2 * t[b, c, i, k] * u[k, a, c, j]).local_terms[0]

    repr1, coeff1 = term.orbit_repr(group, (a, b), symms, dumms)
    repr2, coeff2 = partner.orbit_repr(group, (a, b), symms, dumms)
    assert repr1 == repr2
    assert coeff1 == coeff2
    assert abs(coeff1) == 2
    # The representative has unit coefficient.
    _, repr_coeff = repr1.amp_factors
    assert repr_coeff == 1

    # A term symmetric under the swap is annihilated by antisymmetrization.
    x = IndexedBase("x")
    symm_term = dr.einst(x[a] * x[b]).local_terms[0]
    _, coeff = symm_term.orbit_repr(group, (a, b), symms, dumms)
    assert coeff == 0

    # Empty groups are rejected.
    with pytest.raises(ValueError):
        term.orbit_repr([], (a, b), symms, dumms)


def test_symm_reduce_recovers_definition(dbbar_res):
    """Test symmetry reduction on the CCD-like residual.

    The seed should have exactly one representative per orbit, with the
    coefficients scaled by the orbit size over the group order, and the
    assembly should reconstruct the original definition.
    """

    tdef = dbbar_res
    dr = tdef.drudge

    seed, assembly = tdef.symm_reduce()

    # One orbit for each of the three kinds of terms.
    assert seed.n_terms == 3
    assert str(seed.base) == "r_s"
    assert seed.exts == tdef.exts

    # Orbit sizes 1, 2, and 4 over the group of order 4, with the quadratic
    # ring term carrying coefficient one in the input after its two equal
    # images are merged.
    coeffs = sorted(abs(term.amp_factors[1]) for term in seed.local_terms)
    assert coeffs == [Rational(1, 4), Rational(1, 2), 1]

    # The assembly has one term per group element, with exactly the original
    # external indices, and it reconstructs the definition.
    assert assembly.n_terms == 4
    assert assembly.lhs == tdef.lhs
    assert assembly.exts == tdef.exts
    reconstructed = seed.act(assembly)
    assert (reconstructed - tdef).simplify() == 0

    # The seed itself does not carry the symmetry of the result.
    assert dr.get_symm(seed.base, 4) is None

    # The wrapper on the drudge gives the same result.
    seed2, assembly2 = dr.symm_reduce(tdef)
    assert seed2 == seed
    assert assembly2 == assembly


def test_symm_reduce_is_deterministic_for_renamed_indices(dbbar_res):
    """Test symmetry reduction with renamed external indices.

    The same definition written with other external indices should give the
    same seed after the indices are renamed back.
    """

    tdef = dbbar_res
    dr = tdef.drudge
    p = dr.names
    a, b = p.V_dumms[:2]
    i, j = p.O_dumms[:2]
    a1, a2 = p.V_dumms[4:6]
    i1, i2 = p.O_dumms[4:6]

    renamed = dr.define(tdef.base[a1, a2, i1, i2], tdef[a1, a2, i1, i2])
    seed_ref, _ = tdef.symm_reduce()
    seed_new, assembly_new = renamed.symm_reduce()

    assert [k[0] for k in seed_new.exts] == [a1, a2, i1, i2]
    assert [k[0] for k in assembly_new.exts] == [a1, a2, i1, i2]

    back = dr.define(seed_new.base[a, b, i, j], seed_new[a, b, i, j])
    assert (back - seed_ref).simplify() == 0


def test_symm_reduce_handles_zero_rhs(parthole):
    """Test symmetry reduction on a definition with empty right-hand side."""

    dr = parthole
    p = dr.names
    a, b = p.V_dumms[:2]
    z = IndexedBase("z")
    dr.set_symm(z, Perm([1, 0], NEG))

    tdef = dr.define(z[a, b], dr.create_tensor([]))
    seed, assembly = tdef.symm_reduce()
    assert seed.n_terms == 0
    assert assembly.n_terms == 2


def test_symm_reduce_names_seed(parthole):
    """Test the naming of the seed of symmetry reduction."""

    dr = parthole
    p = dr.names
    a, b = p.V_dumms[:2]
    x = IndexedBase("x")
    w = IndexedBase("w")
    dr.set_symm(w, Perm([1, 0], NEG))
    dr.set_name(IndexedBase("w_s"))

    tdef = dr.define(w[a, b], dr.einst(x[a, b] - x[b, a]))

    # The default name skips existing names.
    seed, _ = tdef.symm_reduce()
    assert str(seed.base) == "w_s1"

    # Explicit names are honoured, and conflicting ones rejected.
    seed, assembly = tdef.symm_reduce(interm_base=IndexedBase("seed"))
    assert str(seed.base) == "seed"
    assert str(assembly.local_terms[0].amp.atoms(IndexedBase).pop()) == "seed"
    with pytest.raises(ValueError):
        tdef.symm_reduce(interm_base="x")
    with pytest.raises(ValueError):
        tdef.symm_reduce(interm_base=w)


def test_symm_reduce_rejects_invalid_input(parthole):
    """Test the error reporting of symmetry reduction.

    Definitions without declared symmetry, with symmetry actually violated by
    the right-hand side, with permutations mixing ranges, or with conjugation
    should all be rejected.
    """

    dr = parthole
    p = dr.names
    a, b = p.V_dumms[:2]
    i = p.O_dumms[0]
    x = IndexedBase("x")
    y = IndexedBase("y")

    # No symmetry set.
    n = IndexedBase("n")
    with pytest.raises(ValueError):
        dr.define(n[a, b], dr.einst(x[a, b])).symm_reduce()

    # Declared symmetry not satisfied by the right-hand side.
    v = IndexedBase("v")
    dr.set_symm(v, Perm([1, 0], NEG))
    bad = dr.define(v[a, b], dr.einst(x[a] * y[b]))
    with pytest.raises(ValueError):
        bad.symm_reduce()
    # Without the check, the definition is silently projected onto its
    # antisymmetric part, which differs from the original.
    seed, assembly = bad.symm_reduce(check=False)
    assert seed.n_terms == 1
    assert (seed.act(assembly) - bad).simplify() != 0

    # Permutation mixing a particle and a hole index.
    m = IndexedBase("m")
    dr.set_symm(m, Perm([1, 0], NEG))
    with pytest.raises(ValueError):
        dr.define(m[a, i], dr.einst(x[a, i] - x[i, a])).symm_reduce()

    # Conjugation is not supported.
    h = IndexedBase("h")
    dr.set_symm(h, Perm([1, 0], NEG | CONJ))
    with pytest.raises(ValueError):
        dr.define(h[a, b], dr.einst(x[a, b])).symm_reduce()


def test_symm_reduce_rejects_tensors_named_as_dummies(parthole):
    """Test the rejection of tensors sharing a name with a dummy.

    Such tensors get renamed together with the dummies in symbol
    substitutions, so they are refused up front instead of failing the
    reconstruction check with a confusing message.
    """

    dr = parthole
    p = dr.names
    a, b, c = p.V_dumms[:3]
    i, j = p.O_dumms[:2]

    # Tensor c has the same name as the third particle dummy.
    c_tensor = IndexedBase("c")
    r = IndexedBase("rc")
    dr.set_symm(r, Perm([1, 0, 3, 2], IDENT), valence=4)
    tdef = dr.define(r[a, b, i, j], dr.einst(c_tensor[a, i] * c_tensor[b, j]))
    with pytest.raises(ValueError) as info:
        tdef.symm_reduce()
    assert "named as dummies" in str(info.value)

    # Declaring the symmetry of such a tensor warns.
    with pytest.warns(UserWarning):
        dr.set_symm(c_tensor, Perm([1, 0], IDENT))
