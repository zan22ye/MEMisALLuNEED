# MEMisALLuNEED

**MEMisALLuNEED** 是一个以记忆为中心的智能体项目。

它的核心想法很简单：

> 此刻之前的一切，都可以被视为记忆。

系统不应该依赖不断增长的上下文窗口，而应该把记忆作为智能的核心载体。面对一个 query，系统先召回足够相关的记忆；当已有记忆不足时，再接触外部知识；随后将本次形成的新知识、新经验和召回过程重新写入记忆。

因此，系统会在使用中持续成长。

## 核心命题

对于一个 query，系统需要：

1. 足够相关的已有记忆。
2. 当已有记忆不足时，才需要外部知识。

回答完成后，系统会从 query、召回内容、answer、外部知识以及它们之间的连接路径中形成新的记忆。

这意味着系统不是一次性回答问题，而是在每次交互中积累可复用的知识与经验。

## Memory-Centric Agent

MEMisALLuNEED 的核心不是 prompt、tool，也不是静态 RAG，而是一个持续成长的 memory substrate。

这个 agent 会：

- 为每个 query 召回相关记忆；
- 判断召回的记忆是否足够；
- 在必要时接触外部知识；
- 基于记忆与知识生成 answer；
- 从完整交互过程中形成新记忆；
- 持续更新记忆之间的关系。

在这个视角下，记忆不只是在回答之后被保存。记忆也会在回忆过程中形成。

## 记忆类型

系统使用统一的 memory item 结构，同时通过类型区分不同记忆。

### Knowledge Memory

Knowledge Memory 是经过处理后的知识，来源可以是内部推理，也可以是外部资料。

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

### Source Reference

外部知识默认不以全文原文形式保存。

系统保存的是来源引用，例如：

- source URL；
- 标题；
- 访问时间；
- 可用时记录发布时间；
- 可信度或置信度说明。

系统保存的是被加工后的知识，以及这些知识在具体场景中的使用方式；原始资料则以引用形式保留。

## 外部知识获取

外部知识不会对每个 query 默认添加。

系统会先召回已有记忆，并进行 memory sufficiency check。只有在以下情况出现时，才会触发 external knowledge acquisition：

- 找不到足够相关的记忆；
- 召回记忆的置信度较低；
- 召回记忆之间存在冲突；
- query 涉及时效性或最新事实；
- 已有记忆缺少证据支撑；
- 已有记忆只能覆盖 query 的一部分。

外部知识被获取后，会经过清洗、压缩和结构化，然后写入记忆。

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
- 关系更新。

失败、错误和不确定的回答也会被写入记忆，因为失败经验同样是有价值的记忆。它们会通过 memory state 和 metadata 被标记。

## Memory State 与 Metadata

每条 memory item 可以包含以下 metadata：

- `type`：knowledge、experience、recall 或 source；
- `state`：success、failed、uncertain、contradicted 或 outdated；
- `confidence`；
- `created_at`；
- `source_ref`；
- `query_context`；
- `embedding`；
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

它们会形成一个关系图：

- 一条记忆可以支持另一条记忆；
- 一条记忆可以反驳另一条记忆；
- 一条记忆可以从另一条记忆派生；
- 一条记忆可以更新或取代另一条记忆；
- 多条记忆可以在同一次 recall 中共同出现；
- 记忆可以连接到它们参与生成的 answer。

这样，系统记住的不只是信息本身，也包括信息之间如何相互作用。

## Session Context Constraint

一个 active session 只保留有限的原始上下文：

- 最近 `k` 轮对话；或
- 最近 `k` 个 token。

更早的 session 内容不会继续保留在 active context window 中，而是会通过 memory formation 转化为记忆。

如果后续再次需要更早的信息，系统必须通过 recall 将其重新带回。

这条规则防止系统依赖不断增长的 prompt，并迫使系统真正依赖记忆。

## Rolling Memory Write

系统使用滚动写入和每轮轻量检查。

当 session 超过 `k` 轮或 `k` token 限制时：

1. 最旧的内容会从 active context 中移除；
2. 小模型对其进行清洗和压缩；
3. 新的 memory items 被写入 memory substrate；
4. 记忆关系和 metadata 被更新。

每一轮 query-answer 结束后，系统也会检查本轮是否产生了重要新记忆，例如：

- 新知识；
- 用户偏好；
- 重要结论；
- 外部知识；
- 错误或失败尝试；
- recall trace；
- 关系更新。

## 成长闭环

系统通过以下闭环成长：

1. 用户提出 query。
2. 系统召回相关记忆。
3. 系统判断记忆是否足够。
4. 必要时，系统获取外部知识。
5. 系统生成 answer。
6. 系统形成新的 knowledge、experience 和 recall memories。
7. 新的 memory items 被写入统一 memory substrate。
8. 系统更新 memory graph。
9. 未来 query 可以复用这些知识和经验。

## 为什么重要

传统系统通常把上下文视为临时状态，把 retrieval 视为访问静态知识库。

MEMisALLuNEED 把记忆视为核心的成长结构：

- 对话会变成可复用经验；
- 外部知识会变成内部化知识；
- recall 事件会变成未来召回的参考；
- 错误不会消失，而是变成带状态标记的记忆；
- 旧上下文不会堆进 prompt，而是被转化为记忆。

最终目标是构建一个能通过交互持续成长的系统，而不是一个只在上下文窗口内临时回答问题的系统。

## Phase 1 CLI 快速开始

第一个可运行里程碑是 `mem` CLI。

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient."
mem list
mem search "when should external knowledge be used"
mem export
```

本地运行数据存放在 `.memisalluneed/memory.db`，该目录不会提交到 git。

## 项目状态

当前仓库处于概念和设计阶段。

下一步是定义第一个可运行原型：

- memory item schema；
- memory graph storage；
- recall pipeline；
- sufficiency checker；
- external knowledge acquisition interface；
- memory formation model；
- session context manager。
