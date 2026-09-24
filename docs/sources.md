# 开源调研与技术选择

核对日期：2026-09-24。Star 与维护状态为当时快照，并不保证数据接口持续可用。

| 仓库 | Star | 许可证 | 选择结论 |
|---|---:|---|---|
| [flack0x/trendspyg](https://github.com/flack0x/trendspyg) | 50 | MIT | 采用 1.8.0，具备 RSS、浏览器 Explore、共享量纲比较和统一数据结构 |
| [akvise/trends-checker](https://github.com/akvise/trends-checker) | 392 | MIT | 可用作命令行研究工具；依赖 pytrends，付费备用后端不纳入本项目 |
| [sdil87/trendspy](https://github.com/sdil87/trendspy) | 121 | MIT | 功能较全，但最近提交停留在 2024-12 |
| [pat310/google-trends-api](https://github.com/pat310/google-trends-api) | 974 | MIT | Node.js 历史方案，更新较旧，未采用 |
| [GeneralMills/pytrends](https://github.com/GeneralMills/pytrends) | 3,729 | Apache-2.0 | 2025-04-17 已归档，未作为本项目直接依赖 |
| [chrisrzhou/google-globe-trends](https://github.com/chrisrzhou/google-globe-trends) | 44 | MIT | 地球可视化参考，未复用代码 |

## 文档依据

通过 Context7 MCP 先解析库 ID，再查询文档：

- `/websites/fastapi_tiangolo`：请求体、StaticFiles、JSONResponse 和 TestClient；对应 [FastAPI 官方文档](https://fastapi.tiangolo.com/)。
- `/flack0x/trendspyg`：ExploreEnvelope、ComparisonEnvelope、RSS 标准化结构和重试/浏览器约束；对应 [trendspyg API 文档](https://github.com/flack0x/trendspyg/blob/main/docs/API.md)。
- 安装的 1.8.0 源码签名与 Context7 结果交叉核对，避免以旧接口编写适配。

本项目通过公开 Python 包调用 trendspyg，没有复制其源码或以官方 Google API 产品名义提供服务。
