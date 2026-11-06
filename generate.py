"""Synthetic question-response events for a small adaptive-learning platform (no real pupil data).

Planted problems, the kind a production feed has:
  - duplicate deliveries: the same response_id arrives twice (retries)
  - late arrivals: answers made offline reach the warehouse days later, some after the term ended
  - clock skew: a few answered_at values are in the future
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import duckdb

TERM_END = datetime(2026, 7, 17, 23, 59, 59)       # summer term end
START = datetime(2026, 4, 20)
TOPICS = ["fractions", "ratio", "algebra", "reading_inference", "vocabulary"]


def generate(path: str, seed: int = 7, pupils: int = 300) -> dict:
    rnd = random.Random(seed)
    rows, n = [], 0
    for p in range(1, pupils + 1):
        ability = {t: rnd.uniform(0.35, 0.9) for t in TOPICS}
        for _ in range(rnd.randint(60, 160)):
            t = rnd.choice(TOPICS)
            answered = START + timedelta(seconds=rnd.randint(0, int((TERM_END - START).total_seconds()) + 20 * 86400))
            loaded = answered + timedelta(minutes=rnd.randint(0, 30))
            if rnd.random() < 0.04:                                # offline device syncs later
                loaded = answered + timedelta(days=rnd.randint(2, 12))
            correct = rnd.random() < min(0.97, ability[t] + 0.002 * n / pupils)
            n += 1
            rows.append((f"r{n:07d}", f"p{p:04d}", t, answered, loaded, correct))
    dupes = rnd.sample(rows, k=len(rows) // 50)                     # 2% retried deliveries
    rows += [(r[0], r[1], r[2], r[3], r[4] + timedelta(seconds=rnd.randint(1, 90)), r[5]) for r in dupes]
    skew = rnd.sample(range(len(rows)), k=12)                        # device clocks in the future
    for i in skew:
        r = rows[i]
        rows[i] = (r[0], r[1], r[2], datetime(2027, 1, 1) + timedelta(hours=i % 50), r[4], r[5])
    rnd.shuffle(rows)
    con = duckdb.connect(path)
    con.execute("create or replace table raw_responses(response_id varchar, pupil_id varchar, topic varchar, "
                "answered_at timestamp, loaded_at timestamp, is_correct boolean)")
    con.executemany("insert into raw_responses values (?,?,?,?,?,?)", rows)
    con.close()
    return {"rows": len(rows), "duplicates": len(dupes), "future_clock": len(skew)}


if __name__ == "__main__":
    print(generate("atom_demo.duckdb"))
