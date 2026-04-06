# Heartbeat & Cron System

ai-companion 实现了生产级的 heartbeat 和 cron 定时任务系统，参考了 claw0（教学示例）和 OpenClaw（生产环境）的优秀设计。

## 功能概述

### Heartbeat（心跳）
- **主动定期检查**：让 AI 在后台定期执行检查任务
- **lane 互斥机制**：用户消息优先，心跳自动让步
- **HEARTBEAT_OK 约定**：无需报告内容时简洁应答
- **成本优化**：支持轻量上下文和会话隔离
- **灵活配置**：可配置间隔、活跃时间、可见性等

### Cron（定时任务）
- **三种调度类型**：
  - `at`: 一次性时间戳
  - `every`: 固定间隔（带锚点对齐）
  - `cron`: 标准 cron 表达式（5字段）
- **多种 payload**：
  - `agent_turn`: 完整的 agent turn（可使用工具）
  - `system_event`: 简单文本通知
- **投递模式**：支持 `announce`、`webhook`、`none`
- **错误重试**：指数退避策略
- **时区支持**：每个任务可配置独立时区

## 文件结构

```
src ai_companion/
├── config/
│   ├── heartbeat.py      # HeartbeatConfig schema
│   ├── cron.py           # CronConfig schema
│   └── schema.py          # Updated with heartbeat/cron
├── heartbeat/
│   └── runner.py        # HeartbeatRunner
├── cron/
│   ├── types.py          # Runtime types
│   └── scheduler.py     # CronScheduler
└── services/
    └── scheduler_service.py # SchedulerService orchestrator
```

## 配置示例

### workspace/HEARTBEAT.md
```markdown
# 心跳提醒指引

检查以下项目，仅当需要关注时报告。

## 检查项目

1. **待办提醒**：是否有用户设置的待办事项现在到期了？
2. **每日总结**：如果是下午6点后且今天没有发送过每日总结，准备一个简短的总结。
3. **跟进事项**：是否有最近的对话主题值得跟进？

## 响应规则

- 如果没有需要关注的内容，请确应答：HEARTBEAT_OK
- 如果需要报告，请简洁明了。
- 不要以"我检查了..."或"在心跳期间..."开头——自然地报告发现。
- 优先级：提醒 > 跟进事项 > 总结
```

### workspace/CRON.json
```json
{
  "jobs": [
    {
      "id": "morning-briefing",
      "name": "Morning Briefing",
      "enabled": true,
      "schedule": {
        "kind": "cron",
        "expr": "0 9 * * *",
        "timezone": "Asia/Shanghai"
      },
      "payload": {
        "kind": "agent_turn",
        "message": "查看今天的日历、天气预报和任何待处理提醒事项。给出一个简短的晨间摘要。"
      },
      "delivery": {
        "mode": "announce"
      }
    },
    {
      "id": "health-check",
      "name": "System Health Check",
      "enabled": true,
      "schedule": {
        "kind": "every",
        "every_seconds": 3600
      },
      "payload": {
        "kind": "agent_turn",
        "message": "检查系统健康状况：内存使用、磁盘空间和运行服务。仅在需要关注时报告。"
      }
    }
  ]
}
```

## 配置说明

### Heartbeat 配置
在 `.env` 或环境变量中配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `heartbeat.enabled` | true | 是否启用心跳 |
| `heartbeat.interval_seconds` | 1800 | 执行间隔（秒） |
| `heartbeat.active_hours` | (9, 22) | 活跃时间范围（小时） |
| `heartbeat.light_context` | false | 轻量上下文模式 |
| `heartbeat.isolated_session` | false | 使用独立会话 |
| `heartbeat.show_ok` | false | 显示 HEARTBEAT_OK |
| `heartbeat.show_alerts` | true | 显示警告消息 |
| `heartbeat.use_indicator` | false | 发送指示器事件 |

### Cron 配置
在 `.env` 或环境变量中配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `cron.enabled` | true | 是否启用 cron |
| `cron`_concurrent_runs` | 3 | 最大并发执行数 |
| `cron.session_retention` | "24h" | 会话保留时长 |
| `cron.run_log_max_bytes` | 2000000 | 运行日志最大字节数 |
| `cron.run_log_keep_lines` | 2000 | 运行日志保留行数 |

## 集成方式

### 在主应用中集成
```python
import asyncio
from pathlib import Path

from ai_companion.config.schema import AppConfig
from ai_companion.services.scheduler_service import SchedulerService
from ai_companion.concurrency.lanes import NamedLaneManager
from ai_companion.intelligence.builder import PromptBuilder
from ai_companion.providers.anthropic import AnthropicProvider

async def on_message(msg):
    """处理外发消息"""
    print(f"[OUTBOUND] To {msg.target_channel}: {msg.content}")

async def main():
    # 加载配置
    config = AppConfig()

    # 初始化组件
    lane_manager = NamedLaneManager()
    prompt_builder = PromptBuilder(Path("./workspace"))
    provider = AnthropicProvider(
        api_key=config.anthropic_api_key,
        base_url=config.anthropic_base_url
    )

    # 创建调度服务
    scheduler = SchedulerService(
        config=config,
        workspace_dir=Path("./workspace"),
        prompt_builder=prompt_builder,
        lane_manager=lane_manager,
        provider=provider,
        on_message=on_message,
    )

    # 启动调度器
    await scheduler.start()

    # ... 主应用逻辑 ...

    # 关闭调度器
    await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## 设计亮点

### 结合了 claw0 和 OpenClaw 的优势

**claw0 优势**：
- 简洁的 lane 互斥机制
- 清晰的前置条件检查
- HEARTBEAT_OK 约定
- 易于理解和维护

**OpenClaw 优势**：
- 灵活的配置选项
- 轻量上下文优化
- 会话隔离支持
- 多 Agent 支持（预留）
- 时区支持
- 重试策略

### ai-companion 特有优势

- **Async-first**: 使用 asyncio 而非 threading，与项目架构一致
- **NamedLane 集成**: 复用现有的并发控制系统
- **WriteAheadQueue 支持**: 可扩展为使用现有的消息队列
- **8层提示词组装**: 复用 PromptBuilder 系统
- **配置驱动**: 所有配置通过 Pydantic schema 定义
- **可扩展性**: 清晰的接口和扩展点

## 运行日志

Cron 运行日志保存在 `workspace/cron/runs.jsonl`：
```jsonl
{"job_id": "health-check", "run_at": "2026-04-06T12:00:00Z", "status": "ok", "output_preview": "System health check complete.", "duration_seconds": 5.2}
{"job_id": "health-check", "run_at": "2026-04-06T13:00:00Z", "status": "error", "error": "Network timeout", "duration_seconds": 30.1}
```

## 示例程序

运行 `examples/scheduler_demo.py` 可以查看调度系统的工作方式：

```bash
cd examples
python scheduler_demo.py
```

交互式命令：
- `status` - 显示调度器状态
- `heartbeat` - 显示心跳详情
- `cron` - 列出 cron 任务
- `trigger` - 手动触发心跳
- `start` - 启动调度器
- `stop` - 停止调度器
- `quit` - 退出

## 故障排查

### 心跳不运行
- 检查 `heartbeat.enabled` 配置
- 确认 `workspace/HEARTBEAT.md` 存在且非空
- 检查活跃时间范围
- 查看日志中的错误信息

### Cron 任务不执行
- 检查 `cron.enabled` 配置
- 确认 `workspace/CRON.json` 格式正确
- 验证 cron 表达式语法
- 检查任务是否被禁用（连续错误超过阈值）
- 查看 `workspace/cron/runs.jsonl` 日志

### 时区问题
- 使用标准 IANA 时区（如 `Asia/Shanghai`）
- 检查系统时区设置
- 在任务配置中明确指定时区

## 未来增强

- 支持更多调度类型（如 `until`）
- Webhook 投递的完整实现
- 任务依赖关系支持
- 多 Agent 路由
- 会话隔离的完整实现
- 统计和监控 API
- Web UI 管理界面
