#!/usr/bin/env bash
set -euo pipefail

# The 'pentagram' volume is persisted by Buildkite at .nix-cache
CACHE_DIR="$(pwd)/.nix-cache"
CACHE_LINK_DIR=""
DAEMON_LOG=""
telemetry_dir=""

cleanup() {
  if [[ -n "$CACHE_LINK_DIR" ]]; then
    rm -rf "$CACHE_LINK_DIR"
  fi
  if [[ -n "$DAEMON_LOG" ]]; then
    rm -f "$DAEMON_LOG"
  fi
  if [[ -n "$telemetry_dir" ]]; then
    rm -rf "$telemetry_dir"
  fi
}
trap cleanup EXIT

report_cache_size() {
  if [[ -d "$CACHE_DIR" ]]; then
    du -shH "$CACHE_DIR"
  else
    echo "Cache dir $CACHE_DIR does not exist"
  fi
}

echo "+++ :nix: Installing Determinate Nix"
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix/tag/v3.14.0 | sh -s -- install linux \
  --determinate \
  --init none \
  --no-confirm

. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh

echo "+++ :nix: Starting Determinate Daemon"
# Run the enterprise daemon in the background to enable optimized caching
DAEMON_LOG="$(mktemp /tmp/determinate-nixd.XXXXXXXX.log)"
nohup determinate-nixd daemon </dev/null >"$DAEMON_LOG" 2>&1 &
for i in {1..50}; do
  if determinate-nixd status &>/dev/null; then break; fi
  sleep 0.1
done
if ! determinate-nixd status &>/dev/null; then
  echo "ERROR: determinate-nixd failed to become ready" >&2
  cat "$DAEMON_LOG" >&2
  exit 1
fi

echo "+++ :nix: Building Environment"
echo "--- :nix: Cache size before build"
report_cache_size

mkdir -p "$CACHE_DIR"
CACHE_LINK_DIR="$(mktemp -d /tmp/pentagram-nix-cache.XXXXXXXX)"
ln -s "$CACHE_DIR" "$CACHE_LINK_DIR/cache"
CACHE_URI="file://$CACHE_LINK_DIR/cache"

echo "--- :nix: Running build"
# Point Nix to our 'pentagram' volume for instant binary substitution.
# -v provides moderate verbosity (what is being built/downloaded).
nix build --verbose .#default \
  --extra-substituters "$CACHE_URI?priority=10&trusted=1"

echo "--- :nix: Syncing to 'pentagram' volume"
# Populate .nix-cache before running 0 check so cache sync runs independent of check exit status
nix copy --quiet --to "$CACHE_URI?compression=zstd&parallel-compression=true" .#default

echo "--- :nix: Cache size after sync"
report_cache_size

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
    elif [ -f "$telemetry_db" ]; then
      echo "WARNING: Python test telemetry database was not finalized" >&2
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
