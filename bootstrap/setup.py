from setuptools import setup

setup(
    name="pentagram-bootstrap",
    packages=["pentagram"],
    entry_points={
        "console_scripts": [
            "_dev=pentagram.bin._dev:main",
            "pentagram=pentagram.bin.pentagram:main",
        ]
    },
)
