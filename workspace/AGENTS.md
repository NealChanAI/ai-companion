# 智能体配置

本文件配置可用的智能体以及路由规则。

## 默认智能体

默认智能体就是这个 AI 伴侣，使用工作区文件中的配置。

## 格式

每个智能体定义包含：
- agent_id：唯一标识符
- name：显示名称
- description：该智能体的功能描述
- workspace_path：该智能体的工作区目录路径

示例：

```
- agent_id: companion
  name: AI 伴侣
  description: 你的个人情感伴侣
  workspace_path: ./workspace
```
