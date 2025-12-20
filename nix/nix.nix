final: prev: {
  pentagram-nix = final.symlinkJoin {
    name = "pentagram-nix";
    paths = [
      final.nixfmt-rfc-style
      final.nil
    ];
  };
}
