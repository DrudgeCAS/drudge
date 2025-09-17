# Drudge Repository - Copilot Instructions

## Repository Overview

**Drudge** is a symbolic algebra system for tensorial and noncommutative algebras, built on top of SymPy. It specializes in quantum chemistry and many-body theory applications, focusing on symbolic manipulation of indexed quantities, summations, and noncommutative algebraic systems.

### Key Features
- Symbolic tensor algebra with symmetry support
- Canonical forms for mathematical expressions with complex symmetries
- Noncommutative algebra frameworks (CCR/CAR, Clifford algebras, su(2))
- C++ extensions for performance-critical canonicalization operations
- Integration with companion package [gristmill](https://github.com/DrudgeCAS/gristmill) for code generation

### Repository Statistics
- **Languages**: Python (primary), C++ (extensions), DRS (Drudge Scripts)
- **Size**: ~16K lines of Python code, 164 test cases
- **Python Version**: 3.12+ (currently testing on 3.13)
- **Dependencies**: SymPy, PySpark/DummyRDD, Jinja2, C++ compiler

## Build and Development Instructions

### Environment Setup (ALWAYS follow this order)

1. **Always initialize submodules first:**
   ```bash
   git submodule update --init --recursive
   ```

2. **Always install uv before building** (if not available):
   ```bash
   # uv is the required package manager
   pip install uv
   ```

3. **Install dependencies and build:**
   ```bash
   uv sync --locked --extra dev
   ```

4. **CRITICAL: Always set DUMMY_SPARK=1 for testing:**
   ```bash
   export DUMMY_SPARK=1
   ```
   This environment variable is **required** for all test runs. Without it, tests may fail or behave unexpectedly as the project is migrating from pyspark to dask.

### Build Commands

| Command | Purpose | Time | Notes |
|---------|---------|------|-------|
| `uv sync --locked --extra dev` | Install all dependencies | ~7s | Always run after clone |
| `uv build` | Build package distribution | ~30s | Creates wheel and source dist |
| `uv run pytest tests/` | Run full test suite | ~24s | Requires DUMMY_SPARK=1 |
| `uv run pytest tests/filename_test.py` | Run specific test file | ~2s | For targeted testing |

### Testing and Validation

**Test Environment Setup:**
```bash
# ALWAYS set this before running tests
export DUMMY_SPARK=1
uv run pytest tests/ -v
```

**Key Test Files by Functionality:**
- `free_algebra_test.py` - Core tensor algebra
- `genmb_test.py` - Many-body theory
- `parthole_test.py` - Particle-hole formalism  
- `drs_test.py` - Drudge script system
- `term_test.py` - Basic term operations

**Test Validation Steps:**
1. All 164 tests should pass with only warnings about pdflatex (safe to ignore)
2. Test runtime should be under 30 seconds
3. No errors about missing SparkContext when DUMMY_SPARK=1 is set

### Common Issues and Workarounds

**Build Issues:**
- **Missing submodules**: Always run `git submodule update --init --recursive` first
- **C++ compilation warnings**: Some warnings about uninitialized variables are expected and safe
- **License deprecation warning**: Expected warning about pyproject.toml license format

**Test Issues:**
- **PySpark errors**: Ensure `export DUMMY_SPARK=1` is set before running tests
- **Missing pdflatex warning**: Safe to ignore; only affects LaTeX report generation

## Project Layout and Architecture

### Root Directory Structure
```
drudge/
├── .github/workflows/        # CI/CD pipelines
│   ├── ci.yml               # Main CI (Ubuntu/macOS)
│   ├── copilot-setup-steps.yml  # Setup reference  
│   └── windows.yml          # Windows builds (experimental)
├── deps/libcanon/           # Git submodule for C++ canonicalization
├── docs/                    # Sphinx documentation
│   ├── examples/            # Example scripts and notebooks
│   ├── conf.py             # Sphinx configuration
│   └── Makefile            # Documentation build
├── drudge/                  # Main Python package
├── tests/                   # Test suite (pytest)
├── pyproject.toml          # Modern Python project config
├── setup.py                # Legacy setup with C++ extensions
├── MANIFEST.in             # Package data inclusion
└── uv.lock                 # Locked dependencies
```

### Main Package Structure (`drudge/`)
- `__init__.py` - Package exports and version (v0.11.0)
- `drudge.py` - Core Drudge class and tensor framework
- `term.py` - Basic term and vector operations
- `canon.py` - Canonicalization algorithms
- `canonpy.cpp/.h` - C++ extension for permutation groups
- `wickcore.cpp` - C++ extension for Wick's theorem
- `fock.py` - Fock space and many-body operators
- `genquad.py` - General quadratic algebras
- `clifford.py` - Clifford algebra implementation
- `su2.py` - SU(2) algebra implementation
- `drs.py` - Drudge script system
- `templates/` - Jinja2 templates for code generation

### Configuration Files
- `pyproject.toml` - Modern Python packaging, dependencies, entry points
- `setup.py` - C++ extension compilation settings
- `MANIFEST.in` - Include C++ headers and templates in distributions
- `.github/workflows/ci.yml` - CI pipeline with coverage reporting

### Dependencies That Aren't Obvious
- **libcanon submodule**: Required for C++ canonicalization algorithms
- **DummyRDD**: Git dependency for Spark-like interface during migration
- **C++ compiler**: Required for building canonpy and wickcore extensions
- **Jinja2**: Used for code generation templates

## CI/CD and Validation Pipelines

### GitHub Actions Workflows
1. **ci.yml**: Main CI pipeline
   - Runs on Ubuntu and macOS
   - Tests with Python from pyproject.toml
   - Uses `DUMMY_SPARK=1` environment
   - Reports coverage to Coveralls (Ubuntu only)

2. **copilot-setup-steps.yml**: Reference implementation for setup
   - Shows exact steps for agent setup
   - Includes submodule initialization and uv setup

3. **windows.yml**: Windows build testing (currently experimental)

### Validation Checklist for Changes
1. **Environment**: Ensure `DUMMY_SPARK=1` is set
2. **Build**: `uv sync --locked --extra dev` should complete without errors
3. **Tests**: All 164 tests should pass with `uv run pytest tests/`
4. **Package**: `uv build` should create distributions successfully
5. **Examples**: Validate example scripts run without errors

### Pre-commit Validation
No formal pre-commit hooks configured, but always run:
```bash
export DUMMY_SPARK=1
uv run pytest tests/
```

## Important Guidelines for Agents

### Environment Requirements
- **ALWAYS use `uv` for package management** - pip installations may not work correctly
- **ALWAYS set `export DUMMY_SPARK=1`** before running tests or examples
- **ALWAYS initialize submodules** before building
- **Trust these instructions** - they have been validated and tested

### Key Architectural Patterns
- **Drudge objects**: Core computational context, typically created with SparkContext
- **Tensor operations**: Use `einst()` for Einstein summation notation
- **Canonicalization**: Automatic for expressions with symmetries
- **DRS scripts**: Domain-specific language for symbolic computations

### File Locations for Common Tasks
- **Add new algebra**: Create new file in `drudge/` following `fock.py` pattern
- **Add tests**: Create `*_test.py` in `tests/` directory
- **Add examples**: Place in `docs/examples/` with appropriate extension
- **Modify C++ extensions**: Edit `.cpp` files in `drudge/` (requires rebuild)

### Documentation and Examples
- Main docs: Uses Sphinx, build with `sphinx-build` from `docs/`
- Examples in `docs/examples/`: `.py`, `.drs`, and `.ipynb` files
- DRS scripts: Use `.drs` extension for domain-specific language

**When implementing changes, always validate with the test suite and ensure the build process remains working. The codebase is stable and well-tested - focus on minimal, surgical changes that preserve existing functionality.**