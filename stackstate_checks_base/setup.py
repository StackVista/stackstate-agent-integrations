# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from setuptools import setup
from codecs import open  # To use a consistent encoding
from os import path


HERE = path.abspath(path.dirname(__file__))

ABOUT = {}
with open(path.join(HERE, "stackstate_checks", "base", "__about__.py")) as f:
    exec(f.read(), ABOUT)

# Get the long description from the README file
LONG_DESC = ""
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    LONG_DESC = f.read()


def get_requirements(fpath, exclude=[], only=[]):
    with open(path.join(HERE, fpath), encoding='utf-8') as f:
        requirements = []
        for line in f:
            name = line.split("==")[0]
            if only:
                if name in only:
                    requirements.append(line.rstrip())
            else:
                if name not in exclude:
                    requirements.append(line.rstrip())
        return requirements


setup(
    # Version should always match one from an agent release
    version=ABOUT["__version__"],
    name='stackstate_checks_base',
    description='The StackState Check Toolkit',
    long_description=LONG_DESC,
    long_description_content_type='text/markdown',
    keywords='stackstate agent checks',
    url='https://github.com/StackVista/stackstate-agent-integrations',
    author='StackState',
    author_email='info@stackstate.com',
    license='BSD',

    # See https://pypi.org/classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    packages=['stackstate_checks'],
    include_package_data=True,

    extras_require={
        'deps': get_requirements(
            'requirements.in',
            exclude=['kubernetes', 'orjson'],
        ),
        'json': get_requirements('requirements.in', only=['orjson']),
        'kube': get_requirements('requirements.in', only=['kubernetes']),
    },
)
