# setup.py

from setuptools import setup

setup(
    name="PromptProbe",
    version="0.1",
    py_modules=["main"],
    entry_points={
        'console_scripts': [
            'PromptProbe=main:main',
        ],
    },
)
