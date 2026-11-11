# Setup

Initialize Jujutsu and install the repository's Nix profile before changing or building Pentagram. Jujutsu is installed separately; use the [official installation and setup guide](https://docs.jj-vcs.dev/latest/install-and-setup/) to obtain it.

## Source control

From a new repository checkout, initialize Jujutsu with the existing Git repository as its colocated backend:

```sh
jj git init --colocate
jj status
```

Do not run the initialization command again in a checkout that already contains `.jj/`. The [source-control document](source-control.md) defines the repository model and working commands.

## Nix package manager

1. Install Nix 2.32.4 with the Determinate Systems 3.14.0 installer.
2. Install the repository profile.

```sh
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix/tag/v3.14.0 | sh -s -- install
nix profile install .
```

## Run repository commands

Use the repository package environment for checks and tests so the configured Python and development tools are available:

```sh
nix shell .#default -c 0 check --skip-commit
```

This environment includes pytest, pytest-xdist, Ruff, ty, and Watchman. The [command-plane guide](zero/README.md) documents Python test selection, timing, parallel execution, and watch mode.

### Upgrade

1. **Nix:** uninstall, then reinstall it.

   ```sh
   /nix/nix-installer uninstall
   # Then run the install command above
   ```

2. **Profile:** find and upgrade the profile.

   ```sh
   nix profile list
   nix profile upgrade <PROFILE-NAME>
   ```
