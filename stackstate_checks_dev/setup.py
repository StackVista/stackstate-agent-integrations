# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from io import open
from os import path

from setuptools import setup


HERE = path.dirname(path.abspath(__file__))

with open(path.join(HERE, 'stackstate_checks', 'dev', '__about__.py'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('__version__'):
            VERSION = line.split('=')[1].strip(' \'"')
            break
    else:
        VERSION = '0.0.1'

with open(path.join(HERE, 'README.md'), 'r', encoding='utf-8') as f:
    README = f.read()


REQUIRES = [
    'coverage<5.0',
    'mock',
    'pytest',
    'pytest-benchmark>=3.2.1',
    'pytest-cov>=2.6.1',
    'pytest-mock',
    'requests>=2.20.0',
    'six==1.14.0',
    'Deprecated==1.2.10',
    "enum34==1.1.10; python_version < '3.4'",
    'schematics==2.1.0'
]


setup(
    name='stackstate_checks_dev',
    version=VERSION,

    description='The StackState Checks Developer Tools',
    long_description=README,
    long_description_content_type='text/markdown',
    keywords='stackstate agent checks dev tools tests',

    url='https://github.com/StackVista/stackstate-agent-integrations',
    author='StackState',
    author_email='info@stackstate.com',
    license='BSD',

    # See https://pypi.org/classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],

    packages=['stackstate_checks', 'stackstate_checks.dev'],
    install_requires=REQUIRES,
    include_package_data=True,

    extras_require={
        'cli': [
            'appdirs',
            'atomicwrites',
            'click',
            'colorama',
            'datadog-a7',
            'docker-compose>=1.23.1,<1.24.0',
            'in-toto==0.2.3',
            'pip-tools',
            'pylint',
            'pyperclip>=1.7.0',
            'PyYAML>=3.13',
            'semver',
            'setuptools>=38.6.0',
            'toml>=0.9.4, <1.0.0',
            'tox',
            'twine>=1.11.0',
            'wheel>=0.31.0',
        ],
    },

    entry_points={
        'pytest11': ['stackstate_checks = stackstate_checks.dev.plugin.plugin'],
        'console_scripts': [
            'checksdev = stackstate_checks.dev.tooling.cli:checksdev',
        ],
    },
)
