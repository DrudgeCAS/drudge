"""Tests for user utility functions."""

import functools
import types
from unittest.mock import MagicMock, patch

from sympy import IndexedBase, symbols, Symbol

from drudge import (
    Vec,
    sum_,
    prod_,
    Stopwatch,
    ScalarLatexPrinter,
    InvariantIndexable,
    Range,
)
from drudge.term import parse_terms, try_resolve_range
from drudge.utils import extract_alnum, SymbResolver


def test_sum_prod_utility():
    """Test the summation and product utility."""

    v = Vec("v")
    vecs = [v[i] for i in range(3)]
    v0, v1, v2 = vecs

    # The proxy object cannot be directly compared.
    assert parse_terms(sum_(vecs)) == parse_terms(v0 + v1 + v2)
    assert parse_terms(prod_(vecs)) == parse_terms(v0 * v1 * v2)

    assert sum_([]) == 0
    assert prod_([]) == 1


def test_stopwatch():
    """Test the stopwatch utility.

    The clock is driven by a stub rather than by real time.  What is under
    test is the arithmetic the stopwatch does on the readings, so feeding it
    known readings makes the expected output exact and independent of how
    busy the machine is.
    """

    tensor = types.SimpleNamespace(n_terms=2, cache=MagicMock())
    res_holder = [None]

    def print_cb(stamp):
        res_holder[0] = stamp

    # One reading per call the stopwatch makes: construction, the two tocks,
    # and the total.
    readings = iter([0.0, 0.5, 1.25, 2.0])

    with patch(
        "drudge.utils.time.perf_counter", side_effect=lambda: next(readings)
    ):
        stamper = Stopwatch(print_cb)

        stamper.tock("Nothing")
        res = res_holder[0]
        assert res == "Nothing done, wall time: 0.50 s"

        stamper.tock("Tensor", tensor)
        res = res_holder[0]
        assert res == "Tensor done, 2 terms, wall time: 0.75 s"
        tensor.cache.assert_called_once_with()

        stamper.tock_total()
        res = res_holder[0]
        assert res == "Total wall time: 2.00 s"


def test_invariant_indexable():
    """Test the utility for invariant indexables."""

    val = Symbol("G")
    tensor = InvariantIndexable(val)
    assert tensor[1] == val
    assert tensor[1, Symbol("i")] == val


def test_scalar_latex_printing():
    """Test the printing of scalars into LaTeX form."""

    x1 = IndexedBase("x1")
    i, j = symbols("i j")
    expr = x1[i, j]
    assert ScalarLatexPrinter().doprint(expr) == "x^{(1)}_{i,j}"


def test_extracting_alnum_substring():
    """Test the utility to extract alphanumeric part of a string."""
    assert extract_alnum("x_{1, 2}") == "x12"


def test_symb_resolvers():
    """Test the functionality of symbol resolvers in strict mode."""
    r = Range("R")
    a, b = symbols("a b")

    strict, normal = [
        functools.partial(
            try_resolve_range,
            sums_dict={},
            resolvers=[SymbResolver([(r, [a])], strict=i)],
        )
        for i in [True, False]
    ]

    # Strict mode.
    assert strict(a) == r
    assert strict(b) is None
    assert strict(a + 1) is None

    # Normal mode.
    assert normal(a) == r
    assert normal(b) is None
    assert normal(a + 1) == r
