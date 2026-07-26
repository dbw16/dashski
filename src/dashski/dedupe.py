"""Cleanup for rows stored before dedupe existed (ADR 0016).

`run_source` now skips an identical refetch, but a DB that ran without it holds
one advisory row per fetch — off-season, dozens a day saying the same thing,
each one a Snapshot the slider has to be dragged through. This deletes the rows
that a dedupe-aware fetch would never have written, keeping the earliest of each
identical set so the Snapshot that first showed the advisory survives.

Reports by default; pass --apply to delete:

    python -m dashski.dedupe [--apply]
"""

import argparse
import sqlite3

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from dashski import db
from dashski.models import AvalancheAdvisory


def redundant_advisories(session: Session) -> list[AvalancheAdvisory]:
    """Advisories whose content was already stored by an earlier fetch.

    Keyed on `content_key()` alone, which already carries source, region and
    issued_at — the same comparison `_already_stored` makes at write time.
    """
    rows = session.exec(
        select(AvalancheAdvisory).order_by(
            col(AvalancheAdvisory.fetched_at), col(AvalancheAdvisory.id)
        )
    ).all()
    seen: set[object] = set()
    redundant: list[AvalancheAdvisory] = []
    for row in rows:
        key = row.content_key()
        if key in seen:
            redundant.append(row)
        else:
            seen.add(key)
    return redundant


def delete_advisories(session: Session, rows: list[AvalancheAdvisory]) -> None:
    """Delete rows and their problems — the relationship has no cascade."""
    for row in rows:
        for problem in row.problems:
            session.delete(problem)
        session.delete(row)
    session.commit()


def backup(engine: Engine) -> str:
    """Copy the DB file beside itself and return the path — the only undo there is.

    Uses SQLite's backup API rather than `cp` so the copy is consistent even if
    the scheduler writes mid-run; the app keeps serving throughout.
    """
    path = engine.url.database
    if path is None:
        raise RuntimeError("engine has no database file to back up")
    target = f"{path}.bak"
    source_conn, target_conn = sqlite3.connect(path), sqlite3.connect(target)
    try:
        with target_conn:
            source_conn.backup(target_conn)
    finally:
        source_conn.close()
        target_conn.close()
    return target


def _report(session: Session) -> str:
    advisories = session.exec(select(AvalancheAdvisory)).all()
    snapshots = {row.fetched_at for row in advisories}
    return f"{len(advisories)} advisories, {len(snapshots)} snapshots"


def main() -> None:
    parser = argparse.ArgumentParser(description="Collapse duplicate advisory rows (ADR 0016).")
    parser.add_argument("--apply", action="store_true", help="delete the rows (default: report)")
    args = parser.parse_args()

    engine = db.get_engine()
    with Session(engine) as session:
        print(f"before: {_report(session)}")
        rows = redundant_advisories(session)
        print(f"redundant: {len(rows)} advisories")
        if not args.apply:
            print("dry run — pass --apply to delete")
            return
        print(f"backup: {backup(engine)}")
        delete_advisories(session, rows)
        print(f"after: {_report(session)}")


if __name__ == "__main__":
    main()
