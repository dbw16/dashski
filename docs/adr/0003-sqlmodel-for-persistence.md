# SQLModel over stdlib sqlite3

Readings are persisted to SQLite via SQLModel (Pydantic + SQLAlchemy) rather
than hand-written stdlib `sqlite3`. Stdlib would have kept dependencies minimal,
but SQLModel gives typed table models that double as Pydantic models for the
FastAPI layer, and removes hand-written row↔dataclass mapping under strict
type checking.
