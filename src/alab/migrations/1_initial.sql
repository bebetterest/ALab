CREATE TABLE IF NOT EXISTS homes (
  home_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (home_id LIKE 'home-%')
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  audit_id TEXT PRIMARY KEY,
  project_id TEXT NULL,
  exp_id TEXT NULL,
  actor_credential_id TEXT NULL,
  actor_type TEXT NOT NULL,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  cascade INTEGER NOT NULL,
  reason TEXT NULL,
  deleted_ids_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  CHECK (actor_type IN ('root','admin','token','system')),
  CHECK (action IN ('add','update','archive','unarchive','remove','restore','repair','revoke','regenerate','prune','gc','clear')),
  CHECK (object_type IN ('project','source','experiment','run','validation','artifact','log','annotation','credential','secret_value','cache','backup','catalog','lock','worktree','inspection_checkout')),
  CHECK (cascade IN (0,1)),
  CHECK (reason IS NULL OR (typeof(reason) = 'text' AND length(CAST(reason AS BLOB)) <= 65536))
);
CREATE INDEX IF NOT EXISTS idx_audit_project_created ON audit_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_project_exp_created ON audit_events(project_id, exp_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_events(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor_credential_id, created_at);

CREATE TABLE IF NOT EXISTS credentials (
  credential_id TEXT PRIMARY KEY,
  credential_type TEXT NOT NULL,
  project_id TEXT NULL,
  exp_id TEXT NULL,
  token_mode TEXT NULL,
  registered_path_hash TEXT NULL,
  status TEXT NOT NULL,
  salt BLOB NOT NULL,
  verifier_hash BLOB NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT NULL,
  metadata_json TEXT NOT NULL,
  CHECK (credential_type IN ('root','admin','token')),
  CHECK (status IN ('active','revoked')),
  CHECK (
    (
      credential_type = 'root'
      AND project_id IS NULL
      AND exp_id IS NULL
      AND token_mode IS NULL
      AND registered_path_hash IS NULL
    )
    OR (
      credential_type = 'admin'
      AND project_id IS NOT NULL
      AND exp_id IS NULL
      AND token_mode IS NULL
      AND registered_path_hash IS NULL
    )
    OR (
      credential_type = 'token'
      AND project_id IS NOT NULL
      AND exp_id IS NOT NULL
      AND token_mode IN ('worktree','inspection')
      AND registered_path_hash IS NOT NULL
    )
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_root ON credentials(credential_type) WHERE credential_type='root' AND status='active';
CREATE INDEX IF NOT EXISTS idx_credential_project_status ON credentials(project_id, credential_type, status);
CREATE INDEX IF NOT EXISTS idx_token_project_exp_mode_status ON credentials(project_id, exp_id, token_mode, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_worktree_token ON credentials(exp_id) WHERE credential_type='token' AND token_mode='worktree' AND status='active';

CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  pre_archive_status TEXT NULL,
  canonical_repo_path TEXT NOT NULL UNIQUE,
  control_path TEXT NOT NULL UNIQUE,
  secret_fingerprint_key BLOB NOT NULL,
  latest_attempted_config_version INTEGER NULL,
  active_valid_config_version INTEGER NULL,
  active_validation_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT NULL,
  CHECK (status IN ('valid','invalid','archived')),
  CHECK (
    (status = 'archived' AND pre_archive_status IS NOT NULL AND pre_archive_status IN ('valid','invalid'))
    OR (status != 'archived' AND pre_archive_status IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_projects_status_updated ON projects(status, updated_at);

CREATE TABLE IF NOT EXISTS project_config_versions (
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
  CHECK (validation_status IN ('running','passed','failed','error','timeout','skipped','inherited','interrupted')),
  CHECK (baseline_required IN (0,1)),
  CHECK (
    (validation_status = 'inherited' AND inherited_from_validation_id IS NOT NULL)
    OR (validation_status != 'inherited' AND inherited_from_validation_id IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_config_project_status ON project_config_versions(project_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_config_project_hash ON project_config_versions(project_id, config_hash);

CREATE TABLE IF NOT EXISTS secret_values (
  secret_value_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  value TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by_credential_id TEXT NULL,
  replaced_at TEXT NULL,
  CHECK (typeof(value) = 'text' AND length(CAST(value AS BLOB)) >= 4 AND instr(value, char(0)) = 0),
  CHECK (typeof(fingerprint) = 'text' AND fingerprint GLOB 'hmac-sha256:*' AND length(CAST(fingerprint AS BLOB)) > 12)
);
CREATE INDEX IF NOT EXISTS idx_secret_project_name_created ON secret_values(project_id, name, created_at);
CREATE INDEX IF NOT EXISTS idx_secret_project_fingerprint ON secret_values(project_id, fingerprint);

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  name_slug TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  tree_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  origin_metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  archived_at TEXT NULL,
  CHECK (status IN ('active','archived')),
  CHECK (source_ref = 'alab/source/' || source_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_project_slug ON sources(project_id, name_slug);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_project_ref ON sources(project_id, source_ref);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_project_active_tree ON sources(project_id, tree_hash) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_source_project_status ON sources(project_id, status);

CREATE TABLE IF NOT EXISTS experiments (
  exp_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  bound_config_version INTEGER NOT NULL,
  bound_validation_id TEXT NOT NULL,
  baseline_commit TEXT NOT NULL,
  branch_name TEXT NOT NULL,
  worktree_path TEXT NULL,
  worktree_path_hash TEXT NULL,
  worktree_state TEXT NOT NULL,
  status TEXT NOT NULL,
  pre_archive_status TEXT NULL,
  metadata_json TEXT NOT NULL,
  policy_json TEXT NOT NULL,
  latest_run_id TEXT NULL,
  latest_commit TEXT NULL,
  final_run_id TEXT NULL,
  final_commit TEXT NULL,
  final_run_removed_at TEXT NULL,
  final_run_removed_by TEXT NULL,
  final_run_removed_audit_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  closed_at TEXT NULL,
  archived_at TEXT NULL,
  CHECK (worktree_state IN ('active','removed')),
  CHECK (status IN ('open','closed','archived')),
  CHECK (
    (status = 'archived' AND pre_archive_status IS NOT NULL AND pre_archive_status IN ('open','closed'))
    OR (status != 'archived' AND pre_archive_status IS NULL)
  ),
  CHECK (closed_at IS NULL OR status = 'closed' OR (status = 'archived' AND pre_archive_status = 'closed')),
  CHECK (
    (
      final_run_removed_at IS NULL
      AND final_run_removed_by IS NULL
      AND final_run_removed_audit_id IS NULL
    )
    OR (
      final_run_removed_at IS NOT NULL
      AND final_run_removed_by IS NOT NULL
      AND final_run_removed_audit_id IS NOT NULL
    )
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_project_branch ON experiments(project_id, branch_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_project_name_slug ON experiments(project_id, json_extract(metadata_json,'$.name_slug'));
CREATE INDEX IF NOT EXISTS idx_exp_project_status_updated ON experiments(project_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_exp_project_source ON experiments(project_id, source_id);
CREATE INDEX IF NOT EXISTS idx_exp_project_validation ON experiments(project_id, bound_validation_id);

CREATE TABLE IF NOT EXISTS experiment_submissions (
  submission_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  exp_id TEXT NOT NULL,
  final_run_id TEXT NOT NULL,
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_exp ON experiment_submissions(exp_id);
CREATE INDEX IF NOT EXISTS idx_submission_project_created ON experiment_submissions(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_submission_project_run ON experiment_submissions(project_id, final_run_id);

CREATE TABLE IF NOT EXISTS experiment_tags (
  project_id TEXT NOT NULL,
  exp_id TEXT NOT NULL,
  tag_slug TEXT NOT NULL,
  created_by_type TEXT NOT NULL,
  created_by_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (exp_id, tag_slug),
  CHECK (created_by_type IN ('root','admin','token')),
  CHECK (
    typeof(tag_slug) = 'text'
    AND length(CAST(tag_slug AS BLOB)) BETWEEN 1 AND 64
    AND tag_slug NOT GLOB '*[^a-z0-9-]*'
    AND tag_slug NOT GLOB '-*'
    AND tag_slug NOT GLOB '*-'
    AND tag_slug NOT GLOB '*--*'
  )
);
CREATE INDEX IF NOT EXISTS idx_tags_project_tag ON experiment_tags(project_id, tag_slug);
CREATE INDEX IF NOT EXISTS idx_tags_project_exp ON experiment_tags(project_id, exp_id);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  exp_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  config_version INTEGER NOT NULL,
  status TEXT NOT NULL,
  exit_code INTEGER NULL,
  reward_value REAL NULL,
  reward_parse_status TEXT NOT NULL,
  archive_status TEXT NOT NULL,
  archived_at TEXT NULL,
  unarchived_at TEXT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NULL,
  rolled_back_auto_commit TEXT NULL,
  record_json TEXT NOT NULL,
  CHECK (status IN ('running','passed','failed','error','timeout','interrupted')),
  CHECK (reward_parse_status IN ('not_attempted','parsed','missing','invalid','error')),
  CHECK (archive_status IN ('active','archived')),
  CHECK (archive_status = 'archived' OR archived_at IS NULL),
  CHECK ((status = 'running' AND ended_at IS NULL) OR (status != 'running' AND ended_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_runs_project_exp_started ON runs(project_id, exp_id, started_at);
CREATE INDEX IF NOT EXISTS idx_runs_project_commit ON runs(project_id, commit_sha);
CREATE INDEX IF NOT EXISTS idx_runs_project_status ON runs(project_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_project_archive ON runs(project_id, archive_status);
CREATE INDEX IF NOT EXISTS idx_runs_project_reward ON runs(project_id, reward_value);

CREATE TABLE IF NOT EXISTS project_validations (
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
  CHECK (status IN ('running','passed','failed','error','timeout','interrupted','skipped')),
  CHECK (reward_parse_status IN ('not_attempted','parsed','missing','invalid','error')),
  CHECK (archive_status IN ('active','archived')),
  CHECK (archive_status = 'archived' OR archived_at IS NULL),
  CHECK ((status = 'running' AND ended_at IS NULL) OR (status != 'running' AND ended_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  exp_id TEXT NULL,
  run_id TEXT NULL,
  validation_id TEXT NULL,
  root TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  size_bytes INTEGER NULL,
  content_hash TEXT NULL,
  status TEXT NOT NULL,
  archive_status TEXT NOT NULL,
  blob_path TEXT NULL,
  capture_error TEXT NULL,
  archived_at TEXT NULL,
  unarchived_at TEXT NULL,
  created_at TEXT NOT NULL,
  CHECK (root IN ('workspace','run')),
  CHECK (status IN ('captured','skipped','error')),
  CHECK (archive_status IN ('active','archived')),
  CHECK ((run_id IS NOT NULL) + (validation_id IS NOT NULL) = 1),
  CHECK (size_bytes IS NULL OR size_bytes >= 0),
  CHECK (status != 'captured' OR (blob_path IS NOT NULL AND content_hash IS NOT NULL AND size_bytes IS NOT NULL)),
  CHECK (status = 'captured' OR blob_path IS NULL),
  CHECK (status != 'error' OR capture_error IS NOT NULL),
  CHECK (status = 'error' OR capture_error IS NULL),
  CHECK (archive_status = 'archived' OR archived_at IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_run ON artifacts(project_id, exp_id, run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_validation ON artifacts(project_id, validation_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_hash ON artifacts(project_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_status ON artifacts(project_id, status);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_archive ON artifacts(project_id, archive_status);

CREATE TABLE IF NOT EXISTS log_streams (
  log_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  exp_id TEXT NULL,
  run_id TEXT NULL,
  validation_id TEXT NULL,
  stream TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  stored_bytes INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  truncated INTEGER NOT NULL,
  hidden INTEGER NOT NULL,
  archive_status TEXT NOT NULL,
  file_path TEXT NOT NULL,
  preview_text TEXT NULL,
  archived_at TEXT NULL,
  unarchived_at TEXT NULL,
  created_at TEXT NOT NULL,
  CHECK (stream IN ('stdout','stderr','hidden_stdout','hidden_stderr')),
  CHECK (size_bytes >= 0),
  CHECK (stored_bytes >= 0),
  CHECK (stored_bytes <= size_bytes),
  CHECK (truncated IN (0,1)),
  CHECK (hidden IN (0,1)),
  CHECK ((stream IN ('hidden_stdout','hidden_stderr') AND hidden = 1) OR (stream IN ('stdout','stderr') AND hidden = 0)),
  CHECK (archive_status IN ('active','archived')),
  CHECK ((run_id IS NOT NULL) + (validation_id IS NOT NULL) = 1),
  CHECK (archive_status = 'archived' OR archived_at IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_logs_project_run ON log_streams(project_id, exp_id, run_id);
CREATE INDEX IF NOT EXISTS idx_logs_project_validation ON log_streams(project_id, validation_id);
CREATE INDEX IF NOT EXISTS idx_logs_project_hidden ON log_streams(project_id, hidden);
CREATE INDEX IF NOT EXISTS idx_logs_project_archive ON log_streams(project_id, archive_status);

CREATE TABLE IF NOT EXISTS annotations (
  annotation_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
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
  CHECK (target_type IN ('experiment','run','artifact','path','lines')),
  CHECK (status IN ('active','archived')),
  CHECK (created_by_type IN ('root','admin','token')),
  CHECK (current_revision >= 1),
  CHECK (target_type NOT IN ('path','lines') OR resolved_commit IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_annotations_project_status_updated ON annotations(project_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_annotations_target ON annotations(project_id, target_type, target_id);

CREATE TABLE IF NOT EXISTS annotation_revisions (
  annotation_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  body TEXT NOT NULL,
  author_label TEXT NULL,
  created_at TEXT NOT NULL,
  created_by_type TEXT NOT NULL,
  created_by_id TEXT NOT NULL,
  PRIMARY KEY (annotation_id, revision),
  CHECK (revision >= 1),
  CHECK (created_by_type IN ('root','admin','token'))
);

CREATE TABLE IF NOT EXISTS path_registry (
  path_registry_id TEXT PRIMARY KEY,
  path_hash TEXT NOT NULL,
  path TEXT NOT NULL,
  context_type TEXT NOT NULL,
  home_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  exp_id TEXT NULL,
  token_id TEXT NULL,
  status TEXT NOT NULL,
  removed_at TEXT NULL,
  removed_by_credential_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (context_type IN ('project','experiment','inspection')),
  CHECK (status IN ('active','removed')),
  CHECK (
    (context_type = 'project' AND exp_id IS NULL AND token_id IS NULL)
    OR (context_type IN ('experiment','inspection') AND exp_id IS NOT NULL AND token_id IS NOT NULL)
  ),
  CHECK (
    (status = 'active' AND removed_at IS NULL AND removed_by_credential_id IS NULL)
    OR (status = 'removed' AND removed_at IS NOT NULL)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_path_active_path ON path_registry(path) WHERE status='active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_path_active_hash ON path_registry(path_hash) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_path_hash_status ON path_registry(path_hash, status);
CREATE INDEX IF NOT EXISTS idx_path_project_exp_type ON path_registry(project_id, exp_id, context_type);
CREATE INDEX IF NOT EXISTS idx_path_token ON path_registry(token_id);

CREATE TABLE IF NOT EXISTS locks (
  lock_name TEXT PRIMARY KEY,
  owner_operation_id TEXT NOT NULL,
  owner_host TEXT NOT NULL,
  owner_pid INTEGER NOT NULL,
  project_id TEXT NULL,
  exp_id TEXT NULL,
  acquired_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_locks_project_exp ON locks(project_id, exp_id);
CREATE INDEX IF NOT EXISTS idx_locks_expires ON locks(expires_at);

CREATE TABLE IF NOT EXISTS runtime_capabilities (
  capability_key TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  details_json TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  CHECK (status IN ('supported','unsupported','error'))
);

CREATE TABLE IF NOT EXISTS catalogs (
  catalog_key TEXT PRIMARY KEY,
  catalog_type TEXT NOT NULL,
  origin_url TEXT NOT NULL,
  pinned_commit TEXT NOT NULL,
  local_path TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  removed_at TEXT NULL,
  CHECK (catalog_key IN ('skydiscover')),
  CHECK (catalog_type IN ('skydiscover')),
  CHECK (status IN ('active','removed')),
  CHECK (
    (status = 'active' AND removed_at IS NULL)
    OR (status = 'removed' AND removed_at IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS cache_entries (
  cache_id TEXT PRIMARY KEY,
  cache_kind TEXT NOT NULL,
  cache_key TEXT NOT NULL,
  project_id TEXT NULL,
  path TEXT NULL,
  docker_tag TEXT NULL,
  size_bytes INTEGER NULL,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_used_at TEXT NULL,
  removed_at TEXT NULL,
  CHECK (cache_kind IN ('docker_image','skydiscover_python_env','trash')),
  CHECK (status IN ('active','removed')),
  CHECK (size_bytes IS NULL OR size_bytes >= 0),
  CHECK (
    (status = 'active' AND removed_at IS NULL)
    OR (status = 'removed' AND removed_at IS NOT NULL)
  ),
  CHECK (
    (cache_kind = 'docker_image' AND path IS NULL AND docker_tag IS NOT NULL)
    OR (cache_kind IN ('skydiscover_python_env','trash') AND path IS NOT NULL AND docker_tag IS NULL)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_active_kind_key ON cache_entries(cache_kind, cache_key) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_cache_kind_status_used ON cache_entries(cache_kind, status, last_used_at);
CREATE INDEX IF NOT EXISTS idx_cache_project_kind_status ON cache_entries(project_id, cache_kind, status);
