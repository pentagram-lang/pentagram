final: prev:

{
  pentagram-python = final.symlinkJoin {
    name = "pentagram-python";
    paths = [
      (final.python3.withPackages (ps: [
        ps.markdown-it-py
        ps.click
        ps.pywatchman
        ps.pytest
        ps.pytest-xdist
        ps.wcwidth
      ]))
      final.ruff
      final.ty
      final.gitMinimal
    ];
  };
}
