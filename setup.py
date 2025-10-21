from setuptools import setup, find_packages

setup(
    name="checkpoint2",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask",
        "werkzeug",
    ],
    python_requires=">=3.8",
)