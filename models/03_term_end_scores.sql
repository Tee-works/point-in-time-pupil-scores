-- "What was this pupil's score at the end of summer term?" answered two ways.
-- restated: with everything we know now (late offline answers included)
-- as_reported: what a teacher's dashboard could have shown on the last day of term
create or replace table term_end_scores as
with restated as (
  select pupil_id, topic, score from pupil_topic_score_history
  where valid_from <= $term_end and valid_to > $term_end
),
as_reported as (
  -- rebuild the history using only answers loaded by term end, then take the same point in time
  select pupil_id, topic, score from (
    select pupil_id, topic, answered_at,
           avg(is_correct::int) over (partition by pupil_id, topic order by answered_at, response_id
                                      rows between 19 preceding and current row) as score,
           row_number() over (partition by pupil_id, topic order by answered_at desc, response_id desc) as rn
    from stg_responses where loaded_at <= $term_end and answered_at <= $term_end
  ) where rn = 1
)
select coalesce(r.pupil_id, a.pupil_id) as pupil_id, coalesce(r.topic, a.topic) as topic,
       round(r.score, 4) as restated_score, round(a.score, 4) as as_reported_score,
       round(r.score, 4) is distinct from round(a.score, 4) as changed_after_term
from restated r full outer join as_reported a using (pupil_id, topic);
