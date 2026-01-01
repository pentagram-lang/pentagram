{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/release-25.11";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      rust-overlay,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        overlays = [
          (import ./nix/rust.nix { inherit rust-overlay; })
          (import ./nix/watchman.nix)
          (import ./nix/python.nix)
          (import ./nix/nix.nix)
          (import ./nix/task.nix)
        ];
        pkgs = import nixpkgs { inherit system overlays; };
      in
      {
        packages.default = pkgs.buildEnv {
          name = "pentagram-profile";
          paths = [
            pkgs.pentagram-rust
            pkgs.pentagram-watchman
            pkgs.pentagram-python
            pkgs.pentagram-nix
            pkgs.pt
          ];
        };
      }
    );
}
