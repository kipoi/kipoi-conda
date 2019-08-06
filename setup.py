#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

requirements = [
    "six",
    "related",
    "six",
    "kipoi_utils>=0.3.0"
]

test_requirements = [
    "bumpversion",
    "wheel",
    "pytest>=3.3.1",
    "pytest-xdist",  # running tests in parallel
    "pytest-pep8",  # see https://github.com/kipoi/kipoi/issues/91
    "pytest-cov",
    "coveralls",
    "numpy",
    "pandas>=0.21.0"
]

desc = "kipoi-conda: conda/pip related functionality used by Kipoi"
setup(
    name='kipoi_conda',
    version='0.2.2',
    description=desc,
    author="Kipoi team",
    author_email='avsec@in.tum.de',
    url='https://github.com/kipoi/kipoi-conda',
    long_description=desc,
    packages=find_packages(),
    install_requires=requirements,
    extras_require={
        "develop": test_requirements,
    },
    license="MIT license",
    zip_safe=False,
    keywords=["model zoo", "deep learning",
              "computational biology", "bioinformatics", "genomics"],
    test_suite='tests',
    include_package_data=False,
    tests_require=test_requirements
)
