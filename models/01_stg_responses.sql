-- Grain: one row per response_id. Retried deliveries collapse to the first load; deterministic tie-break.
-- Rows with answered_at in the future (device clock skew) are quarantined with a reason, not dropped.
create or replace table quarantine_responses as
select *, 'answered_at after loaded_at (device clock skew)' as reason
from raw_responses where answered_at > loaded_at;

create or replace table stg_responses as
select response_id, pupil_id, topic, answered_at, loaded_at, is_correct
from raw_responses
where answered_at <= loaded_at
qualify row_number() over (partition by response_id order by loaded_at, is_correct) = 1;
