<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./brand/logo-dark.svg">
  <img src="./brand/logo.svg" alt="Hivemind" width="360">
</picture>

**社会群体智能模拟。围绕任何事件搭建一个模拟互联网，观察它如何反应。**

[English](./README.md) | [中文文档](./README-ZH.md)

### [在线体验 → hivemind-production-25f13fa5.up.railway.app](https://hivemind-production-25f13fa5.up.railway.app)

<sub>公开演示站：所有访客每天共 5 次新运行，每次最多 10 轮。历史运行可随意浏览。</sub>

</div>

Hivemind 把一个问题变成一群模拟的公众。给它一个情境（只需一个问题，或问题加资料），它会把相关的人物、组织和关系整理成知识图谱，把其中每个角色变成一个拥有人设和记忆的 AI 智能体，并让它们在两个模拟社交平台（类 Twitter 信息流和类 Reddit 论坛）上逐轮发帖、评论、点赞和争论。运行结束后，它用通俗的语言说明各方在哪里达成一致、在哪里分歧，以及每个群体可能如何回应；你还可以向报告智能体提问，或采访任何一个模拟参与者。

所有参与者均为模拟。这是一次预演，不是真实事件的记录，也不是可以据此行动的预测。

## 一次运行的流程

| 阶段 | 内容 |
| --- | --- |
| 1. 知识图谱 | 模型阅读你的资料和问题（没有资料时先自行撰写背景简报），设计本体（10 类角色及其关系），再由 Zep Cloud 抽取实体与关系，构建时序知识图谱。 |
| 2. 智能体设定 | 图谱中每个已分类的实体成为一个智能体并获得人设；模型设定模拟时钟、开场帖子和每个智能体的活跃度；Hivemind 还会补充关键角色身边的人。 |
| 3. 模拟 | 独立的 CAMEL-AI OASIS 进程并行运行两个平台，每轮随机激活部分智能体，由模型为其选择行动；所有行动写入日志并作为记忆写回图谱。最后一轮结束后智能体保持在线，以便采访。 |
| 4. 报告 | 报告智能体规划 2 到 5 个章节，借助图谱检索和实时采访工具逐章撰写。 |
| 5. 互动 | 与报告智能体对话、采访任意模拟人物，或同时向多人发起问卷。 |

运行结束后，分析页面会给出简报（结论与可信度、共识与分歧、各群体与各公司的反应和可能的下一步）、运行经过、智能体关系网络、传播树和运行健康检查，并可下载简报 PDF。

## 快速开始

需要 Node.js 20.19 及以上（推荐 22）、Python 3.12 和 [uv](https://docs.astral.sh/uv/)，以及两个你自己的密钥：

| 密钥 | 用途 | 获取地址 |
| --- | --- | --- |
| `LLM_API_KEY` | Claude，扮演每个模拟参与者并撰写简报 | [console.anthropic.com](https://console.anthropic.com/) |
| `ZEP_API_KEY` | 知识图谱与智能体记忆 | [app.getzep.com](https://app.getzep.com/)（免费额度足够小规模运行） |

```bash
git clone https://github.com/slimboi34/hivemind.git
cd hivemind
./hivemind.sh       # 首次运行会创建 .env，并提示需要填写的两行
```

在 `.env` 中填入两个密钥后再次运行 `./hivemind.sh`。应用地址：http://localhost:3000 ，API 地址：http://localhost:5001 。密钥只保存在 `.env` 中，该文件已被 gitignore，不会被提交。界面支持英文和中文，可通过语言切换器切换。

## 文档（英文）

| 文档 | 内容 |
| --- | --- |
| [README](./README.md) | 项目总览、功能介绍与截图 |
| [Architecture](./docs/ARCHITECTURE.md) | 组件、进程模型、数据流、磁盘存储、外部服务与设计决策 |
| [Pipeline](./docs/PIPELINE.md) | 各阶段详解：接口、代码、提示词、写入的文件、耗时与成本 |
| [API](./docs/API.md) | 全部 HTTP 接口及公开站点的限制 |
| [Analytics](./docs/ANALYTICS.md) | 分析页面、简报、运行经过和 PDF 中每个指标的计算方法 |
| [Configuration](./docs/CONFIGURATION.md) | 所有环境变量及默认值 |
| [Deployment](./docs/DEPLOYMENT.md) | 公开站点：限制策略、Docker 镜像、Railway、持久化与运维 |
| [Development](./docs/DEVELOPMENT.md) | 本地运行、测试、代码导览、本地化、开发约定 |
| [Limitations](./docs/LIMITATIONS.md) | 输出的含义与局限 |

## 许可

基于 [GNU AGPL-3.0](./LICENSE) 许可。如果你将修改后的版本作为网络服务运行，必须向用户提供其源代码。

本软件部分代码源自一个以相同许可发布的开源项目；按该许可要求保留此声明。智能体模拟由 [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) 提供支持。
