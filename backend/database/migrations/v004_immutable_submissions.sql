CREATE TRIGGER IF NOT EXISTS trg_submissions_immutable
BEFORE UPDATE ON submissions
BEGIN
    SELECT RAISE(ABORT, 'submissions are immutable once created');
END;
