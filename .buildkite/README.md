# Buildkite CI

This directory contains the Buildkite pipeline definition and its CI script.

## Pipeline identity

- **Organization:** `dan-cecile`
- **Repository:** `pentagram-lang/pentagram`
- **Pipeline:** `pentagram`
- **Default branch:** `main`

The GitHub provider is configured to build pull requests and branches and to publish commit status. The pipeline has one `:nix: Check` step with key `check`, using the `default` agent queue.

## Execution

[`pipeline.yml`](pipeline.yml) invokes [`ci-check.sh`](ci-check.sh). The script:

1. Installs and starts the Determinate Nix environment.
2. Builds the repository's `.#default` flake output, using the `.nix-cache` Buildkite cache as a substituter.
3. Runs exactly `0 check` inside the built Nix environment, through the Python telemetry wrapper when Buildkite run identity is available.
4. Copies the resulting store paths into `.nix-cache` after `0 check` succeeds.

The repository validation performed by this pipeline is therefore the complete `0 check` cycle, including commit-history validation. Its unfiltered `zero/` and `proj/` Python suites use pytest-xdist with automatic worker selection; pytest reports every test duration.

For a Buildkite job with a build ID, job ID, and commit revision, the wrapper writes one SQLite database per check run; the script uploads it as `test-telemetry/BUILD_ID/JOB_ID.sqlite3` after the database is finalized. Each pytest test start is committed to `test_started`; `test_result` stores the linked full pytest node ID, outcome, worker, and timestamps. Normal results have measured start and end times. If pytest-xdist reports a worker crash, the outcome is `failed`, but its actual end and duration are unknown; the report time is stored in `recovered_at_ns`. If a start has no result when `0 check` exits, it is recorded as `incomplete` with a recovery timestamp; its end time and duration remain unset because they are unknown. The `run` and `run_event` tables identify the check, and `resource_sample` stores its time series. Resource samples cover the process session started for `0 check`: CPU core equivalents, summed resident-set size, and read/write bytes per second. The resident-set sum can count shared pages more than once. If a process's I/O counters are missing, unreadable, or malformed, both I/O rates are stored as `NULL` for that and later samples; they are not reported as zero because cumulative I/O can no longer support a reliable rate. CPU and memory samples continue. Samples are taken every half-second while the check runs. Test intervals and resource samples use Unix-epoch nanoseconds so they can be compared directly.

The script uploads a finalized artifact after `0 check` returns, including when the check fails. If telemetry setup or finalization fails, the script warns and skips the upload. Test-recording, resource-sampling, setup, and artifact-upload errors are warnings and do not change the check's exit status; recording errors can leave corresponding observations absent. If the required Buildkite identity is absent, the script runs `0 check` directly without telemetry. Download the artifact from the corresponding check job in Buildkite to inspect or query its SQLite records. Artifacts are retained according to the Buildkite artifact-storage policy; the repository does not configure or verify that external retention period.

## Build cache

The pipeline persists `.nix-cache` as a Buildkite cache named `pentagram`. Before building, `ci-check.sh` configures that directory as a trusted local Nix substituter with priority over remote substitutes. Nix can reuse previously built `.#default` inputs instead of rebuilding them on every CI run. After `0 check` succeeds, the script copies the resulting store paths back into `.nix-cache` for later builds.

## Inspecting builds

Use `bk` with the explicit pipeline identity to inspect CI state:

```text
bk build list --pipeline dan-cecile/pentagram
bk build view --pipeline dan-cecile/pentagram
bk build watch --pipeline dan-cecile/pentagram
```

Pass a build number to `view` or `watch` to inspect a specific build. Pass `--branch NAME` when the relevant build is not on the current branch.
