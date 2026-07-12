# BeautifulSoup for HTML scraping, promoted to a main dependency

The first real snow report source (The Remarkables) scrapes plain rendered
HTML — no JSON API is available. `beautifulsoup4` was already a dev-only
dependency (used to inspect our own htmx output in tests); it's now promoted
to a main dependency rather than hand-writing regex/stdlib `html.parser`
parsing, consistent with this project's preference for established libraries
over minimal-dependency alternatives (see ADR 0002, ADR 0003).
