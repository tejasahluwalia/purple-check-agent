PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, giver TEXT, receiver TEXT, rating TEXT, comment TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, giver_role TEXT, receiver_role TEXT, deal_stage TEXT, `platform` text DEFAULT 'INSTAGRAM' NOT NULL, `medium` text DEFAULT 'DIRECT' NOT NULL, `source` text DEFAULT 'DM' NOT NULL);
CREATE TABLE IF NOT EXISTS user_message_logs (
user_id TEXT NOT NULL,
message TEXT NOT NULL,
stage TEXT NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_feedback ON feedback (giver, receiver);
COMMIT;
