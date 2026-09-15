# Source control

Pentagram uses Jujutsu for source-control work. Contributors use `jj` for every direct repository operation and do not invoke Git directly. Every `jj diff` uses `--git`.

The repository is colocated with a Git backend so automated tooling, GitHub, and Buildkite can continue to exchange ordinary Git commits and branches. Automation may use Git internally; contributors still enter through Jujutsu.

This document defines the shared workflow. The [Pentagram agent system](sys.md) adds agent-specific instructions, and the [commit-message standard](doc/structure/commit-message.md) defines final change descriptions.

## Working copy

Jujutsu represents the working copy as the commit named `@`. Filesystem edits are not staged. At the start of an ordinary `jj` command, Jujutsu automatically snapshots current edits into `@` before running the command.

Run `jj status` before reasoning from repository state, invoking automated tooling, or changing the graph. This snapshots the working copy and makes its state visible.

A change keeps the same change ID when Jujutsu rewrites its commit.

Inspect one change or a cumulative result in Git format:

```sh
jj diff --git --revision CHANGE
jj diff --git --from BASE --to RESULT
```

## Start and resume work

`main@origin` is the locally recorded state of the remote `main` bookmark. Naming it does not contact `origin`, and `jj rebase` does not fetch. Run `jj git fetch --remote origin` before using it to start or resume work.

Start independent work on the latest remote `main`:

```sh
jj status
jj git fetch --remote origin
jj new main@origin --message 'wip: <work boundary>'
```

Resume existing project work by fetching first, inspecting the updated graph, and then rebasing its changes:

```sh
jj status
jj git fetch --remote origin
jj log
jj rebase --branch @ --onto main@origin
```

Here, `--branch @` selects the complete line of changes containing `@` relative to `main@origin`; it does not select only the working-copy change. These commands position the project's development line relative to `main`. The next section governs the distinct changes within that line.

## Maintain distinct changes

A development change holds one coherent work boundary. A project can use several development changes to keep distinct concerns independently editable while producing one final contribution. Those changes usually form a single stack, although Jujutsu can also represent branched or merged development histories.

`@` is the change currently being edited. Continue editing it while new edits belong to the same boundary. Give every non-empty development change a short description of the form `wip: <work boundary>`:

```sh
jj describe CHANGE --message 'wip: <work boundary>'
```

When a new concern begins, snapshot the current change and create a child for the new boundary:

```sh
jj status
jj new --message 'wip: <work boundary>'
```

Return to an existing change with `jj edit CHANGE`. `jj prev --edit` and `jj next --edit` move to an existing relative change; their `--no-edit` forms create a new change at the selected position instead.

Editing an earlier change is a temporary history-maintenance position. Jujutsu rewrites its descendants as the earlier change changes, and bookmarks on those descendants follow the rewritten changes. After finishing the earlier change, return the working copy to the latest intended project tip and inspect the stable result:

```sh
jj edit TIP
jj status
jj log
jj bookmark list --all
```

Do this before continuing task work, running final checks, handing off, or reporting success. An intentional rewrite may leave a local bookmark both ahead of and behind its remote counterpart until the next authorized force push; that relationship is expected when the graph and working-copy tip match the intended result.

A project owns the mutable subgraph created or continued for its work. This ownership defines the boundary within which contributors may rewrite history. A remote bookmark records the last pushed version of a branch; it does not remove the project's revisions from that boundary. Within it, rewriting is encouraged whenever the current history no longer preserves distinct changes.

Use `jj split` to separate concerns that entered one change, `jj squash` to combine changes that represent one concern, and `jj rebase` to correct their order or dependencies without combining them. Changes may also be created, edited, reordered, or abandoned within the owned boundary. Do not rewrite immutable or unrelated work.

The maintained history should leave every non-empty development change with one coherent purpose, an accurate `wip:` description, and the intended relationship to the other changes.

## Recover work

Jujutsu records repository mutations in its operation log. Immediately reverse a mistaken operation with `jj undo`, and reapply an undone operation with `jj redo`.

For an older recovery point, inspect the log without changing the working copy, then restore the selected operation:

```sh
jj --at-op=@ --ignore-working-copy op log
jj op restore OPERATION
```

Recovery cannot restore ignored files, unsnapshotted filesystem state, or external effects. Operation recovery can affect the repository beyond `@`, so do not use it to overwrite unrelated work. Inspect the result with `jj status`, `jj log`, and the relevant `jj diff --git`.

## Publish a branch

A bookmark exposes a finished change as a Git branch. It does not mark or organize intermediate development changes.

Each published branch contains one squashed change on top of its latest parent branch. Development changes preserve useful boundaries while work is in progress; publication deliberately consolidates them rather than exporting them as a multi-commit branch.

Before publication, fetch and rebase again. Use `jj split`, `jj rebase`, and `jj squash` until the branch contribution is one change. Inspect the complete result, run the required tests and reviews, and write the final message required by the [commit-message standard](doc/structure/commit-message.md).

Apply the final message, create an empty working-copy change above it, move the bookmark to the finished change, and validate the exported Git state:

```sh
jj describe CHANGE --stdin < .tmp/commit-message.md
jj new CHANGE
jj bookmark set BOOKMARK --revision @-
jj status
0 check
```

Moving a bookmark is local. Pushing changes the remote repository and therefore requires authority for that external effect. When authorized, push only the named bookmark:

```sh
jj git push --remote origin --bookmark BOOKMARK
```

A branch may be force-pushed when its owned history is rewritten. Each remote update still requires authority for the named bookmark and effect.

For a dependent branch stack, prepare and publish each branch from parent to child. Each branch remains one squashed change relative to its parent.
