final: prev:

{
  pentagram-watchman = final.symlinkJoin {
    name = "pentagram-watchman";
    paths = [
      final.watchman
    ];
  };
}
