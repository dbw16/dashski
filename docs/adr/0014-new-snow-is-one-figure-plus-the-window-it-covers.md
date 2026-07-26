# New snowfall is one figure plus the window it covers, not a column per window

> **Superseded by ADR 0015** — snow reports were removed from Dashski entirely;
> this records why the shape was what it was while they existed.

`SnowReport` originally had a column per snowfall window — `new_snow_24h_cm`
and `new_snow_7d_cm` — and the widget had a table column for each. That assumed
the windows a field publishes are fixed. They aren't: The Remarkables published
"Last 7 Days" in mid-July 2026 and, a fortnight later, had swapped that tile for
"Last 48 Hours" with no 7-day figure anywhere on the page. Under the old shape a
swap like that empties both columns and the widget silently shows nothing, which
is exactly what happened.

So a snow report now carries `new_snow_cm` with `new_snow_window_hours` beside
it (24, 48, 168), and the widget renders one "New snow cm" column labelled with
whichever window the figure covers — `5.0 / 48h`. A new window a field starts
publishing costs one entry in the source's tile map and no schema or template
change. Where several windows are on the page at once, the source takes the
shortest: the freshest thing the field is saying about new snow.

The cost is that a field publishing two windows only gets its shortest one on
the dashboard. That's the right trade for a touring tool — recent snow is what
decides a day out, and a 7-day total that nobody reads isn't worth a permanent
column on a phone-width screen.

The calculated 24h figure (ADR 0008) rides on top of this and still wins the
column when it can be derived, but is now gated on both reports carrying a
168h window. The estimate works by subtracting consecutive totals, and what
that subtraction removes is the day falling out the far end of the window — a
week old and usually zero. On a 48h window the day falling out is the day
before yesterday, so the same arithmetic would routinely cancel real snow
against real snow.
