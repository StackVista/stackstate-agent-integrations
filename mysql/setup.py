# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from setuptools import setup
from codecs import open
from os import path

HERE = path.abspath(path.dirname(__file__))

# Get version info
ABOUT = {}
with open(path.join(HERE, "stackstate_checks", "mysql", "__about__.py")) as f:
    exec(f.read(), ABOUT)

# Get the long description from the README file
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


CHECKS_BASE_REQ = 'stackstate-checks-base'


setup(
    name='stackstate-mysql',
    version=ABOUT['__version__'],
    description='The MySQL check',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='stackstate agent mysql check',

    # The project's main homepage.
    url='https://github.com/StackVista/stackstate-agent-integrations',

    # Author details
    author='StackState',
    author_email='info@stackstate.com',

    # License
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    # The package we're going to ship
    packages=['stackstate_checks.mysql'],

    # Run-time dependencies
    install_requires=[CHECKS_BASE_REQ],

    # Extra files to ship with the wheel package
    include_package_data=True,
)
