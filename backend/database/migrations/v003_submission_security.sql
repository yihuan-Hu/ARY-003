ALTER TABLE submissions ADD COLUMN content_hash TEXT DEFAULT '';
ALTER TABLE submissions ADD COLUMN content_commitment TEXT DEFAULT '';
ALTER TABLE submissions ADD COLUMN content_public_summary TEXT DEFAULT '[protected submission]';
ALTER TABLE submissions ADD COLUMN content_protection TEXT DEFAULT 'sealed_commitment_v1';
