#!/usr/bin/env bash
set -euo pipefail

# The 'pentagram' volume is persisted by Buildkite at .nix-cache
CACHE_DIR="$(pwd)/.nix-cache"
if [ -d $CACHE_DIR ]; then
  echo "Cache dir $CACHE_DIR missing"
fi

echo "+++ :nix: Installing Determinate Nix"
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix/tag/v3.14.0 | sh -s -- install linux \
  --determinate \
  --init none \
  --no-confirm

. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh

echo "+++ :nix: Starting Determinate Daemon"
# Run the enterprise daemon in the background to enable optimized caching
nohup determinate-nixd daemon &
for i in {1..50}; do
  if determinate-nixd status &>/dev/null; then break; fi
  sleep 0.1
done

echo "+++ :nix: Building Environment"
echo "--- :nix: Cache size before build"
ls $CACHE_DIR
du -shL $CACHE_DIR || true

echo "--- :nix: Running build"
# Point Nix to our 'pentagram' volume for instant binary substitution.
# -v provides moderate verbosity (what is being built/downloaded).
nix build --verbose .#default \
  --extra-substituters "file://$CACHE_DIR?priority=10&trusted=1"

echo "+++ :pentagram: Running pt check"
nix shell .#default --command pt check

echo "--- :nix: Syncing to 'pentagram' volume"
# Export the build results after success (version is abandonned anyway on
# failure)
nix copy --quiet --to "file://$CACHE_DIR" .#default

echo "--- :nix: Cache size after sync"
ls $CACHE_DIR
du -shL $CACHE_DIR || true
