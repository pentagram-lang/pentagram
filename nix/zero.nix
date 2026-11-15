final: prev:

{
  zero =
    let
      launcher = final.writeShellScript "zero" ''
        if current=$(pwd -P) && [ -n "$current" ]; then
          while true; do
            candidate="''${current%/}/zero/__main__.py"
            if [ -f "$candidate" ]; then
              if ! CDPATH="" cd -- "$current"; then
                echo "Error: failed to enter repository root: $current" >&2
                exit 1
              fi
              exec python3 -m zero "$@"
            fi
            if [ "$current" = "/" ]; then
              break
            fi
            parent="''${current%/*}"
            if [ -z "$parent" ]; then
              current="/"
            else
              current="$parent"
            fi
          done
        fi
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
