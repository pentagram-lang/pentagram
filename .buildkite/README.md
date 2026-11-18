# Buildkite CI

This directory defines Pentagram's pull-request merge-gate pipeline in Buildkite. Repository files ([`pipeline.yml`](pipeline.yml) and [`ci-check.sh`](ci-check.sh)) define the job step and execution commands, whereas external Buildkite and GitHub settings govern pipeline identity, build triggers, commit-status publishing, and cache-volume persistence.

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
4. Runs `nix shell .#default --command 0 check`.

The pipeline's validation step is therefore the complete `0 check` cycle, including commit-history validation, as documented in [the command-plane reference](../zero/README.md). Its unfiltered `zero/` and `proj/` Python suites run under `pytest-xdist` with automatic worker selection, and `pytest` reports every test duration.

## Build cache

[`pipeline.yml`](pipeline.yml) mounts `.nix-cache` as a Buildkite cache volume named `pentagram`. Within each job, [`ci-check.sh`](ci-check.sh) addresses `$(pwd)/.nix-cache` through a temporary `/tmp` symlink so Nix's `file://` store parser handles workspace paths containing whitespace or URI-reserved characters cleanly. Before building, it passes `--extra-substituters ...?priority=10&trusted=1` to `nix build --verbose .#default`, giving `.nix-cache` higher substitution priority than default-priority remote substituters such as `cache.nixos.org` at priority `40` for that build command only. Immediately after `nix build` succeeds and before `0 check` runs, the script copies `.#default` and its runtime store-path closure into `.nix-cache` using `compression=zstd&parallel-compression=true`; build-only derivation inputs outside `.#default`'s runtime closure are not copied.

Within the job, `ci-check.sh` therefore always populates `.nix-cache` before `0 check` runs. Across builds, persistence and eviction of the `pentagram` cache volume are governed externally by Buildkite's hosted cache-volume lifecycle, which commits updated volume snapshots from passing jobs, abandons volume changes from failed jobs, and evicts unused volumes under Buildkite's retention policy.

## Inspecting builds

Inspect CI builds with `bk`, an external Buildkite CLI installed and authenticated (`bk configure`) outside `.#default`:

```text
bk build list --pipeline dan-cecile/pentagram
bk build list --pipeline dan-cecile/pentagram --branch <bookmark>
bk build view <number> --pipeline dan-cecile/pentagram
bk build watch <number> --pipeline dan-cecile/pentagram
```

Pentagram's colocated Jujutsu checkouts leave `.git/HEAD` detached rather than checking out a Git branch, and omitting `<number>` causes `bk build view` and `bk build watch` to resolve a current Git branch and query `/v2/user` (`read_user` token scope). Select `<number>` from `bk build list`—filtering by published Jujutsu bookmark with `--branch <bookmark>` (for example, `main` or `sys`)—and pass `<number>` explicitly.
