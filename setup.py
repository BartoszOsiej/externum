"""Externum package setup."""

import os

from externum import __version__
from setuptools import setup, find_packages

_long_description = ''
_readme = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')
if os.path.isfile(_readme):
    with open(_readme, 'r', encoding='utf-8') as f:
        _long_description = f.read()

setup(
    name="externum",
    version=__version__,
    description="A self-hosted programming language blending Python readability, binary performance, and Bash control",
    long_description=_long_description,
    long_description_content_type="text/markdown",
    author="Bartosz Osiej",
    url="https://github.com/BartoszOsiej/externum",
    project_urls={
        "Homepage": "https://github.com/BartoszOsiej/externum",
        "Repository": "https://github.com/BartoszOsiej/externum",
        "Issues": "https://github.com/BartoszOsiej/externum/issues",
        "Changelog": "https://github.com/BartoszOsiej/externum/blob/main/CHANGELOG.md",
        "Documentation": "https://bartoszosiej.github.io/externum/",
        "Organization": "https://hartwell-labs.github.io/",
    },
    license="MIT",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "externum=externum.__main__:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Compilers",
    ],
)
