# GenSOP

GenSOP 是为 SOPower 小程序配套使用的 AI SOP 生成 Skill。它根据自然语言需求生成包含步骤、时长和可选标签的定时 SOP，先展示完整预览，并且只有在用户明确确认当前预览后，才导出一个 SOPower 可导入的 `.sop.json` Share 文件。

GenSOP 是独立运行的 Skill，不是 SOPower 小程序内置的 AI 功能，也不会修改 SOPower。生成过程使用宿主 Agent 自带模型，不调用 Kimi 或其他额外云端模型 API，因此不需要用户提供额外模型 API Key。

## 运行要求

- Python 3.10 或更高版本
- 仅使用 Python 标准库
- 支持加载 Skill 并调用本地 Python 脚本的宿主 Agent

## WorkBuddy 安装

1. 前往 [GitHub Releases](https://github.com/SelinaHwang/GenSOP/releases) 下载 Release 附件 `GenSOP-WorkBuddy-v0.3.0.zip`。
2. 在 WorkBuddy 的技能添加页面直接上传原始 ZIP。
3. 不要先解压，也不要把解压后的文件重新打包。

GitHub 自动生成的 “Source code” ZIP 不是 WorkBuddy 安装包，请使用 Release 中单独上传的 `GenSOP-WorkBuddy-v0.3.0.zip`。

## 基本流程

提出自然语言需求 → 查看完整预览 → 请求修改或明确确认 → 导出 `.sop.json` → 在 SOPower 中导入。

## 主要边界

- 只导出单个 SOP Share 文件，不生成完整备份或模板文件。
- 未经用户明确确认当前预览，不会导出。
- 拒绝响应和校验失败的内容不会导出。
- 确定性脚本负责结构、类型、长度、数量、时长和预览一致性检查；目标理解、步骤顺序、粒度、标签语义和安全判断仍由宿主模型完成。
- GenSOP 不直接访问 SOPower 中的数据。

## 版本

当前版本：`v0.3.0`

## License

[MIT License](LICENSE) © 2026 SelinaHwang

---

GenSOP turns natural-language requests into timed SOPs, shows a complete preview, and exports one SOPower-compatible `.sop.json` Share file only after explicit user confirmation. It uses the host agent's model and requires Python 3.10+.
