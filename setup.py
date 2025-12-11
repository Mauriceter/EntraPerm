from setuptools import setup, find_packages

setup(
    name="entraperm",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,

    package_data={
        "entraperm": [
            "data/*.json",
            "data/*.csv"
        ]
    },

    install_requires=[
        "requests"
    ],

    entry_points={
        "console_scripts": [
            "entraperm=entraperm.entraperm:main"
        ]
    },

    description="Microsoft Entra ID permissions inspector",
    author="Your Name",
)
