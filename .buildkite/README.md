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
4. Runs `0 check` inside `.#default`, wrapping it with `python -m zero.telemetry_ci` when `BUILDKITE_BUILD_ID` and `BUILDKITE_JOB_ID` match `^[[:alnum:]][[:alnum:]-]*$`, `BUILDKITE_COMMIT` is non-empty, staging succeeds, and `import zero.telemetry_ci` succeeds; otherwise warns on standard error and runs `0 check` directly.
5. When instrumented, uploads `test-telemetry/<build-id>/<job-id>.sqlite3` as a Buildkite artifact if both the database and its `.complete` marker exist, emits a warning on standard error if creation, finalization, or upload fails, and exits with `0 check`'s status.

The pipeline's validation step is therefore the complete `0 check` cycle, including commit-history validation, as documented in [the command-plane reference](../zero/README.md). Its unfiltered `zero/` and `proj/` Python suites run under `pytest-xdist` with automatic worker selection, and `pytest` reports every test duration.

## Build cache

[`pipeline.yml`](pipeline.yml) mounts `.nix-cache` as a Buildkite cache volume named `pentagram`. Within each job, [`ci-check.sh`](ci-check.sh) addresses `$(pwd)/.nix-cache` through a temporary `/tmp` symlink so Nix's `file://` store parser handles workspace paths containing whitespace or URI-reserved characters cleanly. Before building, it passes `--extra-substituters ...?priority=10&trusted=1` to `nix build --verbose .#default`, giving `.nix-cache` higher substitution priority than default-priority remote substituters such as `cache.nixos.org` at priority `40` for that build command only. Immediately after `nix build` succeeds and before `0 check` runs, the script copies `.#default` and its runtime store-path closure into `.nix-cache` using `compression=zstd&parallel-compression=true`; build-only derivation inputs outside `.#default`'s runtime closure are not copied.

Within the job, `ci-check.sh` therefore always populates `.nix-cache` before `0 check` runs. Across builds, persistence and eviction of the `pentagram` cache volume are governed externally by Buildkite's hosted cache-volume lifecycle, which commits updated volume snapshots from passing jobs, abandons volume changes from failed jobs, and evicts unused volumes under Buildkite's retention policy.

## Test telemetry

When `BUILDKITE_BUILD_ID` and `BUILDKITE_JOB_ID` match `^[[:alnum:]][[:alnum:]-]*$` and `BUILDKITE_COMMIT` is non-empty, [`ci-check.sh`](ci-check.sh) creates a temporary `.tmp/ci-test-telemetry.XXXXXXXX` staging directory (ignored via `/.tmp/` in `.gitignore` and removed by the `EXIT` trap), checks `python -c 'import zero.telemetry_ci'`, and wraps `0 check` with:

```sh
python -m zero.telemetry_ci --database=<path> --build-id=<id> --job-id=<id> --revision=<rev> -- 0 check
```

where `<path>` is `.tmp/ci-test-telemetry.XXXXXXXX/test-telemetry/<build-id>/<job-id>.sqlite3` (backed by `zero/telemetry_ci.py`, `zero/telemetry.py`, and `zero/telemetry_plugin.py`). When `BUILDKITE_BUILD_ID`, `BUILDKITE_JOB_ID`, or `BUILDKITE_COMMIT` is missing or invalid, or when staging preparation or importing `zero.telemetry_ci` fails, [`ci-check.sh`](ci-check.sh) warns on standard error and runs `0 check` directly without telemetry. Similarly, if `zero.telemetry_ci` cannot import `zero.telemetry_plugin`, initialize the SQLite database, or record `'check-started'`, it warns on standard error and executes the wrapped command uninstrumented without failing the run.

Across the subprocess boundary, `zero/telemetry_ci.py` exports `PENTAGRAM_TEST_TELEMETRY_DB` (resolved database path), `PENTAGRAM_TEST_TELEMETRY_BUILD_ID`, `PENTAGRAM_TEST_TELEMETRY_JOB_ID`, and `PENTAGRAM_TEST_TELEMETRY_REVISION` to the child process, clears `PYTEST_XDIST_WORKER`, and appends `zero.telemetry_plugin` to `PYTEST_PLUGINS`. Once `<job-id>.sqlite3.complete` exists to mark the database as finalized, [`ci-check.sh`](ci-check.sh) uploads `test-telemetry/<build-id>/<job-id>.sqlite3` from that staging root as a standalone per-job Buildkite SQLite artifact even when `0 check` exits non-zero; the repository does not perform cross-build aggregation, cross-run flaky-test classification, or retry of failed tests.

Five append-only tables store the run's observations: `run`, `run_event`, `test_started`, `test_result`, and `resource_sample`. Every row in `run_event`, `test_started`, `test_result`, and `resource_sample` references `run(run_id)` and matches its `(run_id, source_revision)` pair. `test_started` and `test_result` record only Python `pytest` suites (`0 check ztest` and `0 check ptest`), not Rust bootstrap tests (`0 check btest`) or core language tests (`0 check test`).

- `run`: stores `run_id` (`<build-id>:<job-id>`), `build_id`, `job_id`, `source_revision`, `python_version`, and `started_at_ns`.
- `run_event`: stores `event_id`, `run_id`, `source_revision`, `event`, `occurred_at_ns`, and `exit_code`, recording `'check-started'` (with `exit_code` set to `NULL`) and `'check-finished'` (with `0 check`'s `exit_code`).
- `test_started`: stores `event_id`, `run_id`, `source_revision`, `suite`, `nodeid`, `worker_id`, and `started_at_ns`.
- `test_result`: stores `event_id`, `start_event_id`, `run_id`, `source_revision`, `suite`, `nodeid`, `worker_id`, `outcome`, `started_at_ns`, `ended_at_ns`, `duration_ns`, and `recovered_at_ns`. `start_event_id` is a `UNIQUE` foreign key referencing `test_started(event_id)` (giving each `test_started` row at most one `test_result` row, or zero if result recording and exit recovery both fail), and SQLite triggers require `(run_id, source_revision, suite, nodeid, worker_id, started_at_ns)` on `test_result` to match the referenced `test_started` row. `outcome` is `'passed'`, `'failed'`, `'skipped'`, `'xfailed'`, `'xpassed'`, or `'incomplete'`. Normal results populate `ended_at_ns` and `duration_ns` with `recovered_at_ns` set to `NULL`, whereas worker crashes (`outcome = 'failed'`) and unfinished starts remaining at check exit (`outcome = 'incomplete'`) set `ended_at_ns` and `duration_ns` to `NULL` and record `recovered_at_ns`.
- `resource_sample`: stores `event_id`, `run_id`, `source_revision`, `sampled_at_ns`, `interval_ns`, `cpu_cores`, `memory_rss_bytes`, `read_bytes_per_second`, and `write_bytes_per_second`, tracking the `0 check` process session.

In `test_started` and `test_result`, `suite` is the leading directory segment of `nodeid` (for example, `'zero'` or `'proj'`), falling back to the first configured `pytest` `testpaths` directory name or the `rootpath` directory name when `nodeid` has no leading directory segment. `worker_id` is `PYTEST_XDIST_WORKER` (such as `'gw0'`) or `'master'` outside `pytest-xdist` workers. Unlike the suite-relative `--nodeid` selectors accepted by `0 check ztest` and `0 check ptest`, `nodeid` is repository-root-relative (`zero/...` or `proj/...`).

For `resource_sample`, the sampler waits `0.5` seconds before taking an initial baseline `/proc` observation and then records intervals between successive `0.5`-second observations plus a final observation on check exit, so the first `0.5`-second window before that baseline is unsampled and runs shorter than `0.5` seconds produce zero rows. The `memory_rss_bytes` column sums resident-set sizes across live session processes and can count shared pages more than once. Processes that exit or vanish mid-sample are skipped without affecting I/O availability, whereas missing, unreadable, or malformed `/proc/<pid>/io` counters on a live session process set `read_bytes_per_second` and `write_bytes_per_second` to `NULL` for that and subsequent samples rather than `0` while CPU and memory sampling continues. Point-in-time columns (`started_at_ns`, `ended_at_ns`, `recovered_at_ns`, `occurred_at_ns`, `sampled_at_ns`) store Unix-epoch nanoseconds (`ended_at_ns` and `recovered_at_ns` clamped to `>= started_at_ns`), whereas elapsed intervals (`duration_ns`, `interval_ns`) store monotonic-clock nanoseconds.

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
