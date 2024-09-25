# setup.py

from setuptools import setup

setup(
    name="LLMAnalyzer",
    version="0.1",
    py_modules=["main"],
    entry_points={
        'console_scripts': [
            'LLMAnalyzer=main:main',
        ],
    },
)
