# Lint

[Quality](README.md) uses lint for mechanical rules that can be decided reliably from repository state. `0 check doc` runs the documentation rules independently and reports its own timing. `0 check commit` runs commit-message line-length validation independently and reports its own timing. The complete `0 check` cycle includes both steps when commit validation is enabled. Lint does not judge meaning, readability, or usefulness.

## Markdown formatting

Markdown must match the formatter configured in [`dprint.json`](../../dprint.json). Prose uses soft wrapping rather than manual line breaks.

The Markdown rules below read current files through the colocated Git inventory. This is an automated interoperability mechanism allowed by the [source-control model](../../source-control.md#working-copy), not a contributor command surface. Run `jj status` before the check so Jujutsu has snapshotted and exported the current working copy. The inventory includes tracked files and non-ignored untracked files that exist in the working tree. Deleted and ignored files are absent.

## Heading identifiers

Every heading identifier must be unique within its Markdown file. Identifiers use lower-case visible text. They retain letters, numbers, hyphens, and underscores, discard other characters, and replace each whitespace character with a hyphen. Two headings that produce the same identifier fail.

## Local links

Local Markdown links must resolve to one inventoried repository file with exact path case. A fragment must resolve to one heading in that file. Paths outside the repository, directory targets, query strings, missing files, and missing headings fail.

Links with a URI scheme or a destination beginning with `//` are external and are not checked. Links in code and raw HTML are also outside this rule.

## Link text

Within one Markdown document, local links to the same file and fragment must use the same visible text. Links to different fragments are different targets. [House style: write useful links](../style/house.md#write-useful-links) defines the wording rule.

## Documentation indexes

Every directory that contains a Markdown file other than a test companion must contain `README.md`.

When a README has direct children, each child must have exactly one H2 section that links to it, and every H2 must represent exactly one child. Direct children are other non-companion Markdown files beside the README and READMEs in immediate child directories. [Topology: build surfaces from indexes, leaves, and companions](../structure/topology.md#build-surfaces-from-indexes-leaves-and-companions) defines the required relationship.

## Test companions

A file ending in `.test.md` must identify exactly one inventoried subject beside it. Removing `.test.md` gives the base path. The possible subjects are the base path and the base path with `.md` appended; a base path that already ends in `.md` cannot identify itself. `guide.test.md` therefore identifies `guide.md`, while `parser.rs.test.md` can identify `parser.rs`. Missing, ambiguous, and nested companions fail.

The companion must follow the headings, labels, order, and required content defined by [test: write the test contract](test.md#write-the-test-contract). The rule checks the form, not whether the tasks or assertions are useful or correct.

## Conventional Commits

Final commit messages must follow Conventional Commit grammar. [Commit message](../structure/commit-message.md) defines the accepted subject forms and types.

Temporary `wip:` change descriptions are not final commit messages and must be squashed or replaced before complete validation and publication.

## Commit message line length

A complete commit subject must not exceed 72 characters. Body prose must wrap at 72 characters. Only a line made entirely of one exact literal may exceed the limit. [Commit message](../structure/commit-message.md) defines the recognized literal forms and complete format.

The commit check reads the current exported Git `HEAD` message. It does not rewrite or recheck historical messages. The [source-control publication sequence](../../source-control.md#publish-a-branch) places an empty `@` above the final bookmarked change and runs `jj status` before validation so this check reads the intended commit.
