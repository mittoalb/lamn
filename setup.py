# setup.py
from setuptools import setup, find_packages

setup(
    name="lamn",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "Flask",
        "psutil",
        "requests",
        "py-cpuinfo"
    ],
    include_package_data=True,
    package_data={"lamn": ["templates/*.html"]},
    entry_points={
        "console_scripts": [
            "lamn = lamn.cli:main",
        ],
    },
    author="Alberto Mittone, amittone@anl.gov",
    description="A LAN monitoring tool with server and client functionalities",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
)

