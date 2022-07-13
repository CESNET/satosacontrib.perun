from setuptools import setup, find_packages

setup(
    name="satosacontrib.perun",
    python_requires=">=3.9",
    url="https://github.com/CESNET/satosacontrib.perun.git",
    description="Module with satosa microservices",
    packages=find_packages(),
    install_requires=[
        "setuptools",
        "SATOSA>=8.1.1,<9",
        "pysaml2>=7.1.2,<8",
        "requests>=2.28.1,<3",
        "perun.connector>=2.0.1,<3",
        "pycurl>=7.45.1,<8",
        "PyYAML>=6.0,<7",
    ],
)
