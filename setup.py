"""Externum package setup."""

from setuptools import setup, find_packages

setup(
    name="externum",
    version="2.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "externum=externum.__main__:main",
        ],
    },
    python_requires=">=3.10",
)
