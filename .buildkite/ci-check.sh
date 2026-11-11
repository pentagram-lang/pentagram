#!/usr/bin/env bash
set -euo pipefail

# The 'pentagram' volume is persisted by Buildkite at .nix-cache
CACHE_DIR="$(pwd)/.nix-cache"
if [[ ! -d "$CACHE_DIR" ]]; then
  echo "Cache dir $CACHE_DIR does not exist"
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

echo "+++ :pentagram: Running 0 check"
if [[ ${BUILDKITE_BUILD_ID:-} =~ ^[[:alnum:]-]+$ &&
      ${BUILDKITE_JOB_ID:-} =~ ^[[:alnum:]-]+$ &&
      -n ${BUILDKITE_COMMIT:-} ]]; then
  if mkdir -p .tmp && \
    telemetry_dir="$(mktemp -d .tmp/ci-test-telemetry.XXXXXXXX)"; then
    telemetry_db="$telemetry_dir/test-telemetry/$BUILDKITE_BUILD_ID/$BUILDKITE_JOB_ID.sqlite3"
    if nix shell .#default --command python -m zero.ci_telemetry \
      --database "$telemetry_db" \
      --build-id "$BUILDKITE_BUILD_ID" \
      --job-id "$BUILDKITE_JOB_ID" \
      --revision "$BUILDKITE_COMMIT" \
      -- 0 check; then
      check_status=0
    else
      check_status=$?
    fi

    if [ -f "$telemetry_db" ] && [ -f "$telemetry_db.complete" ]; then
      if (
        cd "$telemetry_dir" &&
        buildkite-agent artifact upload \
          "test-telemetry/$BUILDKITE_BUILD_ID/$BUILDKITE_JOB_ID.sqlite3"
      ); then
        echo "Uploaded Python test telemetry for build $BUILDKITE_BUILD_ID"
      else
        echo "WARNING: unable to upload Python test telemetry artifact" >&2
      fi
    else
      echo "WARNING: Python test telemetry database was not created" >&2
    fi
    if [ "$check_status" -ne 0 ]; then
      exit "$check_status"
    fi
  else
    echo "WARNING: unable to prepare Python test telemetry; running 0 check" >&2
    nix shell .#default --command 0 check
  fi
else
  echo "WARNING: Buildkite run identity unavailable; running 0 check without telemetry" >&2
  nix shell .#default --command 0 check
fi

echo "--- :nix: Syncing to 'pentagram' volume"
# Export the build results after success (version is abandonned anyway on
# failure)
nix copy --quiet --to "file://$CACHE_DIR" .#default

echo "--- :nix: Cache size after sync"
ls $CACHE_DIR
du -shL $CACHE_DIR || true
