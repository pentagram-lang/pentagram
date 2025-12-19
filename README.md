# Pentagram

## Setup

### Nix package manager

1. Install Nix 2.32.4 (pinned via Determinate Systems 3.14.0 installer)
2. Install profile flake

```sh
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix/tag/v3.14.0 | sh -s -- install
nix profile install .
```

#### Upgrade

1. **Nix**: Uninstall, then reinstall.
   ```sh
   /nix/nix-installer uninstall
   # Then run the install command above
   ```
2. **Profile**: Find and upgrade the profile.
   ```sh
   nix profile list
   nix profile upgrade <PROFILE-NAME>
   ```
