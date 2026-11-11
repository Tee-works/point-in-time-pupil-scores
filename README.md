# Point-in-time pupil scores

A small, honest demo by Iyanujesu Taiwo Akinyefa. It runs on **synthetic data only**, with no real pupils.

Pupil assessment data has four hard parts: the right grain, point-in-time correctness ("reconstruct a pupil's score as it stood last term"), builds that give the same answer every time, and catching data quality problems before they reach a teacher. This repo works on all four in about 150 lines of SQL and Python.

## What it does

`generate.py` creates 33,284 question responses for 300 pupils across 5 topics in the summer term, with the faults a real feed has:

- **Retried deliveries:** 652 responses arrive twice.
- **Offline devices:** about 4% of answers reach the warehouse 2 to 12 days late, some after term has ended.
- **Clock skew:** 12 answers carry a timestamp in the future.

The models run in order and can be re-run:

| Model | Grain | Point |
|---|---|---|
| `01_stg_responses` | one row per `response_id` | Retries collapse to the first load, with a deterministic tie-break. Clock-skewed rows are quarantined with a reason, not dropped. |
| `02_pupil_topic_score_history` | one row per pupil, topic and score change | A type-2 history kept on **two clocks**. `valid_from`/`valid_to` say when a score was true in the world (answer time). `known_from` says when the warehouse could first have shown it (load time). |
| `03_term_end_scores` | one row per pupil and topic | "What was the score at the end of term?", answered two ways: **restated** (with everything known now) and **as reported** (what a dashboard could have shown on the last day). |

## What it shows

- The late answers are planted, so the point isn't that they exist. The point is that **the model keeps the 57 of 1,500 term-end pupil-topic scores (3.8%, across 53 pupils) restated after term apart from what teachers originally saw.** The largest move was 0.107, about 11 percentage points.
- So "the score last term" means two different things. A report of what teachers were told needs the *as reported* view. A model trained on true ability needs the *restated* one. Building one table that silently mixes them is how a predicted grade drifts from what a teacher remembers seeing.

## Checks and tests

`python run.py` builds the models and runs five checks:

- one row per response;
- no overlapping validity windows;
- exactly one current row per pupil and topic;
- every score within 0 to 1;
- `known_from` never earlier than `valid_from`.

`pytest` (5 tests) proves the following:

- All checks pass on a fresh dataset.
- **Re-running every model gives a byte-identical result** (an order-independent SHA-256 over all outputs).
- Duplicates collapse and skewed rows are quarantined.
- The point-in-time lookup from the history table matches a direct recomputation from raw answers.
- A planted overlapping window is caught.

```
python generate.py && python run.py && pytest -q
```

## In BigQuery and dbt

The SQL uses window functions and `QUALIFY`, which BigQuery supports. In dbt:

- `stg_responses` would be an incremental model keyed on `response_id`, with a lookback over `loaded_at` wide enough for offline syncs.
- The history would be built from that model, not from a dbt snapshot, because snapshots capture *load* time. Point-in-time correctness here needs *answer* time as well.
- The checks would become dbt tests.
