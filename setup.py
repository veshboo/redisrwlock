from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='redisrwlock',
    version='0.1.1',
    description='Distributed read-write lock (rwlock) for python using redis',
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
