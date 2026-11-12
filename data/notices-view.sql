CREATE VIEW IF NOT EXISTS notices AS
WITH combined AS (
    SELECT 'job' AS notice_type, id, target_audience, organizer, deadline, selection_date, benefit, category, title, full_text, created_at, updated_at, main_category, subcategory, eligibility_conditions, classification_status, classification_reason FROM jobs
    UNION ALL
    SELECT 'scholarship' AS notice_type, id, target_audience, organizer, deadline, selection_date, benefit, category, title, full_text, created_at, updated_at, main_category, subcategory, eligibility_conditions, classification_status, classification_reason FROM scholarships
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY id ORDER BY (length(trim(full_text)) > 0) DESC,
        updated_at DESC, length(full_text) DESC, notice_type ASC
    ) AS source_rank FROM combined
)
SELECT * FROM ranked WHERE source_rank = 1 AND
    (id < 1000000000 OR EXISTS (SELECT 1 FROM notice_origins origin WHERE origin.notice_id = ranked.id));
