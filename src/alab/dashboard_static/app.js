const TOKEN_HEADER = "X-ALab-Dashboard-Token";
const ASSET_ALL_PROJECTS = "__all__";
const NAV = [
  ["overview", "layout-dashboard", "Overview", "总览"],
  ["projects", "folder-kanban", "Projects", "项目"],
  ["experiments", "flask-conical", "Experiments", "实验"],
  ["runs", "play-circle", "Runs", "运行"],
  ["assets", "file-stack", "Logs & Artifacts", "日志与产物"],
  ["audit", "shield-check", "Audit", "审计"],
  ["feedback", "message-square", "Feedback", "反馈"],
  ["system", "server-cog", "System", "系统"],
];

const INTERACTIVE_CARD_SELECTOR = [
  ".project-card",
  ".experiment-card",
  ".run-card",
  ".asset-card",
  ".audit-card",
  ".feedback-card",
  ".annotation-card",
  ".record-card",
  ".signal-item",
  ".failure-card",
  ".attention-item",
  "button.highlight-item",
].join(",");

const I18N = {
  en: {
    "brand.subtitle": "Local Viewer",
    "global.search": "Search",
    "global.refresh": "Refresh",
    "global.pause": "Pause auto refresh",
    "global.resume": "Resume auto refresh",
    "global.autoDisabled": "Auto refresh disabled",
    "global.searchPlaceholder": "Search current view",
    "global.clearSearch": "Clear search",
    "global.updated": "Updated",
    "global.never": "not yet",
    "empty": "No records match the current filters.",
    "overview.subtitle": "Global ALab home health, project activity, runs, feedback, and system state.",
    "projects.subtitle": "All projects, current validation state, run health, and per-project best results.",
    "experiments.subtitle": "Experiment status, tags, latest runs, and final submissions.",
    "runs.subtitle": "Recent runs across projects with reward, status, logs, artifacts, and runner metadata.",
    "assets.subtitle": "Global or project-scoped logs and artifacts, including hidden logs available in this local viewer.",
    "audit.subtitle": "Sanitized lifecycle audit history.",
    "feedback.subtitle": "Plaintext HOME-level feedback entries.",
    "system.subtitle": "Locks, runtime capabilities, catalogs, caches, and global config.",
  },
  zh: {
    "brand.subtitle": "本地视图",
    "global.search": "搜索",
    "global.refresh": "刷新",
    "global.pause": "暂停自动刷新",
    "global.resume": "恢复自动刷新",
    "global.autoDisabled": "自动刷新已关闭",
    "global.searchPlaceholder": "搜索当前视图",
    "global.clearSearch": "清空搜索",
    "global.updated": "已更新",
    "global.never": "尚未刷新",
    "empty": "当前筛选下没有记录。",
    "overview.subtitle": "ALab home 全局健康、项目活动、运行、反馈和系统状态。",
    "projects.subtitle": "所有项目、当前验证状态、运行健康和各项目内最佳结果。",
    "experiments.subtitle": "实验状态、标签、最新运行与最终提交。",
    "runs.subtitle": "跨项目近期运行、奖励、状态、日志、产物和运行器元数据。",
    "assets.subtitle": "全局或项目范围日志与产物；本地视图可查看隐藏日志。",
    "audit.subtitle": "已脱敏生命周期审计历史。",
    "feedback.subtitle": "本地明文反馈记录。",
    "system.subtitle": "锁、运行时能力、目录、缓存与全局配置。",
  },
};

const state = {
  token: null,
  language: localStorage.getItem("alab-dashboard-language") || "en",
  view: localStorage.getItem("alab-dashboard-view") || "overview",
  search: searchFromLocation(),
  paused: false,
  refreshSeconds: 15,
  summary: null,
  projects: [],
  experiments: [],
  runs: [],
  pages: {
    projects: null,
    experiments: null,
    runs: null,
  },
  projectDetail: null,
  projectDetails: new Map(),
  charts: new Map(),
  currentProjectId: localStorage.getItem("alab-dashboard-project") || "",
  assetProjectId: localStorage.getItem("alab-dashboard-asset-project") || ASSET_ALL_PROJECTS,
  assetScope: null,
  assetKind: localStorage.getItem("alab-dashboard-asset-kind") || "logs",
  detailRerender: null,
  detailSuppressFocus: false,
  projectDetailTab: "overview",
  filters: {
    projects: localStorage.getItem("alab-dashboard-filter-projects") || "all",
    experiments: localStorage.getItem("alab-dashboard-filter-experiments") || "all",
    runs: localStorage.getItem("alab-dashboard-filter-runs") || "all",
    asset_logs: localStorage.getItem("alab-dashboard-filter-asset_logs") || "all",
    asset_artifacts: localStorage.getItem("alab-dashboard-filter-asset_artifacts") || "all",
    audit: localStorage.getItem("alab-dashboard-filter-audit") || "all",
    feedback: localStorage.getItem("alab-dashboard-filter-feedback") || "all",
    project_experiments: localStorage.getItem("alab-dashboard-filter-project_experiments") || "all",
    project_runs: localStorage.getItem("alab-dashboard-filter-project_runs") || "all",
    project_logs: localStorage.getItem("alab-dashboard-filter-project_logs") || "all",
    project_artifacts: localStorage.getItem("alab-dashboard-filter-project_artifacts") || "all",
    experiment_runs: localStorage.getItem("alab-dashboard-filter-experiment_runs") || "all",
    experiment_logs: localStorage.getItem("alab-dashboard-filter-experiment_logs") || "all",
    experiment_artifacts: localStorage.getItem("alab-dashboard-filter-experiment_artifacts") || "all",
    run_logs: localStorage.getItem("alab-dashboard-filter-run_logs") || "all",
    run_artifacts: localStorage.getItem("alab-dashboard-filter-run_artifacts") || "all",
    system_capabilities: localStorage.getItem("alab-dashboard-filter-system_capabilities") || "all",
    system_catalogs: localStorage.getItem("alab-dashboard-filter-system_catalogs") || "all",
    system_cache: localStorage.getItem("alab-dashboard-filter-system_cache") || "all",
  },
  sorts: {
    projects: localStorage.getItem("alab-dashboard-sort-projects") || "attention",
    experiments: localStorage.getItem("alab-dashboard-sort-experiments") || "updated",
    runs: localStorage.getItem("alab-dashboard-sort-runs") || "started",
    asset_logs: localStorage.getItem("alab-dashboard-sort-asset_logs") || "created",
    asset_artifacts: localStorage.getItem("alab-dashboard-sort-asset_artifacts") || "created",
    audit: localStorage.getItem("alab-dashboard-sort-audit") || "created",
    feedback: localStorage.getItem("alab-dashboard-sort-feedback") || "created",
    project_experiments: localStorage.getItem("alab-dashboard-sort-project_experiments") || "updated",
    project_runs: localStorage.getItem("alab-dashboard-sort-project_runs") || "started",
    project_logs: localStorage.getItem("alab-dashboard-sort-project_logs") || "created",
    project_artifacts: localStorage.getItem("alab-dashboard-sort-project_artifacts") || "created",
    experiment_runs: localStorage.getItem("alab-dashboard-sort-experiment_runs") || "started",
    experiment_logs: localStorage.getItem("alab-dashboard-sort-experiment_logs") || "created",
    experiment_artifacts: localStorage.getItem("alab-dashboard-sort-experiment_artifacts") || "created",
    run_logs: localStorage.getItem("alab-dashboard-sort-run_logs") || "created",
    run_artifacts: localStorage.getItem("alab-dashboard-sort-run_artifacts") || "created",
    system_capabilities: localStorage.getItem("alab-dashboard-sort-system_capabilities") || "checked",
    system_catalogs: localStorage.getItem("alab-dashboard-sort-system_catalogs") || "updated",
    system_cache: localStorage.getItem("alab-dashboard-sort-system_cache") || "size",
  },
  detailReturnFocus: null,
  detailScrollLockY: 0,
  lastLoadedAt: null,
};

function searchFromLocation() {
  return new URLSearchParams(window.location.search).get("q") || "";
}

function tokenFromLocation() {
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return sessionStorage.getItem("alab-dashboard-token") || "";
  const params = new URLSearchParams(raw);
  const token = params.get("token") || raw;
  sessionStorage.setItem("alab-dashboard-token", token);
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return token;
}

function updateSearchQuery(value) {
  const url = new URL(window.location.href);
  if (value) {
    url.searchParams.set("q", value);
  } else {
    url.searchParams.delete("q");
  }
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function t(key) {
  return (I18N[state.language] && I18N[state.language][key]) || I18N.en[key] || key;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/vendor/lucide-icons.svg#${name}`);
  svg.appendChild(use);
  return svg;
}

function escapeText(value) {
  if (value === null || value === undefined || value === "") return "none";
  return String(value);
}

function escapeHtml(value) {
  return escapeText(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function valueOrNone(value) {
  return value === null || value === undefined || value === "" ? statusLabel("none") : value;
}

function shortText(value, maxLength = 28) {
  const text = escapeText(value);
  if (text.length <= maxLength) return text;
  const available = Math.max(8, maxLength - 3);
  const head = Math.max(6, Math.ceil(available * 0.62));
  const tail = Math.max(4, available - head);
  return `${text.slice(0, head)}...${text.slice(-tail)}`;
}

function factValue(value, maxLength = 28, titleValue = value) {
  const text = escapeText(valueOrNone(value));
  const title = escapeText(valueOrNone(titleValue));
  return `<b title="${escapeHtml(title)}">${escapeHtml(shortText(text, maxLength))}</b>`;
}

function jsonPre(value) {
  return `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function L(en, zh) {
  return state.language === "zh" ? zh : en;
}

function jsonShape(value) {
  if (Array.isArray(value)) return `${value.length} ${L("items", "项")}`;
  if (value && typeof value === "object") return `${Object.keys(value).length} ${L("keys", "键")}`;
  if (value === null || value === undefined) return statusLabel("none");
  return typeof value;
}

function jsonDetails(title, value) {
  if (value === null || value === undefined) {
    return `
      <div class="json-empty">
        <span>${escapeHtml(title)}</span>
        <strong>${escapeHtml(L("No record", "没有记录"))}</strong>
      </div>
    `;
  }
  return `
    <details class="json-disclosure">
      <summary>
        <span>${escapeHtml(title)}</span>
        <span>${escapeHtml(jsonShape(value))}</span>
      </summary>
      ${jsonPre(value)}
    </details>
  `;
}

function statusLabel(value) {
  const text = escapeText(value);
  if (state.language !== "zh") return text;
  return ({
    active: "活跃",
    archived: "已归档",
    captured: "已捕获",
    closed: "已关闭",
    error: "错误",
    failed: "失败",
    hidden: "隐藏",
    inherited: "继承",
    interrupted: "中断",
    invalid: "无效",
    open: "开放",
    passed: "通过",
    removed: "已移除",
    running: "运行中",
    skipped: "跳过",
    supported: "支持",
    timeout: "超时",
    unsupported: "不支持",
    valid: "有效",
    visible: "可见",
    parsed: "已解析",
    none: "无",
  })[text] || text;
}

function statusCountText(counts, statuses) {
  return statuses
    .map((status) => `${Number((counts || {})[status] || 0)} ${statusLabel(status)}`)
    .join(" / ");
}

function sumCounts(counts) {
  return Object.values(counts || {}).reduce((total, value) => total + Number(value || 0), 0);
}

function formatDate(value) {
  if (!value) return statusLabel("none");
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString(state.language === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCompactDate(value) {
  if (!value) return statusLabel("none");
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString(state.language === "zh" ? "zh-CN" : "en-US", {
    month: "numeric",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatTime(value) {
  if (!value) return t("global.never");
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleTimeString(state.language === "zh" ? "zh-CN" : "en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

function formatDurationMs(ms) {
  if (!Number.isFinite(ms) || ms < 0) return statusLabel("none");
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  if (totalSeconds === 0) return L("<1s", "<1秒");
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (state.language === "zh") {
    if (hours) return `${hours}小时 ${minutes}分`;
    if (minutes) return `${minutes}分 ${seconds}秒`;
    return `${seconds}秒`;
  }
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes) return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
  return `${seconds}s`;
}

function runDuration(run) {
  if (!run || !run.started_at) return statusLabel("none");
  if (!run.ended_at) return run.status === "running" ? statusLabel("running") : statusLabel("none");
  const started = Date.parse(run.started_at);
  const ended = Date.parse(run.ended_at);
  if (Number.isNaN(started) || Number.isNaN(ended)) return statusLabel("none");
  return formatDurationMs(ended - started);
}

function statusTotal(counts, names) {
  return names.reduce((total, name) => total + Number((counts || {})[name] || 0), 0);
}

function passRateFromCounts(counts) {
  const passed = Number((counts || {}).passed || 0);
  const failed = statusTotal(counts, ["failed", "error", "timeout", "interrupted"]);
  const total = passed + failed;
  return total ? `${Math.round((passed / total) * 100)}%` : statusLabel("none");
}

function projectName(projectId) {
  const project = state.projects.find((item) => item.project_id === projectId);
  return project ? project.name || project.project_id : valueOrNone(projectId);
}

function shortId(value) {
  const text = escapeText(value);
  if (text.length <= 28) return text;
  return `${text.slice(0, 17)}...${text.slice(-8)}`;
}

function idChip(value) {
  const text = escapeText(value);
  return `<code class="table-id" title="${escapeHtml(text)}">${escapeHtml(shortId(text))}</code>`;
}

function openCardLabel(kind, title, context = "") {
  return [L("Open", "打开"), kind, title, context].filter(Boolean).map(escapeText).join(" · ");
}

function cardLabelAttrs(label) {
  const text = escapeText(label);
  return `title="${escapeHtml(text)}" aria-label="${escapeHtml(text)}"`;
}

function objectTypeLabel(type) {
  const text = escapeText(type);
  if (state.language !== "zh") return text;
  return ({
    annotation: "标注",
    artifact: "产物",
    cache: "缓存",
    catalog: "目录",
    experiment: "实验",
    feedback: "反馈",
    key: "密钥",
    log: "日志",
    project: "项目",
    run: "运行",
    source: "来源",
    token: "令牌",
    validation: "验证",
  })[text] || text;
}

function objectChip(type, id) {
  return `<span class="object-ref"><span title="${escapeHtml(type || "object")}">${escapeHtml(objectTypeLabel(type || "object"))}</span>${idChip(id)}</span>`;
}

function tagList(tags) {
  const values = tags || [];
  if (!values.length) return `<span class="muted">${escapeHtml(L("none", "无"))}</span>`;
  return `<span class="tag-list">${values.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</span>`;
}

function warningSummary(codes) {
  const values = (codes || []).filter(Boolean);
  return values.length ? values.join(", ") : statusLabel("none");
}

function artifactKind(path) {
  const name = String(path || "");
  const lower = name.toLowerCase();
  const extension = lower.includes(".") ? lower.slice(lower.lastIndexOf(".") + 1) : "";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(extension)) return L("image", "图像");
  if (["json", "jsonl", "csv", "tsv", "txt", "md", "log", "yaml", "yml"].includes(extension)) return extension || L("text", "文本");
  if (["pt", "pth", "ckpt", "onnx", "bin"].includes(extension)) return L("model/binary", "模型/二进制");
  return extension || L("file", "文件");
}

function artifactCardSummary(artifact) {
  const owner = artifact.run_id
    ? L("run output", "运行产出")
    : artifact.validation_id
      ? L("validation output", "验证产出")
      : L("project artifact", "项目产物");
  const root = artifact.root ? `${valueOrNone(artifact.root)} ${L("root", "根")}` : L("root not recorded", "未记录根");
  return [
    artifactKind(artifact.relative_path || artifact.artifact_id),
    statusLabel(artifact.status || "none"),
    formatBytes(artifact.size_bytes),
    owner,
    root,
  ].join(" · ");
}

function kvList(items) {
  return `<div class="kv-list">${items.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
}

function fieldLabel(key) {
  const text = String(key || "").replace(/_/g, " ");
  if (state.language !== "zh") return text;
  return ({
    action: "动作",
    actor_type: "执行者",
    artifact_id: "产物",
    cache_id: "缓存",
    cache_kind: "缓存类型",
    capability_key: "能力",
    catalog_key: "目录",
    catalog_type: "目录类型",
    checked_at: "检查时间",
    config_version: "配置版本",
    created_at: "创建时间",
    ended_at: "结束时间",
    exit_code: "退出码",
    exp_id: "实验",
    expires_at: "过期时间",
    failure_reason: "失败原因",
    fingerprint: "指纹",
    hidden: "隐藏",
    lock_name: "锁",
    log_id: "日志",
    object_id: "对象",
    object_type: "对象类型",
    owner_host: "主机",
    owner_operation_id: "操作",
    owner_pid: "进程",
    project_id: "项目",
    relative_path: "相对路径",
    reward_value: "奖励",
    run_id: "运行",
    size_bytes: "大小",
    source_commit: "来源提交",
    source_id: "来源",
    source_ref: "来源引用",
    started_at: "开始时间",
    status: "状态",
    stored_bytes: "已存储",
    stream: "流",
    updated_at: "更新时间",
    validation_id: "验证",
    visibility: "可见性",
    visibility_scope: "可见性",
    warning_codes: "警告",
  })[key] || text;
}

function objectDisplayValue(key, value) {
  if (value === null || value === undefined || value === "") return statusLabel("none");
  if (key === "project_id") {
    const name = projectName(value);
    return name && name !== value ? `${name} (${value})` : value;
  }
  if (key === "object_type") return objectTypeLabel(value);
  if (key === "status") return statusLabel(value);
  if (key === "hidden") return value ? statusLabel("hidden") : L("visible", "可见");
  if (key.endsWith("_bytes")) return formatBytes(value);
  if (key.endsWith("_at") || key === "expires_at") return formatDate(value);
  if (typeof value === "boolean") return value ? L("yes", "是") : L("no", "否");
  if (Array.isArray(value)) return value.length ? value.join(", ") : statusLabel("none");
  if (value && typeof value === "object") return jsonShape(value);
  return value;
}

function objectPrimaryText(obj) {
  if (!obj || typeof obj !== "object") return statusLabel("none");
  const metadata = obj.metadata || {};
  const candidates = [
    obj.name,
    metadata.title,
    obj.title,
    obj.capability_key,
    obj.catalog_key,
    obj.lock_name,
    obj.relative_path,
    obj.source_ref,
    obj.action,
    obj.object_id,
    obj.cache_id,
    obj.validation_id,
    obj.source_id,
    obj.annotation_id,
    obj.artifact_id,
    obj.log_id,
    obj.run_id,
    obj.exp_id,
    obj.project_id,
  ];
  return candidates.find((value) => value !== null && value !== undefined && value !== "") || statusLabel("none");
}

function objectSubtitle(obj) {
  const parts = [];
  if (obj.project_id) parts.push(projectName(obj.project_id));
  if (obj.exp_id) parts.push(`${L("experiment", "实验")}: ${shortId(obj.exp_id)}`);
  if (obj.run_id) parts.push(`${L("run", "运行")}: ${shortId(obj.run_id)}`);
  if (obj.object_type && obj.object_id) parts.push(`${objectTypeLabel(obj.object_type)} ${shortId(obj.object_id)}`);
  if (obj.metadata && obj.metadata.role) parts.push(obj.metadata.role);
  return parts.filter(Boolean).join(" · ") || L("Read-only record detail", "只读记录详情");
}

function objectStatusHtml(obj) {
  if (obj.status) return statusBadge(obj.status);
  if (obj.hidden !== undefined) return statusBadge(obj.hidden ? "hidden" : "visible");
  if (obj.action) return `<span class="badge">${escapeHtml(obj.action)}</span>`;
  if (obj.metadata && obj.metadata.kind) return `<span class="badge">${escapeHtml(obj.metadata.kind)}</span>`;
  return "";
}

function objectKeyFields(obj) {
  if (!obj || typeof obj !== "object") return [];
  const preferred = [
    "status",
    "action",
    "actor_type",
    "object_type",
    "object_id",
    "project_id",
    "exp_id",
    "run_id",
    "validation_id",
    "source_id",
    "log_id",
    "artifact_id",
    "cache_id",
    "cache_kind",
    "capability_key",
    "catalog_key",
    "catalog_type",
    "lock_name",
    "owner_operation_id",
    "owner_host",
    "owner_pid",
    "stream",
    "hidden",
    "relative_path",
    "source_ref",
    "source_commit",
    "config_version",
    "reward_value",
    "exit_code",
    "failure_reason",
    "warning_codes",
    "size_bytes",
    "stored_bytes",
    "visibility",
    "visibility_scope",
    "created_at",
    "updated_at",
    "checked_at",
    "started_at",
    "ended_at",
    "expires_at",
  ];
  const seen = new Set();
  const fields = [];
  const addField = (key) => {
    if (seen.has(key) || !(key in obj)) return;
    seen.add(key);
    fields.push([fieldLabel(key), objectDisplayValue(key, obj[key])]);
  };
  preferred.forEach(addField);
  for (const [key, value] of Object.entries(obj)) {
    if (fields.length >= 14) break;
    if (seen.has(key) || value === null || value === undefined || value === "") continue;
    if (typeof value === "object" && !Array.isArray(value)) continue;
    addField(key);
  }
  return fields.slice(0, 14);
}

function objectDetailHtml(title, obj) {
  const fields = objectKeyFields(obj);
  return `
    <div class="entity-summary object-detail-summary">
      <div>
        <div class="metric-label">${escapeHtml(title)}</div>
        <div class="project-detail-title">${escapeHtml(objectPrimaryText(obj))}</div>
        <div class="summary-note">${escapeHtml(objectSubtitle(obj))}</div>
      </div>
      <div class="entity-summary-side">
        ${objectStatusHtml(obj)}
        ${relatedActions(obj || {})}
      </div>
    </div>
    ${panel(L("Key fields", "关键字段"), fields.length ? kvList(fields) : emptyHtml({ compact: true }))}
    ${panel(L("Raw record", "原始记录"), jsonDetails(L("Record JSON", "记录 JSON"), obj))}
  `;
}

function metricSummaryHtml(metrics) {
  const entries = Object.entries(metrics || {});
  if (!entries.length) return emptyHtml({ compact: true });
  return `
    <div class="metric-list">
      ${entries.map(([name, value]) => {
        const isComplex = value !== null && typeof value === "object";
        const display = isComplex ? JSON.stringify(value) : valueOrNone(value);
        return `
          <div class="metric-item">
            <span>${escapeHtml(name)}</span>
            <strong title="${escapeHtml(display)}">${escapeHtml(display)}</strong>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function runnerSummary(runner) {
  if (!runner) return statusLabel("none");
  if (typeof runner !== "object") return runner;
  return [runner.type, runner.platform, runner.host].filter(Boolean).join(" / ") || JSON.stringify(runner);
}

function runnerCompactSummary(runner) {
  if (!runner) return statusLabel("none");
  if (typeof runner !== "object") return runner;
  return [runner.type, runner.platform].filter(Boolean).join(" / ") || runnerSummary(runner);
}

function configHighlights(config) {
  const runner = config.runner || {};
  const reward = config.reward || {};
  const artifacts = config.artifacts || {};
  const secretEnv = config.secret_env || {};
  const secretSummary = Object.entries(secretEnv)
    .map(([name, marker]) => `${name}: ${marker && marker.fingerprint ? marker.fingerprint : L("fingerprint unavailable", "指纹不可用")}`)
    .join(", ") || statusLabel("none");
  return kvList([
    [L("runner", "运行器"), valueOrNone(runner.type)],
    [L("runner command", "运行命令"), Array.isArray(runner.command) ? runner.command.join(" ") : valueOrNone(runner.command || runner.program_path)],
    [L("reward", "奖励"), `${valueOrNone(reward.type)} / ${valueOrNone(reward.direction || "maximize")} / ${valueOrNone(reward.primary_metric || "reward")}`],
    [L("artifact globs", "产物匹配"), (artifacts.globs || []).join(", ") || statusLabel("none")],
    [L("env keys", "环境键"), Object.keys(config.env || {}).join(", ") || statusLabel("none")],
    ["secret_env", secretSummary],
  ]);
}

function systemMetadataHtml(system) {
  const home = system.home || {};
  const globalConfig = system.global_config || {};
  return `
    ${kvList([
      [L("home path", "HOME 路径"), home.path || state.summary.home_path || statusLabel("none")],
      [L("home schema", "HOME schema"), valueOrNone(home.schema_version || home.storage_schema_version)],
      [L("created", "创建"), formatDate(home.created_at)],
      [L("updated", "更新"), formatDate(home.updated_at)],
      [L("global config", "全局配置"), jsonShape(globalConfig)],
      [L("feedback entries", "反馈记录"), valueOrNone(system.feedback_count)],
    ])}
    ${jsonDetails(L("Home record", "HOME 记录"), home)}
    ${jsonDetails(L("Global config", "全局配置"), globalConfig)}
  `;
}

function statusBars(counts, order) {
  const entries = order
    .map((name) => [name, Number((counts || {})[name] || 0)])
    .filter(([, value]) => value > 0);
  const total = entries.reduce((acc, [, value]) => acc + value, 0);
  if (!total) return emptyHtml({ compact: true });
  return `
    <div class="status-bars">
      ${entries.map(([name, value]) => `
        <div class="status-row">
          <span title="${escapeHtml(name)}">${escapeHtml(statusLabel(name))}</span>
          <progress class="${escapeHtml(name)}" value="${value}" max="${total}"></progress>
          <strong>${value}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function statusBadge(value) {
  const text = escapeText(value);
  const cls = ["passed", "valid", "active", "open", "supported"].includes(text)
    ? "good"
    : ["running", "archived", "skipped", "inherited"].includes(text)
      ? "warn"
      : ["failed", "error", "timeout", "invalid", "interrupted", "unsupported"].includes(text)
        ? "bad"
        : "";
  const label = statusLabel(text);
  const title = label === text ? "" : ` title="${escapeHtml(text)}"`;
  return `<span class="badge ${cls}"${title}>${escapeHtml(label)}</span>`;
}

function bySearch(rows, fields) {
  const q = state.search.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((row) => fields.some((field) => {
    const value = typeof field === "function" ? field(row) : row[field];
    return String(value ?? "").toLowerCase().includes(q);
  }));
}

function filterMeta(shown, total, context = "", page = null) {
  const query = state.search.trim();
  const parts = [`${L("Showing", "显示")} ${shown}/${total}`];
  const pageTotal = Number(page && page.total);
  if (Number.isFinite(pageTotal) && pageTotal > total) {
    parts.push(`${L("loaded", "已加载")} ${total}/${pageTotal}`);
  }
  if (context) parts.push(context);
  if (query) parts.push(`${L("search", "搜索")}: ${query}`);
  return `<div class="filter-meta">${parts.map(escapeHtml).join(" · ")}</div>`;
}

function activeFilter(view, options) {
  const values = new Set(options.map((option) => option.value));
  const active = state.filters[view] || "all";
  return values.has(active) ? active : "all";
}

function activeSort(view, options) {
  const values = new Set(options.map((option) => option.value));
  const active = state.sorts[view] || (options[0] && options[0].value) || "";
  return values.has(active) ? active : (options[0] && options[0].value) || "";
}

function quickFilters(view, options) {
  const active = activeFilter(view, options);
  const visibleOptions = options.filter((option) => (
    option.value === "all"
    || option.value === active
    || Number(option.count || 0) > 0
  ));
  return `
    <div class="quick-filters" role="group" aria-label="${escapeHtml(L("Quick filters", "快速筛选"))}">
      ${visibleOptions.map((option) => {
        const isActive = option.value === active;
        return `
        <button class="${isActive ? "active" : ""}" type="button" data-filter="${escapeHtml(option.value)}" aria-pressed="${isActive ? "true" : "false"}">
          <span>${escapeHtml(option.label)}</span>
          <strong>${escapeHtml(option.count)}</strong>
        </button>
      `;
      }).join("")}
    </div>
  `;
}

function wireQuickFilters(container, view, onChange = render) {
  for (const button of container.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      state.filters[view] = button.dataset.filter || "all";
      localStorage.setItem(`alab-dashboard-filter-${view}`, state.filters[view]);
      onChange();
    });
  }
  for (const button of container.querySelectorAll("[data-reset-filter]")) {
    button.addEventListener("click", () => {
      const targetView = button.dataset.resetFilter || view;
      state.filters[targetView] = "all";
      localStorage.setItem(`alab-dashboard-filter-${targetView}`, "all");
      onChange();
    });
  }
}

function sortControl(view, options) {
  const active = activeSort(view, options);
  return `
    <label class="select-shell sort-shell">
      <span>${escapeHtml(L("Sort", "排序"))}</span>
      <select id="${escapeHtml(view)}-sort">
        ${options.map((option) => `<option value="${escapeHtml(option.value)}" ${option.value === active ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}
      </select>
    </label>
  `;
}

function wireSortControl(container, view, options, onChange = render) {
  const select = container.querySelector("select");
  if (!select) return;
  const active = activeSort(view, options);
  if (select.value !== active) select.value = active;
  select.addEventListener("change", () => {
    state.sorts[view] = select.value;
    localStorage.setItem(`alab-dashboard-sort-${view}`, state.sorts[view]);
    onChange();
  });
}

function listControls(view, filterOptions, sortOptions) {
  const filter = activeFilter(view, filterOptions);
  const resetFilter = filter === "all" ? "" : `<button class="link-button reset-filter-control" type="button" data-reset-filter="${escapeHtml(view)}">${escapeHtml(L("Reset filter", "重置筛选"))}</button>`;
  return `
    <div class="list-controls">
      ${quickFilters(view, filterOptions)}
      <div class="list-tools">
        ${resetFilter}
        ${sortControl(view, sortOptions)}
      </div>
    </div>
  `;
}

function renderListChrome({
  controlsNode,
  metaNode,
  view,
  allRows,
  rows,
  filterOptions,
  sortOptions,
  filter,
  sort,
  page = null,
  onChange = render,
}) {
  if (!controlsNode || !metaNode) return;
  if (!allRows.length) {
    controlsNode.innerHTML = "";
    metaNode.innerHTML = "";
    return;
  }
  controlsNode.innerHTML = listControls(view, filterOptions, sortOptions);
  wireQuickFilters(controlsNode, view, onChange);
  wireSortControl(controlsNode, view, sortOptions, onChange);
  const context = [
    quickFilterLabel(filterOptions, filter),
    quickSortLabel(sortOptions, sort),
  ].filter(Boolean).join(" · ");
  metaNode.innerHTML = filterMeta(rows.length, allRows.length, context, page);
}

function quickFilterLabel(options, value) {
  const option = options.find((item) => item.value === value);
  if (!option || option.value === "all") return "";
  return `${L("filter", "筛选")}: ${option.label}`;
}

function quickSortLabel(options, value) {
  const option = options.find((item) => item.value === value);
  return option ? `${L("sort", "排序")}: ${option.label}` : "";
}

function hasRunIssue(run) {
  return ["failed", "error", "timeout", "interrupted"].includes(run.status);
}

function hasProjectIssue(project) {
  return project.status === "invalid" || Number((project.counts || {}).failed_runs || 0) > 0;
}

function hasExperimentIssue(exp) {
  const status = exp.latest_run ? exp.latest_run.status : "";
  return hasRunIssue({ status });
}

function filterProjects(rows, filter) {
  if (filter === "attention") return rows.filter(hasProjectIssue);
  if (filter === "valid") return rows.filter((project) => project.status === "valid");
  if (filter === "invalid") return rows.filter((project) => project.status === "invalid");
  if (filter === "archived") return rows.filter((project) => project.status === "archived");
  return rows;
}

function projectFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "attention", label: L("Needs attention", "需关注"), count: rows.filter(hasProjectIssue).length },
    { value: "valid", label: statusLabel("valid"), count: rows.filter((project) => project.status === "valid").length },
    { value: "invalid", label: statusLabel("invalid"), count: rows.filter((project) => project.status === "invalid").length },
    { value: "archived", label: statusLabel("archived"), count: rows.filter((project) => project.status === "archived").length },
  ];
}

function projectSortOptions() {
  return [
    { value: "attention", label: L("Attention first", "关注优先") },
    { value: "updated", label: L("Recently updated", "最近更新") },
    { value: "runs", label: L("Most runs", "运行最多") },
    { value: "experiments", label: L("Most experiments", "实验最多") },
    { value: "name", label: L("Name A-Z", "名称 A-Z") },
  ];
}

function sortProjects(rows, sortKey) {
  const rank = (project) => {
    if (project.status === "invalid") return 0;
    if (Number((project.counts || {}).failed_runs || 0) > 0) return 1;
    if (project.status === "valid") return 2;
    if (project.status === "archived") return 3;
    return 4;
  };
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "updated") return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
    if (sortKey === "runs") return Number((b.counts || {}).runs || 0) - Number((a.counts || {}).runs || 0) || rank(a) - rank(b);
    if (sortKey === "experiments") return Number((b.counts || {}).experiments || 0) - Number((a.counts || {}).experiments || 0) || rank(a) - rank(b);
    if (sortKey === "name") return String(a.name || a.project_id).localeCompare(String(b.name || b.project_id));
    return rank(a) - rank(b) || String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
  });
  return sorted;
}

function projectActivityScore(project) {
  const counts = project.counts || {};
  return Number(counts.runs || 0) + Number(counts.experiments || 0);
}

function projectOutputScore(project) {
  const counts = project.counts || {};
  return Number(counts.artifacts || 0) + Number(counts.logs || 0);
}

function projectAttentionScore(project) {
  const counts = project.counts || {};
  return (project.status === "invalid" ? 1000 : 0) + Number(counts.failed_runs || 0);
}

function projectAttentionDisplayScore(project) {
  const counts = project.counts || {};
  return Number(counts.failed_runs || 0) + (project.status === "invalid" ? 1 : 0);
}

function projectSignalListHtml(rows, kind) {
  const sorted = [...(rows || [])];
  let label;
  let detail;
  let scoreFor;
  if (kind === "attention") {
    label = L("issues", "问题");
    scoreFor = projectAttentionDisplayScore;
    detail = (project) => {
      const counts = project.counts || {};
      if (project.status === "invalid") return L("Invalid project status", "项目状态无效");
      const failures = Number(counts.failed_runs || 0);
      return failures ? `${failures} ${L("failed runs", "失败运行")}` : L("No active issues", "暂无活动问题");
    };
    sorted.sort((a, b) => projectAttentionScore(b) - projectAttentionScore(a) || String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  } else if (kind === "activity") {
    label = L("activity", "活跃度");
    scoreFor = projectActivityScore;
    detail = (project) => {
      const counts = project.counts || {};
      return `${Number(counts.runs || 0)} ${L("runs", "运行")} · ${Number(counts.experiments || 0)} ${L("experiments", "实验")}`;
    };
    sorted.sort((a, b) => projectActivityScore(b) - projectActivityScore(a) || String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  } else {
    label = L("records", "记录");
    scoreFor = projectOutputScore;
    detail = (project) => {
      const counts = project.counts || {};
      return `${Number(counts.artifacts || 0)} ${L("artifacts", "产物")} · ${Number(counts.logs || 0)} ${L("logs", "日志")}`;
    };
    sorted.sort((a, b) => projectOutputScore(b) - projectOutputScore(a) || String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  }
  const rowsToShow = sorted.filter((project) => {
    if (kind === "attention") return projectAttentionScore(project) > 0;
    if (kind === "activity") return projectActivityScore(project) > 0;
    return projectOutputScore(project) > 0;
  }).slice(0, 3);
  if (!rowsToShow.length) return emptyHtml({ compact: true });
  return `
    <div class="signal-list">
      ${rowsToShow.map((project) => {
        const cardLabel = openCardLabel(L("project detail", "项目详情"), project.name || project.project_id, detail(project));
        return `
          <button class="signal-item ${kind === "attention" ? "has-risk" : ""}" type="button" data-project-id="${escapeHtml(project.project_id)}" ${cardLabelAttrs(cardLabel)}>
            <span class="signal-main">
              <strong>${escapeHtml(project.name || project.project_id)}</strong>
              <small>${escapeHtml(detail(project))}</small>
            </span>
            <span class="signal-side">
              ${statusBadge(project.status)}
              <b>${escapeHtml(scoreFor(project))}</b>
              <small>${escapeHtml(label)}</small>
            </span>
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function filterExperiments(rows, filter) {
  if (filter === "open") return rows.filter((exp) => exp.status === "open");
  if (filter === "submitted") return rows.filter((exp) => exp.final_run);
  if (filter === "active_worktree") return rows.filter((exp) => exp.worktree_state === "active");
  if (filter === "attention") return rows.filter(hasExperimentIssue);
  if (filter === "archived") return rows.filter((exp) => exp.status === "archived");
  return rows;
}

function experimentFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "attention", label: L("Needs attention", "需关注"), count: rows.filter(hasExperimentIssue).length },
    { value: "open", label: statusLabel("open"), count: rows.filter((exp) => exp.status === "open").length },
    { value: "submitted", label: L("Submitted", "已提交"), count: rows.filter((exp) => exp.final_run).length },
    { value: "active_worktree", label: L("Active worktree", "活跃工作树"), count: rows.filter((exp) => exp.worktree_state === "active").length },
    { value: "archived", label: statusLabel("archived"), count: rows.filter((exp) => exp.status === "archived").length },
  ];
}

function experimentSortOptions() {
  return [
    { value: "updated", label: L("Recently updated", "最近更新") },
    { value: "attention", label: L("Attention first", "关注优先") },
    { value: "runs", label: L("Most runs", "运行最多") },
    { value: "project", label: L("Project A-Z", "项目 A-Z") },
    { value: "name", label: L("Name A-Z", "名称 A-Z") },
  ];
}

function sortExperiments(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "attention") return Number(hasExperimentIssue(b)) - Number(hasExperimentIssue(a)) || String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
    if (sortKey === "runs") return Number(b.run_count || 0) - Number(a.run_count || 0) || String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
    if (sortKey === "project") return projectName(a.project_id).localeCompare(projectName(b.project_id)) || String(a.name || a.exp_id).localeCompare(String(b.name || b.exp_id));
    if (sortKey === "name") return String(a.name || a.exp_id).localeCompare(String(b.name || b.exp_id));
    return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
  });
  return sorted;
}

function filterRuns(rows, filter) {
  if (filter === "attention") return rows.filter(hasRunIssue);
  if (filter === "passed") return rows.filter((run) => run.status === "passed");
  if (filter === "running") return rows.filter((run) => run.status === "running");
  if (filter === "warnings") return rows.filter((run) => (run.warning_codes || []).length);
  if (filter === "rewards") return rows.filter((run) => run.reward_value !== null && run.reward_value !== undefined);
  return rows;
}

function runFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "attention", label: L("Needs attention", "需关注"), count: rows.filter(hasRunIssue).length },
    { value: "passed", label: statusLabel("passed"), count: rows.filter((run) => run.status === "passed").length },
    { value: "running", label: statusLabel("running"), count: rows.filter((run) => run.status === "running").length },
    { value: "warnings", label: L("Warnings", "警告"), count: rows.filter((run) => (run.warning_codes || []).length).length },
    { value: "rewards", label: L("Rewards", "奖励"), count: rows.filter((run) => run.reward_value !== null && run.reward_value !== undefined).length },
  ];
}

function runSortOptions() {
  return [
    { value: "started", label: L("Newest started", "最新开始") },
    { value: "attention", label: L("Attention first", "关注优先") },
    { value: "warnings", label: L("Warnings first", "警告优先") },
    { value: "project", label: L("Project A-Z", "项目 A-Z") },
    { value: "status", label: L("Status A-Z", "状态 A-Z") },
  ];
}

function sortRuns(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "attention") return Number(hasRunIssue(b)) - Number(hasRunIssue(a)) || String(b.started_at || b.ended_at || "").localeCompare(String(a.started_at || a.ended_at || ""));
    if (sortKey === "warnings") return Number((b.warning_codes || []).length) - Number((a.warning_codes || []).length) || String(b.started_at || "").localeCompare(String(a.started_at || ""));
    if (sortKey === "project") return projectName(a.project_id).localeCompare(projectName(b.project_id)) || String(b.started_at || "").localeCompare(String(a.started_at || ""));
    if (sortKey === "status") return statusLabel(a.status).localeCompare(statusLabel(b.status)) || String(b.started_at || "").localeCompare(String(a.started_at || ""));
    return String(b.started_at || b.ended_at || "").localeCompare(String(a.started_at || a.ended_at || ""));
  });
  return sorted;
}

function filterLogs(rows, filter) {
  if (filter === "hidden") return rows.filter((log) => log.hidden);
  if (filter === "visible") return rows.filter((log) => !log.hidden);
  if (filter === "stdout") return rows.filter((log) => log.stream === "stdout" || log.stream === "hidden_stdout");
  if (filter === "stderr") return rows.filter((log) => log.stream === "stderr" || log.stream === "hidden_stderr");
  if (filter === "truncated") return rows.filter((log) => log.truncated);
  return rows;
}

function logFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "hidden", label: statusLabel("hidden"), count: rows.filter((log) => log.hidden).length },
    { value: "visible", label: statusLabel("visible"), count: rows.filter((log) => !log.hidden).length },
    { value: "stdout", label: "stdout", count: rows.filter((log) => log.stream === "stdout" || log.stream === "hidden_stdout").length },
    { value: "stderr", label: "stderr", count: rows.filter((log) => log.stream === "stderr" || log.stream === "hidden_stderr").length },
    { value: "truncated", label: L("Truncated", "已截断"), count: rows.filter((log) => log.truncated).length },
  ];
}

function logSortOptions() {
  return [
    { value: "created", label: L("Newest created", "最新创建") },
    { value: "stored", label: L("Stored bytes", "存储字节") },
    { value: "stream", label: L("Stream A-Z", "流 A-Z") },
    { value: "run", label: L("Run A-Z", "运行 A-Z") },
  ];
}

function sortLogs(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "stored") return Number(b.stored_bytes || b.size_bytes || 0) - Number(a.stored_bytes || a.size_bytes || 0) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    if (sortKey === "stream") return String(a.stream || "").localeCompare(String(b.stream || "")) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    if (sortKey === "run") return String(a.run_id || a.validation_id || "").localeCompare(String(b.run_id || b.validation_id || "")) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  });
  return sorted;
}

function filterArtifacts(rows, filter) {
  if (filter === "captured") return rows.filter((artifact) => artifact.status === "captured");
  if (filter === "error") return rows.filter((artifact) => artifact.status === "error");
  if (filter === "skipped") return rows.filter((artifact) => artifact.status === "skipped");
  if (filter === "large") return rows.filter((artifact) => Number(artifact.size_bytes || 0) >= 1024 * 1024);
  return rows;
}

function artifactFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "captured", label: statusLabel("captured"), count: rows.filter((artifact) => artifact.status === "captured").length },
    { value: "error", label: statusLabel("error"), count: rows.filter((artifact) => artifact.status === "error").length },
    { value: "skipped", label: statusLabel("skipped"), count: rows.filter((artifact) => artifact.status === "skipped").length },
    { value: "large", label: L(">= 1 MB", ">= 1 MB"), count: rows.filter((artifact) => Number(artifact.size_bytes || 0) >= 1024 * 1024).length },
  ];
}

function artifactSortOptions() {
  return [
    { value: "created", label: L("Newest created", "最新创建") },
    { value: "size", label: L("Largest size", "最大文件") },
    { value: "status", label: L("Status A-Z", "状态 A-Z") },
    { value: "path", label: L("Path A-Z", "路径 A-Z") },
  ];
}

function sortArtifacts(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "size") return Number(b.size_bytes || 0) - Number(a.size_bytes || 0) || String(a.relative_path || a.artifact_id).localeCompare(String(b.relative_path || b.artifact_id));
    if (sortKey === "status") return statusLabel(a.status).localeCompare(statusLabel(b.status)) || String(a.relative_path || a.artifact_id).localeCompare(String(b.relative_path || b.artifact_id));
    if (sortKey === "path") return String(a.relative_path || a.artifact_id).localeCompare(String(b.relative_path || b.artifact_id));
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  });
  return sorted;
}

function filterAuditRows(rows, filter) {
  if (filter === "root") return rows.filter((row) => row.actor_type === "root");
  if (filter === "admin") return rows.filter((row) => row.actor_type === "admin");
  if (filter === "cascade") return rows.filter((row) => row.cascade);
  if (filter === "project") return rows.filter((row) => row.object_type === "project");
  if (filter === "run") return rows.filter((row) => row.object_type === "run");
  return rows;
}

function auditFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "root", label: "root", count: rows.filter((row) => row.actor_type === "root").length },
    { value: "admin", label: "admin", count: rows.filter((row) => row.actor_type === "admin").length },
    { value: "cascade", label: L("Cascade", "级联"), count: rows.filter((row) => row.cascade).length },
    { value: "project", label: objectTypeLabel("project"), count: rows.filter((row) => row.object_type === "project").length },
    { value: "run", label: objectTypeLabel("run"), count: rows.filter((row) => row.object_type === "run").length },
  ];
}

function auditSortOptions() {
  return [
    { value: "created", label: L("Newest event", "最新事件") },
    { value: "action", label: L("Action A-Z", "动作 A-Z") },
    { value: "actor", label: L("Actor A-Z", "执行者 A-Z") },
    { value: "object", label: L("Object A-Z", "对象 A-Z") },
    { value: "project", label: L("Project A-Z", "项目 A-Z") },
  ];
}

function sortAuditRows(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "action") return String(a.action || "").localeCompare(String(b.action || "")) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    if (sortKey === "actor") return String(a.actor_type || "").localeCompare(String(b.actor_type || "")) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    if (sortKey === "object") return `${a.object_type || ""}:${a.object_id || ""}`.localeCompare(`${b.object_type || ""}:${b.object_id || ""}`) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    if (sortKey === "project") return projectName(a.project_id).localeCompare(projectName(b.project_id)) || String(b.created_at || "").localeCompare(String(a.created_at || ""));
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  });
  return sorted;
}

function feedbackKind(row) {
  return (row.metadata && row.metadata.kind) || "";
}

function feedbackRole(row) {
  return (row.metadata && row.metadata.role) || "";
}

function feedbackBodyWords(row) {
  const body = String((row && row.body) || "").trim();
  if (!body) return 0;
  const words = body.split(/\s+/).filter(Boolean).length;
  return words || body.length;
}

function feedbackBodyBytes(row) {
  return new TextEncoder().encode(String((row && row.body) || "")).length;
}

function feedbackDay(row) {
  const created = row && row.metadata && row.metadata.created_at;
  return created ? String(created).slice(0, 10) : statusLabel("none");
}

function filterFeedbackRows(rows, filter) {
  if (filter === "bug") return rows.filter((row) => feedbackKind(row) === "bug");
  if (filter === "question") return rows.filter((row) => feedbackKind(row) === "question");
  if (filter === "note") return rows.filter((row) => feedbackKind(row) === "note");
  if (filter === "showcase") return rows.filter((row) => feedbackRole(row) === "dashboard-showcase");
  if (filter === "detailed") return rows.filter((row) => feedbackBodyWords(row) >= 8);
  return rows;
}

function feedbackFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "bug", label: "bug", count: rows.filter((row) => feedbackKind(row) === "bug").length },
    { value: "question", label: "question", count: rows.filter((row) => feedbackKind(row) === "question").length },
    { value: "note", label: "note", count: rows.filter((row) => feedbackKind(row) === "note").length },
    { value: "showcase", label: L("Showcase role", "示例角色"), count: rows.filter((row) => feedbackRole(row) === "dashboard-showcase").length },
    { value: "detailed", label: L("Detailed", "详细反馈"), count: rows.filter((row) => feedbackBodyWords(row) >= 8).length },
  ];
}

function feedbackSortOptions() {
  return [
    { value: "created", label: L("Newest feedback", "最新反馈") },
    { value: "body", label: L("Most detailed", "内容最多") },
    { value: "kind", label: L("Kind A-Z", "类型 A-Z") },
    { value: "role", label: L("Role A-Z", "角色 A-Z") },
    { value: "title", label: L("Title A-Z", "标题 A-Z") },
  ];
}

function sortFeedbackRows(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    const aMeta = a.metadata || {};
    const bMeta = b.metadata || {};
    if (sortKey === "body") return feedbackBodyWords(b) - feedbackBodyWords(a) || String(bMeta.created_at || "").localeCompare(String(aMeta.created_at || ""));
    if (sortKey === "kind") return String(aMeta.kind || "").localeCompare(String(bMeta.kind || "")) || String(bMeta.created_at || "").localeCompare(String(aMeta.created_at || ""));
    if (sortKey === "role") return String(aMeta.role || "").localeCompare(String(bMeta.role || "")) || String(bMeta.created_at || "").localeCompare(String(aMeta.created_at || ""));
    if (sortKey === "title") return String(aMeta.title || "").localeCompare(String(bMeta.title || ""));
    return String(bMeta.created_at || "").localeCompare(String(aMeta.created_at || ""));
  });
  return sorted;
}

function hasCapabilityIssue(row) {
  return ["error", "unsupported", "failed", "invalid"].includes(row.status);
}

function filterCapabilities(rows, filter) {
  if (filter === "issues") return rows.filter(hasCapabilityIssue);
  if (filter === "supported") return rows.filter((row) => row.status === "supported");
  if (filter === "error") return rows.filter((row) => row.status === "error");
  if (filter === "unsupported") return rows.filter((row) => row.status === "unsupported");
  return rows;
}

function capabilityFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "issues", label: L("Issues", "问题"), count: rows.filter(hasCapabilityIssue).length },
    { value: "supported", label: statusLabel("supported"), count: rows.filter((row) => row.status === "supported").length },
    { value: "error", label: statusLabel("error"), count: rows.filter((row) => row.status === "error").length },
    { value: "unsupported", label: statusLabel("unsupported"), count: rows.filter((row) => row.status === "unsupported").length },
  ];
}

function capabilitySortOptions() {
  return [
    { value: "checked", label: L("Newest checked", "最新检查") },
    { value: "status", label: L("Status A-Z", "状态 A-Z") },
    { value: "key", label: L("Key A-Z", "键 A-Z") },
  ];
}

function sortCapabilities(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "status") return statusLabel(a.status).localeCompare(statusLabel(b.status)) || String(a.capability_key || "").localeCompare(String(b.capability_key || ""));
    if (sortKey === "key") return String(a.capability_key || "").localeCompare(String(b.capability_key || ""));
    return String(b.checked_at || "").localeCompare(String(a.checked_at || ""));
  });
  return sorted;
}

function filterCatalogs(rows, filter) {
  if (filter === "active") return rows.filter((row) => row.status === "active");
  if (filter === "inactive") return rows.filter((row) => row.status && row.status !== "active");
  if (filter === "skydiscover") return rows.filter((row) => row.catalog_type === "skydiscover" || row.catalog_key === "skydiscover");
  return rows;
}

function catalogFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "active", label: statusLabel("active"), count: rows.filter((row) => row.status === "active").length },
    { value: "inactive", label: L("Inactive", "非活跃"), count: rows.filter((row) => row.status && row.status !== "active").length },
    { value: "skydiscover", label: "SkyDiscover", count: rows.filter((row) => row.catalog_type === "skydiscover" || row.catalog_key === "skydiscover").length },
  ];
}

function catalogSortOptions() {
  return [
    { value: "updated", label: L("Newest updated", "最新更新") },
    { value: "key", label: L("Key A-Z", "键 A-Z") },
    { value: "type", label: L("Type A-Z", "类型 A-Z") },
    { value: "status", label: L("Status A-Z", "状态 A-Z") },
  ];
}

function sortCatalogs(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "key") return String(a.catalog_key || "").localeCompare(String(b.catalog_key || ""));
    if (sortKey === "type") return String(a.catalog_type || "").localeCompare(String(b.catalog_type || "")) || String(a.catalog_key || "").localeCompare(String(b.catalog_key || ""));
    if (sortKey === "status") return statusLabel(a.status).localeCompare(statusLabel(b.status)) || String(a.catalog_key || "").localeCompare(String(b.catalog_key || ""));
    return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
  });
  return sorted;
}

function filterCacheRows(rows, filter) {
  if (filter === "active") return rows.filter((row) => row.status === "active");
  if (filter === "removed") return rows.filter((row) => row.status === "removed");
  if (filter === "docker") return rows.filter((row) => String(row.cache_kind || "").includes("docker"));
  if (filter === "trash") return rows.filter((row) => String(row.cache_kind || "").includes("trash"));
  return rows;
}

function cacheFilterOptions(rows) {
  return [
    { value: "all", label: L("All", "全部"), count: rows.length },
    { value: "active", label: statusLabel("active"), count: rows.filter((row) => row.status === "active").length },
    { value: "removed", label: statusLabel("removed"), count: rows.filter((row) => row.status === "removed").length },
    { value: "docker", label: "Docker", count: rows.filter((row) => String(row.cache_kind || "").includes("docker")).length },
    { value: "trash", label: L("Trash", "回收站"), count: rows.filter((row) => String(row.cache_kind || "").includes("trash")).length },
  ];
}

function cacheSortOptions() {
  return [
    { value: "size", label: L("Largest size", "最大大小") },
    { value: "used", label: L("Recently used", "最近使用") },
    { value: "kind", label: L("Kind A-Z", "类型 A-Z") },
    { value: "status", label: L("Status A-Z", "状态 A-Z") },
  ];
}

function sortCacheRows(rows, sortKey) {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    if (sortKey === "used") return String(b.last_used_at || b.created_at || "").localeCompare(String(a.last_used_at || a.created_at || ""));
    if (sortKey === "kind") return String(a.cache_kind || "").localeCompare(String(b.cache_kind || "")) || Number(b.size_bytes || 0) - Number(a.size_bytes || 0);
    if (sortKey === "status") return statusLabel(a.status).localeCompare(statusLabel(b.status)) || Number(b.size_bytes || 0) - Number(a.size_bytes || 0);
    return Number(b.size_bytes || 0) - Number(a.size_bytes || 0);
  });
  return sorted;
}

function emptyHtml(options = {}) {
  const query = state.search.trim();
  const compact = options.compact ? " compact" : "";
  if (query && !options.unfiltered) {
    return `
      <div class="empty${compact}">
        <strong>${escapeHtml(L("No matches", "没有匹配结果"))}</strong>
        <span>${escapeHtml(L("Current search", "当前搜索"))}: ${escapeHtml(query)}</span>
        <button class="link-button clear-search-inline" type="button">${escapeHtml(L("Clear search", "清空搜索"))}</button>
      </div>
    `;
  }
  const message = options.unfiltered
    ? L("No records are available for this section.", "此区域暂无可显示记录。")
    : t("empty");
  return `<div class="empty${compact}"><strong>${escapeHtml(L("No records", "没有记录"))}</strong><span>${escapeHtml(message)}</span></div>`;
}

function wireInlineClearSearch(container = document) {
  for (const button of container.querySelectorAll(".clear-search-inline")) {
    button.addEventListener("click", () => {
      state.search = "";
      const search = document.getElementById("global-search");
      if (search) search.value = "";
      updateSearchQuery("");
      renderSearchControl();
      render();
    });
  }
}

function countBy(rows, getter) {
  const counts = {};
  for (const row of rows || []) {
    const value = getter(row) || "none";
    counts[value] = (counts[value] || 0) + 1;
  }
  return counts;
}

function countExperimentTags(rows) {
  const counts = {};
  for (const exp of rows || []) {
    const tags = (exp.tags || []).filter(Boolean);
    if (!tags.length) {
      counts.none = (counts.none || 0) + 1;
      continue;
    }
    for (const tag of tags) {
      counts[tag] = (counts[tag] || 0) + 1;
    }
  }
  return counts;
}

function uniqueCount(rows, getter) {
  return new Set((rows || []).map(getter).filter(Boolean)).size;
}

function latestValue(rows, getter) {
  return (rows || [])
    .map(getter)
    .filter(Boolean)
    .sort((a, b) => String(b).localeCompare(String(a)))[0];
}

function countListHtml(counts, labeler = (value) => (value === "none" ? statusLabel("none") : value)) {
  const entries = Object.entries(counts || {})
    .sort((a, b) => Number(b[1]) - Number(a[1]) || String(a[0]).localeCompare(String(b[0])))
    .slice(0, 8);
  if (!entries.length) return emptyHtml({ compact: true });
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0);
  return `
    <div class="count-list">
      ${entries.map(([name, value]) => `
        <div class="count-row">
          <span>${escapeHtml(labeler(name))}</span>
          <progress value="${escapeHtml(value)}" max="${escapeHtml(total)}"></progress>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function sizeListHtml(rows, groupGetter, sizeGetter, labeler = (value) => (value === "none" ? statusLabel("none") : value)) {
  const totals = {};
  for (const row of rows || []) {
    const name = groupGetter(row) || "none";
    totals[name] = (totals[name] || 0) + Number(sizeGetter(row) || 0);
  }
  const entries = Object.entries(totals)
    .sort((a, b) => Number(b[1]) - Number(a[1]) || String(a[0]).localeCompare(String(b[0])))
    .slice(0, 8);
  if (!entries.length) return emptyHtml({ compact: true });
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0);
  return `
    <div class="count-list size-list">
      ${entries.map(([name, value]) => `
        <div class="count-row size-row">
          <span>${escapeHtml(labeler(name))}</span>
          <progress value="${escapeHtml(value)}" max="${escapeHtml(total)}"></progress>
          <strong>${escapeHtml(formatBytes(value))}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function diagnosticListHtml(items) {
  if (!items.length) return `<div class="empty compact"><strong>${escapeHtml(L("No active diagnostics need attention.", "暂无需要关注的活动诊断。"))}</strong></div>`;
  const label = (severity) => {
    if (severity === "bad") return L("Risk", "风险");
    if (severity === "warn") return L("Warn", "警告");
    return L("OK", "正常");
  };
  return `
    <div class="diagnostic-list">
      ${items.map((item) => `
        <div class="diagnostic-item ${escapeHtml(item.severity)}">
          <span>${escapeHtml(label(item.severity))}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.detail)}</small>
        </div>
      `).join("")}
    </div>
  `;
}

async function api(path) {
  const response = await fetch(path, {
    headers: { [TOKEN_HEADER]: state.token },
    cache: "no-store",
  });
  if (!response.ok) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = { error: response.statusText };
    }
    throw new Error(payload.reason || payload.error || response.statusText);
  }
  return response.json();
}

async function apiBlob(path) {
  const response = await fetch(path, {
    headers: { [TOKEN_HEADER]: state.token },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.blob();
}

function setTitle(view) {
  const navItem = NAV.find((item) => item[0] === view) || NAV[0];
  document.getElementById("view-title").textContent = state.language === "zh" ? navItem[3] : navItem[2];
  document.getElementById("view-subtitle").textContent = t(`${view}.subtitle`);
}

function navigateToView(view) {
  closeDetailPanel({ restoreFocus: false });
  state.view = view;
  localStorage.setItem("alab-dashboard-view", view);
  render().then(() => window.scrollTo(0, 0));
}

function renderNav() {
  const nav = document.getElementById("nav");
  nav.replaceChildren();
  for (const [view, iconName, en, zh] of NAV) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = view === state.view ? "active" : "";
    if (view === state.view) button.setAttribute("aria-current", "page");
    button.append(icon(iconName), document.createTextNode(state.language === "zh" ? zh : en));
    button.addEventListener("click", () => {
      navigateToView(view);
    });
    nav.appendChild(button);
  }
}

function closeDetailPanel(options = {}) {
  const panelEl = document.getElementById("detail-panel");
  const backdropEl = document.getElementById("detail-backdrop");
  const wasOpen = panelEl.classList.contains("open");
  panelEl.classList.remove("open", "wide");
  if (wasOpen) {
    document.body.classList.remove("detail-open");
    document.body.style.top = "";
    window.scrollTo(0, state.detailScrollLockY || 0);
    state.detailScrollLockY = 0;
  }
  if (backdropEl) backdropEl.hidden = true;
  panelEl.removeAttribute("role");
  panelEl.removeAttribute("aria-label");
  panelEl.removeAttribute("aria-labelledby");
  panelEl.removeAttribute("aria-describedby");
  panelEl.removeAttribute("aria-modal");
  panelEl.setAttribute("aria-hidden", "true");
  destroyChartsIn(panelEl);
  panelEl.replaceChildren();
  state.detailRerender = null;
  if (wasOpen && options.restoreFocus !== false && state.detailReturnFocus && document.contains(state.detailReturnFocus)) {
    state.detailReturnFocus.focus({ preventScroll: true });
  }
  if (wasOpen) {
    state.detailReturnFocus = null;
    state.projectDetailTab = "overview";
  }
}

async function rerenderOpenDetailPanel(options = {}) {
  const panelEl = document.getElementById("detail-panel");
  if (!panelEl || !panelEl.classList.contains("open") || !state.detailRerender) return;
  const activeElement = document.activeElement;
  const activeId = options.preserveFocus && activeElement && panelEl.contains(activeElement) ? activeElement.id : "";
  state.detailSuppressFocus = Boolean(options.preserveFocus);
  try {
    await state.detailRerender();
  } finally {
    state.detailSuppressFocus = false;
  }
  if (!activeId) return;
  const nextPanelEl = document.getElementById("detail-panel");
  const replacement = document.getElementById(activeId);
  if (replacement && nextPanelEl && nextPanelEl.contains(replacement) && typeof replacement.focus === "function") {
    replacement.focus({ preventScroll: true });
  }
}

function detailFocusableElements(panelEl) {
  const selector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");
  return Array.from(panelEl.querySelectorAll(selector)).filter((node) => {
    const style = window.getComputedStyle(node);
    return !node.hidden && style.display !== "none" && style.visibility !== "hidden";
  });
}

function trapDetailPanelFocus(event) {
  const panelEl = document.getElementById("detail-panel");
  if (!panelEl || !panelEl.classList.contains("open")) return;
  const focusable = detailFocusableElements(panelEl);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!panelEl.contains(document.activeElement)) {
    event.preventDefault();
    first.focus({ preventScroll: true });
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus({ preventScroll: true });
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus({ preventScroll: true });
  }
}

function localize() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  document.getElementById("global-search").placeholder = t("global.searchPlaceholder");
  renderSearchControl();
  renderRefreshButton();
  renderFreshness();
}

function renderFreshness() {
  const node = document.getElementById("last-refresh");
  if (!node) return;
  node.textContent = `${t("global.updated")}: ${formatTime(state.lastLoadedAt)}`;
}

function renderSearchControl() {
  const button = document.getElementById("clear-search");
  if (!button) return;
  button.hidden = !state.search.trim();
  button.title = t("global.clearSearch");
  button.setAttribute("aria-label", t("global.clearSearch"));
  button.replaceChildren(icon("x"));
}

function metric(label, value, note) {
  return `<div class="card"><div class="metric-label" title="${escapeHtml(label)}">${escapeHtml(label)}</div><div class="metric-value" title="${escapeHtml(value)}">${escapeHtml(value)}</div><div class="metric-note" title="${escapeHtml(note)}">${escapeHtml(note)}</div></div>`;
}

function statCell(label, value, note = "") {
  return `<div class="stat-cell"><div class="metric-label">${escapeHtml(label)}</div><div class="stat-value">${escapeHtml(value)}</div><div class="metric-note">${escapeHtml(note)}</div></div>`;
}

function panel(title, body, actions = "") {
  const actionsHtml = actions ? `<div class="panel-actions">${actions}</div>` : "";
  return `<section class="panel"><div class="panel-header"><div class="panel-title">${escapeHtml(title)}</div>${actionsHtml}</div><div class="panel-body">${body}</div></section>`;
}

function renderTable(container, rows, columns, options = {}) {
  if (!rows.length) {
    container.innerHTML = emptyHtml();
    wireInlineClearSearch(container);
    return;
  }
  const sortIndex = Number(container.dataset.sortIndex ?? -1);
  const sortDirection = container.dataset.sortDirection || "asc";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headRow = document.createElement("tr");
  const sortRows = (index, column) => {
    const nextDirection = sortIndex === index && sortDirection === "asc" ? "desc" : "asc";
    container.dataset.sortIndex = String(index);
    container.dataset.sortDirection = nextDirection;
    const sortValue = column.sortValue || column.value || (() => "");
    rows.sort((a, b) => {
      const left = sortValue(a);
      const right = sortValue(b);
      const result = typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left ?? "").localeCompare(String(right ?? ""));
      return nextDirection === "asc" ? result : -result;
    });
    renderTable(container, rows, columns, options);
  };
  for (const [index, column] of columns.entries()) {
    const th = document.createElement("th");
    th.textContent = `${column.label}${sortIndex === index ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;
    th.setAttribute("aria-sort", sortIndex === index ? (sortDirection === "asc" ? "ascending" : "descending") : "none");
    th.setAttribute("tabindex", "0");
    th.title = L("Sort column", "排序此列");
    th.addEventListener("click", () => sortRows(index, column));
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        sortRows(index, column);
      }
    });
    headRow.appendChild(th);
  }
  if (options.onRow) {
    const th = document.createElement("th");
    th.className = "action-heading";
    th.textContent = options.actionLabel || L("Open", "查看");
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (options.onRow) {
      tr.classList.add("clickable-row");
      tr.addEventListener("click", () => options.onRow(row));
      tr.setAttribute("tabindex", "0");
      tr.setAttribute("role", "button");
      tr.setAttribute("aria-label", `${options.actionLabel || L("Open", "查看")} ${columns.map((column) => {
        if (column.value) return escapeText(column.value(row));
        if (column.sortValue) return escapeText(column.sortValue(row));
        return "";
      }).filter(Boolean).join(" ")}`);
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          options.onRow(row);
        }
      });
    }
    for (const column of columns) {
      const td = document.createElement("td");
      if (column.wrap) td.classList.add("wrap");
      const html = column.html ? column.html(row) : null;
      if (html !== null && html !== undefined) {
        td.innerHTML = html;
      } else {
        td.textContent = escapeText(column.value(row));
      }
      tr.appendChild(td);
    }
    if (options.onRow) {
      const td = document.createElement("td");
      td.className = "action-cell";
      const action = document.createElement("span");
      action.className = "row-action";
      action.textContent = options.actionLabel || L("Open", "查看");
      td.appendChild(action);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.append(thead, tbody);
  container.replaceChildren(table);
}

function renderChart(id, type, labels, datasets, options = {}) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const { ariaLabel, ...chartOptions } = options;
  const fallbackLabel = datasets.map((dataset) => dataset.label).filter(Boolean).join(", ") || id;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", ariaLabel || fallbackLabel);
  if (!window.Chart) return;
  if (state.charts.has(id)) state.charts.get(id).destroy();
  const defaultPlugins = {
    legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true } },
    tooltip: { mode: "index", intersect: false },
  };
  const defaultInteraction = { mode: "nearest", intersect: false };
  const chart = new Chart(canvas, {
    type,
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...chartOptions,
      plugins: {
        ...defaultPlugins,
        ...(chartOptions.plugins || {}),
        legend: {
          ...defaultPlugins.legend,
          ...((chartOptions.plugins || {}).legend || {}),
        },
        tooltip: {
          ...defaultPlugins.tooltip,
          ...((chartOptions.plugins || {}).tooltip || {}),
        },
      },
      interaction: {
        ...defaultInteraction,
        ...(chartOptions.interaction || {}),
      },
    },
  });
  state.charts.set(id, chart);
}

function destroyChartsIn(container) {
  if (!container) return;
  for (const canvas of container.querySelectorAll("canvas[id]")) {
    const chart = state.charts.get(canvas.id);
    if (chart) {
      chart.destroy();
      state.charts.delete(canvas.id);
    }
  }
}

function rewardTrendData(runsInput, directionInput = "maximize") {
  const runs = [...(runsInput || [])]
    .filter((run) => run.reward_value !== null && run.reward_value !== undefined)
    .sort((a, b) => {
      const aTime = Date.parse(a.ended_at || a.started_at || "") || 0;
      const bTime = Date.parse(b.ended_at || b.started_at || "") || 0;
      return aTime - bTime || String(a.run_id).localeCompare(String(b.run_id));
    });
  const labels = runs.map((_run, index) => `#${index + 1}`);
  const rewards = runs.map((run) => Number(run.reward_value));
  const direction = directionInput === "minimize" ? "minimize" : "maximize";
  let bestValue = null;
  const bestPoints = rewards.map((value) => {
    const improved = bestValue === null || (direction === "minimize" ? value < bestValue : value > bestValue);
    if (improved) {
      bestValue = value;
      return value;
    }
    return null;
  });
  return { labels, rewards, bestPoints, direction, runs };
}

function trendSummaryItem(label, value, note = "") {
  return `
    <span class="trend-summary-item">
      <b>${escapeHtml(value)}</b>
      <span>${escapeHtml(label)}</span>
      ${note ? `<small>${escapeHtml(note)}</small>` : ""}
    </span>
  `;
}

function rewardTrendSummaryHtml(runs, directionInput = "maximize") {
  const data = rewardTrendData(runs, directionInput);
  if (!data.runs.length) {
    return `<div class="trend-summary is-empty">${trendSummaryItem(L("scored runs", "有分运行"), "0", L("no reward values recorded", "未记录奖励值"))}</div>`;
  }
  const latest = data.runs[data.runs.length - 1];
  const best = bestRunForRuns(data.runs, data.direction);
  const newBestCount = data.bestPoints.filter((value) => value !== null).length;
  const directionLabel = data.direction === "minimize" ? L("minimize", "最小化") : L("maximize", "最大化");
  return `
    <div class="trend-summary">
      ${trendSummaryItem(L("scored runs", "有分运行"), String(data.runs.length), L("chronological", "按时间顺序"))}
      ${trendSummaryItem(L("best reward", "最佳奖励"), valueOrNone(best && best.reward_value), best ? shortId(best.run_id) : statusLabel("none"))}
      ${trendSummaryItem(L("latest reward", "最新奖励"), valueOrNone(latest.reward_value), shortId(latest.run_id))}
      ${trendSummaryItem(L("new best points", "新最佳点"), String(newBestCount), directionLabel)}
    </div>
  `;
}

function renderRewardTrendChart(id, runs, direction) {
  const data = rewardTrendData(runs, direction);
  renderChart(id, "line", data.labels, [
    {
      label: L("run reward", "运行奖励"),
      data: data.rewards,
      borderColor: "#1f7a8c",
      backgroundColor: "rgba(31, 122, 140, 0.12)",
      pointRadius: 4,
      tension: 0.25,
      spanGaps: true,
    },
    {
      label: data.direction === "minimize" ? L("new best low", "新的最低最佳") : L("new best high", "新的最高最佳"),
      data: data.bestPoints,
      borderColor: "#c53030",
      backgroundColor: "#c53030",
      pointRadius: 5,
      pointHoverRadius: 7,
      tension: 0.15,
      spanGaps: true,
    },
  ], {
    ariaLabel: L(
      "Run reward trend. The main line shows every run reward and red points mark new best values.",
      "运行奖励趋势。主折线显示每次运行奖励，红点标记新的最佳值。",
    ),
    plugins: {
      tooltip: {
        mode: "index",
        intersect: false,
        callbacks: {
          title: (items) => {
            const index = items[0] ? items[0].dataIndex : 0;
            const run = data.runs[index] || {};
            return `${data.labels[index]} ${run.exp_name || run.exp_id || run.run_id || ""}`;
          },
          afterBody: (items) => {
            const index = items[0] ? items[0].dataIndex : 0;
            const run = data.runs[index] || {};
            return [
              `${L("status", "状态")}: ${statusLabel(run.status || "none")}`,
              `${L("run", "运行")}: ${run.run_id || statusLabel("none")}`,
              `${L("started", "开始")}: ${formatDate(run.started_at)}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: L("run order", "运行序号") },
        ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
      },
      y: {
        title: { display: true, text: L("reward", "奖励") },
        grace: "12%",
      },
    },
  });
}

function renderProjectRewardChart(detail) {
  const summary = document.getElementById("project-reward-summary");
  if (summary) summary.innerHTML = rewardTrendSummaryHtml(detail.runs || [], detail.project.reward_direction);
  renderRewardTrendChart("project-reward-chart", detail.runs || [], detail.project.reward_direction);
}

function renderRunActivityChart(id, runs) {
  const statuses = ["passed", "failed", "error", "timeout", "interrupted", "running"];
  const buckets = new Map();
  for (const run of runs || []) {
    const key = (run.started_at || run.ended_at || "unknown").slice(0, 10);
    if (!buckets.has(key)) buckets.set(key, {});
    buckets.get(key)[run.status] = (buckets.get(key)[run.status] || 0) + 1;
  }
  const labels = [...buckets.keys()].sort();
  const colors = {
    passed: "#2f855a",
    failed: "#c53030",
    error: "#9b2c2c",
    timeout: "#b7791f",
    interrupted: "#26547c",
    running: "#718096",
  };
  renderChart(id, "bar", labels, statuses.map((status) => ({
    label: statusLabel(status),
    data: labels.map((label) => buckets.get(label)[status] || 0),
    backgroundColor: colors[status],
  })), {
    ariaLabel: L("Run activity by day and status.", "按日期和状态统计的运行活动。"),
    scales: {
      x: { stacked: true, ticks: { maxRotation: 0 } },
      y: { stacked: true, beginAtZero: true, precision: 0 },
    },
  });
}

function renderAuditActivityChart(id, rows) {
  const types = ["project", "experiment", "run", "source", "validation", "artifact", "log", "annotation", "other"];
  const colors = {
    project: "#26547c",
    experiment: "#1f7a8c",
    run: "#2f855a",
    source: "#7b61a8",
    validation: "#b7791f",
    artifact: "#d97706",
    log: "#718096",
    annotation: "#805ad5",
    other: "#94a3b8",
  };
  const buckets = new Map();
  for (const row of rows || []) {
    const key = (row.created_at || "unknown").slice(0, 10);
    const type = types.includes(row.object_type) ? row.object_type : "other";
    if (!buckets.has(key)) buckets.set(key, {});
    buckets.get(key)[type] = (buckets.get(key)[type] || 0) + 1;
  }
  const labels = [...buckets.keys()].sort();
  renderChart(id, "bar", labels, types.map((type) => ({
    label: objectTypeLabel(type),
    data: labels.map((label) => buckets.get(label)[type] || 0),
    backgroundColor: colors[type],
  })), {
    ariaLabel: L("Audit activity by day and object type.", "按日期和对象类型统计的审计活动。"),
    scales: {
      x: { stacked: true, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
      y: { stacked: true, beginAtZero: true, precision: 0 },
    },
  });
}

function attentionItems() {
  const counts = state.summary.counts || {};
  const items = [];
  for (const project of state.projects) {
    const failed = Number((project.counts || {}).failed_runs || 0);
    if (project.status === "invalid") {
      items.push({
        severity: "bad",
        title: project.name || project.project_id,
        detail: `${L("Project is invalid", "项目验证无效")} · ${failed} ${L("failed runs", "失败运行")}`,
        action: L("Open project", "打开项目"),
        project_id: project.project_id,
      });
    } else if (failed > 0 && project.status !== "archived") {
      items.push({
        severity: "warn",
        title: project.name || project.project_id,
      detail: `${failed} ${L("failed or interrupted runs", "失败或中断运行")} · ${valueOrNone(project.runner_type)}`,
        action: L("Open project", "打开项目"),
        project_id: project.project_id,
      });
    }
  }
  for (const run of (state.summary.recent_failures || []).slice(0, 4)) {
    items.push({
      severity: ["failed", "error", "timeout", "interrupted"].includes(run.status) ? "bad" : "warn",
      title: run.exp_name || run.exp_id || run.run_id,
      detail: `${projectName(run.project_id)} · ${statusLabel(run.status)} · ${run.failure_reason || L("no reason recorded", "未记录原因")}`,
      action: L("Open run", "打开运行"),
      run_id: run.run_id,
    });
  }
  if (Number(counts.active_locks || 0) > 0) {
    items.push({
      severity: "warn",
      title: L("Active locks", "活动锁"),
      detail: `${counts.active_locks} ${L("lock rows are present in the home", "条锁记录存在")}`,
      action: L("Open system", "打开系统"),
      view: "system",
    });
  }
  if (!items.length) {
    items.push({
      severity: "good",
      title: L("No immediate attention items", "暂无需要立即关注的事项"),
      detail: L("Projects, runs, locks, and recent failures look clean.", "项目、运行、锁和最近失败看起来正常。"),
      action: "",
    });
  }
  return items;
}

function attentionPanelHtml() {
  const severityLabel = (severity) => {
    if (severity === "bad") return L("Risk", "风险");
    if (severity === "warn") return L("Warn", "警告");
    if (severity === "good") return L("OK", "正常");
    return severity;
  };
  const allItems = attentionItems();
  const items = bySearch(allItems, ["severity", "title", "detail", "action"]);
  return `
    ${filterMeta(items.length, allItems.length)}
    <div class="attention-list" id="attention-list">
      ${items.length ? items.map((item) => {
        const label = openCardLabel(L("attention detail", "关注详情"), item.title, item.detail);
        return `
          <button class="attention-item ${escapeHtml(item.severity)}" type="button"
            ${item.project_id ? `data-project-id="${escapeHtml(item.project_id)}"` : ""}
            ${item.run_id ? `data-run-id="${escapeHtml(item.run_id)}"` : ""}
            ${item.view ? `data-view="${escapeHtml(item.view)}"` : ""}
            ${cardLabelAttrs(label)}
            ${item.action ? "" : "disabled"}>
            <span class="attention-severity">${escapeHtml(severityLabel(item.severity))}</span>
            <span class="attention-copy">
              <strong>${escapeHtml(item.title)}</strong>
              <small>${escapeHtml(item.detail)}</small>
            </span>
            <em>${escapeHtml(item.action || L("Done", "已处理"))}</em>
          </button>
        `;
      }).join("") : emptyHtml({ compact: true })}
    </div>
  `;
}

function failureReasonsForRunsHtml(runs, options = {}) {
  const failedStatuses = new Set(["failed", "error", "timeout", "interrupted"]);
  const groups = new Map();
  for (const run of runs || []) {
    if (!failedStatuses.has(run.status)) continue;
    const reason = run.failure_reason
      || ((run.warning_codes || []).length ? (run.warning_codes || []).join(", ") : "")
      || run.status
      || L("unknown", "未知");
    if (!groups.has(reason)) {
      groups.set(reason, { count: 0, experiments: new Set(), projects: new Set(), latest: "" });
    }
    const group = groups.get(reason);
    group.count += 1;
    if (run.exp_id) group.experiments.add(run.exp_id);
    if (run.project_id) group.projects.add(run.project_id);
    const timestamp = run.started_at || run.ended_at || "";
    if (String(timestamp).localeCompare(group.latest) > 0) group.latest = timestamp;
  }
  const rows = [...groups.entries()]
    .sort((a, b) => b[1].count - a[1].count || String(b[1].latest).localeCompare(String(a[1].latest)))
    .slice(0, 6);
  if (!rows.length) return emptyHtml({ compact: true });
  return `
    <div class="reason-list">
      ${rows.map(([reason, data]) => `
        <div class="reason-row">
          <strong>${escapeHtml(reason)}</strong>
          <span>${escapeHtml(options.projectScope
            ? `${data.count} ${L("runs", "运行")} · ${data.experiments.size} ${L("experiments", "实验")} · ${formatDate(data.latest)}`
            : `${data.count} ${L("runs", "运行")} · ${data.projects.size} ${L("projects", "项目")}`)}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function failureReasonsHtml() {
  return failureReasonsForRunsHtml(state.runs || []);
}

function projectStatsHtml(detail) {
  const counts = detail.project.counts || {};
  const runs = detail.runs || [];
  const completedRuns = runs.filter((run) => run.status && run.status !== "running").length;
  const passedRuns = runs.filter((run) => run.status === "passed").length;
  const best = detail.project.best_run;
  const successRate = completedRuns ? `${Math.round((passedRuns / completedRuns) * 100)}%` : statusLabel("none");
  return `
    <div class="stat-grid project-stats-grid">
      ${statCell(L("Experiments", "实验"), counts.experiments || 0, `${counts.open_experiments || 0} ${statusLabel("open")}`)}
      ${statCell(L("Runs", "运行"), counts.runs || 0, `${counts.failed_runs || 0} ${statusLabel("failed")}`)}
      ${statCell(L("Success rate", "成功率"), successRate, `${passedRuns}/${completedRuns} ${L("completed passed", "已完成通过")}`)}
      ${statCell(L("Best reward", "最佳奖励"), best ? best.reward_value : statusLabel("none"), detail.project.reward_direction || "maximize")}
      ${statCell(L("Sources", "来源"), counts.sources || 0, L("registered source snapshots", "已登记来源快照"))}
      ${statCell(L("Artifacts", "产物"), counts.artifacts || 0, `${counts.logs || 0} ${L("log streams", "日志流")}`)}
    </div>
  `;
}

function projectHealthBlock(title, body) {
  return `
    <section class="health-block">
      <h3>${escapeHtml(title)}</h3>
      ${body}
    </section>
  `;
}

function projectHealthHtml(detail) {
  const runs = detail.runs || [];
  const experiments = detail.experiments || [];
  return `
    <div class="project-health-grid">
      ${projectHealthBlock(L("Run status mix", "运行状态分布"), statusBars(countBy(runs, (run) => run.status), ["passed", "failed", "error", "timeout", "interrupted", "running"]))}
      ${projectHealthBlock(L("Experiment status mix", "实验状态分布"), statusBars(countBy(experiments, (exp) => exp.status), ["open", "closed", "archived"]))}
      ${projectHealthBlock(L("Project failure reasons", "项目失败原因"), failureReasonsForRunsHtml(runs, { projectScope: true }))}
      ${projectHealthBlock(L("Run coverage", "运行覆盖"), countListHtml(countBy(runs, (run) => run.exp_name || run.exp_id)))}
    </div>
  `;
}

function latestRunForProject(runs, predicate = () => true) {
  return [...(runs || [])]
    .filter(predicate)
    .sort((a, b) => String(b.started_at || b.ended_at || "").localeCompare(String(a.started_at || a.ended_at || "")))[0];
}

function bestRunForRuns(runs, direction = "maximize") {
  const candidates = [...(runs || [])].filter((run) => run.reward_value !== null && run.reward_value !== undefined);
  if (!candidates.length) return null;
  const factor = direction === "minimize" ? 1 : -1;
  candidates.sort((a, b) => {
    const rewardDiff = (Number(a.reward_value) - Number(b.reward_value)) * factor;
    return rewardDiff || String(b.started_at || b.ended_at || "").localeCompare(String(a.started_at || a.ended_at || ""));
  });
  return candidates[0];
}

function projectHighlightItem(item) {
  const isAction = item.run_id || item.log_id || item.artifact_id;
  const tag = isAction ? "button" : "div";
  const label = isAction ? openCardLabel(L("highlight detail", "要点详情"), item.title, item.detail) : "";
  const attrs = [
    isAction ? 'type="button"' : "",
    item.run_id ? `data-highlight-run-id="${escapeHtml(item.run_id)}"` : "",
    item.log_id ? `data-highlight-log-id="${escapeHtml(item.log_id)}"` : "",
    item.artifact_id ? `data-highlight-artifact-id="${escapeHtml(item.artifact_id)}"` : "",
    isAction ? cardLabelAttrs(label) : "",
  ].filter(Boolean).join(" ");
  return `
    <${tag} class="highlight-item ${escapeHtml(item.tone || "")}" ${attrs}>
      <span class="highlight-copy">
        <small>${escapeHtml(item.label)}</small>
        <strong>${escapeHtml(item.title)}</strong>
        <em>${escapeHtml(item.detail)}</em>
      </span>
      <span class="highlight-side">
        ${item.status ? statusBadge(item.status) : ""}
        ${item.value ? `<b>${escapeHtml(item.value)}</b>` : ""}
      </span>
    </${tag}>
  `;
}

function projectHighlightsHtml(detail) {
  const project = detail.project || {};
  const runs = detail.runs || [];
  const experiments = detail.experiments || [];
  const source = (detail.sources || [])[0];
  const validation = (detail.validations || [])[0];
  const best = project.best_run;
  const latest = latestRunForProject(runs);
  const failure = latestRunForProject(runs, hasRunIssue);
  const submitted = experiments.filter((exp) => exp.final_run).length;
  const items = [];
  if (best) {
    items.push({
      label: L("Best run", "最佳运行"),
      title: best.exp_name || best.exp_id || best.run_id,
      detail: `${shortId(best.run_id)} · ${formatDate(best.started_at)}`,
      status: best.status,
      value: valueOrNone(best.reward_value),
      tone: runCardTone(best.status),
      run_id: best.run_id,
    });
  }
  if (latest) {
    items.push({
      label: L("Latest run", "最新运行"),
      title: latest.exp_name || latest.exp_id || latest.run_id,
      detail: `${shortId(latest.run_id)} · ${runDuration(latest)}`,
      status: latest.status,
      value: formatDate(latest.started_at),
      tone: runCardTone(latest.status),
      run_id: latest.run_id,
    });
  }
  if (failure) {
    items.push({
      label: L("Latest issue", "最近问题"),
      title: failure.exp_name || failure.exp_id || failure.run_id,
      detail: failure.failure_reason || warningSummary(failure.warning_codes) || statusLabel(failure.status),
      status: failure.status,
      value: formatDate(failure.started_at),
      tone: "has-risk",
      run_id: failure.run_id,
    });
  }
  items.push({
    label: L("Config context", "配置上下文"),
    title: project.active_valid_config_version ? `${L("active config", "活动配置")} v${project.active_valid_config_version}` : L("No active validation", "无活动验证"),
    detail: source ? `${valueOrNone(source.name || source.source_id)} · ${shortId(source.source_commit || source.tree_hash)}` : L("No source rows recorded", "未记录来源"),
    status: validation ? validation.status : project.status,
    value: `${submitted}/${experiments.length} ${L("submitted", "已提交")}`,
    tone: validation ? runCardTone(validation.status) : "",
  });
  return `
    <div class="highlight-list">
      ${items.map(projectHighlightItem).join("")}
    </div>
  `;
}

function wireProjectHighlights(container = document) {
  for (const item of container.querySelectorAll("[data-highlight-run-id]")) {
    item.addEventListener("click", () => showRun(item.dataset.highlightRunId));
  }
  for (const item of container.querySelectorAll("[data-highlight-log-id]")) {
    item.addEventListener("click", () => showLog(item.dataset.highlightLogId));
  }
  for (const item of container.querySelectorAll("[data-highlight-artifact-id]")) {
    item.addEventListener("click", () => showArtifact(item.dataset.highlightArtifactId));
  }
}

function alignDetailTabBody(container) {
  const content = container.closest(".detail-content");
  const body = document.getElementById("project-tab-body");
  if (!content || !body) return;
  const tabsRect = container.getBoundingClientRect();
  const bodyRect = body.getBoundingClientRect();
  const targetTop = tabsRect.bottom + 12;
  if (bodyRect.top < targetTop) {
    content.scrollTop += bodyRect.top - targetTop;
  }
}

function focusTabButton(button) {
  setTimeout(() => button.focus({ preventScroll: true }), 0);
}

function wireDetailTabs(container, renderTab) {
  const buttons = Array.from(container.querySelectorAll("[role='tab']"));
  const activate = (button, { focus = false } = {}) => {
    renderTab(button.dataset.tab);
    alignDetailTabBody(container);
    requestAnimationFrame(() => {
      alignDetailTabBody(container);
      if (focus) focusTabButton(button);
    });
  };
  for (const button of buttons) {
    button.addEventListener("click", () => activate(button));
    button.addEventListener("keydown", (event) => {
      const currentIndex = buttons.indexOf(button);
      let nextIndex = currentIndex;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        nextIndex = (currentIndex + 1) % buttons.length;
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
      } else if (event.key === "Home") {
        nextIndex = 0;
      } else if (event.key === "End") {
        nextIndex = buttons.length - 1;
      } else {
        return;
      }
      event.preventDefault();
      activate(buttons[nextIndex], { focus: true });
    });
  }
}

function experimentHighlightsHtml(detail, direction) {
  const exp = detail.experiment || {};
  const runs = detail.runs || [];
  const best = bestRunForRuns(runs, direction);
  const latest = exp.latest_run || latestRunForProject(runs);
  const final = exp.final_run || null;
  const failure = latestRunForProject(runs, hasRunIssue);
  const items = [];
  if (best) {
    items.push({
      label: L("Best run", "最佳运行"),
      title: best.run_id,
      detail: `${formatDate(best.started_at)} · ${runDuration(best)}`,
      status: best.status,
      value: valueOrNone(best.reward_value),
      tone: runCardTone(best.status),
      run_id: best.run_id,
    });
  }
  if (latest) {
    items.push({
      label: L("Latest run", "最新运行"),
      title: latest.run_id,
      detail: `${formatDate(latest.started_at)} · ${runDuration(latest)}`,
      status: latest.status,
      value: valueOrNone(latest.reward_value),
      tone: runCardTone(latest.status),
      run_id: latest.run_id,
    });
  }
  if (final) {
    items.push({
      label: L("Final run", "最终运行"),
      title: final.run_id,
      detail: exp.final_commit ? shortId(exp.final_commit) : L("submitted final run", "已提交最终运行"),
      status: final.status,
      value: valueOrNone(final.reward_value),
      tone: runCardTone(final.status),
      run_id: final.run_id,
    });
  }
  if (failure) {
    items.push({
      label: L("Latest issue", "最近问题"),
      title: failure.run_id,
      detail: failure.failure_reason || warningSummary(failure.warning_codes) || statusLabel(failure.status),
      status: failure.status,
      value: formatDate(failure.started_at),
      tone: "has-risk",
      run_id: failure.run_id,
    });
  }
  items.push({
    label: L("Bound context", "绑定上下文"),
    title: exp.bound_config_version ? `${L("config", "配置")} v${exp.bound_config_version}` : L("No bound config", "无绑定配置"),
    detail: `${valueOrNone(exp.source_id)} · ${statusLabel(exp.worktree_state || "none")}`,
    status: exp.status,
    value: `${runs.length} ${L("runs", "运行")}`,
    tone: exp.worktree_state === "active" ? "is-good" : "",
  });
  return `
    <div class="highlight-list">
      ${items.map(projectHighlightItem).join("")}
    </div>
  `;
}

function wireExperimentHighlights(container = document) {
  wireProjectHighlights(container);
}

function primaryLogForRun(logs) {
  return [...(logs || [])].sort((a, b) => {
    const hiddenRank = Number(Boolean(b.hidden)) - Number(Boolean(a.hidden));
    const streamRank = String(a.stream || "").localeCompare(String(b.stream || ""));
    return hiddenRank || streamRank || String(b.created_at || "").localeCompare(String(a.created_at || ""));
  })[0];
}

function primaryArtifactForRun(artifacts) {
  return [...(artifacts || [])].sort((a, b) => {
    const capturedRank = Number(b.status === "captured") - Number(a.status === "captured");
    return capturedRank || Number(b.size_bytes || 0) - Number(a.size_bytes || 0) || String(a.relative_path || "").localeCompare(String(b.relative_path || ""));
  })[0];
}

function runHighlightsHtml(detail) {
  const run = detail.run || {};
  const logs = detail.logs || [];
  const artifacts = detail.artifacts || [];
  const warningCount = (run.warning_codes || []).length;
  const primaryLog = primaryLogForRun(logs);
  const primaryArtifact = primaryArtifactForRun(artifacts);
  const issueText = run.failure_reason
    || (warningCount ? warningSummary(run.warning_codes) : "")
    || L("Clean run", "无异常");
  const items = [
    {
      label: L("Outcome", "结果"),
      title: statusLabel(run.status || "none"),
      detail: `${L("exit", "退出码")} ${valueOrNone(run.exit_code)} · ${runDuration(run)}`,
      status: run.status,
      value: valueOrNone(run.reward_value),
      tone: runCardTone(run.status),
    },
    {
      label: L("Diagnostics", "诊断"),
      title: issueText,
      detail: `${runnerCompactSummary(run.runner)} · ${statusLabel(run.reward_parse_status || "none")}`,
      status: hasRunIssue(run) ? run.status : "",
      value: warningCount ? `${warningCount} ${L("warnings", "警告")}` : "",
      tone: hasRunIssue(run) ? "has-risk" : "",
    },
    {
      label: L("Commit context", "提交上下文"),
      title: shortId(run.commit_sha || statusLabel("none")),
      detail: `${projectName(run.project_id)} · ${valueOrNone(run.exp_name || run.exp_id)}`,
      value: run.config_version ? `v${run.config_version}` : "",
    },
  ];
  if (primaryLog) {
    items.push({
      label: primaryLog.hidden ? L("Primary hidden log", "主要隐藏日志") : L("Primary log", "主要日志"),
      title: primaryLog.stream || primaryLog.log_id,
      detail: primaryLog.preview_text || shortId(primaryLog.log_id),
      status: primaryLog.hidden ? "hidden" : "visible",
      value: formatBytes(primaryLog.stored_bytes || primaryLog.size_bytes),
      tone: primaryLog.hidden ? "is-running" : "",
      log_id: primaryLog.log_id,
    });
  }
  if (primaryArtifact) {
    items.push({
      label: L("Primary artifact", "主要产物"),
      title: primaryArtifact.relative_path || primaryArtifact.artifact_id,
      detail: `${statusLabel(primaryArtifact.status)} · ${formatBytes(primaryArtifact.size_bytes)}`,
      status: primaryArtifact.status,
      value: artifactKind(primaryArtifact.relative_path),
      tone: primaryArtifact.status === "error" ? "has-risk" : "",
      artifact_id: primaryArtifact.artifact_id,
    });
  }
  return `
    <div class="highlight-list">
      ${items.map(projectHighlightItem).join("")}
    </div>
  `;
}

function wireRunHighlights(container = document) {
  wireProjectHighlights(container);
}

function logHighlightsHtml(log, payload, loadedContent) {
  const loadedBytes = new TextEncoder().encode(String(loadedContent || "")).length;
  const lineCount = String(loadedContent || "").split(/\r?\n/).filter((line) => line.length).length;
  const items = [
    {
      label: L("Stream", "日志流"),
      title: valueOrNone(log.stream),
      detail: `${log.hidden ? statusLabel("hidden") : statusLabel("visible")} · ${log.truncated ? L("truncated", "已截断") : L("complete record", "完整记录")}`,
      status: log.hidden ? "hidden" : "visible",
      value: `${lineCount} ${L("lines", "行")}`,
      tone: log.hidden ? "is-running" : "",
    },
    {
      label: L("Loaded bytes", "已加载字节"),
      title: `${formatBytes(loadedBytes)} / ${formatBytes(payload.size || log.size_bytes)}`,
      detail: payload.next_offset === null ? L("all available content loaded", "已加载全部可用内容") : L("more content available", "还有内容可加载"),
      value: formatBytes(log.stored_bytes),
    },
    {
      label: L("Run / validation", "运行/验证"),
      title: shortId(log.run_id || log.validation_id || statusLabel("none")),
      detail: `${projectName(log.project_id)} · ${formatDate(log.created_at)}`,
      value: log.run_id ? L("open run", "打开运行") : "",
      run_id: log.run_id,
    },
  ];
  return `<div class="highlight-list evidence-highlight-list">${items.map(projectHighlightItem).join("")}</div>`;
}

function artifactHighlightsHtml(artifact, previewPayload) {
  const preview = previewPayload || {};
  const items = [
    {
      label: L("Preview", "预览"),
      title: statusLabel(preview.kind || "none"),
      detail: preview.content_type || artifact.relative_path || artifact.artifact_id,
      status: artifact.status,
      value: artifactKind(artifact.relative_path),
      tone: artifact.status === "error" ? "has-risk" : "",
    },
    {
      label: L("File", "文件"),
      title: artifact.relative_path || artifact.artifact_id,
      detail: `${valueOrNone(artifact.root)} · ${formatBytes(artifact.size_bytes)}`,
      status: artifact.status,
      value: formatBytes(artifact.size_bytes),
      tone: artifact.status === "error" ? "has-risk" : "",
    },
    {
      label: L("Run / validation", "运行/验证"),
      title: shortId(artifact.run_id || artifact.validation_id || statusLabel("none")),
      detail: `${projectName(artifact.project_id)} · ${valueOrNone(artifact.capture_error || artifact.content_hash)}`,
      value: artifact.run_id ? L("open run", "打开运行") : "",
      run_id: artifact.run_id,
    },
  ];
  return `<div class="highlight-list evidence-highlight-list">${items.map(projectHighlightItem).join("")}</div>`;
}

function wireEvidenceHighlights(container = document) {
  wireProjectHighlights(container);
}

function projectContextFacts(detail) {
  const project = detail.project || {};
  const facts = [
    [L("Runner", "运行器"), valueOrNone(project.runner_type)],
    [L("Reward", "奖励"), `${valueOrNone(project.reward_type)} / ${valueOrNone(project.reward_direction || "maximize")}`],
    [L("Visibility", "可见性"), valueOrNone(project.visibility_scope)],
    [L("Config", "配置"), project.active_valid_config_version ? `v${project.active_valid_config_version}` : statusLabel("none")],
    [L("Updated", "更新"), formatDate(project.updated_at)],
  ];
  return `
    <div class="project-detail-facts">
      ${facts.map(([label, value]) => `
        <span>
          <small>${escapeHtml(label)}</small>
          <strong>${escapeHtml(value)}</strong>
        </span>
      `).join("")}
    </div>
  `;
}

function relatedActions(record) {
  const actions = [];
  const seen = new Set();
  const addAction = (kind, id, label) => {
    if (!id) return;
    const key = `${kind}:${id}`;
    if (seen.has(key)) return;
    seen.add(key);
    actions.push(`<button class="secondary-button related-action" type="button" data-${kind}-id="${escapeHtml(id)}">${escapeHtml(label)}</button>`);
  };
  if (record.project_id) {
    addAction("project", record.project_id, L("Open project", "打开项目"));
  }
  if (record.exp_id) {
    addAction("exp", record.exp_id, L("Open experiment", "打开实验"));
  }
  if (record.run_id) {
    addAction("run", record.run_id, L("Open run", "打开运行"));
  }
  if (record.object_type === "project") {
    addAction("project", record.object_id, L("Open project", "打开项目"));
  }
  if (record.object_type === "experiment") {
    addAction("exp", record.object_id, L("Open experiment", "打开实验"));
  }
  if (record.object_type === "run") {
    addAction("run", record.object_id, L("Open run", "打开运行"));
  }
  return actions.length ? `<div class="entity-actions">${actions.join("")}</div>` : "";
}

function contextSummary(kind, record, facts, statusHtml = "") {
  return `
    <div class="entity-summary compact-entity-summary">
      <div>
        <div class="metric-label">${escapeHtml(kind)}</div>
        <div class="project-detail-title">${idChip(record.log_id || record.artifact_id || record.run_id || record.exp_id || record.project_id)}</div>
        <div class="summary-note">${escapeHtml(projectName(record.project_id))}</div>
        <div class="project-detail-facts">
          ${facts.map(([label, value]) => `
            <span>
              <small>${escapeHtml(label)}</small>
              <strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong>
            </span>
          `).join("")}
        </div>
      </div>
      <div class="entity-summary-side">
        ${statusHtml}
        ${relatedActions(record)}
      </div>
    </div>
  `;
}

function wireRelatedActions(container = document) {
  for (const button of container.querySelectorAll("[data-project-id].related-action")) {
    button.addEventListener("click", () => showProject(button.dataset.projectId));
  }
  for (const button of container.querySelectorAll("[data-exp-id].related-action")) {
    button.addEventListener("click", () => showExperiment(button.dataset.expId));
  }
  for (const button of container.querySelectorAll("[data-run-id].related-action")) {
    button.addEventListener("click", () => showRun(button.dataset.runId));
  }
}

function countsToChartData(counts) {
  const entries = Object.entries(counts || {});
  return {
    labels: entries.map(([name]) => statusLabel(name)),
    values: entries.map(([, value]) => value),
  };
}

async function loadCore() {
  const [summary, projectsPayload, experimentsPayload, runsPayload] = await Promise.all([
    api("/api/summary"),
    api("/api/projects?limit=200"),
    api("/api/experiments?limit=200"),
    api("/api/runs?limit=200"),
  ]);
  state.summary = summary;
  state.refreshSeconds = state.summary.refresh_seconds ?? state.refreshSeconds;
  state.projects = projectsPayload.projects || state.summary.projects || [];
  state.experiments = experimentsPayload.experiments || [];
  state.runs = runsPayload.runs || [];
  state.pages.projects = projectsPayload.page || state.summary.projects_page || null;
  state.pages.experiments = experimentsPayload.page || null;
  state.pages.runs = runsPayload.page || null;
  state.projectDetails.clear();
  state.assetScope = null;
  state.lastLoadedAt = new Date();
  if (!state.currentProjectId && state.projects.length) {
    state.currentProjectId = state.projects[0].project_id;
  }
  const projectIds = new Set(state.projects.map((project) => project.project_id));
  if (state.assetProjectId !== ASSET_ALL_PROJECTS && !projectIds.has(state.assetProjectId)) {
    state.assetProjectId = ASSET_ALL_PROJECTS;
    localStorage.setItem("alab-dashboard-asset-project", state.assetProjectId);
  }
}

function overviewView() {
  const counts = state.summary.counts || {};
  const projectsTotal = sumCounts(counts.projects);
  const experimentsTotal = sumCounts(counts.experiments);
  const runsTotal = sumCounts(counts.runs);
  const validationsTotal = sumCounts(counts.validations);
  const failuresTotal = statusTotal(counts.runs, ["failed", "error", "timeout", "interrupted"]);
  const artifactTotal = sumCounts(counts.artifacts);
  const logTotal = sumCounts(counts.logs);
  const activeLocks = counts.active_locks || 0;
  const feedback = counts.feedback || 0;
  const expChart = countsToChartData(counts.experiments);
  return `
    <section class="overview-hero">
      <div class="home-strip-main">
        <span class="home-status ${failuresTotal ? "warn" : "good"}">
          <span class="home-status-dot" aria-hidden="true"></span>
          <span class="home-status-text">${escapeHtml(failuresTotal ? L("Needs attention", "需关注") : L("Healthy", "健康"))}</span>
        </span>
        <span class="home-path-group">
          <span class="home-label">${escapeHtml(L("ALab home", "ALab home"))}</span>
          <code title="${escapeHtml(state.summary.home_path || "")}">${escapeHtml(state.summary.home_path || "")}</code>
        </span>
      </div>
      <div class="hero-facts">
        <span>${escapeHtml(L("Refresh", "刷新"))}: ${state.refreshSeconds > 0 ? `${state.refreshSeconds}s` : L("manual", "手动")}</span>
        <span>${escapeHtml(L("Local read-only", "本地只读"))}</span>
      </div>
    </section>
    <div class="grid cards dashboard-kpis">
      ${metric(L("Projects", "项目"), projectsTotal, statusCountText(counts.projects, ["valid", "invalid"]))}
      ${metric(L("Experiments", "实验"), experimentsTotal, statusCountText(counts.experiments, ["open", "closed"]))}
      ${metric(L("Runs", "运行"), runsTotal, `${passRateFromCounts(counts.runs)} ${L("pass rate", "通过率")}`)}
      ${metric(L("Failures", "失败"), failuresTotal, ["failed", "error", "timeout", "interrupted"].map(statusLabel).join(" / "))}
      ${metric(L("Artifacts", "产物"), artifactTotal, `${logTotal} ${L("log streams", "日志流")}`)}
      ${metric(L("System", "系统"), activeLocks, `${counts.cache_entries || 0} ${L("active cache entries", "活跃缓存条目")}`)}
      ${metric(L("Validation", "验证"), validationsTotal, `${(counts.validations || {}).passed || 0} ${statusLabel("passed")}`)}
      ${metric(L("Feedback", "反馈"), feedback, L("HOME entries", "本地反馈记录"))}
    </div>
    <div class="grid two overview-primary-grid">
      ${panel(L("Run activity", "运行活动"), '<div class="chart-box compact-chart"><canvas id="overview-run-activity-chart"></canvas></div>')}
      ${panel(L("Attention queue", "关注队列"), attentionPanelHtml())}
    </div>
    <div class="grid two overview-secondary-grid">
      ${panel(L("Experiment status", "实验状态"), `${statusBars(counts.experiments, ["open", "closed", "archived"])}<div class="chart-box compact-chart"><canvas id="exp-status-chart"></canvas></div>`)}
      ${panel(L("Run status", "运行状态"), statusBars(counts.runs, ["passed", "failed", "error", "timeout", "interrupted", "running"]))}
    </div>
    ${panel(L("Project health", "项目健康"), '<div id="project-card-meta"></div><div class="project-card-grid bounded-list" id="project-card-grid"></div>')}
    <div class="grid two">
      ${panel(L("Failure reasons", "失败原因"), failureReasonsHtml())}
      ${panel(L("Recent failures", "最近失败"), '<div id="recent-failures-meta"></div><div id="recent-failures" class="failure-feed compact-scroll"></div>')}
    </div>
    ${panel(L("Recent activity", "最近活动"), '<div id="recent-activity-meta"></div><div id="recent-activity" class="audit-feed compact-feed"></div>')}
  `;
}

function afterOverview() {
  const expData = countsToChartData(state.summary.counts.experiments);
  renderRunActivityChart("overview-run-activity-chart", state.runs || []);
  renderChart("exp-status-chart", "bar", expData.labels, [{ label: L("experiments", "实验"), data: expData.values, backgroundColor: "#1f7a8c" }], {
    ariaLabel: L("Experiment count by status.", "按状态统计的实验数量。"),
  });
  const projectCards = document.getElementById("project-card-grid");
  const sortedProjects = [...state.projects].sort((a, b) => {
    const rank = (project) => {
      if (project.status === "invalid") return 0;
      if ((project.counts || {}).failed_runs) return 1;
      if (project.status === "valid") return 2;
      if (project.status === "archived") return 3;
      return 4;
    };
    return rank(a) - rank(b) || String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
  });
  const rankedProjects = bySearch(sortedProjects, [
    "project_id",
    "name",
    "status",
    "runner_type",
    "task",
    "goal",
    (project) => statusLabel(project.status),
    (project) => project.best_run && project.best_run.reward_value,
  ]);
  document.getElementById("project-card-meta").innerHTML = filterMeta(rankedProjects.length, sortedProjects.length);
  projectCards.innerHTML = rankedProjects.map((project) => {
    const counts = project.counts || {};
    const failed = counts.failed_runs || 0;
    const runs = counts.runs || 0;
    const label = openCardLabel(L("project detail", "项目详情"), project.name || project.project_id, project.task || project.goal || project.project_id);
    return `
      <button class="project-card ${failed ? "has-risk" : ""}" type="button" data-project-id="${escapeHtml(project.project_id)}" ${cardLabelAttrs(label)}>
        <span class="project-card-top">
          <strong>${escapeHtml(project.name || project.project_id)}</strong>
          ${statusBadge(project.status)}
        </span>
        <span class="project-card-task">${escapeHtml(project.task || project.goal || project.project_id)}</span>
        <span class="project-card-metrics">
          <span><b>${counts.experiments || 0}</b>${escapeHtml(L("experiments", "实验"))}</span>
          <span><b>${runs}</b>${escapeHtml(L("runs", "运行"))}</span>
          <span><b>${failed}</b>${escapeHtml(L("failures", "失败"))}</span>
          <span><b>${escapeHtml(project.best_run ? project.best_run.reward_value : statusLabel("none"))}</b>${escapeHtml(L("best", "最佳"))}</span>
        </span>
      </button>
    `;
  }).join("");
  for (const card of projectCards.querySelectorAll("[data-project-id]")) {
    card.addEventListener("click", () => showProject(card.dataset.projectId));
  }
  for (const item of document.querySelectorAll("#attention-list [data-project-id]")) {
    item.addEventListener("click", () => showProject(item.dataset.projectId));
  }
  for (const item of document.querySelectorAll("#attention-list [data-run-id]")) {
    item.addEventListener("click", () => showRun(item.dataset.runId));
  }
  for (const item of document.querySelectorAll("#attention-list [data-view]")) {
    item.addEventListener("click", () => {
      navigateToView(item.dataset.view);
    });
  }
  const recentFailuresAll = state.summary.recent_failures || [];
  const recentFailures = bySearch(recentFailuresAll, [
    "run_id",
    "exp_id",
    "exp_name",
    "status",
    "failure_reason",
    "project_id",
    (row) => projectName(row.project_id),
    (row) => statusLabel(row.status),
  ]);
  document.getElementById("recent-failures-meta").innerHTML = filterMeta(recentFailures.length, recentFailuresAll.length);
  const failuresNode = document.getElementById("recent-failures");
  if (!recentFailures.length) {
    failuresNode.innerHTML = emptyHtml();
    wireInlineClearSearch(failuresNode);
  } else {
    failuresNode.innerHTML = recentFailures.map((run) => {
      const label = openCardLabel(L("run detail", "运行详情"), run.run_id, `${projectName(run.project_id)} · ${statusLabel(run.status)}`);
      return `
        <button class="failure-card" type="button" data-run-id="${escapeHtml(run.run_id)}" ${cardLabelAttrs(label)}>
          <span class="failure-card-main">
            <span class="failure-card-top">
              <strong>${escapeHtml(run.exp_name || run.exp_id || run.run_id)}</strong>
              ${statusBadge(run.status)}
            </span>
            <span class="failure-card-project">${escapeHtml(projectName(run.project_id))}</span>
            <span class="failure-card-reason">${escapeHtml(valueOrNone(run.failure_reason))}</span>
            <span class="failure-card-facts">
              <span>${escapeHtml(L("run", "运行"))}: ${idChip(run.run_id)}</span>
              <span>${escapeHtml(L("started", "开始"))}: ${escapeHtml(formatDate(run.started_at))}</span>
            </span>
          </span>
          <span class="failure-card-score">
            <span>${escapeHtml(L("reward", "奖励"))}</span>
            <strong>${escapeHtml(valueOrNone(run.reward_value))}</strong>
          </span>
        </button>
      `;
    }).join("");
    for (const card of failuresNode.querySelectorAll("[data-run-id]")) {
      card.addEventListener("click", () => showRun(card.dataset.runId));
    }
  }
  const recentActivityAll = (state.summary.recent_activity || []).slice(0, 8);
  const recentActivity = bySearch(recentActivityAll, [
    "action",
    "object_type",
    "object_id",
    "project_id",
    (row) => projectName(row.project_id),
  ]);
  document.getElementById("recent-activity-meta").innerHTML = filterMeta(recentActivity.length, recentActivityAll.length);
  const recentActivityNode = document.getElementById("recent-activity");
  recentActivityNode.innerHTML = auditCardsHtml(recentActivity);
  wireAuditCards(recentActivityNode, recentActivity);
}

function projectsView() {
  const counts = (state.summary && state.summary.counts) || {};
  const runnerCount = uniqueCount(state.projects, (project) => project.runner_type);
  const failedProjects = state.projects.filter((project) => Number((project.counts || {}).failed_runs || 0) > 0).length;
  const activeValidated = state.projects.filter((project) => project.active_valid_config_version).length;
  const portfolioNote = `${state.projects.length} ${L("projects", "项目")} · ${runnerCount} ${L("runner types", "运行器类型")} · ${activeValidated} ${L("validated configs", "已验证配置")} · ${failedProjects} ${L("with failures", "有失败记录")}`;
  return `
    <div class="grid two project-summary-grid">
      ${panel(L("Project portfolio", "项目组合"), `${statusBars(counts.projects, ["valid", "invalid", "archived"])}<div class="summary-note">${escapeHtml(portfolioNote)}</div>`)}
      ${panel(L("Run exposure", "运行暴露"), `${statusBars(counts.runs, ["passed", "failed", "error", "timeout", "interrupted", "running"])}<div class="summary-note">${escapeHtml(L("Rewards are only compared within each project because reward policies may differ.", "奖励值只在项目内比较，因为不同项目的 reward policy 可能不同。"))}</div>`)}
    </div>
    <div class="grid three project-signals">
      ${panel(L("Needs attention", "需要关注"), '<div id="project-signal-attention"></div>')}
      ${panel(L("Most active", "最活跃"), '<div id="project-signal-activity"></div>')}
      ${panel(L("Largest output", "最多输出"), '<div id="project-signal-output"></div>')}
    </div>
    ${panel(L("Projects", "项目"), '<div id="projects-controls"></div><div id="projects-meta"></div><div id="projects-cards" class="project-card-grid bounded-list"></div>')}
  `;
}

function afterProjects() {
  const options = projectFilterOptions(state.projects);
  const sortOptions = projectSortOptions();
  const filter = activeFilter("projects", options);
  const sort = activeSort("projects", sortOptions);
  const filtered = filterProjects(state.projects, filter);
  const rows = sortProjects(bySearch(filtered, ["project_id", "name", "status", "runner_type", "task", "goal"]), sort);
  const controlsNode = document.getElementById("projects-controls");
  controlsNode.innerHTML = listControls("projects", options, sortOptions);
  wireQuickFilters(controlsNode, "projects");
  wireSortControl(controlsNode, "projects", sortOptions);
  document.getElementById("project-signal-attention").innerHTML = projectSignalListHtml(rows, "attention");
  document.getElementById("project-signal-activity").innerHTML = projectSignalListHtml(rows, "activity");
  document.getElementById("project-signal-output").innerHTML = projectSignalListHtml(rows, "output");
  for (const item of document.querySelectorAll(".project-signals [data-project-id]")) {
    item.addEventListener("click", () => showProject(item.dataset.projectId));
  }
  document.getElementById("projects-meta").innerHTML = filterMeta(rows.length, state.projects.length, [quickFilterLabel(options, filter), quickSortLabel(sortOptions, sort)].filter(Boolean).join(" · "), state.pages.projects);
  const target = document.getElementById("projects-cards");
  if (!rows.length) {
    target.innerHTML = emptyHtml();
    wireInlineClearSearch(target);
    return;
  }
  target.innerHTML = rows.map((project) => {
    const counts = project.counts || {};
    const best = project.best_run ? valueOrNone(project.best_run.reward_value) : statusLabel("none");
    const validation = project.active_valid_config_version ? `v${project.active_valid_config_version}` : statusLabel("none");
    const hasRisk = Number(counts.failed_runs || 0) > 0 || project.status === "invalid";
    const label = openCardLabel(L("project detail", "项目详情"), project.name || project.project_id, project.task || project.goal || project.project_id);
    return `
      <button class="project-card ${hasRisk ? "has-risk" : ""}" type="button" data-project-id="${escapeHtml(project.project_id)}" ${cardLabelAttrs(label)}>
        <span class="project-card-top">
          <strong>${escapeHtml(project.name || project.project_id)}</strong>
          ${statusBadge(project.status)}
        </span>
        <span class="project-card-task">${escapeHtml(project.task || project.goal || project.project_id)}</span>
        <span class="project-card-metrics">
          <span><b>${escapeHtml(valueOrNone(project.runner_type))}</b>${escapeHtml(L("runner", "运行器"))}</span>
          <span><b>${escapeHtml(validation)}</b>${escapeHtml(L("validation", "验证"))}</span>
          <span><b>${escapeHtml(counts.experiments || 0)}</b>${escapeHtml(L("experiments", "实验"))}</span>
          <span><b>${escapeHtml(counts.runs || 0)}</b>${escapeHtml(L("runs", "运行"))}</span>
          <span><b>${escapeHtml(counts.failed_runs || 0)}</b>${escapeHtml(L("failed", "失败"))}</span>
          <span><b>${escapeHtml(best)}</b>${escapeHtml(L("best", "最佳"))}</span>
          <span><b>${escapeHtml(counts.artifacts || 0)}</b>${escapeHtml(L("artifacts", "产物"))}</span>
          <span><b>${escapeHtml(formatDate(project.updated_at))}</b>${escapeHtml(L("updated", "更新"))}</span>
        </span>
      </button>
    `;
  }).join("");
  for (const card of target.querySelectorAll("[data-project-id]")) {
    card.addEventListener("click", () => showProject(card.dataset.projectId));
  }
}

function experimentsView() {
  const counts = (state.summary && state.summary.counts) || {};
  const submitted = state.experiments.filter((exp) => exp.final_run).length;
  const activeWorktrees = state.experiments.filter((exp) => exp.worktree_state === "active").length;
  return `
    <div class="grid cards">
      ${metric(L("Experiments", "实验"), state.experiments.length, `${(counts.experiments || {}).open || 0} ${statusLabel("open")}`)}
      ${metric(L("Submitted", "已提交"), submitted, L("experiments with final run", "包含最终运行的实验"))}
      ${metric(L("Active worktrees", "活跃工作树"), activeWorktrees, L("current worktree_state", "当前工作树状态"))}
      ${metric(L("Tagged", "带标签"), state.experiments.filter((exp) => (exp.tags || []).length).length, L("with searchable tags", "可搜索标签"))}
    </div>
    <div class="grid three experiments-insights">
      ${panel(L("Experiment status", "实验状态"), statusBars(counts.experiments, ["open", "closed", "archived"]))}
      ${panel(L("Worktree and latest run", "工作树与最新运行"), '<div class="resource-insights"><div class="summary-note">' + escapeHtml(L("Worktree", "工作树")) + '</div><div id="experiments-worktree-mix"></div><div class="summary-note">' + escapeHtml(L("Latest run", "最新运行")) + '</div><div id="experiments-latest-run-mix"></div></div>')}
      ${panel(L("Tags and projects", "标签与项目"), '<div class="resource-insights"><div class="summary-note">' + escapeHtml(L("Tags", "标签")) + '</div><div id="experiments-tag-mix"></div><div class="summary-note">' + escapeHtml(L("Projects", "项目")) + '</div><div id="experiments-project-mix"></div></div>')}
    </div>
    ${panel(L("Experiments", "实验"), '<div id="experiments-controls"></div><div id="experiments-meta"></div><div id="experiments-cards" class="experiment-card-grid bounded-list"></div>')}
  `;
}

function afterExperiments() {
  const options = experimentFilterOptions(state.experiments);
  const sortOptions = experimentSortOptions();
  const filter = activeFilter("experiments", options);
  const sort = activeSort("experiments", sortOptions);
  const filtered = filterExperiments(state.experiments, filter);
  const rows = sortExperiments(bySearch(filtered, ["exp_id", "name", "status", "project_id", "tags", "goal", (row) => projectName(row.project_id)]), sort);
  const controlsNode = document.getElementById("experiments-controls");
  controlsNode.innerHTML = listControls("experiments", options, sortOptions);
  wireQuickFilters(controlsNode, "experiments");
  wireSortControl(controlsNode, "experiments", sortOptions);
  document.getElementById("experiments-worktree-mix").innerHTML = countListHtml(countBy(rows, (exp) => exp.worktree_state), statusLabel);
  document.getElementById("experiments-latest-run-mix").innerHTML = statusBars(
    countBy(rows, (exp) => exp.latest_run ? exp.latest_run.status : "none"),
    ["passed", "failed", "error", "timeout", "interrupted", "running", "none"],
  );
  document.getElementById("experiments-tag-mix").innerHTML = countListHtml(countExperimentTags(rows));
  document.getElementById("experiments-project-mix").innerHTML = countListHtml(countBy(rows, (exp) => projectName(exp.project_id)));
  document.getElementById("experiments-meta").innerHTML = filterMeta(rows.length, state.experiments.length, [quickFilterLabel(options, filter), quickSortLabel(sortOptions, sort)].filter(Boolean).join(" · "), state.pages.experiments);
  const target = document.getElementById("experiments-cards");
  target.innerHTML = experimentCardsHtml(rows);
  wireExperimentCards(target);
}

function experimentCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((exp) => {
    const latestStatus = exp.latest_run ? exp.latest_run.status : "none";
    const latestReward = exp.latest_run ? valueOrNone(exp.latest_run.reward_value) : statusLabel("none");
    const finalReward = exp.final_run ? valueOrNone(exp.final_run.reward_value) : statusLabel("none");
    const hasRisk = ["failed", "error", "timeout", "interrupted"].includes(latestStatus);
    const label = openCardLabel(L("experiment detail", "实验详情"), exp.name || exp.exp_id, projectName(exp.project_id));
    return `
      <button class="experiment-card ${hasRisk ? "has-risk" : ""}" type="button" data-exp-id="${escapeHtml(exp.exp_id)}" ${cardLabelAttrs(label)}>
        <span class="experiment-card-header">
          <strong>${escapeHtml(exp.name || exp.exp_id)}</strong>
          ${statusBadge(exp.status)}
        </span>
        <span class="experiment-card-project">${escapeHtml(projectName(exp.project_id))}</span>
        <span class="experiment-card-goal">${escapeHtml(exp.goal || exp.branch_name || exp.exp_id)}</span>
        <span class="experiment-card-tags">${tagList(exp.tags)}</span>
        <span class="experiment-card-facts">
          <span><b>${escapeHtml(exp.run_count || 0)}</b>${escapeHtml(L("runs", "运行"))}</span>
          <span><b>${statusBadge(latestStatus)}</b>${escapeHtml(L("latest", "最新"))}</span>
          <span><b>${escapeHtml(latestReward)}</b>${escapeHtml(L("latest reward", "最新奖励"))}</span>
          <span><b>${escapeHtml(finalReward)}</b>${escapeHtml(L("final", "最终"))}</span>
          <span><b>${escapeHtml(statusLabel(exp.worktree_state || "none"))}</b>${escapeHtml(L("worktree", "工作树"))}</span>
        </span>
        <span class="experiment-card-updated">${escapeHtml(formatDate(exp.updated_at))}</span>
      </button>
    `;
  }).join("");
}

function wireExperimentCards(container = document) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-exp-id]")) {
    card.addEventListener("click", () => showExperiment(card.dataset.expId));
  }
}

function runCardTone(status) {
  const text = escapeText(status);
  if (["failed", "error", "timeout", "interrupted"].includes(text)) return "has-risk";
  if (text === "running") return "is-running";
  if (text === "passed") return "is-good";
  return "";
}

function timelineStep(label, value, note = "", tone = "") {
  return `
    <div class="timeline-step ${escapeHtml(tone)}">
      <span class="timeline-step-label">${escapeHtml(label)}</span>
      <strong class="timeline-step-value">${escapeHtml(value)}</strong>
      ${note ? `<span class="timeline-step-note">${escapeHtml(note)}</span>` : ""}
    </div>
  `;
}

function runTimelineHtml(run) {
  const tone = runCardTone(run.status);
  return `
    <div class="timeline-strip">
      ${timelineStep(L("Started", "开始"), formatDate(run.started_at), valueOrNone(run.commit_sha), tone)}
      ${timelineStep(L("Ended", "结束"), formatDate(run.ended_at), statusLabel(run.status || "none"), tone)}
      ${timelineStep(L("Duration", "耗时"), runDuration(run), runnerSummary(run.runner), tone)}
      ${timelineStep(L("Reward", "奖励"), valueOrNone(run.reward_value), statusLabel(run.reward_parse_status || "none"), tone)}
      ${timelineStep(L("Exit", "退出码"), valueOrNone(run.exit_code), warningSummary(run.warning_codes), tone)}
    </div>
  `;
}

function experimentTimelineHtml(exp) {
  const latest = exp.latest_run || {};
  const final = exp.final_run || {};
  return `
    <div class="timeline-strip experiment-timeline">
      ${timelineStep(L("Created", "创建"), formatDate(exp.created_at), valueOrNone(exp.source_id))}
      ${timelineStep(
        L("Latest run", "最新运行"),
        latest.run_id ? valueOrNone(latest.reward_value) : statusLabel("none"),
        latest.run_id ? `${statusLabel(latest.status)} · ${shortId(latest.run_id)}` : L("no runs yet", "尚无运行"),
        runCardTone(latest.status),
      )}
      ${timelineStep(
        L("Final run", "最终运行"),
        final.run_id ? valueOrNone(final.reward_value) : statusLabel("none"),
        final.run_id ? `${statusLabel(final.status)} · ${shortId(final.run_id)}` : L("not submitted", "未提交"),
        runCardTone(final.status),
      )}
      ${timelineStep(L("Worktree", "工作树"), statusLabel(exp.worktree_state || "none"), valueOrNone(exp.branch_name))}
      ${timelineStep(L("Updated", "更新"), formatDate(exp.updated_at), statusLabel(exp.status || "none"))}
    </div>
  `;
}

function runCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((run) => {
    const warning = warningSummary(run.warning_codes);
    const reason = run.failure_reason || (warning === statusLabel("none") ? "" : warning);
    const label = openCardLabel(L("run detail", "运行详情"), run.run_id, `${projectName(run.project_id)} · ${statusLabel(run.status)}`);
    return `
      <button class="run-card ${runCardTone(run.status)}" type="button" data-run-id="${escapeHtml(run.run_id)}" ${cardLabelAttrs(label)}>
        <span class="run-card-main">
          <span class="run-card-top">
            <strong>${escapeHtml(run.exp_name || run.exp_id || run.run_id)}</strong>
            ${statusBadge(run.status)}
          </span>
          <span class="run-card-project">${escapeHtml(projectName(run.project_id))}</span>
          <span class="run-card-id">${idChip(run.run_id)}</span>
          <span class="run-card-reason">${escapeHtml(reason || L("Clean run", "无异常"))}</span>
          <span class="run-card-facts">
            <span>${factValue(formatDate(run.started_at), 22)}${escapeHtml(L("started", "开始"))}</span>
            <span>${factValue(runDuration(run), 18)}${escapeHtml(L("duration", "耗时"))}</span>
            <span>${factValue(runnerCompactSummary(run.runner), 24, runnerSummary(run.runner))}${escapeHtml(L("runner", "运行器"))}</span>
            <span>${factValue(valueOrNone(run.exit_code), 12)}${escapeHtml(L("exit", "退出码"))}</span>
          </span>
        </span>
        <span class="run-card-score">
          <span>${escapeHtml(L("reward", "奖励"))}</span>
          <strong>${escapeHtml(valueOrNone(run.reward_value))}</strong>
        </span>
      </button>
    `;
  }).join("");
}

function wireRunCards(container = document) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-run-id]")) {
    card.addEventListener("click", () => showRun(card.dataset.runId));
  }
}

function runsView() {
  const counts = (state.summary && state.summary.counts) || {};
  const rewardRuns = state.runs.filter((run) => run.reward_value !== null && run.reward_value !== undefined).length;
  const warnings = state.runs.filter((run) => (run.warning_codes || []).length).length;
  return `
    <div class="grid cards">
      ${metric(L("Runs", "运行"), state.runs.length, `${passRateFromCounts(counts.runs)} ${L("pass rate", "通过率")}`)}
      ${metric(L("Rewards parsed", "已解析奖励"), rewardRuns, L("runs with reward_value", "包含奖励值的运行"))}
      ${metric(L("Warnings", "警告"), warnings, L("runs with warning codes", "包含警告代码的运行"))}
      ${metric(L("Failures", "失败"), statusTotal(counts.runs, ["failed", "error", "timeout", "interrupted"]), L("needs attention", "需要关注"))}
    </div>
    <div class="grid three runs-insights">
      ${panel(L("Run activity", "运行活动"), '<div class="chart-box compact-chart"><canvas id="runs-activity-chart"></canvas></div>')}
      ${panel(L("Failure reasons", "失败原因"), '<div id="runs-failure-reasons"></div>')}
      ${panel(L("Run status", "运行状态"), statusBars(counts.runs, ["passed", "failed", "error", "timeout", "interrupted", "running"]))}
    </div>
    ${panel(L("Run timeline", "运行时间线"), '<div id="runs-controls"></div><div id="runs-meta"></div><div id="runs-cards" class="run-card-grid bounded-list"></div>')}
    ${panel(L("Runner and project mix", "运行器与项目分布"), '<div class="resource-insights runs-mix-insights"><div><div class="summary-note">' + escapeHtml(L("Runner", "运行器")) + '</div><div id="runs-runner-mix"></div></div><div><div class="summary-note">' + escapeHtml(L("Project", "项目")) + '</div><div id="runs-project-mix"></div></div></div>')}
  `;
}

function afterRuns() {
  const options = runFilterOptions(state.runs);
  const sortOptions = runSortOptions();
  const filter = activeFilter("runs", options);
  const sort = activeSort("runs", sortOptions);
  const filtered = filterRuns(state.runs, filter);
  const rows = sortRuns(bySearch(filtered, ["run_id", "exp_id", "exp_name", "status", "project_id", "failure_reason", "warning_codes", (row) => projectName(row.project_id)]), sort);
  const controlsNode = document.getElementById("runs-controls");
  controlsNode.innerHTML = listControls("runs", options, sortOptions);
  wireQuickFilters(controlsNode, "runs");
  wireSortControl(controlsNode, "runs", sortOptions);
  renderRunActivityChart("runs-activity-chart", rows);
  document.getElementById("runs-failure-reasons").innerHTML = failureReasonsForRunsHtml(rows);
  document.getElementById("runs-runner-mix").innerHTML = countListHtml(countBy(rows, (run) => runnerSummary(run.runner)));
  document.getElementById("runs-project-mix").innerHTML = countListHtml(countBy(rows, (run) => projectName(run.project_id)));
  document.getElementById("runs-meta").innerHTML = filterMeta(rows.length, state.runs.length, [quickFilterLabel(options, filter), quickSortLabel(sortOptions, sort)].filter(Boolean).join(" · "), state.pages.runs);
  const target = document.getElementById("runs-cards");
  target.innerHTML = runCardsHtml(rows);
  wireRunCards(target);
}

function assetProjectSelector() {
  const selected = state.assetProjectId || ASSET_ALL_PROJECTS;
  return `
    <label class="select-shell">
      <span>${escapeHtml(L("Project", "项目"))}</span>
      <select id="asset-project-select">
        <option value="${ASSET_ALL_PROJECTS}" ${selected === ASSET_ALL_PROJECTS ? "selected" : ""}>${escapeHtml(L("All projects", "全部项目"))}</option>
        ${state.projects.map((project) => `<option value="${escapeHtml(project.project_id)}" ${project.project_id === selected ? "selected" : ""}>${escapeHtml(project.name || project.project_id)}</option>`).join("")}
      </select>
    </label>
  `;
}

function assetsView() {
  return `
    <div id="assets-summary" class="grid cards compact-cards"></div>
    <div class="grid two assets-insights">
      ${panel(L("Log streams", "日志流"), '<div id="assets-log-streams"></div>')}
      ${panel(L("Artifact footprint", "产物构成"), '<div class="resource-insights"><div id="assets-artifact-status"></div><div id="assets-artifact-kinds"></div></div>')}
    </div>
    ${panel(L("Logs & Artifacts", "日志与产物"), `<div class="toolbar">${assetProjectSelector()}<div id="assets-scope-note" class="scope-note"></div></div><div id="assets-tabs" class="tabs"></div><div id="assets-controls"></div><div id="assets-meta"></div><div id="assets-body" class="asset-card-grid bounded-list"></div>`)}
  `;
}

async function afterAssets() {
  const scope = await ensureAssetScope();
  document.getElementById("asset-project-select").onchange = async (event) => {
    state.assetProjectId = event.target.value || ASSET_ALL_PROJECTS;
    localStorage.setItem("alab-dashboard-asset-project", state.assetProjectId);
    state.assetScope = null;
    await afterAssets();
  };
  const tabs = document.getElementById("assets-tabs");
  const selectedKind = state.assetKind === "artifacts" ? "artifacts" : "logs";
  tabs.setAttribute("role", "tablist");
  tabs.innerHTML = `<button class="${selectedKind === "logs" ? "active" : ""}" role="tab" aria-selected="${selectedKind === "logs"}" tabindex="${selectedKind === "logs" ? "0" : "-1"}" data-kind="logs">${escapeHtml(L("Logs", "日志"))}</button><button class="${selectedKind === "artifacts" ? "active" : ""}" role="tab" aria-selected="${selectedKind === "artifacts"}" tabindex="${selectedKind === "artifacts" ? "0" : "-1"}" data-kind="artifacts">${escapeHtml(L("Artifacts", "产物"))}</button>`;
  wireAssetTabs(tabs);
  const logs = scope.logs || [];
  const artifacts = scope.artifacts || [];
  document.getElementById("assets-scope-note").textContent = scope.note;
  document.getElementById("assets-summary").innerHTML = [
    metric(L("Projects", "项目"), scope.projectCount, scope.label),
    metric(L("Logs", "日志"), logs.length, `${logs.filter((item) => item.hidden).length} ${statusLabel("hidden")}`),
    metric(L("Artifacts", "产物"), artifacts.length, `${artifacts.filter((item) => item.status === "captured").length} ${statusLabel("captured")}`),
    metric(L("Log bytes", "日志字节"), formatBytes(logs.reduce((total, item) => total + Number(item.stored_bytes || 0), 0)), L("stored", "已存储")),
    metric(L("Artifact bytes", "产物字节"), formatBytes(artifacts.reduce((total, item) => total + Number(item.size_bytes || 0), 0)), L("reported", "已记录")),
  ].join("");
  document.getElementById("assets-log-streams").innerHTML = countListHtml(
    countBy(logs, (item) => item.hidden ? `${item.stream || "log"}:${statusLabel("hidden")}` : item.stream),
    (value) => value.includes(":") ? value.replace(":", " / ") : value,
  );
  document.getElementById("assets-artifact-status").innerHTML = statusBars(
    countBy(artifacts, (item) => item.status),
    ["captured", "skipped", "error", "archived"],
  );
  document.getElementById("assets-artifact-kinds").innerHTML = countListHtml(
    countBy(artifacts, (item) => artifactKind(item.relative_path)),
    (value) => value,
  );
  renderAssets(selectedKind);
}

function renderAssets(kind) {
  const selectedKind = kind === "artifacts" ? "artifacts" : "logs";
  state.assetKind = selectedKind;
  localStorage.setItem("alab-dashboard-asset-kind", selectedKind);
  for (const button of document.querySelectorAll("#assets-tabs button")) {
    button.classList.toggle("active", button.dataset.kind === selectedKind);
    button.setAttribute("aria-selected", String(button.dataset.kind === selectedKind));
    button.setAttribute("tabindex", button.dataset.kind === selectedKind ? "0" : "-1");
  }
  const body = document.getElementById("assets-body");
  const controlsNode = document.getElementById("assets-controls");
  if (selectedKind === "logs") {
    const allRows = (state.assetScope && state.assetScope.logs) || [];
    const viewKey = "asset_logs";
    const options = logFilterOptions(allRows);
    const sortOptions = logSortOptions();
    const filter = activeFilter(viewKey, options);
    const sort = activeSort(viewKey, sortOptions);
    const filtered = filterLogs(allRows, filter);
    const rows = sortLogs(bySearch(filtered, ["log_id", "stream", "preview_text", "exp_id", "run_id", "project_id", "project_name"]), sort);
    renderListChrome({
      controlsNode,
      metaNode: document.getElementById("assets-meta"),
      view: viewKey,
      allRows,
      rows,
      filterOptions: options,
      sortOptions,
      filter,
      sort,
      page: state.assetScope && state.assetScope.pages && state.assetScope.pages.logs,
    });
    body.innerHTML = resourceCardsHtml(rows, "logs", { total: allRows.length });
    wireResourceCards(body);
  } else {
    const allRows = (state.assetScope && state.assetScope.artifacts) || [];
    const viewKey = "asset_artifacts";
    const options = artifactFilterOptions(allRows);
    const sortOptions = artifactSortOptions();
    const filter = activeFilter(viewKey, options);
    const sort = activeSort(viewKey, sortOptions);
    const filtered = filterArtifacts(allRows, filter);
    const rows = sortArtifacts(bySearch(filtered, ["artifact_id", "relative_path", "status", "exp_id", "run_id", "project_id", "project_name"]), sort);
    renderListChrome({
      controlsNode,
      metaNode: document.getElementById("assets-meta"),
      view: viewKey,
      allRows,
      rows,
      filterOptions: options,
      sortOptions,
      filter,
      sort,
      page: state.assetScope && state.assetScope.pages && state.assetScope.pages.artifacts,
    });
    body.innerHTML = resourceCardsHtml(rows, "artifacts", { total: allRows.length });
    wireResourceCards(body);
  }
}

function wireAssetTabs(container) {
  const buttons = Array.from(container.querySelectorAll("[role='tab']"));
  const activate = (button, { focus = false } = {}) => {
    renderAssets(button.dataset.kind);
    if (focus) {
      focusTabButton(button);
    }
  };
  for (const button of buttons) {
    button.addEventListener("click", () => activate(button));
    button.addEventListener("keydown", (event) => {
      const currentIndex = buttons.indexOf(button);
      let nextIndex = currentIndex;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        nextIndex = (currentIndex + 1) % buttons.length;
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
      } else if (event.key === "Home") {
        nextIndex = 0;
      } else if (event.key === "End") {
        nextIndex = buttons.length - 1;
      } else {
        return;
      }
      event.preventDefault();
      activate(buttons[nextIndex], { focus: true });
    });
  }
}

function resourceCardsHtml(rows, kind, options = {}) {
  if (!rows.length) return emptyHtml({ unfiltered: Number(options.total || 0) === 0 });
  if (kind === "logs") {
    return rows.map((log) => {
      const label = openCardLabel(L("log detail", "日志详情"), log.log_id, `${projectName(log.project_id)} · ${valueOrNone(log.stream)}`);
      return `
      <button class="asset-card log-card ${log.hidden ? "has-warning" : ""}" type="button" data-log-id="${escapeHtml(log.log_id)}" ${cardLabelAttrs(label)}>
        <span class="asset-card-top">
          <strong>${escapeHtml(log.stream || log.log_id)}</strong>
          ${statusBadge(log.hidden ? "hidden" : "visible")}
        </span>
        <span class="asset-card-path">${idChip(log.log_id)}</span>
        <span class="asset-card-preview">${escapeHtml(log.preview_text || L("No preview captured.", "未捕获预览。"))}</span>
        <span class="asset-card-facts">
          <span>${factValue(log.project_name || (log.project_id ? projectName(log.project_id) : ""), 22)}${escapeHtml(L("project", "项目"))}</span>
          <span>${factValue(`${formatBytes(log.stored_bytes)} / ${formatBytes(log.size_bytes)}`, 18)}${escapeHtml(L("stored", "已存储"))}</span>
          <span>${factValue(log.run_id || log.validation_id, 22)}${escapeHtml(L("run / validation", "运行/验证"))}</span>
          <span>${factValue(formatDate(log.created_at), 20)}${escapeHtml(L("created", "创建"))}</span>
        </span>
      </button>
    `;
    }).join("");
  }
  return rows.map((artifact) => {
    const label = openCardLabel(L("artifact detail", "产物详情"), artifact.artifact_id, `${projectName(artifact.project_id)} · ${valueOrNone(artifact.relative_path)}`);
    return `
    <button class="asset-card artifact-card ${artifact.status === "error" ? "has-risk" : ""}" type="button" data-artifact-id="${escapeHtml(artifact.artifact_id)}" ${cardLabelAttrs(label)}>
      <span class="asset-card-top">
        <strong>${escapeHtml(artifact.relative_path || artifact.artifact_id)}</strong>
        ${statusBadge(artifact.status)}
      </span>
      <span class="asset-card-path">${idChip(artifact.artifact_id)}</span>
      <span class="asset-card-preview">${escapeHtml(artifact.capture_error || artifactCardSummary(artifact))}</span>
      <span class="asset-card-facts">
        <span>${factValue(artifact.project_name || (artifact.project_id ? projectName(artifact.project_id) : ""), 22)}${escapeHtml(L("project", "项目"))}</span>
        <span>${factValue(formatBytes(artifact.size_bytes), 14)}${escapeHtml(L("size", "大小"))}</span>
        <span>${factValue(valueOrNone(artifact.root), 16)}${escapeHtml(L("root", "根"))}</span>
        <span>${factValue(artifact.run_id || artifact.validation_id, 22)}${escapeHtml(L("run / validation", "运行/验证"))}</span>
      </span>
    </button>
  `;
  }).join("");
}

function wireResourceCards(container = document) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-log-id]")) {
    card.addEventListener("click", () => showLog(card.dataset.logId));
  }
  for (const card of container.querySelectorAll("[data-artifact-id]")) {
    card.addEventListener("click", () => showArtifact(card.dataset.artifactId));
  }
}

async function fetchProjectDetail(projectId) {
  if (!projectId) return { project: {}, logs: [], artifacts: [] };
  if (state.projectDetails.has(projectId)) return state.projectDetails.get(projectId);
  const detail = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  state.projectDetails.set(projectId, detail);
  return detail;
}

async function ensureAssetScope() {
  const selected = state.assetProjectId || ASSET_ALL_PROJECTS;
  const projectParam = selected === ASSET_ALL_PROJECTS ? "" : `&project=${encodeURIComponent(selected)}`;
  const [logsPayload, artifactsPayload] = await Promise.all([
    api(`/api/logs?limit=500${projectParam}`),
    api(`/api/artifacts?limit=500${projectParam}`),
  ]);
  const logs = (logsPayload.logs || []).map((log) => ({
    ...log,
    project_name: log.project_id ? projectName(log.project_id) : statusLabel("none"),
  }));
  const artifacts = (artifactsPayload.artifacts || []).map((artifact) => ({
    ...artifact,
    project_name: artifact.project_id ? projectName(artifact.project_id) : statusLabel("none"),
  }));
  const logTotal = (logsPayload.page && logsPayload.page.total) || logs.length;
  const artifactTotal = (artifactsPayload.page && artifactsPayload.page.total) || artifacts.length;
  if (selected === ASSET_ALL_PROJECTS) {
    state.assetScope = {
      label: L("All projects", "全部项目"),
      note: `${state.projects.length} ${L("projects indexed", "个项目已索引")} · ${logs.length}/${logTotal} ${L("logs loaded", "条日志已加载")} · ${artifacts.length}/${artifactTotal} ${L("artifacts loaded", "个产物已加载")}`,
      projectCount: state.projects.length,
      logs,
      artifacts,
      pages: { logs: logsPayload.page || null, artifacts: artifactsPayload.page || null },
    };
    return state.assetScope;
  }
  const projectLabel = projectName(selected);
  state.assetScope = {
    label: projectLabel,
    note: `${projectLabel} · ${logs.length}/${logTotal} ${L("logs loaded", "条日志已加载")} · ${artifacts.length}/${artifactTotal} ${L("artifacts loaded", "个产物已加载")}`,
    projectCount: selected ? 1 : 0,
    logs,
    artifacts,
    pages: { logs: logsPayload.page || null, artifacts: artifactsPayload.page || null },
  };
  return state.assetScope;
}

function auditView() {
  return `
    <div id="audit-kpis" class="grid cards compact-cards"></div>
    <div class="grid two audit-insights">
      ${panel(L("Audit activity", "审计活动"), '<div class="chart-box compact-chart"><canvas id="audit-activity-chart"></canvas></div>')}
      ${panel(L("Audit mix", "审计分布"), '<div class="audit-mix-grid"><div><div class="summary-note">' + escapeHtml(L("Action mix", "动作分布")) + '</div><div id="audit-actions"></div></div><div><div class="summary-note">' + escapeHtml(L("Actor mix", "执行者分布")) + '</div><div id="audit-actors"></div></div><div><div class="summary-note">' + escapeHtml(L("Object mix", "对象分布")) + '</div><div id="audit-objects"></div></div><div><div class="summary-note">' + escapeHtml(L("Project coverage", "项目覆盖")) + '</div><div id="audit-projects"></div></div></div>')}
    </div>
    ${panel(L("Audit log", "审计日志"), '<div id="audit-controls"></div><div id="audit-meta"></div><div id="audit-feed" class="audit-feed bounded-list"></div>')}
  `;
}

async function afterAudit() {
  const payload = await api(`/api/audit?query=${encodeURIComponent(state.search)}&limit=500`);
  const allRows = payload.audit || [];
  const options = auditFilterOptions(allRows);
  const sortOptions = auditSortOptions();
  const filter = activeFilter("audit", options);
  const sort = activeSort("audit", sortOptions);
  const rows = sortAuditRows(filterAuditRows(allRows, filter), sort);
  document.getElementById("audit-kpis").innerHTML = [
    metric(L("Entries", "记录"), rows.length, state.search ? L("matching current search", "匹配当前搜索") : L("latest retained rows", "最近保留记录")),
    metric(L("Projects", "项目"), uniqueCount(rows, (row) => row.project_id), L("referenced by audit rows", "被审计记录引用")),
    metric(L("Actions", "动作"), uniqueCount(rows, (row) => row.action), L("distinct action names", "不同动作名称")),
    metric(L("Latest", "最新"), formatCompactDate(latestValue(rows, (row) => row.created_at)), L("newest audit timestamp", "最新审计时间")),
  ].join("");
  const controlsNode = document.getElementById("audit-controls");
  controlsNode.innerHTML = listControls("audit", options, sortOptions);
  wireQuickFilters(controlsNode, "audit");
  wireSortControl(controlsNode, "audit", sortOptions);
  document.getElementById("audit-meta").innerHTML = filterMeta(rows.length, allRows.length, [quickFilterLabel(options, filter), quickSortLabel(sortOptions, sort)].filter(Boolean).join(" · "), payload.page);
  document.getElementById("audit-actions").innerHTML = countListHtml(countBy(rows, (row) => row.action));
  document.getElementById("audit-actors").innerHTML = countListHtml(countBy(rows, (row) => row.actor_type));
  document.getElementById("audit-objects").innerHTML = countListHtml(countBy(rows, (row) => row.object_type), objectTypeLabel);
  document.getElementById("audit-projects").innerHTML = countListHtml(countBy(rows, (row) => projectName(row.project_id)));
  renderAuditActivityChart("audit-activity-chart", rows);
  const feed = document.getElementById("audit-feed");
  feed.innerHTML = auditCardsHtml(rows);
  wireAuditCards(feed, rows);
}

function auditCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((row, index) => {
    const label = openCardLabel(L("audit detail", "审计详情"), row.action, `${objectTypeLabel(row.object_type)} · ${valueOrNone(row.object_id)}`);
    return `
    <button class="audit-card" type="button" data-audit-index="${index}" ${cardLabelAttrs(label)}>
      <span class="audit-card-time">${escapeHtml(formatDate(row.created_at))}</span>
      <span class="audit-card-main">
        <span class="audit-card-title">
          <strong>${escapeHtml(row.action)}</strong>
          <span>${escapeHtml(row.actor_type)}</span>
        </span>
        <span class="audit-card-object">${objectChip(row.object_type, row.object_id)}</span>
        <span class="audit-card-context">${escapeHtml(projectName(row.project_id))}</span>
        <span class="audit-card-reason">${escapeHtml(valueOrNone(row.reason))}</span>
      </span>
    </button>
  `;
  }).join("");
}

function wireAuditCards(container, rows) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-audit-index]")) {
    card.addEventListener("click", () => showObject(() => L("Audit", "审计"), rows[Number(card.dataset.auditIndex)]));
  }
}

function annotationCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((row, index) => {
    const label = openCardLabel(L("annotation detail", "标注详情"), row.annotation_id, `${objectTypeLabel(row.target_type)} · ${valueOrNone(row.target_id)}`);
    return `
      <button class="annotation-card" type="button" data-annotation-index="${index}" ${cardLabelAttrs(label)}>
        <span class="annotation-card-top">
          <strong>${idChip(row.annotation_id)}</strong>
          ${statusBadge(row.status)}
        </span>
        <span class="annotation-card-target">${objectChip(row.target_type, row.target_id)}</span>
        <span class="annotation-card-facts">
          <span><b>${escapeHtml(valueOrNone(row.visibility && row.visibility.scope))}</b>${escapeHtml(L("visibility", "可见性"))}</span>
          <span><b>${escapeHtml(valueOrNone(row.created_by_type))}</b>${escapeHtml(L("author", "作者"))}</span>
          <span><b>${escapeHtml(row.current_revision || 0)}</b>${escapeHtml(L("revision", "修订"))}</span>
          <span><b>${escapeHtml(formatDate(row.updated_at))}</b>${escapeHtml(L("updated", "更新"))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function wireAnnotationCards(container, rows) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-annotation-index]")) {
    card.addEventListener("click", () => showObject(() => L("Annotation", "标注"), rows[Number(card.dataset.annotationIndex)]));
  }
}

function sourceCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((row, index) => {
    const origin = row.origin_metadata || {};
    const kind = origin.adapter || origin.origin || row.name;
    const label = openCardLabel(L("source detail", "来源详情"), row.name || row.source_id, `${valueOrNone(kind)} · ${shortId(row.source_id)}`);
    return `
      <button class="record-card source-card" type="button" data-source-index="${index}" ${cardLabelAttrs(label)}>
        <span class="record-card-top">
          <strong>${escapeHtml(row.name || row.source_id)}</strong>
          ${statusBadge(row.status)}
        </span>
        <span class="record-card-ref">${idChip(row.source_id)}</span>
        <span class="record-card-body">${escapeHtml(row.source_ref || row.source_commit || row.tree_hash || statusLabel("none"))}</span>
        <span class="record-card-facts">
          <span><b>${escapeHtml(shortId(row.source_commit))}</b>${escapeHtml(L("commit", "提交"))}</span>
          <span><b>${escapeHtml(valueOrNone(kind))}</b>${escapeHtml(L("kind", "类型"))}</span>
          <span><b>${escapeHtml(shortId(row.tree_hash))}</b>${escapeHtml(L("tree", "树"))}</span>
          <span><b>${escapeHtml(formatDate(row.created_at))}</b>${escapeHtml(L("created", "创建"))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function validationCardsHtml(rows) {
  if (!rows.length) return emptyHtml();
  return rows.map((row, index) => {
    const warnings = warningSummary((row.record || {}).warning_codes);
    const label = openCardLabel(L("validation detail", "验证详情"), row.validation_id, `${statusLabel(row.status)} · ${valueOrNone(row.source_ref || row.source_commit)}`);
    return `
      <button class="record-card validation-card ${runCardTone(row.status)}" type="button" data-validation-index="${index}" ${cardLabelAttrs(label)}>
        <span class="record-card-top">
          <strong>${idChip(row.validation_id)}</strong>
          ${statusBadge(row.status)}
        </span>
        <span class="record-card-ref">${escapeHtml(row.source_ref || row.source_commit || statusLabel("none"))}</span>
        <span class="record-card-body">${escapeHtml(warnings === statusLabel("none") ? L("Validation completed without warnings.", "验证未记录警告。") : warnings)}</span>
        <span class="record-card-facts">
          <span><b>${escapeHtml(`v${row.config_version}`)}</b>${escapeHtml(L("config", "配置"))}</span>
          <span><b>${escapeHtml(valueOrNone(row.reward_value))}</b>${escapeHtml(L("reward", "奖励"))}</span>
          <span><b>${escapeHtml(valueOrNone(row.exit_code))}</b>${escapeHtml(L("exit", "退出码"))}</span>
          <span><b>${escapeHtml(formatDate(row.started_at))}</b>${escapeHtml(L("started", "开始"))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function wireRecordCards(container, rows, kind) {
  wireInlineClearSearch(container);
  const selector = kind === "validation" ? "[data-validation-index]" : "[data-source-index]";
  const title = kind === "validation" ? () => L("Validation", "验证") : () => L("Source", "来源");
  for (const card of container.querySelectorAll(selector)) {
    const index = Number(kind === "validation" ? card.dataset.validationIndex : card.dataset.sourceIndex);
    card.addEventListener("click", () => showObject(title, rows[index]));
  }
}

function systemCardsHtml(rows, kind) {
  if (!rows.length) return emptyHtml();
  return rows.map((row, index) => {
    if (kind === "locks") {
      const label = openCardLabel(L("lock detail", "锁详情"), row.lock_name || L("Active lock", "活动锁"), `${projectName(row.project_id)} · ${valueOrNone(row.owner_operation_id)}`);
      return `
        <button class="record-card system-card is-running" type="button" data-system-index="${index}" ${cardLabelAttrs(label)}>
          <span class="record-card-top">
            <strong>${escapeHtml(row.lock_name || L("Active lock", "活动锁"))}</strong>
            ${statusBadge("running")}
          </span>
          <span class="record-card-ref">${escapeHtml(projectName(row.project_id))}</span>
          <span class="record-card-body">${escapeHtml(valueOrNone(row.owner_operation_id))}</span>
          <span class="record-card-facts">
            <span><b>${escapeHtml(`${row.owner_host || statusLabel("none")}:${row.owner_pid || statusLabel("none")}`)}</b>${escapeHtml(L("host", "主机"))}</span>
            <span><b>${escapeHtml(formatDate(row.expires_at))}</b>${escapeHtml(L("expires", "过期"))}</span>
          </span>
        </button>
      `;
    }
    if (kind === "capabilities") {
      const label = openCardLabel(L("capability detail", "能力详情"), row.capability_key || L("Capability", "能力"), `${statusLabel(row.status)} · ${shortId(row.fingerprint)}`);
      return `
        <button class="record-card system-card ${runCardTone(row.status)}" type="button" data-system-index="${index}" ${cardLabelAttrs(label)}>
          <span class="record-card-top">
            <strong>${escapeHtml(row.capability_key || L("Capability", "能力"))}</strong>
            ${statusBadge(row.status)}
          </span>
          <span class="record-card-ref">${idChip(row.fingerprint)}</span>
          <span class="record-card-body">${escapeHtml(row.error_message || row.detail || valueOrNone(row.status))}</span>
          <span class="record-card-facts">
            <span><b>${escapeHtml(formatDate(row.checked_at))}</b>${escapeHtml(L("checked", "检查"))}</span>
            <span><b>${escapeHtml(valueOrNone(row.status))}</b>${escapeHtml(L("status", "状态"))}</span>
          </span>
        </button>
      `;
    }
    if (kind === "catalogs") {
      const label = openCardLabel(L("catalog detail", "目录详情"), row.catalog_key || L("Catalog", "目录"), `${valueOrNone(row.catalog_type)} · ${statusLabel(row.status)}`);
      return `
        <button class="record-card system-card ${runCardTone(row.status)}" type="button" data-system-index="${index}" ${cardLabelAttrs(label)}>
          <span class="record-card-top">
            <strong>${escapeHtml(row.catalog_key || L("Catalog", "目录"))}</strong>
            ${statusBadge(row.status)}
          </span>
          <span class="record-card-ref">${escapeHtml(valueOrNone(row.catalog_type))}</span>
          <span class="record-card-body">${escapeHtml(row.source_url || row.path || row.catalog_key || statusLabel("none"))}</span>
          <span class="record-card-facts">
            <span><b>${escapeHtml(valueOrNone(row.catalog_type))}</b>${escapeHtml(L("type", "类型"))}</span>
            <span><b>${escapeHtml(formatDate(row.updated_at))}</b>${escapeHtml(L("updated", "更新"))}</span>
          </span>
        </button>
      `;
    }
    const label = openCardLabel(L("cache detail", "缓存详情"), row.cache_id, `${valueOrNone(row.cache_kind)} · ${formatBytes(row.size_bytes)}`);
    return `
      <button class="record-card system-card ${runCardTone(row.status)}" type="button" data-system-index="${index}" ${cardLabelAttrs(label)}>
        <span class="record-card-top">
          <strong>${idChip(row.cache_id)}</strong>
          ${statusBadge(row.status)}
        </span>
        <span class="record-card-ref">${escapeHtml(valueOrNone(row.cache_kind))}</span>
        <span class="record-card-body">${escapeHtml(projectName(row.project_id))}</span>
        <span class="record-card-facts">
          <span><b>${escapeHtml(formatBytes(row.size_bytes))}</b>${escapeHtml(L("size", "大小"))}</span>
          <span><b>${escapeHtml(formatDate(row.last_used_at || row.created_at))}</b>${escapeHtml(L("last used", "最近使用"))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function wireSystemCards(container, rows, title) {
  wireInlineClearSearch(container);
  for (const card of container.querySelectorAll("[data-system-index]")) {
    card.addEventListener("click", () => showObject(title, rows[Number(card.dataset.systemIndex)]));
  }
}

function feedbackView() {
  return `
    <div id="feedback-kpis" class="grid cards compact-cards"></div>
    <div class="grid three feedback-insights">
      ${panel(L("Feedback kinds", "反馈类型"), '<div id="feedback-kinds"></div>')}
      ${panel(L("Feedback roles", "反馈角色"), '<div id="feedback-roles"></div>')}
      ${panel(L("Recent feedback", "近期反馈"), '<div id="feedback-recency"></div>')}
    </div>
    ${panel(L("Feedback inbox", "反馈收件箱"), '<div id="feedback-controls"></div><div id="feedback-meta"></div><div id="feedback-feed" class="feedback-feed bounded-list"></div>')}
  `;
}

async function afterFeedback() {
  const payload = await api(`/api/feedback?query=${encodeURIComponent(state.search)}&limit=500`);
  const rows = payload.feedback || [];
  const searched = bySearch(rows, ["body", (row) => row.metadata && row.metadata.title, (row) => row.metadata && row.metadata.kind, (row) => row.metadata && row.metadata.role]);
  const options = feedbackFilterOptions(searched);
  const sortOptions = feedbackSortOptions();
  const filter = activeFilter("feedback", options);
  const sort = activeSort("feedback", sortOptions);
  const filtered = sortFeedbackRows(filterFeedbackRows(searched, filter), sort);
  document.getElementById("feedback-kpis").innerHTML = [
    metric(L("Entries", "记录"), filtered.length, state.search ? L("matching current search", "匹配当前搜索") : L("HOME feedback rows", "本地反馈记录")),
    metric(L("Kinds", "类型"), uniqueCount(filtered, (row) => row.metadata && row.metadata.kind), L("distinct feedback kinds", "不同反馈类型")),
    metric(L("Words", "词数"), filtered.reduce((total, row) => total + feedbackBodyWords(row), 0), L("body words across shown entries", "当前记录正文词数")),
    metric(L("Latest", "最新"), formatCompactDate(latestValue(filtered, (row) => row.metadata && row.metadata.created_at)), L("newest feedback timestamp", "最新反馈时间")),
  ].join("");
  const controlsNode = document.getElementById("feedback-controls");
  controlsNode.innerHTML = listControls("feedback", options, sortOptions);
  wireQuickFilters(controlsNode, "feedback");
  wireSortControl(controlsNode, "feedback", sortOptions);
  document.getElementById("feedback-kinds").innerHTML = countListHtml(countBy(filtered, (row) => row.metadata && row.metadata.kind));
  document.getElementById("feedback-roles").innerHTML = countListHtml(countBy(filtered, (row) => row.metadata && row.metadata.role));
  document.getElementById("feedback-recency").innerHTML = countListHtml(countBy(filtered, feedbackDay));
  document.getElementById("feedback-meta").innerHTML = filterMeta(filtered.length, rows.length, [quickFilterLabel(options, filter), quickSortLabel(sortOptions, sort)].filter(Boolean).join(" · "), payload.page);
  const feed = document.getElementById("feedback-feed");
  if (!filtered.length) {
    feed.innerHTML = emptyHtml();
    wireInlineClearSearch(feed);
    return;
  }
  feed.innerHTML = filtered.map((row, index) => {
    const metadata = row.metadata || {};
    const label = openCardLabel(L("feedback detail", "反馈详情"), valueOrNone(metadata.title), `${valueOrNone(metadata.kind)} · ${valueOrNone(metadata.role)}`);
    return `
      <button class="feedback-card" type="button" data-feedback-index="${index}" ${cardLabelAttrs(label)}>
        <span class="feedback-card-top">
          <strong>${escapeHtml(valueOrNone(metadata.title))}</strong>
          <span class="badge">${escapeHtml(valueOrNone(metadata.kind))}</span>
        </span>
        <span class="feedback-card-meta">
          <span>${escapeHtml(formatDate(metadata.created_at))}</span>
          <span>${escapeHtml(valueOrNone(metadata.role))}</span>
          <span>${escapeHtml(valueOrNone(metadata.feedback_id))}</span>
        </span>
        <span class="feedback-card-facts">
          <span>${factValue(feedbackBodyWords(row), 10)}${escapeHtml(L("words", "词"))}</span>
          <span>${factValue(formatBytes(feedbackBodyBytes(row)), 12)}${escapeHtml(L("body", "正文"))}</span>
        </span>
        <span class="feedback-card-body">${escapeHtml(valueOrNone(row.body))}</span>
      </button>
    `;
  }).join("");
  for (const card of feed.querySelectorAll("[data-feedback-index]")) {
    card.addEventListener("click", () => showObject(() => L("Feedback", "反馈"), filtered[Number(card.dataset.feedbackIndex)]));
  }
}

function systemView() {
  return `
    <div id="system-kpis" class="grid cards"></div>
    <div class="grid three system-insights">
      ${panel(L("System attention", "系统关注"), '<div id="system-attention"></div>')}
      ${panel(L("Runtime status mix", "运行时状态分布"), '<div id="system-status-mix"></div>')}
      ${panel(L("Cache footprint", "缓存占用"), '<div class="resource-insights"><div class="summary-note">' + escapeHtml(L("By kind", "按类型")) + '</div><div id="system-cache-kind-size"></div><div class="summary-note">' + escapeHtml(L("By project", "按项目")) + '</div><div id="system-cache-project-size"></div></div>')}
    </div>
    <div id="system-blocks" class="grid"></div>
  `;
}

async function afterSystem() {
  const system = await api("/api/system?cache_limit=500");
  const capabilityIssues = (system.capabilities || []).filter((item) => ["error", "unsupported", "failed", "invalid"].includes(item.status));
  const cacheBytes = (system.cache_entries || []).reduce((total, item) => total + Number(item.size_bytes || 0), 0);
  document.getElementById("system-kpis").innerHTML = [
    metric(L("Locks", "锁"), system.locks.length, L("active rows", "活动记录")),
    metric(L("Capabilities", "能力"), system.capabilities.length, `${capabilityIssues.length} ${L("issues", "问题")}`),
    metric(L("Catalogs", "目录"), system.catalogs.length, L("configured sources", "已配置来源")),
    metric(L("Cache", "缓存"), system.cache_entries.length, formatBytes(cacheBytes)),
  ].join("");
  const diagnostics = [
    ...(system.locks || []).map((lock) => ({
      severity: "warn",
      title: lock.lock_name || L("Active lock", "活动锁"),
      detail: `${projectName(lock.project_id)} · ${valueOrNone(lock.owner_operation_id)}`,
    })),
    ...capabilityIssues.map((item) => ({
      severity: "bad",
      title: item.capability_key || L("Capability issue", "能力问题"),
      detail: `${statusLabel(item.status)} · ${formatDate(item.checked_at)}`,
    })),
  ];
  document.getElementById("system-attention").innerHTML = diagnosticListHtml(diagnostics);
  document.getElementById("system-status-mix").innerHTML = [
    `<div class="summary-note">${escapeHtml(L("Capabilities", "能力"))}</div>`,
    countListHtml(countBy(system.capabilities || [], (row) => row.status), statusLabel),
    `<div class="summary-note">${escapeHtml(L("Cache", "缓存"))}</div>`,
    countListHtml(countBy(system.cache_entries || [], (row) => row.status), statusLabel),
  ].join("");
  document.getElementById("system-cache-kind-size").innerHTML = sizeListHtml(
    system.cache_entries || [],
    (row) => row.cache_kind,
    (row) => row.size_bytes,
  );
  document.getElementById("system-cache-project-size").innerHTML = sizeListHtml(
    system.cache_entries || [],
    (row) => projectName(row.project_id),
    (row) => row.size_bytes,
  );
  const target = document.getElementById("system-blocks");
  target.innerHTML = [
    panel(L("Locks", "锁"), '<div id="system-lock-cards" class="record-card-grid bounded-list"></div>'),
    panel(L("Capabilities", "能力"), '<div id="system-capability-controls"></div><div id="system-capability-meta"></div><div id="system-capability-cards" class="record-card-grid bounded-list"></div>'),
    panel(L("Catalogs", "目录"), '<div id="system-catalog-controls"></div><div id="system-catalog-meta"></div><div id="system-catalog-cards" class="record-card-grid bounded-list"></div>'),
    panel(L("Cache entries", "缓存条目"), '<div id="system-cache-controls"></div><div id="system-cache-meta"></div><div id="system-cache-cards" class="record-card-grid bounded-list"></div>'),
    panel(L("Home metadata", "HOME 元数据"), systemMetadataHtml(system)),
  ].join("");
  const lockCards = document.getElementById("system-lock-cards");
  const capabilityCards = document.getElementById("system-capability-cards");
  const catalogCards = document.getElementById("system-catalog-cards");
  const cacheCards = document.getElementById("system-cache-cards");
  const rerenderSystem = () => afterSystem();
  lockCards.innerHTML = systemCardsHtml(system.locks || [], "locks");
  const capabilityRowsAll = system.capabilities || [];
  const capabilityOptions = capabilityFilterOptions(capabilityRowsAll);
  const capabilitySortChoices = capabilitySortOptions();
  const capabilityFilter = activeFilter("system_capabilities", capabilityOptions);
  const capabilitySort = activeSort("system_capabilities", capabilitySortChoices);
  const capabilityRows = sortCapabilities(bySearch(filterCapabilities(capabilityRowsAll, capabilityFilter), ["capability_key", "status", "fingerprint", "detail", "error_message"]), capabilitySort);
  const capabilityControls = document.getElementById("system-capability-controls");
  capabilityControls.innerHTML = listControls("system_capabilities", capabilityOptions, capabilitySortChoices);
  wireQuickFilters(capabilityControls, "system_capabilities", rerenderSystem);
  wireSortControl(capabilityControls, "system_capabilities", capabilitySortChoices, rerenderSystem);
  document.getElementById("system-capability-meta").innerHTML = filterMeta(capabilityRows.length, capabilityRowsAll.length, [quickFilterLabel(capabilityOptions, capabilityFilter), quickSortLabel(capabilitySortChoices, capabilitySort)].filter(Boolean).join(" · "));
  const catalogRowsAll = system.catalogs || [];
  const catalogOptions = catalogFilterOptions(catalogRowsAll);
  const catalogSortChoices = catalogSortOptions();
  const catalogFilter = activeFilter("system_catalogs", catalogOptions);
  const catalogSort = activeSort("system_catalogs", catalogSortChoices);
  const catalogRows = sortCatalogs(bySearch(filterCatalogs(catalogRowsAll, catalogFilter), ["catalog_key", "catalog_type", "status", "source_url", "path"]), catalogSort);
  const catalogControls = document.getElementById("system-catalog-controls");
  catalogControls.innerHTML = listControls("system_catalogs", catalogOptions, catalogSortChoices);
  wireQuickFilters(catalogControls, "system_catalogs", rerenderSystem);
  wireSortControl(catalogControls, "system_catalogs", catalogSortChoices, rerenderSystem);
  document.getElementById("system-catalog-meta").innerHTML = filterMeta(catalogRows.length, catalogRowsAll.length, [quickFilterLabel(catalogOptions, catalogFilter), quickSortLabel(catalogSortChoices, catalogSort)].filter(Boolean).join(" · "));
  const cacheRowsAll = system.cache_entries || [];
  const cacheOptions = cacheFilterOptions(cacheRowsAll);
  const cacheSortChoices = cacheSortOptions();
  const cacheFilter = activeFilter("system_cache", cacheOptions);
  const cacheSort = activeSort("system_cache", cacheSortChoices);
  const cacheRows = sortCacheRows(bySearch(filterCacheRows(cacheRowsAll, cacheFilter), ["cache_id", "cache_kind", "cache_key", "status", "project_id", (row) => projectName(row.project_id)]), cacheSort);
  const cacheControls = document.getElementById("system-cache-controls");
  cacheControls.innerHTML = listControls("system_cache", cacheOptions, cacheSortChoices);
  wireQuickFilters(cacheControls, "system_cache", rerenderSystem);
  wireSortControl(cacheControls, "system_cache", cacheSortChoices, rerenderSystem);
  document.getElementById("system-cache-meta").innerHTML = filterMeta(cacheRows.length, cacheRowsAll.length, [quickFilterLabel(cacheOptions, cacheFilter), quickSortLabel(cacheSortChoices, cacheSort)].filter(Boolean).join(" · "), system.cache_entries_page);
  capabilityCards.innerHTML = systemCardsHtml(capabilityRows, "capabilities");
  catalogCards.innerHTML = systemCardsHtml(catalogRows, "catalogs");
  cacheCards.innerHTML = systemCardsHtml(cacheRows, "cache");
  wireSystemCards(lockCards, system.locks || [], () => L("Lock", "锁"));
  wireSystemCards(capabilityCards, capabilityRows, () => L("Capability", "能力"));
  wireSystemCards(catalogCards, catalogRows, () => L("Catalog", "目录"));
  wireSystemCards(cacheCards, cacheRows, () => L("Cache", "缓存"));
}

async function render() {
  setTitle(state.view);
  renderNav();
  localize();
  const content = document.getElementById("content");
  destroyChartsIn(content);
  const views = {
    overview: [overviewView, afterOverview],
    projects: [projectsView, afterProjects],
    experiments: [experimentsView, afterExperiments],
    runs: [runsView, afterRuns],
    assets: [assetsView, afterAssets],
    audit: [auditView, afterAudit],
    feedback: [feedbackView, afterFeedback],
    system: [systemView, afterSystem],
  };
  const [view, after] = views[state.view] || views.overview;
  content.innerHTML = view();
  await after();
}

function showPanel(title, body, options = {}) {
  const panelEl = document.getElementById("detail-panel");
  const backdropEl = document.getElementById("detail-backdrop");
  const closeLabel = L("Close", "关闭");
  const refreshLabel = L("Refresh detail", "刷新详情");
  const fullTitle = options.titleFull || title;
  const kicker = options.kicker || "";
  const subtitle = options.subtitle || "";
  const activeElement = document.activeElement;
  if (activeElement && activeElement !== document.body && !panelEl.contains(activeElement)) {
    state.detailReturnFocus = activeElement;
  }
  panelEl.classList.toggle("wide", Boolean(options.wide));
  panelEl.setAttribute("role", "dialog");
  panelEl.setAttribute("aria-modal", "true");
  panelEl.setAttribute("aria-labelledby", "detail-title");
  if (subtitle) panelEl.setAttribute("aria-describedby", "detail-subtitle");
  else panelEl.removeAttribute("aria-describedby");
  panelEl.setAttribute("aria-hidden", "false");
  if (!document.body.classList.contains("detail-open")) {
    state.detailScrollLockY = window.scrollY;
    document.body.style.top = `-${state.detailScrollLockY}px`;
  }
  document.body.classList.add("detail-open");
  if (backdropEl) backdropEl.hidden = false;
  destroyChartsIn(panelEl);
  state.detailRerender = options.rerender || null;
  const showRefreshButton = Boolean(options.refreshable && state.detailRerender);
  const refreshButtonHtml = showRefreshButton ? `<button class="icon-button detail-refresh-button" id="refresh-detail" type="button" title="${escapeHtml(refreshLabel)}" aria-label="${escapeHtml(refreshLabel)}"></button>` : "";
  panelEl.innerHTML = `<div class="detail-header"><div class="detail-heading"><div class="detail-title-row">${kicker ? `<span class="detail-kicker" title="${escapeHtml(kicker)}">${escapeHtml(kicker)}</span> ` : ""}<strong class="detail-title" id="detail-title" title="${escapeHtml(fullTitle)}">${escapeHtml(title)}</strong></div>${subtitle ? ` <span class="detail-subtitle" id="detail-subtitle" title="${escapeHtml(subtitle)}">${escapeHtml(subtitle)}</span>` : ""}</div><div class="detail-actions">${refreshButtonHtml}<button class="icon-button" id="close-detail" type="button" title="${escapeHtml(closeLabel)}" aria-label="${escapeHtml(closeLabel)}"></button></div></div><div class="detail-content">${body}</div>`;
  const refreshButton = document.getElementById("refresh-detail");
  if (refreshButton) {
    refreshButton.appendChild(icon("refresh-cw"));
    refreshButton.addEventListener("click", () => rerenderOpenDetailPanel({ preserveFocus: true }));
  }
  const closeButton = document.getElementById("close-detail");
  closeButton.appendChild(icon("x"));
  closeButton.addEventListener("click", () => closeDetailPanel());
  closeButton.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      closeDetailPanel();
    }
  });
  panelEl.classList.add("open");
  if (!state.detailSuppressFocus) closeButton.focus({ preventScroll: true });
}

function resolveObjectTitle(title) {
  return typeof title === "function" ? title() : title;
}

function showObject(title, obj) {
  const resolvedTitle = resolveObjectTitle(title);
  showPanel(resolvedTitle, objectDetailHtml(resolvedTitle, obj), {
    rerender: () => showObject(title, obj),
  });
  wireRelatedActions(document.getElementById("detail-panel"));
}

async function showProject(projectId, options = {}) {
  const detail = await fetchProjectDetail(projectId);
  state.currentProjectId = projectId;
  state.projectDetail = detail;
  state.projectDetailTab = options.tab || "overview";
  const projectSummary = [detail.project.task, detail.project.goal]
    .filter((item, index, values) => item && values.indexOf(item) === index)
    .join(" · ") || detail.project.project_id;
  const projectTitle = detail.project.name || projectId;
  showPanel(projectTitle, `
    <div class="project-detail-summary">
      <div>
        <div class="metric-label">${escapeHtml(L("Project overview", "项目概览"))}</div>
        <div class="project-detail-title">${escapeHtml(detail.project.name || detail.project.project_id)}</div>
        <div class="summary-note">${escapeHtml(projectSummary)}</div>
        ${projectContextFacts(detail)}
      </div>
      ${statusBadge(detail.project.status)}
    </div>
    <div class="detail-tabs" id="project-detail-tabs" role="tablist">
      <button type="button" role="tab" aria-selected="false" data-tab="overview">${escapeHtml(L("Overview", "概览"))}</button>
      <button type="button" role="tab" aria-selected="false" data-tab="experiments">${escapeHtml(L("Experiments", "实验"))}</button>
      <button type="button" role="tab" aria-selected="false" data-tab="runs">${escapeHtml(L("Runs", "运行"))}</button>
      <button type="button" role="tab" aria-selected="false" data-tab="assets">${escapeHtml(L("Logs & Artifacts", "日志与产物"))}</button>
      <button type="button" role="tab" aria-selected="false" data-tab="config">${escapeHtml(L("Sources & Config", "来源与配置"))}</button>
      <button type="button" role="tab" aria-selected="false" data-tab="audit">${escapeHtml(L("Audit", "审计"))}</button>
    </div>
    <div id="project-tab-body" class="project-tab-body"></div>
  `, {
    wide: true,
    titleFull: `${L("Project", "项目")} ${projectTitle}`,
    kicker: L("Project", "项目"),
    subtitle: projectSummary,
    rerender: () => showProject(projectId, { tab: state.projectDetailTab || "overview" }),
    refreshable: true,
  });
  wireDetailTabs(document.getElementById("project-detail-tabs"), (tab) => {
    state.projectDetailTab = tab;
    renderProjectDetailTab(detail, tab);
  });
  renderProjectDetailTab(detail, state.projectDetailTab || "overview");
}

function renderProjectDetailTab(detail, tab) {
  for (const button of document.querySelectorAll("#project-detail-tabs button")) {
    button.classList.toggle("active", button.dataset.tab === tab);
    button.setAttribute("aria-selected", String(button.dataset.tab === tab));
    button.setAttribute("tabindex", button.dataset.tab === tab ? "0" : "-1");
  }
  const body = document.getElementById("project-tab-body");
  if (!body) return;
  const config = detail.configs && detail.configs[0] ? detail.configs[0].config : {};
  if (tab === "experiments") {
    body.innerHTML = panel(L("Experiments", "实验"), `<div id="project-exp-controls"></div><div id="project-exp-meta"></div><div class="experiment-card-grid bounded-list" id="project-exp-cards"></div>`);
    const viewKey = "project_experiments";
    const allRows = detail.experiments || [];
    const options = experimentFilterOptions(allRows);
    const sortOptions = experimentSortOptions();
    const filter = activeFilter(viewKey, options);
    const sort = activeSort(viewKey, sortOptions);
    const rows = sortExperiments(bySearch(filterExperiments(allRows, filter), ["exp_id", "name", "status", "project_id", "tags", "goal"]), sort);
    const controlsNode = document.getElementById("project-exp-controls");
    const rerender = () => renderProjectDetailTab(detail, "experiments");
    renderListChrome({
      controlsNode,
      metaNode: document.getElementById("project-exp-meta"),
      view: viewKey,
      allRows,
      rows,
      filterOptions: options,
      sortOptions,
      filter,
      sort,
      page: detail.pages && detail.pages.experiments,
      onChange: rerender,
    });
    const projectExpCards = document.getElementById("project-exp-cards");
    projectExpCards.innerHTML = experimentCardsHtml(rows);
    wireExperimentCards(projectExpCards);
    return;
  }
  if (tab === "runs") {
    body.innerHTML = `
      ${panel(L("Run reward trend", "运行奖励趋势"), '<div id="project-reward-summary"></div><div class="chart-box project-chart-box"><canvas id="project-reward-chart"></canvas></div>')}
      ${panel(L("Runs", "运行"), `<div id="project-run-controls"></div><div id="project-run-meta"></div><div class="run-card-grid bounded-list" id="project-run-cards"></div>`)}
    `;
    const viewKey = "project_runs";
    const allRows = detail.runs || [];
    const options = runFilterOptions(allRows);
    const sortOptions = runSortOptions();
    const filter = activeFilter(viewKey, options);
    const sort = activeSort(viewKey, sortOptions);
    const rows = sortRuns(bySearch(filterRuns(allRows, filter), ["run_id", "exp_id", "exp_name", "status", "project_id", "failure_reason", "warning_codes"]), sort);
    const controlsNode = document.getElementById("project-run-controls");
    const rerender = () => renderProjectDetailTab(detail, "runs");
    renderListChrome({
      controlsNode,
      metaNode: document.getElementById("project-run-meta"),
      view: viewKey,
      allRows,
      rows,
      filterOptions: options,
      sortOptions,
      filter,
      sort,
      page: detail.pages && detail.pages.runs,
      onChange: rerender,
    });
    document.getElementById("project-reward-summary").innerHTML = rewardTrendSummaryHtml(rows, detail.project.reward_direction);
    renderRewardTrendChart("project-reward-chart", rows, detail.project.reward_direction);
    const runCards = document.getElementById("project-run-cards");
    runCards.innerHTML = runCardsHtml(rows);
    wireRunCards(runCards);
    return;
  }
  if (tab === "assets") {
    body.innerHTML = `
      <div class="grid two detail-table-grid">
        ${panel(L("Logs", "日志"), `<div id="project-log-controls"></div><div id="project-log-meta"></div><div class="asset-card-grid bounded-list" id="project-log-cards"></div>`)}
        ${panel(L("Artifacts", "产物"), `<div id="project-artifact-controls"></div><div id="project-artifact-meta"></div><div class="asset-card-grid bounded-list" id="project-artifact-cards"></div>`)}
      </div>
    `;
    const rerender = () => renderProjectDetailTab(detail, "assets");
    const logViewKey = "project_logs";
    const logRowsAll = detail.logs || [];
    const logOptions = logFilterOptions(logRowsAll);
    const logSortChoices = logSortOptions();
    const logFilter = activeFilter(logViewKey, logOptions);
    const logSort = activeSort(logViewKey, logSortChoices);
    const logRows = sortLogs(bySearch(filterLogs(logRowsAll, logFilter), ["log_id", "stream", "preview_text", "exp_id", "run_id"]), logSort);
    const logControls = document.getElementById("project-log-controls");
    renderListChrome({
      controlsNode: logControls,
      metaNode: document.getElementById("project-log-meta"),
      view: logViewKey,
      allRows: logRowsAll,
      rows: logRows,
      filterOptions: logOptions,
      sortOptions: logSortChoices,
      filter: logFilter,
      sort: logSort,
      page: detail.pages && detail.pages.logs,
      onChange: rerender,
    });
    const artifactViewKey = "project_artifacts";
    const artifactRowsAll = detail.artifacts || [];
    const artifactOptions = artifactFilterOptions(artifactRowsAll);
    const artifactSortChoices = artifactSortOptions();
    const artifactFilter = activeFilter(artifactViewKey, artifactOptions);
    const artifactSort = activeSort(artifactViewKey, artifactSortChoices);
    const artifactRows = sortArtifacts(bySearch(filterArtifacts(artifactRowsAll, artifactFilter), ["artifact_id", "relative_path", "status", "exp_id", "run_id"]), artifactSort);
    const artifactControls = document.getElementById("project-artifact-controls");
    renderListChrome({
      controlsNode: artifactControls,
      metaNode: document.getElementById("project-artifact-meta"),
      view: artifactViewKey,
      allRows: artifactRowsAll,
      rows: artifactRows,
      filterOptions: artifactOptions,
      sortOptions: artifactSortChoices,
      filter: artifactFilter,
      sort: artifactSort,
      page: detail.pages && detail.pages.artifacts,
      onChange: rerender,
    });
    const logCards = document.getElementById("project-log-cards");
    const artifactCards = document.getElementById("project-artifact-cards");
    logCards.innerHTML = resourceCardsHtml(logRows, "logs", { total: logRowsAll.length });
    artifactCards.innerHTML = resourceCardsHtml(artifactRows, "artifacts", { total: artifactRowsAll.length });
    wireResourceCards(logCards);
    wireResourceCards(artifactCards);
    return;
  }
  if (tab === "config") {
    body.innerHTML = `
      <div class="grid two detail-table-grid">
        ${panel(L("Sources", "来源"), `<div class="record-card-grid" id="project-source-cards"></div>`)}
        ${panel(L("Validations", "验证"), `<div class="record-card-grid" id="project-validation-cards"></div>`)}
      </div>
      ${panel(L("Config highlights", "配置摘要"), configHighlights(config))}
      ${panel(L("Config snapshot", "配置快照"), `
        ${jsonDetails(L("Current config", "当前配置"), config)}
        ${jsonDetails(L("Project record", "项目记录"), detail.project)}
      `)}
    `;
    const sourceCards = document.getElementById("project-source-cards");
    const validationCards = document.getElementById("project-validation-cards");
    sourceCards.innerHTML = sourceCardsHtml(detail.sources || []);
    validationCards.innerHTML = validationCardsHtml(detail.validations || []);
    wireRecordCards(sourceCards, detail.sources || [], "source");
    wireRecordCards(validationCards, detail.validations || [], "validation");
    return;
  }
  if (tab === "audit") {
    body.innerHTML = `
      <div class="grid two detail-table-grid">
        ${panel(L("Annotations", "标注"), `<div class="annotation-feed" id="project-annotation-cards"></div>`)}
        ${panel(L("Audit", "审计"), `<div class="audit-feed compact-feed" id="project-audit-cards"></div>`)}
      </div>
    `;
    const annotationCards = document.getElementById("project-annotation-cards");
    const auditCards = document.getElementById("project-audit-cards");
    annotationCards.innerHTML = annotationCardsHtml(detail.annotations || []);
    auditCards.innerHTML = auditCardsHtml(detail.audit || []);
    wireAnnotationCards(annotationCards, detail.annotations || []);
    wireAuditCards(auditCards, detail.audit || []);
    return;
  }
  body.innerHTML = `
    ${panel(L("Project statistics", "项目统计"), projectStatsHtml(detail))}
    <div class="project-overview-grid">
      ${panel(L("Run reward trend", "运行奖励趋势"), '<div id="project-reward-summary"></div><div class="chart-box project-chart-box"><canvas id="project-reward-chart"></canvas></div>')}
      <div class="project-overview-side">
        ${panel(L("Project highlights", "项目要点"), projectHighlightsHtml(detail))}
        ${panel(L("Project health", "项目健康"), projectHealthHtml(detail))}
      </div>
    </div>
    <div class="grid">
      ${panel(L("Recent runs", "近期运行"), `<div class="run-card-grid bounded-list" id="project-run-cards"></div>`)}
      ${panel(L("Experiments", "实验"), `<div class="experiment-card-grid bounded-list" id="project-exp-cards"></div>`)}
    </div>
  `;
  renderProjectRewardChart(detail);
  const projectOverviewRunCards = document.getElementById("project-run-cards");
  projectOverviewRunCards.innerHTML = runCardsHtml((detail.runs || []).slice(0, 8));
  wireRunCards(projectOverviewRunCards);
  const projectOverviewExpCards = document.getElementById("project-exp-cards");
  projectOverviewExpCards.innerHTML = experimentCardsHtml(detail.experiments || []);
  wireExperimentCards(projectOverviewExpCards);
  wireProjectHighlights(body);
}

async function showExperiment(expId) {
  const detail = await api(`/api/experiments/${encodeURIComponent(expId)}`);
  const exp = detail.experiment;
  const project = state.projects.find((item) => item.project_id === exp.project_id) || {};
  const direction = project.reward_direction || "maximize";
  const finalReward = exp.final_run ? exp.final_run.reward_value : statusLabel("none");
  const experimentTitle = detail.experiment.name || expId;
  showPanel(experimentTitle, `
    <div class="entity-summary">
      <div>
        <div class="metric-label">${escapeHtml(L("Experiment overview", "实验概览"))}</div>
        <div class="project-detail-title">${escapeHtml(exp.goal || exp.exp_id)}</div>
        <div class="summary-note">${escapeHtml(projectName(exp.project_id))} · ${escapeHtml(valueOrNone(exp.branch_name))}</div>
      </div>
      <div class="entity-summary-side">
        ${statusBadge(exp.status)}
        ${relatedActions({ project_id: exp.project_id })}
      </div>
    </div>
    <div class="grid cards compact-cards detail-kpis">
      ${metric(L("Runs", "运行"), detail.runs.length, exp.latest_run ? `${L("latest", "最新")} ${statusLabel(exp.latest_run.status)}` : statusLabel("none"))}
      ${metric(L("Final reward", "最终奖励"), finalReward, exp.final_run ? L("submitted final run", "已提交最终运行") : L("not submitted", "未提交"))}
      ${metric(L("Worktree", "工作树"), statusLabel(exp.worktree_state || "none"), L("current state", "当前状态"))}
      ${metric(L("Tags", "标签"), (detail.tags || []).length, (detail.tags || []).join(", ") || statusLabel("none"))}
    </div>
    <div class="experiment-overview-grid">
      ${panel(L("Reward trend", "奖励趋势"), '<div id="experiment-reward-summary"></div><div class="chart-box"><canvas id="experiment-reward-chart"></canvas></div>')}
      <div class="experiment-overview-side">
        ${panel(L("Experiment highlights", "实验要点"), experimentHighlightsHtml(detail, direction))}
        ${panel(L("Experiment timeline", "实验时间线"), experimentTimelineHtml(exp))}
      </div>
    </div>
    ${panel(L("Runs", "运行"), `<div id="exp-run-controls"></div><div id="exp-run-meta"></div><div class="run-card-grid bounded-list" id="exp-run-cards"></div>`)}
    <div class="grid two detail-table-grid">
      ${panel(L("Logs", "日志"), `<div id="exp-log-controls"></div><div id="exp-log-meta"></div><div class="asset-card-grid bounded-list" id="exp-log-cards"></div>`)}
      ${panel(L("Artifacts", "产物"), `<div id="exp-artifact-controls"></div><div id="exp-artifact-meta"></div><div class="asset-card-grid bounded-list" id="exp-artifact-cards"></div>`)}
    </div>
    ${panel(L("Submission and metadata", "提交与元数据"), `
      ${jsonDetails(L("Submission", "提交"), detail.submission)}
      ${jsonDetails(L("Experiment record", "实验记录"), detail.experiment)}
    `)}
  `, {
    wide: true,
    titleFull: `${L("Experiment", "实验")} ${experimentTitle}`,
    kicker: `${L("Experiment", "实验")} · ${statusLabel(exp.status)}`,
    subtitle: `${projectName(exp.project_id)} · ${valueOrNone(exp.branch_name)}`,
    rerender: () => showExperiment(expId),
    refreshable: true,
  });
  const rerenderExperiment = () => showExperiment(expId);
  const runViewKey = "experiment_runs";
  const runRowsAll = detail.runs || [];
  const runOptions = runFilterOptions(runRowsAll);
  const runSortChoices = runSortOptions();
  const runFilter = activeFilter(runViewKey, runOptions);
  const runSort = activeSort(runViewKey, runSortChoices);
  const runRows = sortRuns(bySearch(filterRuns(runRowsAll, runFilter), ["run_id", "exp_id", "exp_name", "status", "project_id", "failure_reason", "warning_codes"]), runSort);
  const runControls = document.getElementById("exp-run-controls");
  renderListChrome({
    controlsNode: runControls,
    metaNode: document.getElementById("exp-run-meta"),
    view: runViewKey,
    allRows: runRowsAll,
    rows: runRows,
    filterOptions: runOptions,
    sortOptions: runSortChoices,
    filter: runFilter,
    sort: runSort,
    page: detail.pages && detail.pages.runs,
    onChange: rerenderExperiment,
  });
  document.getElementById("experiment-reward-summary").innerHTML = rewardTrendSummaryHtml(runRows, direction);
  renderRewardTrendChart("experiment-reward-chart", runRows, direction);
  const expRunCards = document.getElementById("exp-run-cards");
  expRunCards.innerHTML = runCardsHtml(runRows);
  wireRunCards(expRunCards);
  const logViewKey = "experiment_logs";
  const logRowsAll = detail.logs || [];
  const logOptions = logFilterOptions(logRowsAll);
  const logSortChoices = logSortOptions();
  const logFilter = activeFilter(logViewKey, logOptions);
  const logSort = activeSort(logViewKey, logSortChoices);
  const logRows = sortLogs(bySearch(filterLogs(logRowsAll, logFilter), ["log_id", "stream", "preview_text", "exp_id", "run_id"]), logSort);
  const logControls = document.getElementById("exp-log-controls");
  renderListChrome({
    controlsNode: logControls,
    metaNode: document.getElementById("exp-log-meta"),
    view: logViewKey,
    allRows: logRowsAll,
    rows: logRows,
    filterOptions: logOptions,
    sortOptions: logSortChoices,
    filter: logFilter,
    sort: logSort,
    page: detail.pages && detail.pages.logs,
    onChange: rerenderExperiment,
  });
  const artifactViewKey = "experiment_artifacts";
  const artifactRowsAll = detail.artifacts || [];
  const artifactOptions = artifactFilterOptions(artifactRowsAll);
  const artifactSortChoices = artifactSortOptions();
  const artifactFilter = activeFilter(artifactViewKey, artifactOptions);
  const artifactSort = activeSort(artifactViewKey, artifactSortChoices);
  const artifactRows = sortArtifacts(bySearch(filterArtifacts(artifactRowsAll, artifactFilter), ["artifact_id", "relative_path", "status", "exp_id", "run_id"]), artifactSort);
  const artifactControls = document.getElementById("exp-artifact-controls");
  renderListChrome({
    controlsNode: artifactControls,
    metaNode: document.getElementById("exp-artifact-meta"),
    view: artifactViewKey,
    allRows: artifactRowsAll,
    rows: artifactRows,
    filterOptions: artifactOptions,
    sortOptions: artifactSortChoices,
    filter: artifactFilter,
    sort: artifactSort,
    page: detail.pages && detail.pages.artifacts,
    onChange: rerenderExperiment,
  });
  const expLogCards = document.getElementById("exp-log-cards");
  const expArtifactCards = document.getElementById("exp-artifact-cards");
  expLogCards.innerHTML = resourceCardsHtml(logRows, "logs", { total: logRowsAll.length });
  expArtifactCards.innerHTML = resourceCardsHtml(artifactRows, "artifacts", { total: artifactRowsAll.length });
  wireResourceCards(expLogCards);
  wireResourceCards(expArtifactCards);
  wireExperimentHighlights(document.getElementById("detail-panel"));
  wireRelatedActions(document.getElementById("detail-panel"));
}

async function showRun(runId) {
  const detail = await api(`/api/runs/${encodeURIComponent(runId)}`);
  const run = detail.run;
  const logTotal = (detail.pages && detail.pages.logs && detail.pages.logs.total) || detail.logs.length;
  const artifactTotal = (detail.pages && detail.pages.artifacts && detail.pages.artifacts.total) || detail.artifacts.length;
  showPanel(shortId(runId), `
    <div class="entity-summary">
      <div>
        <div class="metric-label">${escapeHtml(L("Run overview", "运行概览"))}</div>
        <div class="project-detail-title">${escapeHtml(run.exp_name || run.exp_id || run.run_id)}</div>
        <div class="summary-note">${escapeHtml(projectName(run.project_id))} · ${escapeHtml(valueOrNone(run.commit_sha))}</div>
      </div>
      <div class="entity-summary-side">
        ${statusBadge(run.status)}
        ${relatedActions({ project_id: run.project_id, exp_id: run.exp_id })}
      </div>
    </div>
    <div class="grid cards compact-cards detail-kpis">
      ${metric(L("Reward", "奖励"), valueOrNone(run.reward_value), statusLabel(run.reward_parse_status || "none"))}
      ${metric(L("Duration", "耗时"), runDuration(run), `${formatDate(run.started_at)} - ${formatDate(run.ended_at)}`)}
      ${metric(L("Exit", "退出码"), run.exit_code, L("process exit code", "进程退出码"))}
      ${metric(L("Warnings", "警告"), (run.warning_codes || []).length, warningSummary(run.warning_codes))}
      ${metric(L("Artifacts", "产物"), artifactTotal, `${logTotal} ${L("logs", "日志")}`)}
    </div>
    <div class="run-overview-grid">
      ${panel(L("Run highlights", "运行要点"), runHighlightsHtml(detail))}
      <div class="run-overview-side">
        ${panel(L("Run timeline", "运行时间线"), runTimelineHtml(run))}
        ${panel(L("Failure / runner", "失败与运行器"), `
          ${kvList([
            [L("failure reason", "失败原因"), run.failure_reason || statusLabel("none")],
            [L("runner", "运行器"), runnerSummary(run.runner)],
            [L("started", "开始"), formatDate(run.started_at)],
            [L("ended", "结束"), formatDate(run.ended_at)],
          ])}
        `)}
      </div>
    </div>
    ${panel(L("Metrics", "指标"), metricSummaryHtml(run.metrics))}
    <div class="grid two detail-table-grid">
      ${panel(L("Logs", "日志"), `<div id="run-log-controls"></div><div id="run-log-meta"></div><div class="asset-card-grid bounded-list" id="run-log-cards"></div>`)}
      ${panel(L("Artifacts", "产物"), `<div id="run-artifact-controls"></div><div id="run-artifact-meta"></div><div class="asset-card-grid bounded-list" id="run-artifact-cards"></div>`)}
    </div>
    ${panel(L("Raw run record", "原始运行记录"), `
      ${jsonDetails(L("Run record", "运行记录"), detail.run)}
    `)}
  `, {
    wide: true,
    titleFull: `${L("Run", "运行")} ${runId}`,
    kicker: `${L("Run", "运行")} · ${statusLabel(run.status)}`,
    subtitle: `${projectName(run.project_id)} · ${valueOrNone(run.exp_name || run.exp_id)} · ${valueOrNone(run.commit_sha)}`,
    rerender: () => showRun(runId),
    refreshable: true,
  });
  const rerenderRun = () => showRun(runId);
  const logViewKey = "run_logs";
  const logRowsAll = detail.logs || [];
  const logOptions = logFilterOptions(logRowsAll);
  const logSortChoices = logSortOptions();
  const logFilter = activeFilter(logViewKey, logOptions);
  const logSort = activeSort(logViewKey, logSortChoices);
  const logRows = sortLogs(bySearch(filterLogs(logRowsAll, logFilter), ["log_id", "stream", "preview_text", "exp_id", "run_id"]), logSort);
  const logControls = document.getElementById("run-log-controls");
  renderListChrome({
    controlsNode: logControls,
    metaNode: document.getElementById("run-log-meta"),
    view: logViewKey,
    allRows: logRowsAll,
    rows: logRows,
    filterOptions: logOptions,
    sortOptions: logSortChoices,
    filter: logFilter,
    sort: logSort,
    page: detail.pages && detail.pages.logs,
    onChange: rerenderRun,
  });
  const artifactViewKey = "run_artifacts";
  const artifactRowsAll = detail.artifacts || [];
  const artifactOptions = artifactFilterOptions(artifactRowsAll);
  const artifactSortChoices = artifactSortOptions();
  const artifactFilter = activeFilter(artifactViewKey, artifactOptions);
  const artifactSort = activeSort(artifactViewKey, artifactSortChoices);
  const artifactRows = sortArtifacts(bySearch(filterArtifacts(artifactRowsAll, artifactFilter), ["artifact_id", "relative_path", "status", "exp_id", "run_id"]), artifactSort);
  const artifactControls = document.getElementById("run-artifact-controls");
  renderListChrome({
    controlsNode: artifactControls,
    metaNode: document.getElementById("run-artifact-meta"),
    view: artifactViewKey,
    allRows: artifactRowsAll,
    rows: artifactRows,
    filterOptions: artifactOptions,
    sortOptions: artifactSortChoices,
    filter: artifactFilter,
    sort: artifactSort,
    page: detail.pages && detail.pages.artifacts,
    onChange: rerenderRun,
  });
  const runLogCards = document.getElementById("run-log-cards");
  const runArtifactCards = document.getElementById("run-artifact-cards");
  runLogCards.innerHTML = resourceCardsHtml(logRows, "logs", { total: logRowsAll.length });
  runArtifactCards.innerHTML = resourceCardsHtml(artifactRows, "artifacts", { total: artifactRowsAll.length });
  wireResourceCards(runLogCards);
  wireResourceCards(runArtifactCards);
  wireRunHighlights(document.getElementById("detail-panel"));
  wireRelatedActions(document.getElementById("detail-panel"));
}

async function showLog(logId) {
  const chunkLimit = 262144;
  const payload = await api(`/api/logs/${encodeURIComponent(logId)}/content?limit=${chunkLimit}`);
  let content = payload.content;
  let nextOffset = payload.next_offset;
  const log = payload.log;
  showPanel(shortId(logId), `
    ${contextSummary(L("Log context", "日志上下文"), log, [
      [L("stream", "流"), valueOrNone(log.stream)],
      [L("run / validation", "运行/验证"), valueOrNone(log.run_id || log.validation_id)],
      [L("stored", "已存储"), `${formatBytes(log.stored_bytes)} / ${formatBytes(log.size_bytes)}`],
      [L("created", "创建"), formatDate(log.created_at)],
    ], statusBadge(log.hidden ? "hidden" : "visible"))}
    ${panel(L("Log evidence", "日志证据"), logHighlightsHtml(log, payload, content))}
    ${panel(L("Content", "内容"), `
      <div class="log-tools">
        <div class="log-search-row">
          <input id="log-search" type="search" autocomplete="off" aria-label="${escapeHtml(L("Find in log", "在日志中查找"))}" placeholder="${escapeHtml(L("Find in log", "在日志中查找"))}">
          <span id="log-load-state" class="muted log-state-pill" title="${escapeHtml(L("Loaded log bytes", "已加载日志字节"))}" aria-label="${escapeHtml(L("Loaded log bytes", "已加载日志字节"))}">${escapeHtml(formatBytes(content.length))} / ${escapeHtml(formatBytes(payload.size))}</span>
        </div>
        <div class="log-action-row">
          <span id="log-search-count" class="muted log-search-status" role="status" aria-live="polite"></span>
          <span id="log-copy-status" class="muted log-copy-status" role="status" aria-live="polite"></span>
          <button class="secondary-button log-match-button" id="log-prev-match" type="button" title="${escapeHtml(L("Previous match", "上一处匹配"))}" disabled>${escapeHtml(L("Previous", "上一处"))}</button>
          <button class="secondary-button log-match-button" id="log-next-match" type="button" title="${escapeHtml(L("Next match", "下一处匹配"))}" disabled>${escapeHtml(L("Next", "下一处"))}</button>
          <button class="secondary-button" id="copy-log" type="button" title="${escapeHtml(L("Copy loaded log content", "复制已加载日志内容"))}">${escapeHtml(L("Copy", "复制"))}</button>
          <button class="secondary-button" id="load-log-more" type="button" title="${escapeHtml(L("Load the next log chunk", "加载下一段日志"))}" ${nextOffset === null ? "disabled" : ""}>${escapeHtml(L("Load more", "加载更多"))}</button>
        </div>
      </div>
      <pre id="log-content">${escapeHtml(content)}</pre>
    `, `<button class="secondary-button" id="download-log" type="button">${escapeHtml(L("Download", "下载"))}</button>`)}
    ${panel(L("Metadata", "元数据"), `
      ${jsonDetails(L("Log record", "日志记录"), log)}
    `)}
  `, {
    titleFull: `${L("Log", "日志")} ${logId}`,
    kicker: `${L("Log", "日志")} · ${statusLabel(log.hidden ? "hidden" : "visible")}`,
    subtitle: `${projectName(log.project_id)} · ${valueOrNone(log.run_id || log.validation_id)} · ${valueOrNone(log.stream)}`,
    rerender: () => showLog(logId),
    refreshable: true,
  });
  wireEvidenceHighlights(document.getElementById("detail-panel"));
  wireRelatedActions(document.getElementById("detail-panel"));
  let activeLogMatch = 0;
  const applyLogSearch = (index = 0) => {
    const result = renderLogSearch(content, document.getElementById("log-search").value, index);
    activeLogMatch = result.activeIndex;
  };
  document.getElementById("download-log").addEventListener("click", () => downloadBlob(`/api/logs/${encodeURIComponent(logId)}/download`, `${logId}.log`));
  document.getElementById("copy-log").addEventListener("click", async () => {
    const copyStatus = document.getElementById("log-copy-status");
    try {
      await copyTextToClipboard(content);
      copyStatus.textContent = L("copied loaded content", "已复制已加载内容");
    } catch (_error) {
      copyStatus.textContent = L("copy failed", "复制失败");
    }
  });
  document.getElementById("log-search").addEventListener("input", (event) => {
    document.getElementById("log-copy-status").textContent = "";
    activeLogMatch = 0;
    const result = renderLogSearch(content, event.target.value, activeLogMatch);
    activeLogMatch = result.activeIndex;
  });
  document.getElementById("log-prev-match").addEventListener("click", () => {
    applyLogSearch(activeLogMatch - 1);
  });
  document.getElementById("log-next-match").addEventListener("click", () => {
    applyLogSearch(activeLogMatch + 1);
  });
  document.getElementById("load-log-more").addEventListener("click", async () => {
    if (nextOffset === null) return;
    const chunk = await api(`/api/logs/${encodeURIComponent(logId)}/content?offset=${nextOffset}&limit=${chunkLimit}`);
    content += chunk.content;
    nextOffset = chunk.next_offset;
    document.getElementById("load-log-more").disabled = nextOffset === null;
    document.getElementById("log-load-state").textContent = `${formatBytes(content.length)} / ${formatBytes(chunk.size)}`;
    document.getElementById("log-copy-status").textContent = "";
    applyLogSearch(activeLogMatch);
  });
}

function renderLogSearch(content, query, activeIndex = 0) {
  const target = document.getElementById("log-content");
  const count = document.getElementById("log-search-count");
  const prev = document.getElementById("log-prev-match");
  const next = document.getElementById("log-next-match");
  const needle = query.trim();
  if (!needle) {
    target.innerHTML = escapeHtml(content);
    count.textContent = "";
    if (prev) prev.disabled = true;
    if (next) next.disabled = true;
    return { matches: 0, activeIndex: 0 };
  }
  const lowerContent = content.toLowerCase();
  const lowerNeedle = needle.toLowerCase();
  let cursor = 0;
  let matches = 0;
  let html = "";
  while (true) {
    const index = lowerContent.indexOf(lowerNeedle, cursor);
    if (index === -1) break;
    matches += 1;
    html += escapeHtml(content.slice(cursor, index));
    html += `<mark data-log-match="${matches - 1}">${escapeHtml(content.slice(index, index + needle.length))}</mark>`;
    cursor = index + needle.length;
  }
  html += escapeHtml(content.slice(cursor));
  target.innerHTML = html;
  const hasMatches = matches > 0;
  const canStep = matches > 1;
  if (prev) prev.disabled = !canStep;
  if (next) next.disabled = !canStep;
  if (!hasMatches) {
    count.textContent = L("no matches", "无匹配");
    return { matches: 0, activeIndex: 0 };
  }
  const safeIndex = ((activeIndex % matches) + matches) % matches;
  const active = target.querySelector(`[data-log-match="${safeIndex}"]`);
  if (active) {
    active.classList.add("active-log-match");
    active.scrollIntoView({ block: "center", inline: "nearest" });
  }
  count.textContent = `${safeIndex + 1} / ${matches} ${L("matches", "处匹配")}`;
  return { matches, activeIndex: safeIndex };
}

function artifactPreviewHtml(preview) {
  if (preview.kind === "text") {
    return `<pre class="preview-code">${escapeHtml(preview.content)}</pre>`;
  }
  if (preview.kind === "image") {
    return `<img class="preview-image" src="${escapeHtml(preview.data_url)}" alt="${escapeHtml(L("artifact preview", "产物预览"))}">`;
  }
  if (preview.kind === "too_large") {
    return previewStateHtml(
      L("Preview too large", "预览过大"),
      `${escapeHtml(preview.content_type || "application/octet-stream")} · ${escapeHtml(L("limit", "上限"))} ${escapeHtml(formatBytes(preview.limit))}`,
    );
  }
  if (preview.kind === "binary") {
    return previewStateHtml(
      L("Binary artifact", "二进制产物"),
      `${escapeHtml(preview.content_type || "application/octet-stream")} · ${escapeHtml(formatBytes(preview.size))}`,
    );
  }
  if (preview.kind === "unavailable") {
    return previewStateHtml(
      L("Preview unavailable", "无法预览"),
      `${escapeHtml(L("status", "状态"))}: ${escapeHtml(statusLabel(preview.reason))}`,
    );
  }
  return previewStateHtml(L("Preview metadata", "预览元数据"), escapeHtml(JSON.stringify(preview)));
}

function previewStateHtml(title, detail) {
  return `
    <div class="preview-state">
      <strong>${escapeHtml(title)}</strong>
      <span>${detail}</span>
    </div>
  `;
}

async function showArtifact(artifactId) {
  const payload = await api(`/api/artifacts/${encodeURIComponent(artifactId)}/preview`);
  const artifact = payload.artifact;
  const preview = artifactPreviewHtml(payload.preview);
  const isTextPreview = payload.preview && payload.preview.kind === "text";
  const previewActions = `
    <button class="secondary-button" id="download-artifact" type="button" title="${escapeHtml(L("Download raw artifact", "下载原始产物"))}" aria-label="${escapeHtml(L("Download raw artifact", "下载原始产物"))}">${escapeHtml(L("Download", "下载"))}</button>
    ${isTextPreview ? `<button class="secondary-button" id="copy-artifact-preview" type="button" title="${escapeHtml(L("Copy text preview", "复制文本预览"))}" aria-label="${escapeHtml(L("Copy text preview", "复制文本预览"))}">${escapeHtml(L("Copy preview", "复制预览"))}</button><span id="artifact-copy-status" class="muted artifact-copy-status" role="status" aria-live="polite"></span>` : ""}
  `;
  showPanel(shortId(artifactId), `
    ${contextSummary(L("Artifact context", "产物上下文"), artifact, [
      [L("path", "路径"), valueOrNone(artifact.relative_path)],
      [L("run / validation", "运行/验证"), valueOrNone(artifact.run_id || artifact.validation_id)],
      [L("size", "大小"), formatBytes(artifact.size_bytes)],
      [L("root", "根"), valueOrNone(artifact.root)],
    ], statusBadge(artifact.status))}
    ${panel(L("Artifact evidence", "产物证据"), artifactHighlightsHtml(artifact, payload.preview))}
    ${panel(L("Preview", "预览"), preview, previewActions)}
    ${panel(L("Metadata", "元数据"), `
      ${jsonDetails(L("Artifact record", "产物记录"), artifact)}
    `)}
  `, {
    titleFull: `${L("Artifact", "产物")} ${artifactId}`,
    kicker: `${L("Artifact", "产物")} · ${statusLabel(artifact.status)}`,
    subtitle: `${projectName(artifact.project_id)} · ${valueOrNone(artifact.run_id || artifact.validation_id)} · ${valueOrNone(artifact.relative_path)}`,
    rerender: () => showArtifact(artifactId),
    refreshable: true,
  });
  wireEvidenceHighlights(document.getElementById("detail-panel"));
  wireRelatedActions(document.getElementById("detail-panel"));
  document.getElementById("download-artifact").addEventListener("click", () => downloadBlob(`/api/artifacts/${encodeURIComponent(artifactId)}/download`, artifact.relative_path || `${artifactId}.artifact`));
  const copyPreview = document.getElementById("copy-artifact-preview");
  if (copyPreview) {
    copyPreview.addEventListener("click", async () => {
      const status = document.getElementById("artifact-copy-status");
      try {
        await copyTextToClipboard(payload.preview.content || "");
        status.textContent = L("copied preview", "已复制预览");
      } catch (_error) {
        status.textContent = L("copy failed", "复制失败");
      }
    });
  }
}

async function downloadBlob(path, filename) {
  const blob = await apiBlob(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.className = "clipboard-buffer";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("copy failed");
}

function wireInteractiveFocusState() {
  const clear = (except = null) => {
    for (const node of document.querySelectorAll(`${INTERACTIVE_CARD_SELECTOR}.is-focused`)) {
      if (node !== except) node.classList.remove("is-focused");
    }
  };
  const mark = (target) => {
    const card = target && target.closest ? target.closest(INTERACTIVE_CARD_SELECTOR) : null;
    clear(card);
    if (card) card.classList.add("is-focused");
  };
  document.addEventListener("focusin", (event) => mark(event.target));
  document.addEventListener("focusout", (event) => {
    const target = event.target.closest(INTERACTIVE_CARD_SELECTOR);
    if (target) target.classList.remove("is-focused");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Tab" || event.key.startsWith("Arrow") || event.key === "Enter" || event.key === " ") {
      mark(event.target);
      window.requestAnimationFrame(() => mark(document.activeElement || event.target));
    }
  });
  document.addEventListener("pointerdown", () => clear());
}

function wireControls() {
  const detailBackdrop = document.getElementById("detail-backdrop");
  if (detailBackdrop) {
    detailBackdrop.addEventListener("click", () => closeDetailPanel());
  }
  const search = document.getElementById("global-search");
  search.value = state.search;
  search.addEventListener("input", () => {
    state.search = search.value;
    updateSearchQuery(state.search);
    renderSearchControl();
    render();
  });
  const clearSearch = document.getElementById("clear-search");
  clearSearch.addEventListener("click", () => {
    state.search = "";
    search.value = "";
    updateSearchQuery("");
    renderSearchControl();
    render();
  });
  const language = document.getElementById("language-select");
  language.value = state.language;
  language.addEventListener("change", async () => {
    state.language = language.value;
    localStorage.setItem("alab-dashboard-language", state.language);
    await render();
    await rerenderOpenDetailPanel();
  });
  document.getElementById("refresh-now").addEventListener("click", refresh);
  document.getElementById("refresh-toggle").addEventListener("click", () => {
    state.paused = !state.paused;
    renderRefreshButton();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDetailPanel();
    } else if (event.key === "Tab") {
      trapDetailPanelFocus(event);
    }
  });
  renderRefreshButton();
}

function renderRefreshButton() {
  const button = document.getElementById("refresh-toggle");
  if (state.refreshSeconds <= 0) {
    button.replaceChildren(icon("pause"));
    button.title = t("global.autoDisabled");
    button.setAttribute("aria-label", t("global.autoDisabled"));
    button.removeAttribute("aria-pressed");
    button.disabled = true;
    return;
  }
  button.disabled = false;
  button.replaceChildren(icon(state.paused ? "refresh-cw" : "pause"));
  button.title = state.paused ? t("global.resume") : t("global.pause");
  button.setAttribute("aria-label", state.paused ? t("global.resume") : t("global.pause"));
  button.setAttribute("aria-pressed", String(state.paused));
}

async function refresh() {
  try {
    await loadCore();
    await render();
    renderRefreshButton();
    renderFreshness();
  } catch (error) {
    document.getElementById("content").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

async function boot() {
  state.token = tokenFromLocation();
  wireInteractiveFocusState();
  wireControls();
  await refresh();
  if (state.refreshSeconds > 0) {
    window.setInterval(() => {
      if (!state.paused) refresh();
    }, state.refreshSeconds * 1000);
  }
}

boot();
