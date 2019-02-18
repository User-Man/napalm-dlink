"""setup.py file."""

from setuptools import setup, find_packages

__author__ = 'UserMan'

setup(
    name="napalm-dlink",
    version="0.1.1",
    packages=find_packages(),
    author="UserMan",
    description="Network Automation and Programmability Abstraction Layer with Multivendor support",
    classifiers=[
        'Topic :: Utilities',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
    ],
    include_package_data=True,
    install_requires=['napalm>=2.0.0', 'netmiko>=1.4.2'],
)
