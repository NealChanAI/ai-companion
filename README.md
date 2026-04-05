# AI Companion

A Python AI companion for emotional support and meaningful conversation, combining the best architectural patterns from [claw0](https://github.com/.../claw0) and [openclaw](https://github.com/.../openclaw).

## Features

- 🧠 **Layered architecture** from claw0 - incremental design, simple agent loop
- 🔌 **Plugin-based extensibility** from openclaw - add new channels/providers/skills
- 💾 **JSONL session persistence** - simple, robust, no database required
- 📝 **File-based personality** - edit `SOUL.md` and `IDENTITY.md` to change personality without code
- 🤝 **Multi-channel support** - CLI + Feishu (more can be added via plugins)
- 🔑 **Multiple AI providers** - Anthropic Claude and OpenAI support out of the box
- 🛡️ **Production-ready resilience** - exponential backoff, write-ahead queue, retry, concurrency control
- 🧠 **Long-term memory** - Built-in memory skill to remember important user information

## Quick Start

### 1. Install dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using poetry/poetry
# poetry install
```

### 2. Configure

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Check configuration

```bash
python -m ai_companion doctor
```

### 4. Start interactive CLI chat

```bash
python -m ai_companion chat
```

Or with the installed command:

```bash
ai-companion chat
```

### 5. Start server with Feishu

Configure your Feishu credentials in `.env`, then:

```bash
ai-companion serve
```

## Architecture

This project combines:
- **From claw0**: Layered incremental design, agent loop pattern, JSONL session persistence, 8-layer prompt assembly, 5-tier routing, skill system, resilience patterns, concurrency with named lanes
- **From openclaw**: Plugin-based extensibility, channel abstraction, multiple provider support, hierarchical configuration

### Directory Structure

```
src/ai_companion/
├── types/           # Core type definitions
├── config/          # Configuration management (Pydantic)
├── agent/           # Core agent loop (while True + stop_reason)
├── providers/       # LLM providers (Anthropic + OpenAI)
├── sessions/        # JSONL session persistence, context overflow handling
├── channels/        # Channel abstraction (CLI + Feishu)
├── gateway/         # 5-tier routing, webhook server
├── intelligence/    # 8-layer prompt assembly from files
├── plugins/         # Plugin system (adapted from openclaw)
├── skills/          # Skill system (from claw0)
├── delivery/        # Write-ahead queue for guaranteed delivery
├── resilience/      # Retry, API key rotation
├── concurrency/     # Named lanes for concurrency control
└── cli.py           # Command-line interface
```

## Customization

### Changing Personality

Edit `workspace/SOUL.md` to change your AI companion's personality. No code changes needed!

### Adding Skills

Add a new skill by creating:
```
workspace/skills/your-skill/SKILL.md
```
Include frontmatter metadata and the skill instructions. The system will automatically discover it.

### Adding Channels

Channels can be added via the plugin system or built-in. Each channel implements the `Channel` ABC with `receive()` and `send()`.

## Commands

| Command | Description |
|---------|-------------|
| `ai-companion chat` | Start interactive CLI chat |
| `ai-companion serve` | Start server with configured channels |
| `ai-companion list-sessions` | List all saved sessions |
| `ai-companion doctor` | Check configuration |

## License

MIT
