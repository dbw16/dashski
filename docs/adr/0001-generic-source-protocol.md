# One generic Source protocol, kind-typed readings

All sources (forecast, observation, snow report) implement a single generic
`Source` protocol — `fetch() -> RawPayload`, `parse(raw) -> readings` — so the
scheduler, error handling, raw-payload storage, and staleness tracking are
written once, not three times. The alternative (one interface per kind) was
rejected because the orchestration is identical across kinds; only the parsed
output differs, so typing is preserved by having `parse()` return
kind-specific reading models rather than a lossy shared shape.
