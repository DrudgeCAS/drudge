[![Ubuntu](https://github.com/DrudgeCAS/drudge/workflows/Ubuntu/badge.svg)](https://github.com/DrudgeCAS/drudge/actions/workflows/ubuntu.yml)
[![macOS](https://github.com/DrudgeCAS/drudge/workflows/macOS/badge.svg)](https://github.com/DrudgeCAS/drudge/actions/workflows/macos.yml)
[![Windows](https://github.com/DrudgeCAS/drudge/workflows/Windows/badge.svg)](https://github.com/DrudgeCAS/drudge/actions/workflows/windows.yml)
[![Coveralls](https://coveralls.io/repos/github/DrudgeCAS/drudge/badge.svg?branch=master)](https://coveralls.io/github/DrudgeCAS/drudge?branch=master)

<h1 align="center">Drudge</h1>

Drudge is a symbolic algebra system built on top of
[SymPy](http://www.sympy.org), focusing primarily on tensorial and
non-commutative algebras. It is motivated by tedious symbolic derivations in
quantum chemistry and many-body theory but is also useful for any symbolic
manipulation and simplification involving indexed quantities, symbolic
summations, and non-commutative algebras.

Leveraging the generic algorithms implemented in
[libcanon](https://github.com/DrudgeCAS/libcanon) for canonicalization of
combinatorial objects, such as strings and graphs, Drudge can find canonical
forms for mathematical expressions involving tensors with symmetries and
symbolic summations. For example, considering a fourth-order tensor $u$
satisfying

$$
u_{abcd} = -u_{bacd} = -u_{abdc} = u_{badc},
$$

an expression like

$$
\sum_{cd} u_{acbd} \rho_{dc} - \sum_{cd} u_{cabd} \rho_{dc} + \sum_{cd} u_{cdbc} \rho_{cd}
$$

can be automatically simplified to a single term,

$$
3 \sum_{cd} u_{acbd} \rho_{dc},
$$

irrespective of the names and ordering of the summation indices.

In addition to fully considering the permutational symmetries of tensors and
summations, Drudge provides a general framework for handling non-commutative
algebraic systems. Currently, Drudge natively supports the [canonical
commutation relations (CCR) and canonical anticommutation relations (CAR)
algebras](https://en.wikipedia.org/wiki/CCR_and_CAR_algebras) for fermions and
bosons, respectively, in many-body theory, general [Clifford
algebras](https://en.wikipedia.org/wiki/Clifford_algebra), and the [su(2)
algebra](https://en.m.wikipedia.org/wiki/Special_unitary_group#Lie_Algebra) in
its Cartan-Killing basis. Other non-commutative algebraic systems can be added
with ease.

Using symbolic expressions from Drudge, the companion package
[gristmill](https://github.com/DrudgeCAS/gristmill) can automatically optimize
and generate numerical code. Optimal computational complexity can be achieved
for various methods in quantum chemistry, which heavily rely on tensor
contractions and their sums.


## Installation

Drudge can be installed directly from the GitHub repository using
[uv](https://github.com/astral-sh/uv) (recommended)
```bash
uv pip install git+https://github.com/DrudgeCAS/drudge.git
```
or [pip](https://pypi.org/project/pip/)
```bash
pip install git+https://github.com/DrudgeCAS/drudge.git
```

## Acknowledgments

Drudge is developed by Jinmo Zhao and Prof Gustavo E. Scuseria at Rice
University, and was supported as part of the Center for the Computational
Design of Functional Layered Materials, an Energy Frontier Research Center
funded by the U.S. Department of Energy, Office of Science, Basic Energy
Sciences under Award DE-SC0012575.
