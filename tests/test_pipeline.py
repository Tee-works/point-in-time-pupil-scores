import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import generate  # noqa: E402
import run  # noqa: E402


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("d") / "t.duckdb")
    generate.generate(path, seed=11, pupils=60)
    return path


@pytest.fixture(scope="module")
def con(db):
    return run.build(db)


def test_checks_pass(con):
    assert all(v == 0 for v in run.check(con).values()), run.check(con)


def test_rebuild_is_idempotent(con):
    first = run.fingerprint(con)
    for sql in sorted((run.HERE / "models").glob("*.sql")):      # rebuild in place, twice
        con.execute(sql.read_text().replace("$term_end", f"timestamp '{run.TERM_END}'"))
    assert run.fingerprint(con) == first


def test_duplicates_collapse_and_skew_is_quarantined(con):
    raw = con.execute("select count(*), count(distinct response_id) from raw_responses").fetchone()
    stg = con.execute("select count(*) from stg_responses").fetchone()[0]
    q = con.execute("select count(*) from quarantine_responses").fetchone()[0]
    assert q > 0
    assert stg + q >= raw[1] and stg <= raw[1]


def test_point_in_time_lookup_matches_history(con):
    # reconstruct one pupil's score at term end straight from responses and compare with the history table
    pupil, topic = con.execute("select pupil_id, topic from term_end_scores where restated_score is not null limit 1").fetchone()
    direct = con.execute("""
        select round(avg(c), 4) from (
          select is_correct::int c from stg_responses
          where pupil_id = ? and topic = ? and answered_at <= timestamp '2026-07-17 23:59:59'
          order by answered_at desc, response_id desc limit 20)""", [pupil, topic]).fetchone()[0]
    hist = con.execute("select restated_score from term_end_scores where pupil_id = ? and topic = ?", [pupil, topic]).fetchone()[0]
    assert direct == hist


def test_planted_overlap_is_caught(con):
    con.execute("create or replace table _bak as select * from pupil_topic_score_history")
    con.execute("""insert into pupil_topic_score_history
                   select pupil_id, topic, 'zzz', score, answers_in_window, valid_from, valid_to, known_from
                   from pupil_topic_score_history limit 1""")
    assert run.check(con)["history: no overlapping validity windows per pupil and topic"] > 0
    con.execute("create or replace table pupil_topic_score_history as select * from _bak")
