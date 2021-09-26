import glob
from distutils.core import setup

from setuptools import find_packages

setup(
    name='blockchain',
    version='1.0',
    description='Blockchain utils',
    author='Antti Jaakkola',
    url='https://github.com/annttu/blockchain',
    packages=find_packages(include=['blockchain', 'blockchain.*']),
    package_data={'blockchain': ['contracts/*.json']},
    # data_files=[('contracts', glob.glob('contracts/*.json'))],
    python_requires='>=3.6',
    install_requires=[
        'web3>=5.20.0',
        'cachetools',
        'simplejson',
        'aiohttp[speedups]',
        'aiologger',
        'aiofiles'
    ]
)
