# writing-skills

[English](README.md) | 中文

一个教 AI **怎么写 skill** 的 skill —— 并且能接住那些宿主**不报错、直接扔掉**的写法。

为 [DSH](https://github.com/deepseek-ai)（DeepSeek Harness）打造。DSH 的 skill 解析器比公开规范更严，而且会把不合法的 skill 悄悄丢掉，只留一行宿主日志。其中的写作方法部分，对任何支持 `SKILL.md` 的宿主都通用。

---

## 它解决什么问题

**写得不对的 skill 不会报错，它会直接消失。**

宿主记一行警告，模型什么都不知道，这个 skill 就是不出现在技能目录里 —— 而这和「这个 skill 没被触发」**完全无法区分**。结果就是你一直在调描述，真正的毛病却是一个拼错的 frontmatter 键名。

DSH 里两个会这样静默失效的例子：

- `disableModelInvocation`（驼峰）—— **会被直接拒绝**，整个 skill 被丢掉。正确写法是 `disable-model-invocation`。
- `when-to-use` —— 被静默忽略。字段名是 `whenToUse`。

这个 skill 把真实的契约直接交给 AI，并附带一个校验器，把这份沉默变成一句明确的诊断。

## 里面有什么

```
writing-skills/
├── SKILL.md                        # 五步写作流程、改坏后的排查表、DSH 要点
├── references/
│   ├── spec.md                     # 完整契约：frontmatter、校验规则、发现路径、静默失败
│   ├── authoring.md                # 写作方法：简洁预算、描述工程、反模式
│   └── iteration.md                # 评估驱动开发、打分、描述调优
├── scripts/
│   ├── validate_skill.py           # 确定性的契约校验器（仅用标准库）
│   └── test_validate_skill.py      # 15 个夹具，证明每一类失败都能被抓到
├── README.md                       # 英文说明
├── README.zh.md                    # 本文件
└── LICENSE
```

`SKILL.md` 共 175 行，远低于它自己教的 500 行上限。细节放在 `references/` 里，用到才加载。

> 说明：**技能正文本身是英文的**（`SKILL.md` 与 `references/`）。本 README 是中英双语，便于阅读和选型。如果需要中文版的技能正文，可以再提。

## 安装

skill 的安装方式就是把它放进被扫描的目录。不需要构建，也不需要清单文件。

| 作用范围 | 路径 |
|---|---|
| 仅当前项目 | `<项目>/.dsh/skills/writing-skills/` |
| 本机所有项目 | `~/.dsh/skills/writing-skills/` |
| 与其他 agent 工具共用 | `~/.agents/skills/writing-skills/` |

```bash
git clone git@github.com:rrrrrede1/writing-skills.git ~/.dsh/skills/writing-skills
```

这些目录会被监视，所以新加的 skill 下一步就能用上，不用重启。

## 使用

用大白话直接提就行：

> 「帮我把这个流程做成一个 skill」
> 「把这个工作流固化成一个 skill」
> 「这个 skill 怎么都不触发，帮我修一下」

也可以显式调用：`/writing-skills`。

它会走一个五步循环 —— 钉住任务 → 先写描述 → 起草正文 → 把细节拆到 `references/` → 校验并在真实提问上实测 —— 并且带一张「症状 → 病因」表，用来修已经存在的 skill。

## 校验

```bash
python scripts/validate_skill.py <skill-目录路径>
```

检查项包括：frontmatter 契约、名字正则、描述长度是否超过目录上限、布尔值写法、被拒绝的旧键名、目录层级、正文长度、引用文件是否存在、引用是否只有一层。

```
$ python scripts/validate_skill.py .
Validating ./SKILL.md
  note  3 linked resource(s) referenced from SKILL.md

OK: no errors, 0 warning(s)
```

校验器自带测试夹具 —— 因为一个坏掉的校验器比没有校验器更糟：

```bash
python scripts/test_validate_skill.py     # all 15 fixtures passed
```

只用标准库，不需要 `pip install`。需要 Python 3.9+。

## DSH 契约速查表

真正决定一个 skill 能不能被加载的规则。完整细节见 [`references/spec.md`](references/spec.md)。

| 规则 | 取值 |
|---|---|
| 必填字段 | `name`、`description` |
| 名字正则 | `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` —— 小写字母、数字、单个连字符 |
| 可选字段 | `whenToUse`（驼峰）、`metadata`、`disable-model-invocation`、`user-invocable`（短横线） |
| 会被拒绝的键 | `disableModelInvocation`、`modelInvocable`、`userInvocable` —— 会让整个 skill 被丢弃 |
| 布尔值 | `true`/`false`、`yes`/`no`、`on`/`off`、`1`/`0`（大小写不敏感） |
| 目录结构 | `<root>/<name>/SKILL.md` 或 `<root>/<name>.md` —— **只认一层** |
| 发现路径 | `<项目>/.dsh/skills` → `<项目>/.agents/skills` → 自定义 → `~/.dsh/skills` → `~/.agents/skills` |
| 项目根判定 | 最近的含 `.git` 的上级目录，没有就用当前目录 |
| 描述长度上限 | 500 字符 —— 更长的会在筛选阶段被截断 |

最后一行比看上去重要：**描述超长时，被砍掉的正好是模型用来判断「要不要加载这个 skill」的那部分。**

## 测试过了吗？

测过，而且结论好坏参半。三个任务，每个都跑「不给 skill」和「给 skill」两轮，每轮之间重置状态。

| 任务 | 无 skill | 有 skill |
|---|---|---|
| 「把我们的手工发版检查做成可复用工具」 | 描述 **523 字符，超出上限**，开头是 `This skill should be used when…` | 描述 459 字符，带明确的边界说明 |
| 「这个 skill 怎么都不生效，修好它」 | 自己读 provider 源码，故障全诊断对 | 用自带的校验器，故障全诊断对 |
| 反向测试：加固一个 JSON 输出的 system prompt | 没有创建 skill | 正确判断为不相关，没有加载，也没创建 skill |

- **不会误触发** —— 这是真正烧 token 的失败模式，表现干净。
- **描述质量有可测量的提升** —— 这是最清晰的收益，也正是流程第 2 步要解决的问题。
- **诊断能力的提升比预期小** —— 一个够强的 AI 自己去读 provider 源码也能把契约逆出来。skill 在这里的价值是省时间和提供校验器，不是独占知识。

另外，两次方法上的翻车我选择写出来而不是藏起来：第一轮评估无效，一是因为「把 skill 移出技能目录」并不等于藏起来（agent 会翻文件系统找到它），二是因为作者自己的研究笔记泄了题。两轮都作废重做了。想复现的话，`references/iteration.md` 里有做法。

## 致谢

写作方法部分综合了下列来源，并针对 DSH 做了改编：

- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) —— Anthropic
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) —— Anthropic Engineering
- [Agent Skills specification](https://agentskills.io/specification.md) —— 开放标准

DSH 契约部分是我**读这台机器的实现**（`@deepseek-ai/dsh-skill`、`dsh-skill-filesystem`）得出的，而不是照抄文档 —— 因为两者并不一致。没有从 [anthropics/skills](https://github.com/anthropics/skills) 复制任何代码；它那个更重的 `skill-creator` 只在 `references/iteration.md` 里讨论过，是有意不打包进来的。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
