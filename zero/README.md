# Command plane

The command plane unifies repository operational workflows under `0` anchored to the enclosing Pentagram checkout, bridging Jujutsu's exported Git state for Git-backed checks, launching coding agents under `sys.md` without ambient customization drift, and mounting `proj/` for provisional project control.

## Identity and ownership

`zero/` is the command-plane Python package, `zero/__main__.py` is its package entrypoint, and `zero/cli.py` is the Click CLI composition root. The Nix profile exposes the entrypoint as both `zero` and `0`; both names execute the same command plane, and `0` is the working command name used across repository documentation, automation, and `--help`.

Within `zero/`, `zero/lib.py` owns `Diagnostic`, `find_repo_root`, subprocess execution and timed status lines (`run_cmd`, `timed_step`, `run_timed_cmd`), Git-backed file discovery (`git_ls_files`, `nix_files`), Cargo package argument building (`cargo_package_args`), and parent-owned command aliasing (`AliasedGroup`). `zero/boot.py` launches `boot_shell` for `0 run`, and `zero/watch.py` implements Watchman-driven incremental checks (`0 watch`).

Check validators live in `zero/doc_lint.py` (`0 check doc`), `zero/commit_message.py` (`0 check commit`), and `zero/repo_policy.py` (`0 check policy`).

Agent launching lives under `zero/agent/`: `zero.agent.launch` is the configured-agent API, `zero/agent/dispatch.py` maps configured targets to `AgentConfig` records (provider executable and model) and verifies `<repo>/sys.md` and executable availability on `PATH`, `zero/agent/common.py` owns `json_object`/`string_list` narrowing helpers, `expand_env_path`, fail-closed file and directory scanning (`read_regular_text`, `parse_json_object`, `read_json_file`, `check_ambient_file`, `scan_ambient_files`), `raise_preflight`, and `exec_agent` (`os.chdir` and `os.execvpe`), and `zero/agent/codex.py`, `zero/agent/claude.py`, and `zero/agent/agy.py` implement provider-specific preflight and launch behaviour.

## Launcher contract

The installed shell wrapper (`0` / `zero` in `nix/zero.nix`) resolves the physical current working directory (`pwd -P`), walks ancestor directories for `zero/__main__.py`, enters that repository root, and executes `python3 -m zero`—printing an error to stderr and exiting `1` before starting Python when outside a checkout or when `cd` fails. When `zero.cli.main` is entered directly in Python (such as `python -m zero` from the checkout root, or from another directory when `zero` is on `PYTHONPATH`), it enforces the same ancestor check, enters the repository root, and restores the previous working directory on exit (exiting non-zero if finding or entering the root fails).

Inside a checkout, running bare `0`, `0 help`, or `0 --help` prints the root command-plane help and exits `0`. `0 help` takes no subcommand arguments; inspect subcommand options with `0 <command> --help`, except `0 run` and the eight `0 agent <target>` commands, which use `_PassthroughCommand` to bypass Click option parsing and forward all trailing arguments (including `--` and `--help`) verbatim.

Every `0 agent` (`0 a`) target requires `<repo>/sys.md` and the provider executable on `PATH`, binds its configured model, passes `<repo>/sys.md` as system instructions (`--config model_instructions_file=...` and `--cd <repo>` in Codex, `--system-prompt-file` in Claude, and `.agents/agents/pentagram/agent.md` in AGY), and runs an ambient-state preflight before launch so external instructions, memories, skills, plugins, or MCP servers cannot compete with `sys.md`. All eight `0 agent` target subcommands—AGY (`agy-flash-yolo` / `flash`, `agy-argon-yolo` / `argon`, `agy-carbon-yolo` / `carbon`), Codex (`codex-luna-yolo` / `luna`, `codex-sol-yolo` / `sol`, `codex-astra-yolo` / `astra`), and Claude (`claude-sonnet-yolo` / `sonnet`, `claude-fable-yolo` / `fable`)—use `_PassthroughCommand` to forward all trailing arguments (including `--` and `--help`) verbatim to the target harness. AGY and Claude pass `--dangerously-skip-permissions`, and Codex passes `--dangerously-bypass-approvals-and-sandbox`. Codex and Claude replace the Python launcher process (`os.execvpe`) with the target CLI, whereas AGY runs `agy` as a child process so its temporary adapter directory is cleaned up when the session exits. Removing interactive harness approval prompts does not override the repository contract or authorize external publication, unrelated scope, or out-of-scope destructive operations.

The AGY launchers (`0 a flash`, `0 a argon`, and `0 a carbon`) always create a temporary AGY custom-agent adapter inside their runtime directory at `.agents/agents/pentagram/agent.md`, using `AGY_AGENT_TOOLS` in `zero/agent/agy.py` as front matter and `sys.md` as its prompt. Because AGY custom agents default to a small read-only tool set, the adapter explicitly enables the file, shell, web, image, scheduling, subagent, workflow, swarm, and question tools.

Before creating that adapter, each AGY launcher runs a mandatory filesystem-only ambient-state preflight. Any discovered standalone skill (`~/.gemini/config/skills/` and paths registered by `~/.gemini/config/skills.json`, including inherited configurations), standalone rule file (`~/.gemini/AGENTS.md`, `~/.gemini/GEMINI.md`, `~/AGENTS.md`, `~/GEMINI.md`, `~/.gemini/rules/`, `~/.gemini/config/rules/`, `~/.agents/rules/`, and paths registered by `~/.gemini/config/rules.json`, including inherited configurations), or standalone MCP entry in `~/.gemini/config/mcp_config.json` fails the preflight and blocks launch because AGY has no persistent disable setting for them. Installed plugins (`~/.gemini/config/plugins/` and paths registered by `~/.gemini/config/plugins.json`, including inherited configurations) pass only when `~/.gemini/config/config.json` sets `plugins[<name>].enabled` to `false`, or when `config.json` has no entry for `<name>` and `plugin.json` sets `disabled: true` (which also covers MCP servers packaged by disabled plugins). The preflight does not run `agy plugin list` and does not check AGY memory because AGY has no operator-facing memory subsystem; custom AGY agents do not mount bundled skills under `~/.gemini/antigravity-cli/builtin/skills/` in ordinary turns, though explicit slash commands such as `/swarm` and `/run-workflow` still expand built-in skill instructions when invoked.

Set `PENTAGRAM_AGY_TOOLSET` to enable a separate `agy --print --output-format stream-json` probe against the generated `pentagram` adapter before starting the session; the launcher then fails if AGY cannot initialize `pentagram` and resolve every tool in `AGY_AGENT_TOOLS`. The variable never changes the adapter's tool list.

The Codex launchers run a mandatory filesystem-only ambient-authority preflight reading `~/.codex/config.toml`, `<repo>/.codex/config.toml`, and any `~/.codex/<profile>.config.toml` named by the home config before starting Codex; any non-empty `profile` setting in a loaded config is rejected. The preflight checks `features.memories` and `features.plugins`, which pass when set to `false` or omitted; feature findings report the persistent remediation commands `codex features disable memories` and `codex features disable plugins`.

Every configured top-level Codex MCP server must be disabled, every home-level `~/.codex/skills/**/SKILL.md` must be disabled through `/skills`, and any file under `~/.codex/memories` blocks launch because Codex has no persistent setting to disable those files. Execution-policy `.rules` files and MCP or plugin cache contents under disabled `features.plugins` are excluded from those checks, and launcher arguments and environment controls are forwarded unchanged; any failure stops the launcher before replacing the Python launcher process with `codex`.

The Claude preflight is filesystem-only unless `PENTAGRAM_CLAUDE_MCP_SET` is set. It inspects `~/.claude/settings.json`, `<repo>/.claude/settings.json`, `<repo>/.claude/settings.local.json`, `/etc/claude-code/managed-settings.json`, `/Library/Application Support/ClaudeCode/managed-settings.json`, `~/.claude.json`, and `<repo>/.mcp.json`, alongside home-level standalone skill (`~/.claude/skills/**/SKILL.md`) and memory (`~/CLAUDE.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/**/*.md`) files.

Any standalone Claude skill or memory file listed above blocks launch because Claude has no persistent setting to disable them. Auto-memory must be persistently disabled via `/memory`, every configured plugin must be disabled via `/plugin` (excluding plugin-provided skills and MCP servers once disabled), and MCP servers must be disabled via `/mcp`. In `~/.claude.json`, top-level `enabledMcpServers` and `projects[<repo>].enabledMcpServers` must be empty, top-level `mcpServers` entries must appear in top-level `disabledMcpServers`, and `projects[<repo>].mcpServers` entries plus the hardcoded Claude.ai MCP set (`claude.ai Gmail`, `claude.ai Google Calendar`, `claude.ai Google Drive`) must appear in `projects[<repo>].disabledMcpServers`. When `<repo>/.mcp.json` exists, every server in its `mcpServers` must appear in `projects[<repo>].disabledMcpjsonServers` and must not appear in `projects[<repo>].enabledMcpjsonServers`. Set `PENTAGRAM_CLAUDE_MCP_SET` to enable a `claude mcp list` live inventory check that fails if the live inventory differs from the hardcoded set. Any failure stops the launcher before replacing the Python launcher process with `claude`.

Launcher preflights inspect only the home, registered, repository, and fixed managed paths listed above and do not discover arbitrary ancestor instruction files.

## Formatting and boot shell

`0` commands never invoke `jj`. Before running `0 fix` or `0 fix fmt`, contributors and agents run `jj status` under the [source-control document](../source-control.md) to snapshot working-copy changes; `0 fix fmt` discovers `.nix` paths via `nix_files` using the live-filtered `git_ls_files` inventory described under [checks](#checks).

`0 fix` (`0 f`) formats the codebase and applies standard lint fixes by running `0 fix fmt` followed by `0 fix lint`. `0 fix fmt` (`0 f f`) runs `cargo fmt`, `ruff format`, and `dprint fmt`, plus `nixfmt` (emitting the `nix-fmt` status label) across non-ignored repository `.nix` files when any exist. `0 fix lint [PACKAGE]` (`0 f l`) runs `ruff check --fix` across Python and `cargo fixit` plus `cargo clippy` (optionally scoped to Cargo crate `PACKAGE`). In these `0 fix` commands, each underlying command emits a timed `[PASS]` or `[FAIL]` status line and aborts on the first failure; when all steps succeed, the command emits `[PASS] fix-fmt`, `[PASS] fix-lint`, or `[PASS] fix`.

`0 run [ARGS]...` (`0 r`) uses `_PassthroughCommand` to forward all trailing arguments (including `--` and `--help`) verbatim and replaces the launcher process (`os.execvp`) with `cargo run -p boot_shell -- [ARGS]...`.

## Checks

Every `0 check` command (standalone and grouped) emits a timed `[PASS]` or `[FAIL]` status summary line. `0` commands never invoke `jj`. In a colocated Jujutsu checkout, Jujutsu exports `@-` as Git `HEAD` and populates `.git/index` (`--cached`) with every path in `@-` plus intent-to-add entries for paths newly tracked in `@`. Deleting or running `jj file untrack` on a path present in `@-` records `D <path>` in `@` while keeping `<path>` in `--cached` until `@-` no longer contains `<path>`, whereas untracking or deleting a path added only in `@` removes it from `--cached` once Jujutsu snapshots and exports `@`.

`git_ls_files` (`git ls-files --cached --others --exclude-standard`) unions `--cached` with non-ignored untracked files on disk, evaluating `.gitignore` directly against untracked files. `nix_files` (`0 fix fmt`, `0 check fmt`, and `0 watch` `nix-fmt`) filters to existing non-symlink regular files on the live filesystem, whereas `doc_lint` (`0 check doc` and `0 watch` `doc-lint`) filters to existing regular files and symbolic links resolving to regular files within `<repo>`. `0 check policy` filters `git_ls_files` with `os.path.lexists` so paths deleted in `@` do not fail policy checks while broken symbolic links on disk remain included. Consequently, new non-ignored files, `.gitignore` rules on untracked files, and live deletions apply immediately on disk while existing files still in `--cached` remain included even if `.gitignore` matches them. Contributors and agents run `jj status` under the [source-control document](../source-control.md) before grouped `0 check` or any Git-backed subcommand (`fmt`, `policy`, `doc`, `commit`, `history`, or `changelog`) to snapshot working-copy changes and update exported Git `HEAD` and `--cached` entries.

Standalone `0 check` (`0 c`) subcommands cover individual validation tools:

- `0 check fmt` (`0 c f`) runs Cargo, Ruff, and dprint format checks, plus `nixfmt` across non-ignored repository `.nix` files when any exist, without short-circuiting.
- `0 check lint [PACKAGE]` (`0 c l`) runs `ruff check` across first-party Python modules and tests and `cargo clippy` (optionally scoped to Cargo crate `PACKAGE`) without short-circuiting.
- `0 check type` enforces `ty` static type checking across first-party Python modules and tests.
- `0 check policy` (`0 c p`) runs the [repository-policy](#repository-policy) scan.
- `0 check doc` (`0 c d`) runs the heading, link, index, and test-companion checks in the [lint document](../doc/quality/lint.md).
- `0 check ztest` and `0 check ptest` run the command-plane and project [Python tests](#python-tests).
- `0 check btest [PACKAGE [TEST_NAME]]` (`0 c bt`) runs `cargo test`, accepting `-n` / `--nocapture` and `--exact`; `TEST_NAME` requires `PACKAGE` first because both arguments are positional.
- `0 check test` (`0 c t`) runs core `.penta` language tests via `boot_shell`.
- `0 check commit` (`0 c m`) validates exported Git `HEAD` commit messages for Conventional Commit subject format (`<= 72` characters, no trailing `.`), blank line 2, and `<= 72`-character body wrapping with literal exemptions.
- `0 check history` (`0 c h`) runs `cog check` against exported Git history.
- `0 check changelog` (`0 c ch`) runs `git cliff` through the Git interoperability surface.

For `commit`, `history`, and `changelog`, contributors invoke the `0` commands rather than direct Git commands, and during final publication validation the [source-control publication sequence](../source-control.md#publish-a-branch) places an empty `@` above the bookmarked final change and runs `jj status` so exported Git `HEAD` names the commit checked by `0 check commit` and `0 check history`.

The grouped `0 check` command executes `fmt`, `lint`, `type`, `policy`, `doc`, `ztest`, `ptest`, `btest`, and `test` without aborting on the first failure, and then runs `commit` and `history` last (unless `-s` / `--skip-commit` is passed) before reporting overall `check` status. `--skip-commit` cannot be combined with a subcommand.

## Python tests

The command-plane and project test suites use function-based pytest modules in `zero/` and `proj/`. `pyproject.toml` (`[tool.pytest.ini_options]`, `python_files = ["*_test.py"]`, `python_classes = []`, and `--durations=0`) selects both directories and reports every test duration. Use `0 check ztest` for `zero/` tests and `0 check ptest` for `proj/` tests. The full `0 check` cycle runs both suites.

Run Python checks in the repository package environment, which supplies pytest and pytest-xdist:

```sh
nix shell .#default -c 0 check ztest -k commit_message
nix shell .#default -c 0 check ztest --nodeid doc_lint_test.py::test_companion_naming_and_pairing
nix shell .#default -c 0 check ptest -k goals
```

Both test commands accept `-k` keyword expressions, `-m` marker expressions, repeated `--nodeid FILE::TEST` selectors, and `--parallel` or `--no-parallel`. A node ID path is relative to that suite's directory. Unfiltered runs use pytest-xdist with `-n auto` by default; filtered runs execute in the main process unless `--parallel` is given. `--no-parallel` keeps an unfiltered suite in the main process. Use `--help` for the exact command options.

## Watch mode

`0 watch` (`0 w`) and `0 --watch` (`0 -w`, which cannot be combined with a subcommand) monitor changes through Watchman. On startup, `0 watch` queries Watchman `watch-project` for the resolved repository root and opens a single subscription (`pentagram-watch`) from Watchman's initial `clock` (mapping `relative_path` to `relative_root` when present), excluding `.git`, `.jj`, `.tmp`, `.nix-cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `target`, `target-analyzer`, and `result`, and coalescing queued socket PDUs via `select.select`.

Watchman connection, command, protocol, or cancellation errors report `Watchman error: ...` to `stderr` and exit `1`, whereas `boot_shell` spawn `OSError`s report `Watch error: ...` to `stderr` and fail that iteration. After subscribing, `0 watch` runs `cargo build -p boot_shell` (`boot-shell-build`) and starts `target/debug/boot_shell test --watch core` when that build succeeds.

Non-ignored file events run checks sequentially inside a timed `watch-iteration` without short-circuiting on check failures:

- `.py` paths run `ruff format --check` (`py-fmt`), `ruff check` (`py-lint`), and `0 check type` (`type`), plus `0 check ztest` (`ztest`) when `zero/` `.py` files changed and `0 check ptest` (`ptest`) when `proj/` `.py` files changed.
- `.md` paths run `dprint check` (`dprint`) and `0 check doc` (`doc-lint`), using the live-filtered `git_ls_files` inventory described under [checks](#checks).
- `.json` and `.toml` paths run `dprint check` (`dprint`), deduplicated when combined with `.md`.
- `.nix` paths run `nixfmt --check` (`nix-fmt`) across non-ignored repository `.nix` files discovered via `nix_files`.
- `.rs` paths and exact basenames `Cargo.toml` and `Cargo.lock` run `cargo fmt -- --check` (`rust-fmt`), `cargo clippy --all-targets --all-features -- -D warnings` (`clippy`), and `cargo test` (`btest`), followed by `cargo build -p boot_shell` (`boot-shell-build`) and stopping and restarting `boot_shell` when `boot-shell-build` succeeds; `Cargo.toml` also triggers `dprint` as `.toml`.

Compared to `0 check --skip-commit`, `0 watch` omits `0 check policy` (`repo-policy`) and does not re-run language, lint, type, or documentation checks when `.gitignore`, tool configuration files (such as `pyproject.toml` or `rustfmt.toml`, which trigger only `dprint`), or non-Markdown link or companion targets change. While running, `boot_shell` monitors `.penta` files under `core/` through its own Watchman subscription and emits per-test `PASS` / `FAIL` lines outside `watch-iteration` status. When a running `boot_shell` child exits (for example on a `.penta` error), `0 watch` reaps it and logs `[test] boot_shell watcher exited (code <n>)`. The next non-ignored `.penta` change restarts `boot_shell` directly without re-running `cargo build` when a built binary is already available (or after the next passing Rust `boot-shell-build`). `Ctrl-C` stops `boot_shell` and closes the Watchman session.

## Repository policy

`zero/repo_policy.py` filters `git_ls_files` by `os.path.lexists` to scan Git-tracked files and untracked files not excluded by Git's standard ignore rules, skipping paths deleted in `@` while retaining broken symbolic links on disk. Contributors and agents run `jj status` under the [source-control document](../source-control.md) before `0 check policy` while continuing to use `jj` directly.

Using Git's inventory prevents `.ignore` and `.rgignore` from hiding prohibited paths, excludes the `.git` tree, and includes tracked and untracked symbolic links. The scan rejects:

- banned agent instruction filenames (`AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, `GEMINI.md`) and any path containing an `.agents`, `.claude`, `.codex`, or `.gemini` directory component;
- any directory component containing `test` (case-insensitive; use `tst` when testing is the subject); and
- any file basename containing `test` (case-insensitive) that does not have the form `<stem>_test.<comp_ext>` or `<stem>.test.<comp_ext>` alongside a non-test sibling `<stem>.<subj_ext>` in the same directory, with non-empty `<stem>`, `<comp_ext>`, and `<subj_ext>` containing neither `.` nor case-insensitive `test`.

Harnesses can be configured with arbitrary alternate instruction filenames; this fixed-name repository scan does not attempt to infer those operator-specific names.

## Command boundary

`proj/` is not owned by the command plane and has no Python import dependency on `zero/`. `zero/cli.py` mounts `proj.cli.project_group` on the root `AliasedGroup` as `0 proj` (`0 p`) via `add_command` without mutating `proj/` objects, while `zero.cli.main` passes the resolved `<repo>` `Path` through Click's context (`ctx.obj`) so `proj.cli.project_group` resolves `.tmp/<project-name>.sqlite3` at `<repo>` (falling back to the repository root when invoked directly) unless `--root` overrides it. `zero/` delegates `0 proj` argument parsing, database and domain operations, and output presentation to `proj/`. The [project workflow](../proj/README.md) owns and documents `proj/`'s [implementation boundaries](../proj/README.md#implementation-boundaries), [goal activation](../proj/README.md#goal-activation) (including reading or copying exact goal text via `0 proj goal text` and `0 proj goal copy` for harness synchronization), and [`0 proj` command surface](../proj/README.md#0-proj-command-surface) without duplicating or narrowing `proj/`'s contracts.
