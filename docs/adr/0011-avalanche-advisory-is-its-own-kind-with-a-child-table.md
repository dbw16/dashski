# Avalanche advisory is its own source kind, with a child problem table

An avalanche advisory predicts *snowpack behaviour*, not weather and not a ski
field's reported conditions, so it gets its own `SourceKind` and its own tables
per ADR 0004 rather than being flattened into an existing reading table.

Unlike every other reading, an advisory is not flat: it carries 0..n avalanche
problems, each with its own character, likelihood, size, trend and aspect set.
Those go in an `AvalancheProblem` child table — the first parent/child pair in
the codebase — instead of a JSON column (ADR 0004 rejects those) or a lossy
comma-joined string. The aspect and likelihood detail is the part that tells you
*which slopes to avoid*, so losing it would leave the widget decorative.

The advisory's other repeated structures do not need normalising: elevation
bands are always exactly three, and `additionalInformation` is always the same
four sections, so both become fixed columns. Band `description` is a pure
function of `rating` across every band observed, so it is derived at render
time rather than stored.

Everything the source publishes as HTML is stripped to plain text at parse time.
The prose uses only `<p>`, `<span style>`, `<strong>`, `<u>` and `<br>` — no
links, images, lists or tables — so nothing meaningful is lost, and it keeps
third-party markup out of the templates entirely rather than relying on a
sanitiser that must never be bypassed.

One source (`nzaa-advisory`) covers every region we track, not one per region.
The API ignores query parameters and returns all regions in a single ~130KB
payload, so a source per region would refetch and re-store the identical
response. The existing one-source-per-ski-field shape does not apply here
because those sources each hit a distinct URL.
