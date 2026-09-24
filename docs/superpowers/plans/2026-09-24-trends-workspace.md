# Google Trends 工作台实施计划

**Goal:** 交付可本地运行的中文搜索词趋势分析应用与完整使用文档。

**Architecture:** FastAPI 同源提供网页与数据接口。trendspyg 负责真实数据，独立 worker 隔离浏览器；显式演示模式使用确定性合成数据。

**Tech Stack:** Python 3.11+、FastAPI、Uvicorn、trendspyg、原生 HTML/CSS/JavaScript、pytest。

**Spec:** [设计说明](../specs/2026-09-24-trends-workspace-design.md)

## 全局约束

- 仅监听 127.0.0.1，单用户本地应用。
- 同次比较 1–5 个关键词；真实与演示结果不可混淆。
- 查询参数与结果绑定，CSV 保留来源、时间、地区和查询类型。
- 查询超时终止 worker 与子浏览器；缓存有数量和过期上限。
- 原生网页无构建工具依赖，中文界面适配 390px 及以上。

## 审查重点

1. 空白或重复词、含中文标点和特殊符号的关键词：正规化、去重与编码。
2. 上游无数据或数据结构变化：不画虚假的零曲线，不泄漏异常堆栈。
3. 查询中切换视图、模式或筛选：忽略过时响应，保留查询元数据。
4. RSS 新闻内容包含 HTML 或恶意协议：文本显示与 URL 协议过滤。
5. 关键词以等号等字符开头：CSV 不触发表格公式。

## 实施任务

- [x] 数据与服务：创建 `app/models.py`、`app/providers.py`、`app/worker.py`、`app/demo.py`、`app/main.py`。接口为 `POST /api/explore`、`GET /api/trending`、`GET /api/health`。为校验、两种上游结构、限流/超时与缓存建立离线测试；通过 `python -m pytest` 验证。
- [x] 网页：创建 `app/static/index.html`、`styles.css`、`app.js`、`utils.js`。实现探索表单、交互曲线、热搜列表、地区和相关词、本地收藏、CSV 与外链。使用 `node --test tests/frontend.test.mjs` 验证工具函数，再用真实浏览器验证完整操作链与响应式。
- [x] 交付：创建 README、需求与任务说明、来源/许可证说明、启动脚本和锁定依赖。实测实时 RSS、至少一次真实关键词查询，记录结果与限制；确保新环境可按文档安装启动。

## 执行方式

按用户“继续完成项目”的授权在当前任务逐项实现和自检。无需并行代理；不会自动发布、推送或创建远程仓库。

