final: prev:

{
  pt = final.writeShellScriptBin "pt" ''
    current="$PWD"
    while true; do
        if [ -x "$current/task.py" ]; then
            exec "$current/task.py" "$@"
        fi
        parent=$(dirname "$current")
        if [ "$parent" = "$current" ]; then
            break
        fi
        current="$parent"
    done
    echo "Error: task.py not found in parent directories." >&2
    exit 1
  '';
}
