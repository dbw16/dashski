# Dashski is avalanche advisories only; snow reports removed

Dashski started as two dashboards in one: ski field snow reports beside
avalanche advisories. The advisory widget turned out to carry the whole
decision a tourer makes — danger rating per elevation band, the problems
behind it, the aspects to avoid — while the snow report table was a row of
numbers a field publishes for its lift-riding customers, on its own schedule,
in whatever window it felt like that fortnight (ADR 0014). It was screen space
that didn't change anyone's plan. So the app is now avalanche-only: the
`SnowReport` table, the Remarkables scraper, the snow report widget and its
24h-from-7-day-trend estimate (ADR 0008) are gone, along with ADR 0006's scope
carve-out.

The generic framework stays kind-agnostic even though only one kind is left:
`SourceKind`, the `Source` protocol's `parse() -> Sequence[Reading]`, and the
per-kind table split (ADR 0004) all still hold. Collapsing them into
advisory-specific code would be a day's work to undo the first time a second
kind lands — weather observations for a region are the obvious candidate — and
the indirection costs one enum with one member. `Reading` is a type alias for
`AvalancheAdvisory` rather than a union, and becomes a union again if that
happens.

The snow report tables are dropped rather than left in place for later: this
is a work-in-progress app with no migrations, so the DB gets nuked and
recreated, and the deleted code is in git if the scope ever widens back.
