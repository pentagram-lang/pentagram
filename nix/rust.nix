{ rust-overlay }:
final: prev:

let
  cargo-fixit = final.rustPlatform.buildRustPackage rec {
    pname = "cargo-fixit";
    version = "0.1.7";

    src = final.fetchFromGitHub {
      owner = "crate-ci";
      repo = "cargo-fixit";
      rev = "v${version}";
      hash = "sha256-doEsRmsakdazMlHYtr/bgAHpXkoZhxfwUPTKHu3vmHY=";
    };

    cargoLock.lockFile = "${src}/Cargo.lock";

    doCheck = false;

    nativeBuildInputs = [ final.pkg-config ];
    buildInputs = [ final.openssl ];

    meta = with final.lib; {
      description = "A fix tool for cargo";
      homepage = "https://crates.io/crates/cargo-fixit";
      license = licenses.mit;
    };
  };
in
(import rust-overlay final prev)
// {
  inherit cargo-fixit;

  git-cliff = prev.git-cliff.overrideAttrs (old: {
    # Disable update-informer to prevent unconditional network checks.
    cargoBuildFlags = (old.cargoBuildFlags or [ ]) ++ [
      "--no-default-features"
      "--features"
      "integrations"
    ];
  });

  pentagram-rust = final.symlinkJoin {
    name = "pentagram-rust";
    paths = [
      final.openssl
      (final.rust-bin.nightly.latest.default.override {
        extensions = [
          "rust-src"
          "rust-analyzer"
        ];
      })
      cargo-fixit
      final.cocogitto
      final.git-cliff
      final.dprint
    ];
  };
}
