DROP INDEX IF EXISTS idx_submission_exp;
DROP INDEX IF EXISTS idx_submission_project_created;
DROP INDEX IF EXISTS idx_submission_project_run;
DROP INDEX IF EXISTS idx_config_project_status;
DROP INDEX IF EXISTS idx_config_project_hash;

ALTER TABLE experiment_submissions RENAME TO experiment_submissions_old;

CREATE TABLE experiment_submissions (
  submission_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  exp_id TEXT NOT NULL,
  final_run_id TEXT NULL,
  final_commit TEXT NOT NULL,
  message TEXT NOT NULL,
  summary TEXT NOT NULL,
  feedback TEXT NOT NULL,
  refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by_credential_id TEXT NOT NULL,
  CHECK (typeof(message) = 'text' AND length(CAST(message AS BLOB)) <= 300),
  CHECK (typeof(summary) = 'text' AND length(CAST(summary AS BLOB)) <= 65536),
  CHECK (typeof(feedback) = 'text' AND length(CAST(feedback AS BLOB)) <= 65536)
);

INSERT INTO experiment_submissions(
  submission_id,
  project_id,
  exp_id,
  final_run_id,
  final_commit,
  message,
  summary,
  feedback,
  refs_json,
  created_at,
  created_by_credential_id
)
SELECT
  submission_id,
  project_id,
  exp_id,
  final_run_id,
  final_commit,
  message,
  summary,
  feedback,
  refs_json,
  created_at,
  created_by_credential_id
FROM experiment_submissions_old;

DROP TABLE experiment_submissions_old;

CREATE UNIQUE INDEX idx_submission_exp ON experiment_submissions(exp_id);
CREATE INDEX idx_submission_project_created ON experiment_submissions(project_id, created_at);
CREATE INDEX idx_submission_project_run ON experiment_submissions(project_id, final_run_id);

ALTER TABLE project_config_versions RENAME TO project_config_versions_old;

CREATE TABLE project_config_versions (
  project_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  canonical_config_json TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  baseline_required INTEGER NOT NULL,
  validation_status TEXT NOT NULL,
  inherited_from_validation_id TEXT NULL,
  created_at TEXT NOT NULL,
  created_by_credential_id TEXT NULL,
  PRIMARY KEY (project_id, version),
  CHECK (validation_status IN ('running','passed','failed','error','timeout','skipped','inherited','interrupted','not_required')),
  CHECK (baseline_required IN (0,1)),
  CHECK (
    (validation_status = 'inherited' AND inherited_from_validation_id IS NOT NULL)
    OR (validation_status != 'inherited' AND inherited_from_validation_id IS NULL)
  )
);

INSERT INTO project_config_versions(
  project_id,
  version,
  canonical_config_json,
  config_hash,
  baseline_required,
  validation_status,
  inherited_from_validation_id,
  created_at,
  created_by_credential_id
)
SELECT
  project_id,
  version,
  canonical_config_json,
  config_hash,
  baseline_required,
  validation_status,
  inherited_from_validation_id,
  created_at,
  created_by_credential_id
FROM project_config_versions_old;

DROP TABLE project_config_versions_old;

CREATE INDEX idx_config_project_status ON project_config_versions(project_id, validation_status);
CREATE INDEX idx_config_project_hash ON project_config_versions(project_id, config_hash);

ALTER TABLE project_validations RENAME TO project_validations_old;

CREATE TABLE project_validations (
  validation_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  config_version INTEGER NOT NULL,
  source_ref TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  status TEXT NOT NULL,
  exit_code INTEGER NULL,
  reward_value REAL NULL,
  reward_parse_status TEXT NOT NULL,
  archive_status TEXT NOT NULL,
  archived_at TEXT NULL,
  unarchived_at TEXT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NULL,
  record_json TEXT NOT NULL,
  CHECK (status IN ('running','passed','failed','error','timeout','interrupted','skipped','not_required')),
  CHECK (reward_parse_status IN ('not_attempted','parsed','missing','invalid','error')),
  CHECK (archive_status IN ('active','archived')),
  CHECK (archive_status = 'archived' OR archived_at IS NULL),
  CHECK ((status = 'running' AND ended_at IS NULL) OR (status != 'running' AND ended_at IS NOT NULL))
);

INSERT INTO project_validations(
  validation_id,
  project_id,
  config_version,
  source_ref,
  source_commit,
  status,
  exit_code,
  reward_value,
  reward_parse_status,
  archive_status,
  archived_at,
  unarchived_at,
  started_at,
  ended_at,
  record_json
)
SELECT
  validation_id,
  project_id,
  config_version,
  source_ref,
  source_commit,
  status,
  exit_code,
  reward_value,
  reward_parse_status,
  archive_status,
  archived_at,
  unarchived_at,
  started_at,
  ended_at,
  record_json
FROM project_validations_old;

DROP TABLE project_validations_old;
