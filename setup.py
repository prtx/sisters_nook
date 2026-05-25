from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent

setup(
    name="sisters_nook",
    version="0.1.0",
    description="Service layer and schema for the Sisters Nook Cafe CMS",
    long_description=(HERE / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Sisters Nook Developers",
    python_requires=">=3.10",
    packages=find_packages(include=["sisters_nook", "sisters_nook.*"]),
    include_package_data=True,
    install_requires=[
        "SQLAlchemy>=2.0",
        "pytest>=9.0",
    ],
    extras_require={"dev": ["pytest>=9.0"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
