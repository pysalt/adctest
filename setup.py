from setuptools import setup, find_packages

__version__ = "1.0.0"

setup(
    name="adctest",
    version=__version__,
    description="End-to-end testing for AngularJS + Python projects",
    url="https://github.com/AdCombo/adctest",
    author="AdCombo API Team",
    author_email="",  # TODO
    license="MIT",  # TODO: discuss
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="web e2e test testing end-to-end",
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    platforms="any",
    install_requires=[
        'selenium==3.11.0',
        'requests==2.23.0',
        'lxml>=3.6.0',
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
    extras_require={
        "tests": "pytest",
        ":python_version<'3.7'": ["dataclasses"],
    },
)
