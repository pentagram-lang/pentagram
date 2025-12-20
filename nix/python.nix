final: prev:

{
  pentagram-python = final.symlinkJoin {
    name = "pentagram-python";
    paths = [
      (final.python3.withPackages (ps: [ ps.click ps.pywatchman ]))
      final.ruff
    ];
  };
}
