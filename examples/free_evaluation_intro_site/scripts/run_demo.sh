#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$EXAMPLE_DIR/../.." && pwd)"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/run_demo.sh [--dry-run]

Creates one free-evaluation experiment, applies a deterministic website
completion, submits directly, and writes a compact report.
EOF
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

RUN_DIR="$EXAMPLE_DIR/.run"
PROJECT_ENV="$RUN_DIR/secrets/project.env"
LOG_DIR="$RUN_DIR/logs"
REPORT_DIR="${ALAB_REPORT_DIR:-$RUN_DIR/reports}"
WORKTREE_ROOT="${ALAB_EXAMPLE_WORKTREE_ROOT:-$RUN_DIR/worktrees}"
EXP_NAME="${EXP_NAME:-free-evaluation-intro-site-manual}"
UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://pypi.org/simple}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would create and submit a free-evaluation website experiment.

Project env: $PROJECT_ENV
Experiment:  $EXP_NAME
Worktree:    $WORKTREE_ROOT/$EXP_NAME
uv index:    $UV_DEFAULT_INDEX

No alab run command will be executed for this project.
EOF
  exit 0
fi

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"

mkdir -p "$LOG_DIR" "$REPORT_DIR" "$WORKTREE_ROOT"
read -r -a ALAB_CMD <<< "${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"

run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}

extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

CREATE_LOG="$LOG_DIR/manual-exp-create.log"
SUBMIT_LOG="$LOG_DIR/manual-submit.log"
SHOW_LOG="$LOG_DIR/manual-exp-show.log"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
EXP_ID="$(extract_field "exp id" "$CREATE_LOG")"

cat > "$WORKTREE_PATH/index.html" <<'EOF'
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>所有人都在与自己的无价值感斗争 | 中文介绍</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="#top" aria-label="返回页首">
        <span class="brand-mark" aria-hidden="true"></span>
        <span>We Are All Trying Here</span>
      </a>
      <nav class="nav" aria-label="页面导航">
        <a href="#overview">概览</a>
        <a href="#why">为什么看</a>
        <a href="#guide">无剧透指南</a>
      </nav>
    </header>

    <main id="top">
      <section class="hero" aria-labelledby="page-title">
        <div class="hero-copy">
          <p class="kicker">JTBC · 2026 · 生活切片 / 心理剧</p>
          <h1 id="page-title">所有人都在与自己的无价值感斗争</h1>
          <p class="subtitle">
            《모두가 자신의 무가치함과 싸우고 있다》把“我是不是不够好”这种难以启齿的念头，
            拍成一群成年人互相试探、崩溃、靠近与重新确认自我的故事。
          </p>
          <div class="hero-actions">
            <a class="primary-link" href="#overview">读剧集介绍</a>
            <a class="secondary-link" href="#guide">查看观看指南</a>
          </div>
        </div>
        <figure class="key-visual" aria-label="城市窗光中的抽象人物剪影">
          <img src="assets/hero-scene.png" alt="城市夜景窗光下的三个人物剪影" />
          <figcaption>一座城市里，每个人都在和自己的价值感谈判。</figcaption>
        </figure>
      </section>

      <section id="overview" class="section overview" aria-labelledby="overview-title">
        <div class="section-heading">
          <p class="eyebrow">Overview</p>
          <h2 id="overview-title">剧集概览</h2>
        </div>
        <div class="copy-panel two-column">
          <p>
            这是一部以现实情绪为核心的韩剧。它关心的不是“成功的人如何继续成功”，
            而是那些在朋友、同事和亲密关系面前总觉得自己落后一截的人，如何把羞耻、
            嫉妒和孤独说出口。
          </p>
          <p>
            剧名直译近似“所有人都在与自己的无价值感斗争”。中文介绍页可以把它理解为：
            每个人都想被看见，但每个人也都害怕自己根本不值得被爱。
          </p>
        </div>
      </section>

      <section id="why" class="section" aria-labelledby="why-title">
        <div class="section-heading">
          <p class="eyebrow">Why Watch</p>
          <h2 id="why-title">为什么值得关注</h2>
        </div>
        <div class="thread-grid">
          <article>
            <h3>它写失败感</h3>
            <p>人物不是简单地逆袭，而是在“做不到”和“还想试试”之间反复摇摆。</p>
          </article>
          <article>
            <h3>它写关系里的镜子</h3>
            <p>别人身上的成功、脆弱和执拗，会照出主角最不愿承认的缺口。</p>
          </article>
          <article>
            <h3>它适合慢慢看</h3>
            <p>这类剧的重量通常藏在沉默、停顿、台词余味和人物回望里。</p>
          </article>
        </div>
      </section>

      <section id="guide" class="section guide" aria-labelledby="guide-title">
        <div class="section-heading">
          <p class="eyebrow">Spoiler-safe Guide</p>
          <h2 id="guide-title">无剧透观看指南</h2>
        </div>
        <ul class="guide-list">
          <li>适合喜欢《我的大叔》《我的解放日志》式现实情绪和人物群像的观众。</li>
          <li>建议先把它当作人物剧，而不是强情节爽剧。</li>
          <li>如果要补充平台、集数、收视或结局信息，请先核对官方或可靠来源。</li>
        </ul>
      </section>

      <section class="section credits" aria-labelledby="credits-title">
        <div class="section-heading">
          <p class="eyebrow">Credits</p>
          <h2 id="credits-title">资料与署名提示</h2>
        </div>
        <p>
          公开资料显示，本剧由朴海英编剧、车荣勋执导，常见英文名为
          <span lang="en">We Are All Trying Here</span>。本示例不内置自动事实校验；
          正式发布前请再次确认播出、平台和演员信息。
        </p>
      </section>
    </main>

    <footer class="site-footer">
      <p>ALab free evaluation example. Manual review replaces numeric reward.</p>
      <button type="button" id="theme-toggle" aria-pressed="false">切换夜间氛围</button>
    </footer>

    <script src="script.js"></script>
  </body>
</html>
EOF

cat > "$WORKTREE_PATH/styles.css" <<'EOF'
:root {
  color-scheme: light;
  --bg: #f3efe5;
  --ink: #1f2527;
  --muted: #626a6d;
  --line: #d9d0c1;
  --panel: #fffaf1;
  --accent: #2d7670;
  --accent-dark: #174f52;
  --warm: #b35c3f;
  --shadow: 0 22px 60px rgba(26, 34, 38, 0.16);
}

body.night {
  color-scheme: dark;
  --bg: #101820;
  --ink: #edf1ea;
  --muted: #aeb8b7;
  --line: #2a3a40;
  --panel: #18242b;
  --accent: #7bc0b2;
  --accent-dark: #9fd4cb;
  --warm: #e4a36c;
  --shadow: 0 22px 60px rgba(0, 0, 0, 0.36);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  line-height: 1.65;
}

a {
  color: inherit;
}

.site-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem clamp(1rem, 4vw, 3rem);
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 90%, transparent);
  backdrop-filter: blur(16px);
}

.brand,
.nav,
.hero-actions,
.site-footer {
  display: flex;
  align-items: center;
}

.brand {
  gap: 0.65rem;
  font-weight: 750;
  text-decoration: none;
}

.brand-mark {
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  border: 2px solid var(--accent);
  box-shadow: inset 0 0 0 4px color-mix(in srgb, var(--accent) 24%, transparent);
}

.nav {
  gap: 0.35rem;
}

.nav a,
.primary-link,
.secondary-link,
.site-footer button {
  min-height: 2.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.9rem;
  border-radius: 0.45rem;
  font-weight: 700;
  text-decoration: none;
}

.nav a {
  color: var(--muted);
}

.nav a:hover {
  color: var(--ink);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

main,
.site-footer {
  width: min(1120px, calc(100vw - 2rem));
  margin: 0 auto;
}

.hero {
  min-height: calc(100vh - 5rem);
  display: grid;
  grid-template-columns: minmax(0, 1.04fr) minmax(18rem, 0.96fr);
  align-items: center;
  gap: clamp(2rem, 6vw, 5rem);
  padding: clamp(3rem, 7vw, 6rem) 0;
}

.kicker,
.eyebrow {
  margin: 0 0 0.75rem;
  color: var(--warm);
  font-size: 0.82rem;
  font-weight: 850;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  max-width: 12.5ch;
  margin-bottom: 1.25rem;
  font-size: clamp(2.7rem, 8.5vw, 5.7rem);
  line-height: 0.98;
  letter-spacing: 0;
}

h2 {
  font-size: clamp(1.9rem, 4vw, 3rem);
  line-height: 1.12;
  letter-spacing: 0;
}

.subtitle {
  max-width: 43rem;
  color: var(--muted);
  font-size: 1.06rem;
}

.hero-actions {
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 1.75rem;
}

.primary-link {
  background: var(--accent);
  color: white;
}

.secondary-link {
  border: 1px solid var(--line);
  color: var(--accent-dark);
}

.key-visual {
  margin: 0;
  min-height: 30rem;
  display: grid;
  grid-template-rows: 1fr auto;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: #132129;
  box-shadow: var(--shadow);
}

.key-visual img {
  width: 100%;
  height: 100%;
  min-height: 26rem;
  object-fit: cover;
}

.key-visual figcaption {
  padding: 1rem;
  color: #e5e9e4;
  background: rgba(0, 0, 0, 0.36);
}

.section {
  padding: 4rem 0;
  border-top: 1px solid var(--line);
}

.section-heading {
  max-width: 38rem;
  margin-bottom: 1.5rem;
}

.copy-panel,
.thread-grid article {
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: var(--panel);
}

.copy-panel {
  padding: clamp(1.25rem, 3vw, 2rem);
}

.two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem;
}

.thread-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.thread-grid article {
  min-height: 13rem;
  padding: 1.2rem;
}

.thread-grid h3 {
  margin-bottom: 0.65rem;
}

.guide-list {
  max-width: 54rem;
  margin: 0;
  padding-left: 1.25rem;
  color: var(--muted);
}

.credits p {
  max-width: 58rem;
  color: var(--muted);
}

.site-footer {
  justify-content: space-between;
  gap: 1rem;
  padding: 2rem 0 3rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
}

.site-footer p {
  margin: 0;
}

.site-footer button {
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  cursor: pointer;
}

@media (max-width: 760px) {
  .site-header,
  .site-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .nav {
    width: 100%;
    justify-content: space-between;
  }

  .hero,
  .two-column {
    min-height: auto;
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 3rem;
  }

  .key-visual {
    min-height: 22rem;
  }

  .thread-grid {
    grid-template-columns: 1fr;
  }
}
EOF

cat > "$WORKTREE_PATH/script.js" <<'EOF'
const toggle = document.querySelector("#theme-toggle");

if (toggle) {
  toggle.addEventListener("click", () => {
    const enabled = document.body.classList.toggle("night");
    toggle.setAttribute("aria-pressed", String(enabled));
    toggle.textContent = enabled ? "切换白天氛围" : "切换夜间氛围";
  });
}
EOF

(cd "$WORKTREE_PATH" && run_alab submit --message "complete Chinese drama intro site" --summary "Completed a spoiler-safe Simplified Chinese introduction site with overview, reasons to watch, viewing guide, visual polish, and source caution notes." --feedback "Free evaluation project: no runner was expected. Review index.html directly in a browser and inspect the final commit for source changes." --ref none) | tee "$SUBMIT_LOG"

run_alab --key "$ALAB_PROJECT_KEY" exp show --project "$ALAB_PROJECT_ID" "$EXP_ID" | tee "$SHOW_LOG"

REPORT_PATH="$REPORT_DIR/project-report.md"
run_alab --key "$ALAB_PROJECT_KEY" report --project "$ALAB_PROJECT_ID" --out "$REPORT_PATH" --overwrite >/dev/null

cat > "$REPORT_DIR/report.md" <<EOF
# Free Evaluation Intro Site Report

- Experiment: \`$EXP_ID\`
- Worktree: \`$WORKTREE_PATH\`
- Submitted page: \`$WORKTREE_PATH/index.html\`
- Submit log: \`$SUBMIT_LOG\`
- Experiment show log: \`$SHOW_LOG\`
- Project report: \`$REPORT_PATH\`

This project has no evaluator runs. Review the final commit and open
\`index.html\` directly in a browser.
EOF

echo "Report written: $REPORT_DIR/report.md"
echo "Open site: $WORKTREE_PATH/index.html"
