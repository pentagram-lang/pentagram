# Command plane

The command plane provides the repository's operational commands for formatting, checks, tests, agent launch, the boot shell, watch mode, and project-control access.

## Identity and ownership

`zero/` is the command-plane Python package, `zero/__main__.py` is the thin package entrypoint, and `zero/cli.py` is the Click CLI composition root. The Nix profile exposes the entrypoint as both `zero` and `0`; both names execute the same command plane, and `0` is the working command name used across repository documentation, automation, and `--help`.

Within the package, `zero/lib.py` owns command execution, timed status lines, command aliasing, Git-backed Nix-file discovery, and Cargo argument builders. `zero.agent.launch` is the configured-agent API; `zero/agent/dispatch.py` selects a configured provider; `zero/agent/codex.py`, `zero/agent/claude.py`, and `zero/agent/agy.py` own provider-specific preflight and launch behaviour; and `zero/agent/common.py` holds shared agent filesystem and JSON helpers.

## Launcher contract

The installed wrapper resolves the physical current working directory (`pwd -P`), walks parent directories for `zero/__main__.py`, changes to that repository root, and executes `python3 -m zero`. Outside a checkout, `zero.cli.main` enforces the same ancestor check and exits non-zero.

`0 agent` (`0 a`) launches configured agent subcommands across AGY (`agy-flash-yolo` / `flash`, `agy-argon-yolo` / `argon`, `agy-carbon-yolo` / `carbon`), Codex (`codex-luna-yolo` / `luna`, `codex-sol-yolo` / `sol`, `codex-astra-yolo` / `astra`), and Claude (`claude-sonnet-yolo` / `sonnet`, `claude-fable-yolo` / `fable`), forwarding trailing CLI arguments to the underlying harness. AGY and Claude pass `--dangerously-skip-permissions`, and Codex passes `--dangerously-bypass-approvals-and-sandbox`. Codex and Claude replace the Python launcher process (`os.execvpe`) with the target CLI, whereas AGY runs `agy` as a child process so its temporary adapter directory is cleaned up when the session exits. Removing interactive harness approval prompts does not override the repository contract or authorize external publication, unrelated scope, or out-of-scope destructive operations.

The AGY launchers (`0 a flash`, `0 a argon`, and `0 a carbon`) always create a temporary AGY custom-agent adapter inside their runtime directory at `.agents/agents/pentagram/agent.md`, using `AGY_AGENT_TOOLS` in `zero/agent/agy.py` as front matter and `sys.md` as its prompt. Because AGY custom agents default to a small read-only tool set, the adapter explicitly enables the file, shell, web, image, scheduling, subagent, workflow, swarm, and question tools.

Before creating that adapter, each AGY launcher runs a mandatory filesystem-only ambient-state preflight. Any discovered standalone skill (`~/.gemini/config/skills/` and paths registered by `~/.gemini/config/skills.json`, including inherited configurations), standalone rule file (`~/.gemini/AGENTS.md`, `~/.gemini/GEMINI.md`, `~/AGENTS.md`, `~/GEMINI.md`, `~/.gemini/rules/`, `~/.gemini/config/rules/`, `~/.agents/rules/`, and paths registered by `~/.gemini/config/rules.json`, including inherited configurations), or standalone MCP entry in `~/.gemini/config/mcp_config.json` fails the preflight and blocks launch because AGY has no persistent disable setting for them. Installed plugins (`~/.gemini/config/plugins/` and paths registered by `~/.gemini/config/plugins.json`, including inherited configurations) pass only when `~/.gemini/config/config.json` sets `plugins[<name>].enabled` to `false`, or when `config.json` has no entry for `<name>` and `plugin.json` sets `disabled: true` (which also covers MCP servers packaged by disabled plugins). The preflight does not run `agy plugin list` and does not check AGY memory because AGY has no operator-facing memory subsystem; custom AGY agents do not mount bundled skills under `~/.gemini/antigravity-cli/builtin/skills/` in ordinary turns, though explicit slash commands such as `/swarm` and `/run-workflow` still expand built-in skill instructions when invoked.

Set `PENTAGRAM_AGY_TOOLSET` to enable a separate `agy --print --output-format stream-json` probe against the generated `pentagram` adapter before starting the session; the launcher then fails if AGY cannot initialize `pentagram` and resolve every tool in `AGY_AGENT_TOOLS`. The variable never changes the adapter's tool list.

The Codex launchers run a mandatory filesystem-only ambient-authority preflight reading `~/.codex/config.toml`, `<repo>/.codex/config.toml`, and any `~/.codex/<profile>.config.toml` named by the home config before starting Codex; any non-empty `profile` setting in a loaded config is rejected. The preflight checks `features.memories` and `features.plugins`, which pass when set to `false` or omitted; feature findings report the persistent remediation commands `codex features disable memories` and `codex features disable plugins`.

Every configured top-level Codex MCP server must be disabled, every home-level `~/.codex/skills/**/SKILL.md` must be disabled through `/skills`, and any file under `~/.codex/memories` blocks launch because Codex has no persistent setting to disable those files. Execution-policy `.rules` files and MCP or plugin cache contents under disabled `features.plugins` are excluded from those checks, and launcher arguments and environment controls are forwarded unchanged; any failure stops the launcher before replacing the Python launcher process with `codex`.

The Claude preflight is filesystem-only unless `PENTAGRAM_CLAUDE_MCP_SET` is set. It inspects `~/.claude/settings.json`, `<repo>/.claude/settings.json`, `<repo>/.claude/settings.local.json`, `/etc/claude-code/managed-settings.json`, `/Library/Application Support/ClaudeCode/managed-settings.json`, `~/.claude.json`, and `<repo>/.mcp.json`, alongside home-level standalone skill (`~/.claude/skills/**/SKILL.md`) and memory (`~/CLAUDE.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/**/*.md`) files.

Any standalone Claude skill or memory file listed above blocks launch because Claude has no persistent setting to disable them. Auto-memory must be persistently disabled via `/memory`, every configured plugin must be disabled via `/plugin` (excluding plugin-provided skills and MCP servers once disabled), and MCP servers must be disabled via `/mcp`: top-level `mcpServers` entries in `~/.claude.json` must appear in top-level `disabledMcpServers`, `<repo>/.mcp.json` entries in `projects[<repo>].disabledMcpjsonServers`, and `projects[<repo>].mcpServers` entries plus the hardcoded Claude.ai MCP set (`claude.ai Gmail`, `claude.ai Google Calendar`, `claude.ai Google Drive`) in `projects[<repo>].disabledMcpServers`, with none listed in the corresponding `enabledMcp*` lists. Set `PENTAGRAM_CLAUDE_MCP_SET` to enable a `claude mcp list` live inventory check that fails if the live inventory differs from the hardcoded set. Any failure stops the launcher before replacing the Python launcher process with `claude`.

Launcher preflights inspect only the home, registered, repository, and fixed managed paths listed above and do not discover arbitrary ancestor instruction files.

## Formatting and boot shell

`0 fix` (`0 f`) formats the codebase and applies standard lint fixes by running `0 fix fmt` followed by `0 fix lint`. `0 fix fmt` (`0 f f`) runs `cargo fmt`, `ruff format`, and `dprint fmt`, plus `nixfmt` across non-ignored repository `.nix` files when any exist. `0 fix lint [PACKAGE]` (`0 f l`) runs `ruff check --fix` across Python and `cargo fixit` plus `cargo clippy` (optionally scoped to Cargo crate `PACKAGE`). In these `0 fix` commands, each underlying command emits a timed `[PASS]` or `[FAIL]` status line and aborts on the first failure; when all steps succeed, the command emits `[PASS] fix-fmt`, `[PASS] fix-lint`, or `[PASS] fix`.

`0 run [ARGS]...` (`0 r`) forwards unprocessed arguments unchanged to `boot_shell`.

## Checks

Every `0 check` command (standalone and grouped) emits a timed `[PASS]` or `[FAIL]` status summary line.

Standalone `0 check` (`0 c`) subcommands cover individual validation tools:

- `0 check fmt` (`0 c f`) runs Cargo, Ruff, and dprint format checks, plus `nixfmt` across non-ignored repository `.nix` files when any exist, without short-circuiting.
- `0 check lint [PACKAGE]` (`0 c l`) runs `ruff check` across first-party Python modules and tests and `cargo clippy` (optionally scoped to Cargo crate `PACKAGE`) without short-circuiting.
- `0 check type` enforces `ty` static type checking across first-party Python modules and tests.
- `0 check policy` (`0 c p`) runs the [repository-policy](#repository-policy) scan.
- `0 check doc` (`0 c d`) runs the heading, link, index, and test-companion checks in the [lint document](../doc/quality/lint.md).
- `0 check ztest` and `0 check ptest` run the command-plane and project [Python tests](#python-tests).
- `0 check btest [PACKAGE] [TEST_NAME]` (`0 c bt`) runs `cargo test`, accepting `-n` / `--nocapture` and `--exact`.
- `0 check test` (`0 c t`) runs core `.penta` language tests via `boot_shell`.
- `0 check commit` (`0 c m`) validates exported Git `HEAD` commit-message line lengths.
- `0 check history` (`0 c h`) runs `cog check` against exported Git history.
- `0 check changelog` (`0 c ch`) runs `git cliff` through the Git interoperability surface.

For `commit`, `history`, and `changelog`, contributors invoke the `0` commands rather than direct Git commands, and during final publication validation the [source-control publication sequence](../source-control.md#publish-a-branch) places an empty `@` above the bookmarked final change so Git `HEAD` names the commit checked by `0 check commit` and `0 check history`.

The grouped `0 check` command executes `fmt`, `lint`, `type`, `policy`, `doc`, `ztest`, `ptest`, `btest`, and `test` without aborting on the first failure, and then runs `commit` and `history` last (unless `-s` / `--skip-commit` is passed) before reporting overall `check` status. `--skip-commit` cannot be combined with a subcommand.

## Python tests

The command-plane and project test suites use function-based pytest modules in `zero/` and `proj/`. `pytest.ini` selects both directories and reports every test duration. Use `0 check ztest` for `zero/` tests and `0 check ptest` for `proj/` tests. The full `0 check` cycle runs both suites.

Run Python checks in the repository package environment, which supplies pytest and pytest-xdist:

```sh
nix shell .#default -c 0 check ztest -k telemetry
nix shell .#default -c 0 check ztest --nodeid test_telemetry.py::test_process_io_requires_both_valid_counters
nix shell .#default -c 0 check ptest -k goal_lifecycle
```

Both test commands accept `-k` keyword expressions, `-m` marker expressions, repeated `--nodeid FILE::TEST` selectors, and `--parallel` or `--no-parallel`. A node ID path is relative to that suite's directory. Unfiltered runs use pytest-xdist with `-n auto` by default; filtered runs execute in the main process unless `--parallel` is given. `--no-parallel` keeps an unfiltered suite in the main process. Use `--help` for the exact command options.

## Watch mode

`0 watch` (`0 w`) and `0 --watch` (`0 -w`, which cannot be combined with a subcommand) monitor changes through Watchman. Changes to `.rs`, `.py`, `.md`, `.json`, `.nix`, or `.toml` files, plus `Cargo.toml` and `Cargo.lock`, trigger checks while other file types do not start a parent watch iteration.

Python changes run Ruff formatting and lint checks, plus `0 check ztest` (`zero/`) or `0 check ptest` (`proj/`). Rust changes (`.rs`, `Cargo.toml`, and `Cargo.lock`) run Rust formatting and the Rust build and test pipeline; `Cargo.toml` changes also run `dprint` as a `.toml` file. Markdown, JSON, and TOML changes run `dprint`, and Nix changes run `nixfmt` across non-ignored repository `.nix` files when any exist. Independent checks run concurrently; use `0 check --skip-commit` for full non-watch validation.

When started or restarted, the `boot_shell` core-test watcher separately watches `.penta` files under `core/` and emits per-test `PASS` / `FAIL` lines. Those child-watch results are not included in the parent `watch-iteration` status, and core `.penta` changes trigger the child watcher rather than a parent iteration.

## Repository policy

`zero/repo_policy.py` scans Git-tracked files and untracked files not excluded by Git's standard ignore rules, using automated Git interoperability under the [source-control document](../source-control.md) after `jj status` snapshots and exports the working copy while contributors continue using `jj` directly.

Using Git's inventory prevents `.ignore` and `.rgignore` from hiding prohibited paths, excludes the `.git` tree, and includes tracked and untracked symbolic links. The scan rejects the file basenames `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, and `GEMINI.md`, plus any path containing an `.agents`, `.claude`, `.codex`, or `.gemini` component. These broad path rules cover nested skill, agent, rule, and command surfaces without banning generic names such as `SKILL.md`, `skills`, `agents`, or `rules` elsewhere. Harnesses can be configured with arbitrary alternate instruction filenames; this fixed-name repository scan does not attempt to infer those operator-specific names.

## Command boundary

`proj/` is not owned by the command plane and is mounted on the root CLI as `0 proj` (`0 p`). The [project workflow](../proj/README.md) owns and documents `proj/`'s [implementation boundaries](../proj/README.md#implementation-boundaries), [goal activation](../proj/README.md#goal-activation) commands (`0 proj goal text NAME [GOAL]` and `0 proj goal copy NAME [GOAL]`), and [`0 proj` command surface](../proj/README.md#0-proj-command-surface); `zero/` delegates command parsing and presentation for `0 proj` without duplicating or narrowing `proj/`'s contracts.
