# One generic Source protocol, kind-typed readings

All sources (snow report, avalanche advisory) implement a single generic
`Source` protocol — `fetch() -> RawPayload`, `parse(raw) -> readings` — so the
scheduler, error handling, raw-payload storage, and staleness tracking are
written once, not once per kind. The alternative (one interface per kind) was
rejected because the orchestration is identical across kinds; only the parsed
output differs, so typing is preserved by having `parse()` return
kind-specific reading models rather than a lossy shared shape.
