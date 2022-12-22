# Pentagram (bootstrap)

### The code here

The code here in this Git repo is a temporary interpreter (in Python), created to help bootstrap a self-recursive Pentagram compiler.

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
git clone https://github.com/pentagram-lang/pentagram.git
cd pentagram/bootstrap
direnv allow
pip install -r requirements.txt
pip install -e .
```

### Commands

- `_dev test` to start testing code changes
- `_dev types` to start checking code types
- `_dev precommit` to reformat & check everything

### Python packages

- `_dev deps add` to add a new package
- `_dev deps outdated` to list outdated packages
- `_dev deps upgrade` to updage a package

## License

This project is released under the MIT License (see [LICENSE.md](LICENSE.md) for details).
