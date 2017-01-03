from setuptools import setup, find_packages

setup(
    name='redisrwlock',
    version='0.1',
    packages=['redisrwlock'],
    install_requires=['redis>=2.10'],
    author='Jaesup Kwak',
    description='Distributed read-write lock (rwlock) for python using redis',
    keywords=['redis', 'rwlock'],
    license='BSD',
    url='https://github.com/veshboo/redisrwlock',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
