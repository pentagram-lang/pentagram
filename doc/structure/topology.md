# Topology

Documentation is a tree with links running through it. Directories contain files, files contain sections, and sections contain subsections; each contained unit is a node in one recursive hierarchy. Order gives sibling nodes a default reading path. Links create paths across branches.

[Structure](README.md) calls the design of that tree and its links **topology**. A useful topology answers three questions without a repository-wide search:

- Where am I?
- Where does this subject belong?
- Where should I go next?

Pentagram's aims govern all three answers. Ergonomic topology keeps useful paths close to the work. Deterministic topology gives each subject a predictable home and makes relationships explicit. Efficient topology keeps reading and editing local, avoids competing copies, and gives tools regular structure to follow. The same properties expose system boundaries and keep documentation connected to implementation and evidence.

## Build the hierarchy around the subject

Every level of the hierarchy must express a real relationship. A directory gathers one coherent subject. A file owns a coherent part of that subject. A section develops one part of its file. Children narrow or develop their parent; siblings divide the parent along distinctions readers can understand.

Order siblings along the normal path of thought. Put prerequisites before dependent material, common paths before exceptional branches, and governing material before dependent detail. Links can provide other routes without weakening the hierarchy's default path.

## Keep every surface local

Every documentation surface needs a clear owning system. Put the surface in the same folder as that owner. The folder must match the owner's conceptual and change boundary; physical proximity without shared ownership is not locality.

Use the smallest system that completely owns the subject. Move documentation upward only when the broader system owns the subject, not merely because several components use it. Shared use does not imply shared ownership.

A shared contract belongs with the interface or system that defines it; every consumer links to that owner. If no system clearly owns the contract, repair the design boundary before choosing a documentation location. Putting the contract at the repository root would hide the design problem rather than solve it.

Keep documentation with its owner. Reuse does not change ownership, and consumers do not need their own copies.

## Build surfaces from indexes, leaves, and companions

Once the owner is clear, the local surface has one entry point: `README.md`. The README identifies the subject, establishes the context needed to use the surface, and leads to more detailed documents when they exist.

Make the introduction before the first H2 expressive rather than enumerative. Use connected prose to explain the subject, frame why it matters, and establish the relationships readers need before choosing a path. Do not summarize every child in the introduction; the child sections below own the inventory.

A README with child documents is an index. An index owns orientation and navigation; it does not absorb content owned by its descendants. Give every child document an H2 heading, one direct link, and a short description of the child's job. These sections form the inventory, and the headings and child documents must correspond one to one.

A leaf owns the detailed content for its subject and does not organize child documents. Every leaf is owned by exactly one index, which supplies the leaf's parent context and primary route. Other documents may link to the leaf, but cross-links do not create ownership.

Index and leaf are exclusive roles: no document should attempt to be both. When a surface has child documents, its index provides the ergonomic and efficient mechanism for traversal and exploration. Move detailed content into leaves instead of mixing that content into the index.

A small surface can remain entirely in its README. Add a leaf when a subject needs independent depth, a distinct path to use, or a stable target. Length alone is not a reason to split a document, and avoiding another file is not a reason to combine unrelated jobs.

A structured format can define a **companion** whose exact path binds it to another repository file. A companion supports its owner without becoming another authority or ordinary navigation child. The format must define discovery, structure, and validation precisely; otherwise make the content a leaf with an index entry. For example, [test: store tests beside their subject](../quality/test.md#store-tests-beside-their-subject) binds `guide.test.md` to `guide.md` and `parser.rs.test.md` to `parser.rs` when each pair occupies the same directory.

## Give each document one clear job

A document needs one centre of gravity. Different jobs create different reading paths:

- orientation locates a subject and opens the relevant paths;
- explanation builds a model or preserves rationale;
- a procedure guides a task, recovery, or other transformation;
- reference fixes exact boundaries; and
- change documentation carries understanding across versions.

The jobs are design tools, not a mandatory taxonomy or rigid templates. Combine jobs when they serve one coherent use. Separate jobs when they need different entry conditions, reading orders, depths, or maintenance boundaries.

Layer depth without splitting the truth. An entry document provides enough context to choose the next path. A deeper document develops that context without contradicting or quietly replacing what the reader has already learned.

## Build paths with links

Hierarchy gives every document a home. Links make the hierarchy usable for more than one path.

- Link upward to broader context.
- Link downward to deeper detail.
- Link sideways to related concepts, procedures, implementation, and evidence.

Target the smallest section that satisfies the relationship. The surrounding sentence states whether the target supplies navigation, authority, prerequisite knowledge, rationale, or evidence. The [house style: write useful links](../style/house.md#write-useful-links) section governs link wording and within-document consistency.

A link extends local meaning; it does not replace local meaning. Keep a condition, warning, consequence, default, or result at the point where readers need it. Repeat the minimum context required for correct use, then link to the governing source for depth. Write the repetition as an application of that source, not as a second definition.

## Compose from one authority

Reference, generation, and projection let several documents use one governing source:

- **Reference** links a dependent document to the source.
- **Generation** derives regular facts or structures from the source.
- **Projection** selects and reshapes the source for another path or level of abstraction.

Reference must leave enough context at the point of use. Generation must name a canonical input and use a reproducible transformation. Projection must preserve provenance, scope, and status. None of the three mechanisms creates a second authority.

Purposeful repetition can make a document locally sufficient. Semantic duplication cannot: multiple apparently governing versions will eventually compete or drift.

## Change the whole topology

A path or anchor can be an interface for readers, tools, and external documents. Moving, renaming, splitting, merging, generating, or removing one node can therefore affect the whole graph around it.

Before the change, inventory the node's parent, children, sibling order, inbound links, outbound links, anchors, generated views, and external consumers. During the change, update entry points and dependent links. Preserve an explicit redirect or mapping when compatibility requires a stable path, and make the former source unambiguously obsolete.

After the change, follow the paths in both directions. Readers and authors must still reach the content from its broader context, and the content must still reach the right dependencies. Validate tools, tests, diagnostics, and generated views that treat paths or anchors as structured inputs.

## Recognize topology failures

Topology has failed when its shape creates work or uncertainty instead of removing them:

- **Central warehouse:** documentation lives far from the systems and work it governs.
- **Taxonomy without a path:** the hierarchy classifies information but does not lead through a real decision or task.
- **One giant node:** unrelated jobs and depths force every reader through the same surface.
- **Meaning at a distance:** essential conditions or consequences are scattered across a chain of links.
- **Competing copies:** several nodes appear to govern the same content.
- **Orphan node:** content has no useful route from its local entry point or back to broader context.
- **Incidental locality:** content is physically nearby but belongs to a different conceptual or change boundary.
- **Rigid symmetry:** directories or files mirror code or a template without helping readers.
- **Unstable path:** structural changes break links, anchors, tools, or compatibility without an explicit transition.

Recurring difficulty placing or connecting documentation can expose a poorly defined system boundary. Inspect the governed design before adding hierarchy or links to hide the confusion.
