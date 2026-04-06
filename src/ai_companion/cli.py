"""
Command-line interface for AI Companion.
"""

import asyncio
import click
import logging
from pathlib import Path
from typing import Optional

from ai_companion.config.loader import load_config, validate_config
from ai_companion.config.schema import AppConfig
from ai_companion.logging.logger import setup_logging, get_logger
from ai_companion.providers.base import BaseProvider
from ai_companion.providers.anthropic import AnthropicProvider
from ai_companion.providers.openai import OpenAIProvider
from ai_companion.agent.loop import AgentLoop
from ai_companion.intelligence.bootstrap import bootstrap_prompt_builder
from ai_companion.intelligence.builder import PromptBuilderWithSkills
from ai_companion.sessions.store import SessionStore
from ai_companion.sessions.context_guard import ContextGuard
from ai_companion.channels.base import Channel
from ai_companion.channels.cli import CliChannel
from ai_companion.channels.feishu import FeishuChannel
from ai_companion.gateway.binding import BindingTable
from ai_companion.gateway.router import GatewayRouter
from ai_companion.skills.manager import SkillManager
from ai_companion.services.scheduler_service import SchedulerService
from ai_companion.concurrency.lanes import NamedLaneManager
from ai_companion.types.message import Message, InboundMessage, OutboundMessage
from ai_companion.types.session import Session
from ai_companion.types.tool import ToolCall, ToolResult
from ai_companion.skills.builtin.memory import MemorySkill
from ai_companion.skills.builtin.weather import WeatherSkill

logger = get_logger(__name__)

# Global variable to track the latest active chat ID for heartbeat messages
latest_active_chat_id: Optional[str] = None


def create_provider(config: AppConfig) -> BaseProvider:
    """Create the configured LLM provider."""
    provider_name = config.default_provider
    if provider_name == "anthropic":
        return AnthropicProvider(config)
    elif provider_name == "openai":
        return OpenAIProvider(config)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


async def handle_message(
    inbound: InboundMessage,
    session: Session,
    agent_loop: AgentLoop,
    channel: Channel,
    memory_skill: MemorySkill,
    weather_skill: WeatherSkill
) -> None:
    """Handle a single incoming message through the agent loop."""
    # Update latest active chat ID for feishu channel
    global latest_active_chat_id
    if inbound.channel_id == "feishu":
        latest_active_chat_id = inbound.peer_id
        logger.info(f"Updated latest active chat_id to: {latest_active_chat_id}")

    # Add user message to session
    user_message = Message(
        role="user",
        content=inbound.content,
        metadata={
            "channel_id": inbound.channel_id,
            "message_id": inbound.message_id,
            "timestamp": inbound.timestamp
        }
    )
    session.messages.append(user_message)
    session.metadata.message_count += 1

    # Tool executor that handles tool calls
    def execute_tool(tool_call: ToolCall) -> ToolResult:
        if tool_call.tool_name == "memory-write":
            return memory_skill.execute(tool_call)
        elif tool_call.tool_name == "weather":
            return weather_skill.execute(tool_call)
        # Future: other tools
        return ToolResult(
            tool_name=tool_call.tool_name,
            tool_call_id=tool_call.tool_call_id,
            content=f"Unknown tool: {tool_call.tool_name}",
            success=False
        )

    # Run the agent turn
    result = agent_loop.run_turn(session, execute_tool)

    # Add all messages to session
    for msg in result.messages_added:
        session.messages.append(msg)

    # Save session
    from ai_companion.sessions.store import SessionStore
    # We'll let the caller save, actually just append is enough since
    # append_message already saves

    # If complete and we have a response, send it
    if result.complete and result.assistant_response is not None:
        outbound = OutboundMessage(
            target_channel=inbound.channel_id,
            target_peer=inbound.peer_id,
            content=result.assistant_response
        )
        await channel.send(outbound)


async def run_chat(
    config: AppConfig,
    channel: Channel,
    agent_id: str = "companion"
) -> None:
    """Run chat loop with the given channel."""
    # Setup context guard
    context_guard = ContextGuard(
        max_tokens=config.max_context_tokens,
        enable_compaction=config.enable_compression
    )

    # Setup session store
    session_store = SessionStore(config.sessions_dir, context_guard)

    # Setup binding table
    binding_table = BindingTable()
    # Load bindings from AGENTS.md
    agents_content = (config.workspace_dir / "AGENTS.md").read_text(encoding="utf-8")
    binding_table.load_from_agents_file(agents_content)

    # Setup gateway router
    router = GatewayRouter(binding_table, session_store)

    # Create provider
    provider = create_provider(config)

    # Setup prompt builder
    prompt_builder = PromptBuilderWithSkills(config.workspace_dir)

    # Discover and load skills
    skill_manager = SkillManager(config.workspace_dir)
    skill_manager.discover()
    skill_manager.inject_into_prompt_builder(prompt_builder)

    # Setup built-in skills
    memory_skill = MemorySkill(config.workspace_dir)
    weather_skill = WeatherSkill()

    # Create agent loop
    agent_loop = AgentLoop(
        provider=provider,
        prompt_builder=prompt_builder,
        tools=skill_manager.get_tool_schemas()
    )

    # Start channel
    await channel.start()

    logger.info(f"AI Companion started on {channel.channel_id}")

    try:
        async for inbound in channel.receive():
            session = router.route(inbound)
            await handle_message(inbound, session, agent_loop, channel, memory_skill, weather_skill)
            # Save after handling
            session_store.save(session)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    finally:
        await channel.stop()


@click.group()
@click.option("--config", "-c", default=None, help="Path to .env file")
def cli(config: Optional[str]):
    """AI Companion - your personal emotional companion."""
    pass


@cli.command()
def chat():
    """Start an interactive CLI chat session."""
    config = load_config()
    errors = validate_config(config)
    if errors:
        for error in errors:
            click.echo(f"Error: {error}", err=True)
            click.echo("Exiting...", err=True)
            return

    setup_logging(config.log_level, config.log_file)
    channel = CliChannel()
    asyncio.run(run_chat(config, channel))


@cli.command()
def serve():
    """Start the server with all configured channels."""
    config = load_config()
    errors = validate_config(config)
    if errors:
        for error in errors:
            click.echo(f"Error: {error}", err=True)
        click.echo("Exiting...", err=True)
        return

    setup_logging(config.log_level, config.log_file)
    logger.info("Starting AI Companion server...")

    # Start channels that are configured
    channels: list[Channel] = []

    # Feishu is enabled if app ID is configured
    if config.feishu_app_id and config.feishu_app_secret:
        feishu_channel = FeishuChannel(
            config,
            host=config.host,
            port=config.port
        )
        channels.append(feishu_channel)
        logger.info(f"Feishu channel configured on port {config.port}")

    if not channels:
        click.echo("No channels configured for serve mode. Exiting.", err=True)
        return

    # Run all channels concurrently
    async def process_channel(channel: Channel, config: AppConfig) -> None:
        """Process incoming messages from a channel."""
        agent_id = "companion"
        # Setup context guard
        context_guard = ContextGuard(
            max_tokens=config.max_context_tokens,
            enable_compaction=config.enable_compression
        )

        # Setup session store
        session_store = SessionStore(config.sessions_dir, context_guard)

        # Setup binding table
        binding_table = BindingTable()
        # Load bindings from AGENTS.md
        agents_content = (config.workspace_dir / "AGENTS.md").read_text(encoding="utf-8")
        binding_table.load_from_agents_file(agents_content)

        # Setup gateway router
        router = GatewayRouter(binding_table, session_store)

        # Create provider
        provider = create_provider(config)

        # Setup prompt builder
        prompt_builder = PromptBuilderWithSkills(config.workspace_dir)

        # Discover and load skills
        skill_manager = SkillManager(config.workspace_dir)
        skill_manager.discover()
        skill_manager.inject_into_prompt_builder(prompt_builder)

        # Setup built-in skills
        memory_skill = MemorySkill(config.workspace_dir)
        weather_skill = WeatherSkill()

        # Create agent loop
        agent_loop = AgentLoop(
            provider=provider,
            prompt_builder=prompt_builder,
            tools=skill_manager.get_tool_schemas()
        )

        # Start channel
        await channel.start()

        logger.info(f"AI Companion started on {channel.channel_id}")

        try:
            async for inbound in channel.receive():
                session = router.route(inbound)
                await handle_message(inbound, session, agent_loop, channel, memory_skill, weather_skill)
                # Save after handling
                session_store.save(session)
        except asyncio.CancelledError:
            logger.info(f"Channel {channel.channel_id} cancelled")
        finally:
            await channel.stop()

    async def run_all():
        # Initialize scheduler service
        scheduler_service = SchedulerService(config.workspace_dir)
        await scheduler_service.start()

        # Function to monitor scheduler outputs and send to feishu
        async def monitor_scheduler_outputs():
            """Monitor scheduler outputs and send them to feishu channel."""
            global latest_active_chat_id

            feishu_channel = None
            for ch in channels:
                if isinstance(ch, FeishuChannel):
                    feishu_channel = ch
                    break

            if not feishu_channel:
                logger.warning("No feishu channel found, skipping scheduler output monitoring")
                return

            logger.info("Starting scheduler output monitoring")

            while True:
                try:
                    # Get outputs from scheduler service
                    outputs = await scheduler_service.get_outputs()

                    for output in outputs:
                        # Use the latest active chat ID as target
                        target_peer = latest_active_chat_id
                        if target_peer:
                            outbound = OutboundMessage(
                                target_channel="feishu",
                                target_peer=target_peer,
                                content=output.content
                            )
                            await feishu_channel.send(outbound)
                            logger.info(f"Sent scheduler output to active chat: {target_peer}")
                        else:
                            logger.warning("No active chat available, scheduler output not sent")

                    await asyncio.sleep(1)  # Check every second

                except asyncio.CancelledError:
                    logger.info("Scheduler output monitoring cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error monitoring scheduler outputs: {e}")
                    await asyncio.sleep(1)

        # Start all channels as separate tasks
        tasks = [
            asyncio.create_task(process_channel(ch, config))
            for ch in channels
        ]

        # Add scheduler output monitoring task
        tasks.append(asyncio.create_task(monitor_scheduler_outputs()))

        # Wait indefinitely
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
            # Stop scheduler service
            await scheduler_service.stop()
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run_all())


@cli.command()
def list_sessions():
    """List all saved sessions."""
    config = load_config()
    context_guard = ContextGuard()
    session_store = SessionStore(config.paths.sessions_dir, context_guard)

    sessions = session_store.list_sessions()
    if not sessions:
        click.echo("No saved sessions found.")
        return

    click.echo(f"Found {len(sessions)} saved sessions:\n")
    for meta in sessions:
        click.echo(f"  {meta.session_id}")
        click.echo(f"    Agent: {meta.agent_id}")
        click.echo(f"    Channel: {meta.channel_id}")
        click.echo(f"    Peer: {meta.peer_id}")
        click.echo(f"    Messages: {meta.message_count}")
        click.echo()


@cli.command()
def doctor():
    """Check configuration and dependencies."""
    config = load_config()
    errors = validate_config(config)

    click.echo("AI Companion Doctor Check\n")
    click.echo(f"Workspace directory: {config.workspace_dir}")
    click.echo(f"  Exists: {config.workspace_dir.exists()}")
    click.echo(f"Sessions directory: {config.sessions_dir}")
    click.echo(f"  Exists: {config.sessions_dir.exists()}")
    click.echo(f"Plugins directory: {config.plugins_dir}")
    click.echo(f"  Exists: {config.plugins_dir.exists()}")
    click.echo()

    click.echo("Provider configuration:")
    click.echo(f"  Default provider: {config.default_provider}")
    click.echo(f"  Default model: {config.default_model}")
    click.echo(f"  Anthropic API key configured: {bool(config.anthropic_api_key)}")
    click.echo(f"  OpenAI API key configured: {bool(config.openai_api_key)}")
    click.echo()

    if config.feishu_app_id:
        click.echo("Feishu configuration:")
        click.echo(f"  App ID configured: {bool(config.feishu_app_id)}")
        click.echo(f"  App Secret configured: {bool(config.feishu_app_secret)}")
        click.echo()

    if errors:
        click.echo("Issues found:")
        for error in errors:
            click.echo(f"  ❌ {error}")
        click.echo()
    else:
        click.echo("✅ No configuration errors found.")
        click.echo()
        click.echo("You're ready to go! Try:")
        click.echo("  ai-companion chat    - start interactive CLI chat")
        click.echo("  ai-companion serve   - start server with configured channels")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
