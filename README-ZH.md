<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./brand/logo-dark.svg">
  <img src="./brand/logo.svg" alt="Hivemind" width="360">
</picture>

**社会群体智能模拟。围绕任何事件搭建一个模拟互联网，观察它如何反应。**

[English](./README.md) | [中文文档](./README-ZH.md)

</div>

Hivemind 是一个把 AI 智能体群部署到模拟世界中的工具。给它一个情境（只需一个问题，或问题加资料），它会：

1. **研究情境。** 阅读你的资料，或自行撰写背景简报，并把相关的人物、组织和关系整理成知识图谱。
2. **部署智能体群。** 图谱中的每个角色都会成为一个拥有人设、立场和记忆的 AI 智能体。
3. **运行模拟互联网。** 智能体在两个模拟社交平台上逐轮发帖、回复、点赞和争论。
4. **告诉你发生了什么。** 一份通俗易懂的简报，说明各方在哪里达成一致、在哪里分歧，以及每个群体和公司会如何反应。

所有参与者均为模拟；这是一次预演，而不是真实事件的记录。

## 运行

需要安装 Node.js 20.19 及以上（推荐 22）、Python 3.12 和 [uv](https://docs.astral.sh/uv/)，以及两个你自己的密钥：

| 密钥 | 用途 | 获取地址 |
| --- | --- | --- |
| `LLM_API_KEY` | Claude，扮演每个模拟参与者并撰写简报 | [console.anthropic.com](https://console.anthropic.com/) |
| `ZEP_API_KEY` | 知识图谱与智能体记忆 | [app.getzep.com](https://app.getzep.com/)（免费额度足够小规模运行） |

```bash
git clone https://github.com/slimboi34/hivemind.git
cd hivemind
./hivemind.sh       # 首次运行会创建 .env，并提示需要填写的两行
```

在 `.env` 中填入两个密钥后再次运行 `./hivemind.sh`。应用地址：http://localhost:3000 。
密钥只保存在 `.env` 中，该文件已被 gitignore，不会被提交。

完整说明见 [README.md](./README.md)。

## 许可

基于 [GNU AGPL-3.0](./LICENSE) 许可。本软件部分代码源自一个以相同许可发布的开源项目；按该许可要求保留此声明。
