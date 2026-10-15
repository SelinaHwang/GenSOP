# GenSOP

## 中文版

GenSOP 是为 SOPower 配套使用的 Skill。它把自然语言需求整理成包含步骤、时长和可选标签的定时 SOP，先展示完整预览，只有在用户明确确认当前预览后，才导出一个 SOPower 可导入的 `.sop.json`  文件。

### 安装

可以直接对 Agent 说：

> 帮我从 GitHub 安装 GenSOP Skill。

Skill 的仓库路径是 `gensop`。使用官方安装器时，对应参数为：

```text
--repo SelinaHwang/GenSOP --path gensop
```

安装后请在下一轮对话中使用该 Skill。

### 使用流程

1. 用自然语言描述目标、时间和限制。
2. 检查 GenSOP 给出的完整预览。
3. 请求修改，或明确回复确认导出。
4. 将导出的 `.sop.json` 文件导入 SOPower。

### 必要说明

- 需要 Python 3.10 或更高版本，只使用 Python 标准库。
- 使用 Agent 当前宿主模型，不需要额外模型 API Key。
- 未经用户明确确认当前预览，不会导出文件。
- 只导出单个 SOP Share 文件，不生成完整备份或模板。
- 确定性脚本检查字段、类型、长度、数量、时长和预览一致性；内容目标、步骤顺序、粒度、标签语义及安全判断仍由宿主模型负责。
- GenSOP 独立运行，不是 SOPower 内置 AI，也不会直接访问或修改 SOPower 数据。

## English Version

GenSOP is a Skill designed to work with SOPower. It turns a natural-language request into a timed SOP with steps, durations, and optional tags. It shows a complete preview first and exports one SOPower-compatible `.sop.json` file only after the user explicitly confirms the current preview.

### Installation

Ask Agent:

> Install the GenSOP Skill from the GitHub.

The Skill path inside the repository is `gensop`. With the official installer, use:

```text
--repo SelinaHwang/GenSOP --path gensop
```

Use the Skill in your next conversation turn after installation.

### Basic workflow

1. Describe the goal, timing, and constraints in natural language.
2. Review the complete preview.
3. Request changes or explicitly confirm export.
4. Import the exported `.sop.json` file into SOPower.

### What users should know

- Requires Python 3.10 or newer and uses only the Python standard library.
- Uses the current host model and requires no additional model API key.
- No file is exported without explicit confirmation of the current preview.
- Exports one SOP Share file only; it does not create full backups or templates.
- Deterministic checks cover fields, types, lengths, counts, durations, and preview consistency. Goal interpretation, step order, granularity, tag meaning, and safety judgment remain the host model's responsibility.
- GenSOP runs independently. It is not built into SOPower and does not directly access or modify SOPower data.
