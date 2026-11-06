"""Run the models in order against a DuckDB file and run the data quality checks. Re-runnable."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).parent
TERM_END = "2026-07-17 23:59:59"

CHECKS = {
    "stg grain: one row per response_id":
        "select count(*) from (select response_id from stg_responses group by 1 having count(*) > 1)",
    "history: no overlapping validity windows per pupil and topic":
        """select count(*) from pupil_topic_score_history a join pupil_topic_score_history b
           on a.pupil_id = b.pupil_id and a.topic = b.topic and a.changed_by_response < b.changed_by_response
           and a.valid_from < b.valid_to and b.valid_from < a.valid_to""",
    "history: exactly one current row per pupil and topic":
        """select count(*) from (select pupil_id, topic from pupil_topic_score_history
           where valid_to = timestamp '9999-12-31' group by 1, 2 having count(*) <> 1)""",
    "history: score within [0, 1]":
        "select count(*) from pupil_topic_score_history where score < 0 or score > 1",
    "history: known_from never before valid_from":
        "select count(*) from pupil_topic_score_history where known_from < valid_from",
}


def build(db: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db)
    for sql in sorted((HERE / "models").glob("*.sql")):
        con.execute(sql.read_text().replace("$term_end", f"timestamp '{TERM_END}'"))
    return con


def fingerprint(con) -> str:
    """Order-independent hash of every output table: the same input must give the same answer every run."""
    h = hashlib.sha256()
    for t in ["stg_responses", "quarantine_responses", "pupil_topic_score_history", "term_end_scores"]:
        rows = con.execute(f"select * from {t} order by all").fetchall()
        h.update(f"{t}:{rows}".encode())
    return h.hexdigest()


def check(con) -> dict:
    return {name: con.execute(sql).fetchone()[0] for name, sql in CHECKS.items()}


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "atom_demo.duckdb"
    con = build(db)
    print("fingerprint", fingerprint(con)[:16])
    for k, v in check(con).items():
        print(("PASS " if v == 0 else "FAIL ") + k, v)
    print(con.execute("""select count(*) filter (where changed_after_term) as changed,
                         count(*) as pupil_topics from term_end_scores""").fetchone())
    print("quarantined", con.execute("select count(*) from quarantine_responses").fetchone()[0],
          "| duplicates collapsed", con.execute("select (select count(*) from raw_responses) - "
          "(select count(*) from stg_responses) - (select count(*) from quarantine_responses)").fetchone()[0])
