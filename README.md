[![CI](https://github.com/DrudgeCAS/drudge/actions/workflows/ci.yml/badge.svg)](https://github.com/DrudgeCAS/drudge/actions/workflows/ci.yml)
[![Coveralls](https://coveralls.io/repos/github/DrudgeCAS/drudge/badge.svg?branch=master)](https://coveralls.io/github/DrudgeCAS/drudge?branch=master)
[![Cite this repo](https://img.shields.io/badge/Cite-this_repo-blue.svg)](./CITATION.cff)

<h1 align="center">Drudge</h1>

Drudge is a symbolic algebra system built on top of
[SymPy](http://www.sympy.org), focusing primarily on tensorial and
noncommutative algebras. It is motivated by tedious symbolic derivations in
quantum chemistry and many-body theory but is also useful for any symbolic
manipulation and simplification involving indexed quantities, symbolic
summations, and noncommutative algebras.

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
summations, Drudge provides a general framework for handling noncommutative
algebraic systems. Currently, Drudge natively supports the [canonical
commutation relations (CCR) and canonical anticommutation relations (CAR)
algebras](https://en.wikipedia.org/wiki/CCR_and_CAR_algebras) for fermions and
bosons, respectively, in many-body theory, general [Clifford
algebras](https://en.wikipedia.org/wiki/Clifford_algebra), and the [su(2)
algebra](https://en.m.wikipedia.org/wiki/Special_unitary_group#Lie_Algebra) in
its Cartan-Killing basis. Other noncommutative algebraic systems can be added
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

> **Note:** Native Windows builds are currently not working. Please use WSL
> (Windows Subsystem for Linux) to install and run Drudge on Windows.


## Citation

If you use Drudge in your work, please cite this repository and Jinmo Zhao's
Ph.D. thesis:

**1. The Drudge GitHub repository**  
```bibtex
@misc{DrudgeCAS,
  author       = {Jinmo Zhao and Guo P. Chen and Gaurav Harsha and Matthew Wholey and Thomas M. Henderson and Gustavo E. Scuseria},
  title        = {Drudge: A symbolic algebra system for tensorial and noncommutative algebras},
  publisher    = {GitHub},
  year         = {2016--2025},
  url          = {https://github.com/DrudgeCAS/drudge},
  note         = {GitHub repository}
}
```

**2. Jinmo Zhao’s Ph.D. thesis**  
```bibtex
@phdthesis{Zhao2018Drudge,
  author       = {Jinmo Zhao},
  title        = {Symbolic Solution for Computational Quantum Many-Body Theory Development},
  school       = {Rice University},
  year         = {2018},
  month        = {April},
  address      = {Houston, Texas, USA},
  type         = {PhD thesis},
  url          = {https://www.proquest.com/openview/61a9a86c07dbb6e5270bdeb1c84384db/1?pq-origsite=gscholar&cbl=18750&diss=y}
}
```
Link: [Symbolic Solution for Computational Quantum Many-Body Theory Development — Jinmo Zhao (2018)](https://www.proquest.com/openview/61a9a86c07dbb6e5270bdeb1c84384db/1?pq-origsite=gscholar&cbl=18750&diss=y)

---

You may also use the [`CITATION.cff`](./CITATION.cff) file provided in this
repository, which is compatible with citation managers such as Zotero and
Mendeley.

## Acknowledgments

Drudge was originally developed by Jinmo Zhao during his Ph.D. at Rice
University, under the supervision of Prof. Gustavo E. Scuseria. The project was
supported as part of the Center for the Computational Design of Functional
Layered Materials, an Energy Frontier Research Center funded by the U.S.
Department of Energy, Office of Science, Basic Energy Sciences under Award
DE-SC0012575. The package is currently maintained by Guo P. Chen, Gaurav
Harsha, Matthew Wholey, and members of the Scueria group.

