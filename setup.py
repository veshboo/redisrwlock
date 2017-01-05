import re
from setuptools import setup
from codecs import open

# Single-sourcing project version
with open('redisrwlock/__init__.py', encoding='utf-8') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        f.read(), re.MULTILINE).group(1)
if not version:
    raise RuntimeError('Cannot find version information')

# Short and long descriptions
description = 'Distributed reader-writer lock (rwlock) for python using redis'
with open('README.rst', 'r', encoding='utf-8') as f:
    long_description = f.read()
if not long_description:
    raise RuntimeError('Cannot read README.rst')

setup(
    name='redisrwlock',
    version=version,
    description=description,
    long_description=long_description,
    keywords=['redis', 'rwlock'],
    url='https://github.com/veshboo/redisrwlock',

    author='Jaesup Kwak',
    license='BSD',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: BSD License',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
    ],

    packages=['redisrwlock'],
    install_requires=['redis>=2.10']
)
