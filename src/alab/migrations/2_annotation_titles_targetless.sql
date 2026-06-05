DROP INDEX IF EXISTS idx_annotations_project_status_updated;
DROP INDEX IF EXISTS idx_annotations_target;

ALTER TABLE annotations RENAME TO annotations_old;

CREATE TABLE annotations (
  annotation_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  target_json TEXT NOT NULL,
  resolved_commit TEXT NULL,
  current_revision INTEGER NOT NULL,
  visibility_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_by_type TEXT NOT NULL,
  created_by_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (target_type IN ('none','experiment','run','artifact','path','lines')),
  CHECK (status IN ('active','archived')),
  CHECK (created_by_type IN ('root','admin','token')),
  CHECK (current_revision >= 1),
  CHECK (target_type != 'none' OR target_id = ''),
  CHECK (target_type != 'none' OR TRIM(COALESCE(title, '')) != ''),
  CHECK (target_type NOT IN ('path','lines') OR resolved_commit IS NOT NULL)
);

INSERT INTO annotations(
  annotation_id,
  project_id,
  title,
  target_type,
  target_id,
  target_json,
  resolved_commit,
  current_revision,
  visibility_json,
  status,
  created_by_type,
  created_by_id,
  created_at,
  updated_at
)
SELECT
  annotation_id,
  project_id,
  NULL,
  target_type,
  target_id,
  target_json,
  resolved_commit,
  current_revision,
  visibility_json,
  status,
  created_by_type,
  created_by_id,
  created_at,
  updated_at
FROM annotations_old;

DROP TABLE annotations_old;

CREATE INDEX idx_annotations_project_status_updated ON annotations(project_id, status, updated_at);
CREATE INDEX idx_annotations_target ON annotations(project_id, target_type, target_id);
