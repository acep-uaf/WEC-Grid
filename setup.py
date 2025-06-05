from setuptools import setup, find_packages

setup(
    name="WEC-Grid",  # Change to match the desired software name
    version="0.1.0",
    packages=find_packages(),  # Automatically finds WecGrid and submodules
    install_requires=[
        "numpy>=1.21.6",
        "pandas>=1.0.4",
        "matplotlib>=3.1.0",
        "seaborn>=0.11.0",
        "pypsa",
        "pypower>=5.1.17",
        "pyrlu>=0.2.1",
        "ipycytoscape>=1.3.3",
        "spectate>=1.0.1",
        "bqplot",
        "pywin32>=228; platform_system=='Windows'",
        "ipykernel>=6.0",
    ],
    description=(
        "WecGrid is an open-source Python library crafted to simulate the integration "
        "of Wave Energy Converters (WECs) and Current Energy Converters (CECs) into "
        "renowned power grid simulators like PSS®E & PyPSA."
    ),
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Alexander Barajas-Ritchie",
    author_email="barajale@oregonstate.edu",
    url="https://github.com/acep-uaf/WEC-GRID",
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)