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
3. Runs exactly `0 check` inside the built Nix environment.
4. Copies the successful build result back to the `.nix-cache` volume.

The repository validation performed by this pipeline is therefore the complete `0 check` cycle, including commit-history validation.

## Build cache

The pipeline persists `.nix-cache` as a Buildkite cache named `pentagram`. Before building, `ci-check.sh` configures that directory as a trusted local Nix substituter with priority over remote substitutes. Nix can reuse previously built `.#default` inputs instead of rebuilding them on every CI run. After a successful build, the script copies the resulting store paths back into `.nix-cache` for later builds.

## Inspecting builds

Use `bk` with the explicit pipeline identity to inspect CI state:

```text
bk build list --pipeline dan-cecile/pentagram
bk build view --pipeline dan-cecile/pentagram
bk build watch --pipeline dan-cecile/pentagram
```

Pass a build number to `view` or `watch` to inspect a specific build. Pass `--branch NAME` when the relevant build is not on the current branch.
