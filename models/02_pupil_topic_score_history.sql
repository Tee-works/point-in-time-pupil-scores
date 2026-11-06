-- Type-2 history of each pupil's score per topic, kept on two clocks:
--   valid_from / valid_to : when the score was true in the world (event time, answered_at)
--   known_from            : when the warehouse could first have shown it (loaded_at of the newest answer counted)
-- Score = share correct over the pupil's last 20 answers in the topic.
create or replace table pupil_topic_score_history as
with scored as (
  select pupil_id, topic, response_id, answered_at, loaded_at,
         avg(is_correct::int) over w20 as score,
         count(*) over w20 as answers_in_window,
         max(loaded_at) over (partition by pupil_id, topic order by answered_at, response_id
                              rows between unbounded preceding and current row) as known_from
  from stg_responses
  window w20 as (partition by pupil_id, topic order by answered_at, response_id rows between 19 preceding and current row)
)
select pupil_id, topic, response_id as changed_by_response,
       round(score, 4) as score, answers_in_window,
       answered_at as valid_from,
       coalesce(lead(answered_at) over (partition by pupil_id, topic order by answered_at, response_id),
                timestamp '9999-12-31') as valid_to,
       known_from
from scored;
