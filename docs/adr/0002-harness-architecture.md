# 0002 — Harness 架构：手写 Agent 运行时，不用框架

不用 LangChain、AutoGen、CrewAI 等 Agent 框架，手写 Harness。Agent loop、tool dispatch、stream 解析、context 管理全部自己实现。采用 10 层分层设计：Tools → Skills → Query Engine → Context → Memory → Permission → Sessions → Command → Hook → Sub-agent。

**Considered Options**

1. **LangChain** — 生态成熟、上手快。但抽象层厚重，调试困难，模型调用链路不透明。面试诊断场景需要精细的 token 预算控制和流式输出，LangChain 的封装反而碍事。
2. **AutoGen / CrewAI** — 多 Agent 协作开箱即用。但 sub-agent 间的上下文隔离和权限控制不够细粒度，诊断场景需要严格的上下文边界（内容诊断 agent 不应看到表达诊断的内容）。
3. **手写 Harness** — 开发成本高，没有生态支持。但每一层都是可独立讲解的工程模块，调试透明，上下文管理完全可控。

选择方案 3。核心原因是：这个项目的目标不只是做一个产品，更是一套可讲解的工程教程。"代码即教程"意味着每一层都需要暴露内部实现，而不是躲在框架后面。

**Consequences**

- 开发周期更长，尤其是前三层（Tools、Skills、Query Engine）需要从零搭建。
- 后续任何框架选型（如流式处理、MCP 协议）都需要自己实现适配层。
- 上下文管理和 token 预算可以做到极致精细，这对诊断场景的稳定性至关重要。
