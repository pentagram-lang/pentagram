# Tacit (generation 3) <a href="https://tacit-lang.github.io/"><img width="30" height="30" src="art/favicon.svg?raw=true"/></a>

## About

Tacit is a friendly programming language that uses **ergonomics**, **determinism**, and **efficiency** to help you express your creativity.

- With powerful features like **significant whitespace** and **functional programming**, the Tacit language works together with you and helps you out at every step.

- The Tacit community is here to help too! We know how tough coding can be, and we do our best to make this a safe space where **kindness** and **empathy** are the norm.

### The code here

The code here in this Git repo is a temporary interpreter (in Python), created to help bootstrap a self-recursive Tacit compiler.

## Developing

### Prerequisites

You'll need...
- [Python 3.10](https://www.python.org/downloads)
- [Direnv](https://direnv.net/)
- [NASM](https://www.nasm.us/)

When installing Python on Debian or Ubuntu, use the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) and install `python3.10-venv`.

### Initial setup

These commands will get the code and get you into a running Python environment:

```bash
git clone https://github.com/tacit-lang/tacit-gen3-python.git
cd tacit-gen3-python
direnv allow
pip install -r requirements.txt
```

### Commands

- `pytest-watch` to start testing code changes
- `black .` to reformat everything
- `isort .` to sort imports
- `flake8 .` to check the code style

### Python packages

1. Change installed packages with `pip install` or `pip uninstall`
2. Upgrade and freeze all packages with `./pip_freeze.sh`

## License

This project is released under the MIT License (see [LICENSE.md](LICENSE.md) for details).
