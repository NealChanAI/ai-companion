"""
Orchestrates heartbeat and cron scheduling.
Integrates with existing NamedLane system and AgentLoop.
"""

import asyncio
from pathlib import Path
from typing import Callable

from ai_companion.config.schema import AppConfig
from ai_companion.heartbeat.runner import HeartbeatRunner
from ai_companion.cron.scheduler import CronScheduler
from ai_companion.concurrency.lanes import NamedLaneManager
from ai_companion.intelligence.builder import PromptBuilder
from ai_companion.types.message import OutboundMessage, Message
from ai_companion.providers.base import BaseProvider
from ai_companion.logging.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """
    Orchestrates heartbeat and cron scheduling.

    Integrates with existing NamedLane system and provides
    unified interface for background task management.
    """

    def __init__(
        self,
        config: AppConfig,
        workspace_dir: Path,
        prompt_builder: PromptBuilder,
        lane_manager: NamedLaneManager,
        provider: BaseProvider,  # For LLM calls
        on_message: Callable[[OutboundMessage], None],
    ):
        self.config = config
        self.workspace_dir = workspace_dir
        self.prompt_builder = prompt_builder
        self.lane_manager = lane_manager
        self.provider = provider
        self.on_message = on_message

        # Create dedicated lane for heartbeat
        self.heartbeat_lane = lane_manager.get_or_create("heartbeat")

        # Initialize heartbeat
        self.heartbeat = HeartbeatRunner(
            workspace_dir=workspace_dir,
            lane=self.heartbeat_lane,
            config=config.heartbeat,
            prompt_builder=prompt_builder,
            on_message=on_message,
        )

        # Initialize cron scheduler
        self.cron = CronScheduler(
            workspace_dir=workspace_dir,
            config=config.cron,
            on_message=on_message,
        )

        # Wire up LLM executors
        self._wire_llm_executors()

    def _wire_llm_executors(self) -> None:
        """Wire up LLM execution callbacks for heartbeat and cron."""

        async def heartbeat_llm_executor(prompt: str, system_prompt: str | None) -> str:
            """LLM executor for heartbeat (text-only, no tools)."""
            try:
                messages = [Message(role="user", content=prompt)]
                response = self.provider.complete(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=None,
                    max_tokens=2048,
                )
                if isinstance(response.content, str):
                    return response.content
                else:
                    # Extract text from content blocks
                    text = ""
                    for block in response.content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text += block.get("text", "")
                    return text
            except Exception as exc:
                logger.error(f"[SCHEDULER] Heartbeat LLM error: {exc}")
                return f"[error: {exc}]"

        async def cron_llm_executor(
            prompt: str,
            system_prompt: str | None,
            model_override: str | None = None
        ) -> str:
            """LLM executor for cron jobs (with tools support)."""
            try:
                messages = [Message(role="user", content=prompt)]
                response = self.provider.complete(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=None,  # TODO: Add tools if needed
                    max_tokens=4096,
                    model=model_override,
                )
                if isinstance(response.content, str):
                    return response.content
                else:
                    # Extract text from content blocks
                    text = ""
                    for block in response.content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text += block.get("text", "")
                    return text
            except Exception as exc:
                logger.error(f"[SCHEDULER] Cron LLM error: {exc}")
                return f"[error: {exc}]"

        # Set executors
        self.heartbeat.set_llm_executor(heartbeat_llm_executor)
        self.cron.set_llm_executor(cron_llm_executor)

    async def start(self) -> None:
        """Start all schedulers."""
        logger.info("[SCHEDULER] Starting schedulers")
        await asyncio.gather(
            self.heartbeat.start(),
            self.cron.start(),
        )
        logger.info("[SCHEDULER] All schedulers started")
        # Start output monitor task
        self._output_task = asyncio.create_task(self._monitor_outputs())

    async def _monitor_outputs(self) -> None:
        """Monitor output queues and send messages."""
        logger.info("[SCHEDULER] Output monitor started")
        while True:
            try:
                # Check heartbeat queue
                hb_outputs = await self.heartbeat.drain_output()
                for output in hb_outputs:
                    # Check if this is an error message
                    if output.startswith("[heartbeat error:"):
                        logger.error(f"[SCHEDULER] Heartbeat error: {output}")
                        continue
                    if output == "HEARTBEAT_OK":
                        logger.debug("[SCHEDULER] Heartbeat OK, no message to send")
                        continue
                    logger.info(f"[SCHEDULER] Heartbeat output: {output[:50]}...")
                    # Send message via on_message callback
                    # Use default target from config if available
                    target = self.config.heartbeat.default_target
                    if target:
                        self.on_message(OutboundMessage(
                            target_channel="feishu",
                            target_peer=target,
                            content=output
                        ))
                    else:
                        logger.warning(f"[SCHEDULER] No default target, cannot send: {output[:100]}")

                # Check cron queue
                cron_outputs = await self.cron.drain_output()
                for output in cron_outputs:
                    logger.info(f"[SCHEDULER] Cron output: {output[:50]}...")
                    # TODO: Cron jobs should specify their target
                    # For now, send to default if available
                    target = self.config.heartbeat.default_target
                    if target:
                        self.on_message(OutboundMessage(
                            target_channel="feishu",
                            target_peer=target,
                            content=output
                        ))
                    else:
                        logger.warning(f"[SCHEDULER] No default target, cannot send cron output: {output[:100]}")

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                logger.info("[SCHEDULER] Output monitor cancelled")
                break
            except Exception as exc:
                logger.error(f"[SCHEDULER] Output monitor error: {exc}")

    async def stop(self) -> None:
        """Stop all schedulers."""
        logger.info("[SCHEDULER] Stopping schedulers")
        if hasattr(self, '_output_task') and self._output_task:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(
            self.heartbeat.stop(),
            self.cron.stop(),
        )
        logger.info("[SCHEDULER] All schedulers stopped")

    async def drain_output(self) -> list[str]:
        """Drain all output queues."""
        outputs = []
        outputs.extend(await self.heartbeat.drain_output())
        outputs.extend(await self.cron.drain_output())
        return outputs

    def get_status(self) -> dict:
        """Get comprehensive status."""
        return {
            "heartbeat": self.heartbeat.status(),
            "cron": {
                "enabled": self.cron.config.enabled,
                "jobs_count": len(self.cron.jobs),
                "jobs": self.cron.list_jobs(),
            },
        }
