# Command plane

The command plane provides the repository's operational commands for formatting, checks, tests, agent launch, the boot shell, watch mode, and project-control access.

## Identity and ownership

The command-plane Python package is `zero/`. Its package entrypoint is `zero/__main__.py`. The Nix profile exposes the entrypoint as both `zero` and `0`; both names execute the same command plane. `0` is the working command name used in repository documentation and automation.

The project-control subsystem is not owned by the command plane. Its implementation lives in `proj/`, and the command plane invokes it through the `0 proj` command group.

`zero/__main__.py` is the command-plane composition root. The configured-agent API remains `zero.agent.launch`; `zero/agent/dispatch.py` selects a configured provider, and `zero/agent/codex.py`, `claude.py`, and `agy.py` own provider-specific preflight and launch behaviour. Shared agent filesystem and JSON helpers live in `zero/agent/common.py`.

The project command group owns the operational interface for the project’s active goal. Goal text is read from the project database rather than copied through an agent prompt. Agents that can activate a goal use the exact output of `0 proj goal text NAME`. When an agent cannot activate a goal, it asks the operator to run the exact command `0 proj goal copy NAME`; the project service returns the canonical text, and the CLI emits it through OSC 52 clipboard control characters.

The former `pt` command is not installed or accepted as an alias.

## Launcher contract

The installed wrapper searches from the current directory toward the filesystem root for a repository containing `zero/__main__.py`. It changes to that repository root and runs the Python package entrypoint. This keeps commands independent of the caller's working directory while making the repository boundary explicit.

The AGY launchers (`0 a flash`, `0 a argon`, and `0 a carbon`) always create a temporary AGY custom-agent adapter inside their runtime directory at `.agents/agents/pentagram/agent.md`. Its front matter uses the checked-in tool list in `zero/agent/agy.py`, and its prompt contains `sys.md`. Because AGY custom agents default to a small read-only tool set, the adapter explicitly enables the file, shell, web, image, scheduling, subagent, workflow, swarm, and question tools. Before creating that adapter, each launcher runs a mandatory filesystem-only AGY preflight. It scans operator-home `~/.gemini/config/skills/` and paths registered by `~/.gemini/config/skills.json`, including inherited configurations, and blocks any discovered standalone skill because AGY has no persistent all-skills disable setting. It scans operator-home `~/.gemini/AGENTS.md`, `~/.gemini/GEMINI.md`, `~/AGENTS.md`, `~/GEMINI.md`, `~/.gemini/rules/`, `~/.gemini/config/rules/`, `~/.agents/rules/`, and paths registered by `~/.gemini/config/rules.json`, including inherited configurations, and blocks any discovered rule file because AGY has no persistent setting to disable AGENTS.md/rules files. It scans `~/.gemini/config/plugins/` and paths registered by `~/.gemini/config/plugins.json`, including inherited configurations, reads each `plugin.json`, and requires each effectively installed plugin to be disabled by the `plugins` map in `~/.gemini/config/config.json` or by a manifest-level `disabled: true` fallback. It does not run `agy plugin list`. It scans `~/.gemini/config/mcp_config.json` and blocks every configured standalone MCP server because AGY has no reliable persistent all-MCP disable setting; MCP servers packaged by disabled plugins are covered by the plugin check. The preflight does not inspect launcher arguments or harness environment variables, and it does not check AGY memory because AGY has no operator-facing memory subsystem. Set `PENTAGRAM_AGY_TOOLSET` to enable a separate `agy --print --output-format stream-json` preflight against the generated `pentagram` adapter before starting the session; the launcher then fails if AGY cannot initialize `pentagram` and resolve every tool in `AGY_AGENT_TOOLS`. The variable never changes the adapter's tool list. `--dangerously-skip-permissions` removes approval prompts for the launched session; it does not override the repository contract or authorize external publication, unrelated scope, or out-of-scope destructive operations.

The Codex launchers run a mandatory filesystem-only ambient-authority preflight before starting Codex. It reads the Codex home and project configuration files and the home-level non-plugin Codex skill files; it does not start Codex or contact a network service. Codex represents a disabled feature either with `false` or by omitting the feature key, so both forms pass the preflight. Every configured top-level MCP server must be disabled. Every home-level `~/.codex/skills/**/SKILL.md` must be disabled through the `/skills` menu. Any file under home-level `~/.codex/memories` blocks launch because Codex has no persistent setting that disables those files; remove or rename the file. Codex execution-policy `.rules` files are a separate control surface and are not checked as memory files. Plugin cache contents and plugin-provided MCP settings are excluded because `features.plugins` is disabled. The preflight does not inspect launcher arguments or harness environment controls; those are forwarded unchanged to Codex. Feature findings provide the persistent `codex features disable memories` or `codex features disable plugins` command; MCP findings identify their persistent TOML entries. Any failure stops the launcher before the Codex process is replaced.

The Codex preflight rejects a non-empty `profile` setting in any loaded Codex config; remove that setting to proceed.

The Claude launchers run the same kind of filesystem-only persistent-state preflight. It reads Claude settings, `~/.claude.json`, the project `.mcp.json`, and the home-level standalone skill and memory files; it does not start Claude or inspect launcher arguments or harness environment controls. Every home-level `~/.claude/skills/**/SKILL.md` must be removed or renamed because Claude has no persistent setting to disable standalone skills. Any home-level `~/CLAUDE.md`, `~/.claude/CLAUDE.md`, or `~/.claude/rules/**/*.md` memory file also blocks launch because Claude has no persistent setting to disable those files. Auto-memory must be persistently disabled with the `/memory` setting, every configured plugin must be disabled through `/plugin`, and every MCP in the hardcoded Claude MCP set or persisted MCP configuration must be disabled through `/mcp` in the corresponding persisted disabled list. Set `PENTAGRAM_CLAUDE_MCP_SET` to enable a zero-specific `claude mcp list` inventory check; the launcher then fails if the live inventory differs from the hardcoded set. Plugin-provided skills and MCP settings are excluded when all configured plugins are disabled. Any failure stops the launcher before the Claude process is replaced.

Standalone skill, rule, and memory-file scans use the operator-home paths listed above; AGY also scans skill and rule paths registered in its configuration, which may resolve outside the home directory. Codex and Claude read the project configuration files listed above, and Claude also reads its fixed managed settings paths. The launchers do not discover arbitrary project, repository, or ancestor instruction files. Custom AGY agents do not mount bundled skills under `~/.gemini/antigravity-cli/builtin/skills/` in ordinary turns, though explicit slash commands such as `/swarm` and `/run-workflow` still expand built-in skill instructions when invoked.

## Checks

The standalone `0 check doc` command runs the heading, link, index, and test-companion checks in the [lint document](../doc/quality/lint.md) and reports its own timing. `0 check fmt` runs every repository formatter check, including dprint for Markdown. `0 check lint` runs Ruff and Clippy; Ruff enforces its configured rules across first-party Python implementation and test modules. `0 check type` enforces ty across those modules. The standalone `0 check commit` command validates the exported Git `HEAD` message's line lengths and reports its own timing. The complete `0 check` cycle runs formatting, lint, type checking, repository policy, documentation lint, both Python test suites, Rust bootstrap tests, and core language tests. It also validates commit messages and history unless `--skip-commit` is supplied. Repository policy scans Git-tracked files and untracked files that are not excluded by Git's standard ignore rules.

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

`0 watch` and `0 --watch` monitor changes through Watchman. Changes to `.rs`, `.py`, `.md`, `.json`, `.nix`, or `.toml` files trigger checks; `Cargo.toml` and `Cargo.lock` changes also trigger checks. Other file types do not start a parent watch iteration. Python changes run Ruff formatting and lint checks; a change under `zero/` runs its Python suite, and a change under `proj/` runs its suite. Rust changes run formatting and the build/test pipeline. When started or restarted, the boot-shell core-test watcher separately watches `.penta` files under `core/` and emits per-test `PASS`/`FAIL` lines. Those child-watch results are not included in the parent `watch-iteration` status, and core `.penta` changes trigger the child watcher rather than a parent iteration. Markdown, JSON, and TOML changes run dprint; Nix changes run nixfmt. Independent checks run concurrently. Watch mode runs checks for changed file categories; use the complete `0 check --skip-commit` cycle for full validation.

## Repository policy

These Git reads are automated interoperability mechanisms under the [source-control document](../source-control.md); contributors still use Jujutsu directly. Run `jj status` before a check so Jujutsu has snapshotted and exported the current working copy. During final validation, the source-control publication sequence places an empty `@` above the bookmarked final change so Git `HEAD` names the commit being checked.

Using Git's inventory prevents `.ignore` and `.rgignore` from hiding prohibited paths, excludes the `.git` tree, and includes tracked and untracked symbolic links. The scan rejects the file basenames `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, and `GEMINI.md`, plus any path containing an `.agents`, `.claude`, `.codex`, or `.gemini` component. These broad path rules cover nested skill, agent, rule, and command surfaces without banning generic names such as `SKILL.md`, `skills`, `agents`, or `rules` elsewhere. Harnesses can be configured with arbitrary alternate instruction filenames; this fixed-name repository scan does not attempt to infer those operator-specific names.

## History and changelog

`0 check history` runs Cocogitto against exported Git history. `0 check changelog` runs git-cliff through the Git interoperability surface. Their implementations and test fixtures may invoke Git directly; contributors invoke the `0` commands rather than their internal Git commands.

## Command boundary

The command plane owns operational orchestration and delegates domain behaviour to the subsystem that owns it. It does not duplicate project schema or lifecycle rules. `proj/storage.py` owns the SQLite schema and persisted-state validation; `proj/project.py` owns project operations and cross-entity lifecycle transitions; `proj/cli.py` exposes them through the `0 proj` command group and owns command parsing and presentation.

The [project workflow](../proj/README.md#0-proj-command-surface) documents `0 proj` command groups and their domain semantics; each command's `--help` output lists its available options.
