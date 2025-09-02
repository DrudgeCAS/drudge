"""Setup script for drudge."""

import os.path

from setuptools import setup, find_packages, Extension

PROJ_ROOT = os.path.dirname(os.path.abspath(__file__))
INCLUDE_DIRS = [
    '/'.join([PROJ_ROOT, i])
    for i in ['deps/libcanon/include', 'drudge']
]
COMPILE_FLAGS = ['-std=c++14']

canonpy = Extension(
    'drudge.canonpy',
    ['drudge/canonpy.cpp'],
    include_dirs=INCLUDE_DIRS,
    extra_compile_args=COMPILE_FLAGS
)

wickcore = Extension(
    'drudge.wickcore',
    ['drudge/wickcore.cpp'],
    include_dirs=INCLUDE_DIRS,
    extra_compile_args=COMPILE_FLAGS
)

setup(
    packages=find_packages(),
    ext_modules=[canonpy, wickcore],
    package_data={'drudge': ['templates/*']},
)
