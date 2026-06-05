# Free Evaluation 中文介绍站示例

这个示例演示 ALab free evaluation mode 下的开放式静态网站任务。Project 使用
`runner.type = "none"` 和 `reward.type = "none"`，所以 experiment 会直接
submit，由 project owner 人工查看 final commit，而不是读取 numeric reward。

## Demo 任务

把 `source/index.html`、`source/styles.css` 和 `source/script.js` 完成一个简体
中文介绍网站，主题是 JTBC 韩剧 `모두가 자신의 무가치함과 싸우고 있다`。

任务形态：

- 可编辑文件：`index.html`、`styles.css`、`script.js` 和 `content-notes.md`。
- Baseline behavior：一个可以直接打开、但文案和视觉仍待完善的静态页面。
- Demo improvement：`scripts/run_demo.sh` 会创建一个 experiment，把 starter
  替换成更完整的中文页面，然后不运行 evaluator 直接 submit。
- Review source：submitted commit、summary 和 feedback。
- Reward source：无。这个项目有意只做 manual review。

当任务依赖审美、写作质量、事实谨慎度或 product judgment，而不是可重复 local score
时，可以使用这个示例。

## 覆盖内容

- free evaluation project config；
- project init 时的 `not_required` validation status；
- 不经过 `alab run` 的 direct `alab submit`；
- 渲染为 `none` 的 nullable `final run id`；
- 设计和写作任务的 manual review workflow。

## 运行

从仓库根目录执行：

```sh
examples/free_evaluation_intro_site/scripts/setup_project.sh --dry-run
examples/free_evaluation_intro_site/scripts/setup_project.sh
examples/free_evaluation_intro_site/scripts/run_demo.sh
```

Generated state 会保存在 ignored `.run/` 下。Project admin key 只保存到
`.run/secrets/project.env`；workers 使用 public experiment creation 和
token-scoped submission，不需要 project admin key。

## 查看结果

运行 `scripts/run_demo.sh` 后，直接用浏览器打开 submitted worktree 里的
`index.html`。脚本也会把 compact report 写到：

```text
examples/free_evaluation_intro_site/.run/reports/report.md
```

Free evaluation 不会创建 run、log、artifact 或 reward rows。请查看 experiment
submission 和 final commit。
