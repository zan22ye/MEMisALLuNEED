# MEMisALLuNEED

**MEMisALLuNEED** 是一个以记忆为中心的智能体项目。

它的核心想法很简单：

> 此刻之前的一切，都可以被视为记忆。

系统不应该依赖不断增长的上下文窗口，而应该把记忆作为智能的核心载体。面对一个 query，系统先召回相关记忆；当 host application 提供外部知识时，系统再使用这些 host-supplied evidence；随后将本次形成的新知识、新经验和召回过程重新写入记忆。

因此，系统会在使用中持续成长。

## 核心命题

对于一个 query，系统需要：

1. 足够相关的已有记忆。
2. 当 host application 判断已有记忆不足时，接收 host-supplied external knowledge。

回答完成后，系统会从 query、召回内容、answer、host-supplied evidence 以及它们之间的连接路径中形成新的记忆。

这意味着系统不是一次性回答问题，而是在每次交互中积累可复用的知识与经验。

## 实现边界

MEMisALLuNEED 是 memory core。它负责存储、召回、解析和形成记忆。

它本身不搜索网页、不抓取文档、不调用外部工具、不判断外部 evidence 是否足够，也不决定是否需要外部知识。这些职责属于 host application。MEMisALLuNEED 可以在 host 提供 sources、evidence 和 answer traces 之后，将这些材料整合为记忆。

## Memory-Centric Agent

MEMisALLuNEED 的核心不是 prompt、tool，也不是静态 RAG，而是一个持续成长的 memory substrate。

这个 agent 会：

- 为每个 query 召回相关记忆；
- 在 host 提供外部知识时使用这些材料；
- 基于记忆与知识生成 answer；
- 从完整交互过程中形成新记忆；
- 为未来的 memory relation 能力保留设计空间。

在这个视角下，记忆不只是在回答之后被保存。记忆也会在回忆过程中形成。

## 记忆类型

系统使用统一的 memory item 结构，同时通过类型区分不同记忆。

### Knowledge Memory

Knowledge Memory 是经过处理后的知识，来源可以是内部推理，也可以是 host-supplied external sources。

例如：

- 事实；
- 概念；
- 摘要；
- 实体关系；
- 方法；
- 结论。

### Experience Memory

Experience Memory 记录知识在某次 query-answer 过程里是如何被使用的。

它记录：

- query 在问什么；
- 为什么某些知识和 query 相关；
- 这些知识如何支持 answer；
- 这次回答是成功、失败、不确定，还是不完整。

### Recall Memory

Recall Memory 是一次召回事件的压缩 trace。

它记录：

- 本次召回了哪些记忆；
- 为什么这些记忆相关；
- 它们如何被组合；
- 它们如何参与最终 answer。

### Host-Supplied Source Reference

Host-supplied external knowledge 默认不以全文原文形式保存。

Phase 4 计划中的 source integration 会保存来源引用，例如：

- source URL；
- 标题；
- 访问时间；
- 可用时记录发布时间；
- 可信度或置信度说明。

系统保存的是被加工后的知识，以及这些知识在具体场景中的使用方式；原始资料则以引用形式保留。当前 `mem chat` 不写入 `source` memories；host-supplied source reference integration 是计划中的 Phase 4 能力。

## Host-Supplied External Knowledge

外部知识不会对每个 query 默认添加。

Host application 可以判断已有记忆不足，并在以下情况出现时提供 external evidence 或 source references：

- 找不到足够相关的记忆；
- 召回记忆的置信度较低；
- 召回记忆之间存在冲突；
- query 涉及时效性或最新事实；
- 已有记忆缺少证据支撑；
- 已有记忆只能覆盖 query 的一部分。

当 host 提供这些材料后，MEMisALLuNEED 可以对其进行清洗、压缩和结构化，然后写入记忆。MEMisALLuNEED 本身不执行 external acquisition。

## 记忆形成

记忆会自动写入，但不会以原始对话日志的形式直接写入。

写入前，一个小模型会对 memory candidate 进行清洗和结构化。目标是在保证语义完整的前提下，让记忆尽可能精简。

记忆形成包括：

- 去重；
- 压缩；
- 去噪；
- 知识抽取；
- 经验抽取；
- recall trace 生成；
- metadata 标注；
- 为未来 graph 支持保留的 relation metadata。

失败、错误和不确定的回答也会被写入记忆，因为失败经验同样是有价值的记忆。它们会通过 memory state 和 metadata 被标记。

## Memory State 与 Metadata

每条 memory item 可以包含以下 metadata：

- `type`：knowledge、experience、recall 或 source；
- `state`：success、failed、uncertain、contradicted 或 outdated；
- `confidence`；
- `created_at`；
- `source_ref`；
- `query_context`；
- `vector_index_ref` 或 `semantic_index_ref`；
- `usage_count`；
- `last_recalled_at`；
- `derived_from`；
- `supports`；
- `contradicts`；
- `updates`；
- `supersedes`；
- `recalled_with`；
- `used_in`。

系统不区分短期记忆和长期记忆。所有形成后的记忆都存在于同一个 memory substrate 中。它们未来是否有用，由 recall 时的相关性、置信度、新鲜度、使用频率和关系结构共同决定。

## Memory Graph

Memory item 不是孤立的文本块。

项目设计允许未来阶段表示一个关系图：

- 一条记忆可以支持另一条记忆；
- 一条记忆可以反驳另一条记忆；
- 一条记忆可以从另一条记忆派生；
- 一条记忆可以更新或取代另一条记忆；
- 多条记忆可以在同一次 recall 中共同出现；
- 记忆可以连接到它们参与生成的 answer。

这是计划中的 Phase 5 能力。当前 `mem chat` 不执行 graph reasoning，也不会自动更新 memory relations。

## Session Context Constraint

一个 active session 只保留有限的原始上下文：

- 最近 `k` 轮对话；或
- 最近 `k` 个 token。

更早的 session 内容不会继续保留在 active context window 中，而是会通过 memory formation 转化为记忆。

如果后续再次需要更早的信息，系统必须通过 recall 将其重新带回。

这条规则防止系统依赖不断增长的 prompt，并迫使系统真正依赖记忆。

## Rolling And Flush Memory Formation

当前 chat flow 使用 rolling memory formation 和 exit flush formation。

当 session 超过 `k` 轮或 `k` token 限制时：

1. 最旧的内容会从 active context 中移除；
2. 小模型对其进行清洗和压缩；
3. 新的 memory items 被写入 memory substrate；
4. metadata 会保留 chat formation trace。

当用户退出 chat 时，剩余 active turns 会被 flush 进记忆。当前 `mem chat` 不会在每个 assistant response 后立即形成 memory。

## 成长闭环

系统通过以下闭环成长：

1. 用户提出 query。
2. 系统召回相关记忆。
3. 系统将召回候选解析为 bounded chat context。
4. 系统基于 active session context 和 recalled memory 生成 answer。
5. Host application 可以提供 external sources、evidence 或 answer traces。
6. 系统在 rolling 或 exit flush formation 中形成新的 knowledge、experience 和 recall memories。
7. 新的 memory items 被写入统一 memory substrate。
8. 未来 query 可以复用这些知识和经验。

## 为什么重要

传统系统通常把上下文视为临时状态，把 retrieval 视为访问静态知识库。

MEMisALLuNEED 把记忆视为核心的成长结构：

- 对话会变成可复用经验；
- host-supplied external knowledge 可以变成内部化知识；
- recall 事件会变成未来召回的参考；
- 错误不会消失，而是变成带状态标记的记忆；
- 旧上下文不会堆进 prompt，而是被转化为记忆。

最终目标是构建一个能通过交互持续成长的系统，而不是一个只在上下文窗口内临时回答问题的系统。

## CLI 快速开始

当前可运行入口是 `mem` CLI。

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "Host-supplied external knowledge is integrated only after the host provides it."
mem list
mem search "when should external knowledge be used"
mem export
```

本地运行数据存放在 `.memisalluneed/memory.db`，该目录不会提交到 git。

记忆中心的聊天入口是：

```bash
mem chat
```

chat 流程会召回相关记忆，限制 active session 的大小，将较早的对话滚动写入记忆，并可以显示本轮使用的记忆 trace：

```bash
mem chat --show-memory-trace
```

DeepSeek 可以通过现有的 OpenAI-compatible provider layer 使用。设置
`DEEPSEEK_API_KEY` 后，可以通过参数切换 provider 和 model：

```bash
mem chat --chat-provider deepseek --chat-model deepseek-chat
```

SiliconFlow 也可以通过同一个 OpenAI-compatible provider layer 使用。设置
`SILICONFLOW_API_KEY` 后，选择一个 SiliconFlow 模型即可：

```bash
mem chat --chat-provider siliconflow --chat-model Pro/zai-org/GLM-4.7
```

## 项目状态

当前仓库已经不只是概念和设计阶段。

已经实现：

- Phase 1：CLI memory substrate，使用 SQLite 存储，并支持 JSONL 导出；
- Phase 2：通过 `mem chat` 实现 session-to-memory formation；
- Phase 3：在 `mem chat` 中实现 memory-centric QA；
- Phase 3.5：为 chat context 实现确定性的 timestamp-aware memory resolution。

当前 CLI 命令包括：

- `mem init`
- `mem add`
- `mem list`
- `mem show`
- `mem search`
- `mem export`
- `mem chat`

Phase 4 尚未实现。当前 Phase 4 的方向是 host-supplied knowledge integration：由 host application 负责获取 sources 和 evidence，MEMisALLuNEED 接收 host 提供的材料，并将其形成结构化记忆。计划中的接口包括：

- `mem integrate-source`
- `mem integrate-evidence`
- `mem integrate-answer`

这些 Phase 4 命令目前只是设计目标，还不是可用的 CLI 命令。
