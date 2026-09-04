final: prev:

{
  zero =
    let
      launcher = final.writeShellScript "zero" ''
        current="$PWD"
        while true; do
            if [ -f "$current/zero/__main__.py" ]; then
                cd "$current"
                exec python3 -m zero "$@"
            fi
            parent=$(dirname "$current")
            if [ "$parent" = "$current" ]; then
                break
            fi
            current="$parent"
        done
        echo "Error: zero/__main__.py not found in parent directories." >&2
        exit 1
      '';
    in
    final.stdenvNoCC.mkDerivation {
      pname = "zero";
      version = "0.1.0";
      dontUnpack = true;
      installPhase = ''
        install -Dm755 ${launcher} $out/bin/zero
        ln -s zero $out/bin/0
      '';
    };
}
