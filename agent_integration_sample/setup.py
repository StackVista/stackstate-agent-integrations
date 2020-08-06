# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from codecs import open  # To use a consistent encoding
from os import path

from setuptools import setup

HERE = path.dirname(path.abspath(__file__))

# Get version info
ABOUT = {}
with open(path.join(HERE, 'stackstate_checks', 'agent_integration_sample', '__about__.py')) as f:
    exec(f.read(), ABOUT)

# Get the long description from the README file
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


CHECKS_BASE_REQ = 'stackstate-checks-base'


setup(
    name='stackstate-agent_integration_sample',
    version=ABOUT['__version__'],
    description='The Agent_integration_sample check',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='stackstate agent agent_integration_sample check',

    # The project's main homepage.
    url='https://github.com/StackVista/stackstate-agent-integrations',

    # Author details
    author='StackState',
    author_email='info@stackstate.com',

    # License
    license='BSD-3-Clause',

    # See https://pypi.org/classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],

    # The package we're going to ship
    packages=['stackstate_checks.agent_integration_sample'],

    # Run-time dependencies
    install_requires=[CHECKS_BASE_REQ],

    # Extra files to ship with the wheel package
    include_package_data=True,
)
