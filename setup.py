from setuptools import setup, find_packages

setup(
    name="lamn",
    version="0.1.0",
    author="Alberto Mittone",
    author_email="amittone@anl.gov",
    description="A LAN monitoring tool with server and client functionalities",
    long_description="LAN Monitor (lamn) enables remote client management and system monitoring via SSH with server support.",
    url="https://github.com/yourusername/lamn",  # update if public
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "lamn": ["templates/*.html"]
    },
    install_requires=[
        "Flask",
        "psutil",
        "requests",
        "py-cpuinfo",
        "pexpect"
    ],
    entry_points={
        "console_scripts": [
            "lamn = lamn.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
        "Environment :: Console",
    ],
    python_requires=">=3.6",
)
