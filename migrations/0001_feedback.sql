CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  category TEXT NOT NULL,
  message TEXT NOT NULL,
  contact TEXT,
  page TEXT,
  spec TEXT,
  version TEXT,
  user_agent TEXT,
  ip_hash TEXT,
  status TEXT NOT NULL DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS feedback_created ON feedback(created_at);
CREATE INDEX IF NOT EXISTS feedback_ip ON feedback(ip_hash, created_at);
