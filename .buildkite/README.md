# Buildkite CI

This directory defines Pentagram's pull-request merge-gate pipeline in Buildkite. Repository files ([`pipeline.yml`](pipeline.yml) and [`ci-check.sh`](ci-check.sh)) define the job step and execution commands, whereas external Buildkite and GitHub settings govern pipeline identity, build triggers, commit-status publishing, cache-volume persistence, and artifact retention.

## Pipeline identity

- **Organization:** `dan-cecile`
- **Repository:** `pentagram-lang/pentagram`
- **Pipeline:** `pentagram`
- **Default branch:** `main`

Buildkite and GitHub configure those identity bindings, pull-request and branch triggers, and commit-status reporting externally. Within the repository, [`pipeline.yml`](pipeline.yml) defines one `:nix: Check` step with key `check`, running `./.buildkite/ci-check.sh` on the `default` agent queue with `.nix-cache` mounted as the `pentagram` cache volume.

## Execution

[`pipeline.yml`](pipeline.yml) invokes [`ci-check.sh`](ci-check.sh). The script:

1. Installs Determinate Nix v3.14.0, starts `determinate-nixd`, and verifies that the daemon becomes ready before continuing.
2. Builds the repository's `.#default` flake output, configuring `.nix-cache` as an extra substituter.
3. Copies `.#default` and its runtime store-path closure into `.nix-cache` with parallel `zstd` compression immediately after the build succeeds.
4. Runs `0 check` inside `.#default`, wrapping it with `python -m zero.ci_telemetry` when Buildkite run identity is valid or running `0 check` directly otherwise.

The pipeline's validation step is therefore the complete `0 check` cycle, including commit-history validation, as documented in [the command-plane reference](../zero/README.md). Its unfiltered `zero/` and `proj/` Python suites run under `pytest-xdist` with automatic worker selection, and `pytest` reports every test duration.

## Build cache

[`pipeline.yml`](pipeline.yml) mounts `.nix-cache` as a Buildkite cache volume named `pentagram`. Within each job, [`ci-check.sh`](ci-check.sh) addresses `$(pwd)/.nix-cache` through a temporary `/tmp` symlink so Nix's `file://` store parser handles workspace paths containing whitespace or URI-reserved characters cleanly. Before building, it passes `--extra-substituters ...?priority=10&trusted=1` to `nix build --verbose .#default`, giving `.nix-cache` higher substitution priority than default-priority remote substituters such as `cache.nixos.org` at priority `40` for that build command only. Immediately after `nix build` succeeds and before `0 check` runs, the script copies `.#default` and its runtime store-path closure into `.nix-cache` using `compression=zstd&parallel-compression=true`; build-only derivation inputs outside `.#default`'s runtime closure are not copied.

Within the job, `ci-check.sh` therefore always populates `.nix-cache` before `0 check` runs. Across builds, persistence and eviction of the `pentagram` cache volume are governed externally by Buildkite's hosted cache-volume lifecycle, which commits updated volume snapshots from passing jobs, abandons volume changes from failed jobs, and evicts unused volumes under Buildkite's retention policy.

## Test telemetry

When `BUILDKITE_BUILD_ID` and `BUILDKITE_JOB_ID` match `^[[:alnum:]-]+$` and `BUILDKITE_COMMIT` is non-empty, [`ci-check.sh`](ci-check.sh) creates a temporary `.tmp/ci-test-telemetry.XXXXXXXX` staging directory (ignored via `/.tmp/` in `.gitignore` and removed by the `EXIT` trap) and wraps `0 check` in `python -m zero.ci_telemetry` (`zero/ci_telemetry.py`, backed by `zero/telemetry.py` and the `zero.pytest_telemetry` pytest plugin) writing `.tmp/ci-test-telemetry.XXXXXXXX/test-telemetry/<build-id>/<job-id>.sqlite3`. When that Buildkite run identity is missing or invalid, the script emits a warning and runs `0 check` directly without telemetry. Once `<job-id>.sqlite3.complete` exists to mark the database as finalized, the script uploads `test-telemetry/<build-id>/<job-id>.sqlite3` from that staging root as a Buildkite artifact even if `0 check` exited non-zero.

Five append-only tables store the run's observations: `run`, `run_event`, `test_started`, `test_result`, and `resource_sample`. The `run` table stores `run_id` (`<build-id>:<job-id>`), `build_id`, `job_id`, `source_revision`, `python_version`, and `started_at_ns`. The `run_event` table (`event_id`, `run_id`, `source_revision`, `event`, `occurred_at_ns`, `exit_code`) records `occurred_at_ns` on each lifecycle event: `'check-started'` (with `exit_code` set to `NULL`) and `'check-finished'` (with `0 check`'s `exit_code`). Each test start inserts a `test_started` row (`event_id`, `run_id`, `source_revision`, `suite`, `nodeid`, `worker_id`, `started_at_ns`), and its linked `test_result` row adds `start_event_id`, `outcome` (`'passed'`, `'failed'`, `'skipped'`, `'xfailed'`, `'xpassed'`, or `'incomplete'`), `ended_at_ns`, `duration_ns`, and `recovered_at_ns`. Unlike the suite-relative `--nodeid` selectors accepted by `0 check ztest` and `0 check ptest`, `nodeid` is repository-root-relative (`zero/...` or `proj/...`). Normal test results populate `ended_at_ns` and `duration_ns` with `recovered_at_ns` set to `NULL`, whereas worker crashes (`outcome = 'failed'`) and unfinished starts remaining at check exit (`outcome = 'incomplete'`) set `ended_at_ns` and `duration_ns` to `NULL` and record `recovered_at_ns`.

The `resource_sample` table (`event_id`, `run_id`, `source_revision`, `sampled_at_ns`, `interval_ns`, `cpu_cores`, `memory_rss_bytes`, `read_bytes_per_second`, `write_bytes_per_second`) tracks the `0 check` process session. Its sampler waits `0.5` seconds before taking an initial baseline `/proc` observation and then records intervals between successive `0.5`-second observations plus a final observation on check exit, so the first `0.5`-second window before that baseline is unsampled and runs shorter than `0.5` seconds produce zero rows. The `memory_rss_bytes` column sums resident-set sizes across live session processes and can count shared pages more than once. Missing, unreadable, or malformed `/proc/<pid>/io` counters set `read_bytes_per_second` and `write_bytes_per_second` to `NULL` for that and subsequent samples rather than `0`, while CPU and memory sampling continues. Point-in-time columns (`started_at_ns`, `ended_at_ns`, `recovered_at_ns`, `occurred_at_ns`, `sampled_at_ns`) store Unix-epoch nanoseconds (`ended_at_ns` and `recovered_at_ns` clamped to `>= started_at_ns`), whereas elapsed intervals (`duration_ns`, `interval_ns`) store monotonic-clock nanoseconds.

Telemetry failures never alter `0 check`'s exit status. Setup, test-recording, resource-sampling, finalization, and artifact-upload errors emit warnings on standard error—distinguishing an uncreated database from an unfinalized database—and can leave corresponding observations absent. Buildkite artifact retention follows Buildkite's external artifact-storage policy, which the repository does not configure.

## Inspecting builds

Inspect CI builds and download telemetry artifacts with `bk`, an external Buildkite CLI installed and authenticated (`bk configure`) outside `.#default`:

```text
bk build list --pipeline dan-cecile/pentagram
bk build list --pipeline dan-cecile/pentagram --branch <bookmark>
bk build view <number> --pipeline dan-cecile/pentagram
bk build watch <number> --pipeline dan-cecile/pentagram
bk artifacts list <number> --pipeline dan-cecile/pentagram
bk artifacts download <artifact-uuid>
```

Pentagram's colocated Jujutsu checkouts leave `.git/HEAD` detached rather than checking out a Git branch, and omitting `<number>` causes `bk build view`, `bk build watch`, and `bk artifacts list` to resolve a current Git branch and query `/v2/user` (`read_user` token scope). Select `<number>` from `bk build list`—filtering by published Jujutsu bookmark with `--branch <bookmark>` (for example, `main` or `sys`)—and pass `<number>` explicitly.
