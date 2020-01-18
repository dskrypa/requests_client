
from pathlib import Path
from setuptools import setup, find_packages

project_root = Path(__file__).resolve().parent

with project_root.joinpath('requirements.txt').open('r', encoding='utf-8') as f:
    requirements = f.read().splitlines()

with project_root.joinpath('readme.md').open('r', encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='requests_client',
    version='2020.01.18',
    author='Doug Skrypa',
    author_email='dskrypa@gmail.com',
    description='Requests Client',
    long_description=long_description,
    url='https://github.com/dskrypa/requests_client',
    packages=find_packages(),
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    python_requires='~=3.4',
    install_requires=['wheel'] + requirements
)
