from setuptools import setup, find_packages

setup(
    name="natuurspotter",
    version="0.1.0",
    author="Mazan Ali",
    description="A Python package for mapping Belgian biodiversity",
    license='MIT',
    packages=find_packages(include=['natuurspotter']),
    python_requires=">=3.8",
)