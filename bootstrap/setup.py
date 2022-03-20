from setuptools import setup

setup(
    name="pentagram-bootstrap",
    entry_points={
        "console_scripts": [
            "pentagram=pentagram.main:main",
        ]
    },
)
