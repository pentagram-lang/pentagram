#!/usr/bin/env python
from __future__ import annotations

import click
import subprocess


@click.group()
def main() -> None:
    pass


@main.group()
def deps() -> None:
    pass


@deps.command()
def add() -> None:
    # `pip index versions PACKAGE`
    # Add to `requirements.in`
    # `pip-compile --quiet --allow-unsafe --generate-hashes --no-reuse-hashes --build-isolation --resolver=backtracking`
    # `pip-sync`
    # `pip install -e .
    # `pip check
    pass


def _compile_deps() -> None:
    subprocess.run(
        [
            "pip-compile",
            "--quiet",
            "--allow-unsafe",
            "--generate-hashes",
            "--no-reuse-hashes",
            "--build-isolation",
            "--resolver=backtracking",
        ],
        check=True,
    )
    subprocess.run(["pip-sync"], check=True)
    subprocess.run(
        ["pip", "install", "-e", "."], check=True
    )
    subprocess.run(["pip", "check"], check=True)


@deps.command()
def outdated() -> None:
    subprocess.run(
        ["pip", "list", "--outdated"], check=True
    )


@deps.command()
def upgrade() -> None:
    # Either update `requirements.in` or use `pip-compile` to upgrade
    # `pip-compile --quiet --allow-unsafe --generate-hashes --no-reuse-hashes --build-isolation --resolver=backtracking --upgrade-package PACKAGE`
    # `pip-sync`
    # `pip install -e .
    # `pip check
    pass


@main.command()
def precommit() -> None:
    _compile_deps()
    subprocess.run(["isort", "."], check=True)
    subprocess.run(["black", "."], check=True)
    subprocess.run(["pytest", "."], check=True)
    subprocess.run(["flake8", "."], check=True)
    subprocess.run(["mypy", "."], check=True)


@main.command()
def check() -> None:
    subprocess.run(["pip", "check"], check=True)
    subprocess.run(["isort", "--check", "."], check=True)
    subprocess.run(["black", "--check", "."], check=True)
    subprocess.run(["pytest", "."], check=True)
    subprocess.run(["flake8", "."], check=True)
    subprocess.run(["mypy", "."], check=True)


@main.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def test(args: tuple[str, ...]) -> None:
    subprocess.run(
        [
            "pytest-watch",
            "..",
            "--ext",
            ".py,.penta",
            "--",
            "-x",
            "-vvv",
            *args,
        ],
        check=True,
    )


@main.command()
def types() -> None:
    subprocess.run(["mypy", "."], check=False)
    subprocess.run(
        [
            "watchmedo",
            "shell-command",
            "--patterns",
            "*.py",
            "--recursive",
            "--wait",
            "--drop",
            "--command",
            "[ $watch_event_type != closed ] && mypy .",
            ".",
        ],
        check=True,
    )
