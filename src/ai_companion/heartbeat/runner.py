"""
Async heartbeat runner using NamedLane for concurrency control.
Adapted from claw0's HeartbeatRunner but using asyncio.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime

from ai_companion.config.heartbeat import HeartbeatConfig
from ai_companion.types.message import Message, OutboundMessage
from ai_companion.concurrency.lanes import NamedLane
from ai_companion.intelligence.builder import PromptBuilder
from ai_companion.logging.logger import get_logger

logger = get_logger(__name__)


class HeartbeatRunner:
    """
    Async heartbeat runner using NamedLane for concurrency control.

    Adapted from claw0's HeartbeatRunner but using asyncio instead of threading.
    Key features:
    - Uses NamedLane "heartbeat" for concurrency control
    - Non-blocking check for lane occupation (yields to user messages)
    - 4 precondition checks: enabled, file exists, interval elapsed, active hours
    - HEARTBEAT_OK convention for "nothing to report"
    - Output deduplication
    - Light context mode for cost optimization
    """

    HEARTBEAT_OK_TOKEN = "HEARTBEAT_OK"

    def __init__(
        self,
        workspace_dir: Path,
        lane: "NamedLane",
        config: HeartbeatConfig,
        prompt_builder: PromptBuilder,
        on_message: Callable[[OutboundMessage], None],
    ):
        self.workspace_dir = workspace_dir
        self.lane = lane
        self.config = config
        self.prompt_builder = prompt_builder
        self.on_message = on_message

        self.heartbeat_path = workspace_dir / "HEARTBEAT.md"
        self.last_run_at: float = 0.0
        self.running: bool = False
        self._stopped: bool = False
        self._task: asyncio.Task | None = None
        self._last_output: str = ""
        self._output_queue: asyncio.Queue[str] = asyncio.Queue(
            maxsize=config.max_queue_size
        )

        # LLM execution callback (injected by SchedulerService)
        self._llm_executor: Callable[[str, str | None], str] | None = None

    def set_llm_executor(self, executor: Callable[[str, str | None], str]) -> None:
        """Set LLM execution callback."""
        self._llm_executor = executor

    def should_run(self) -> tuple[bool, str]:
        """4 precondition checks."""
        if not self.config.enabled:
            return False, "heartbeat disabled"

        if not self.heartbeat_path.exists():
            return False, "HEARTBEAT.md not found"

        content = self.heartbeat_path.read_text(encoding="utf-8").strip()
        if not content:
            return False, "HEARTBEAT.md is empty"

        now = time.time()
        elapsed = now - self.last_run_at
        if elapsed < self.config.interval_seconds:
            remaining = self.config.interval_seconds - elapsed
            return False, f"interval not elapsed ({remaining:.0f}s remaining)"

        hour = datetime.now().hour
        start, end = self.config.active_hours
        in_hours = (start <= hour < end) if start <= end else not (end <= hour < start)
        if not in_hours:
            return False, f"outside active hours ({start}:00-{end}:00)"

        if self.running:
            return False, "already running"

        return True, "all checks passed"

    def _build_heartbeat_prompt(self) -> str:
        """Build prompt with current time and context."""
        instructions = self.heartbeat_path.read_text(encoding="utf-8").strip()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.config.light_context:
            # Minimal prompt for cost optimization
            prompt = f"{instructions}\n\nCurrent time: {current_time}"
            logger.debug(f"[HEARTBEAT] Prompt (light context): {prompt[:200]}...")
            return prompt

        # Full prompt with all layers
        system_prompt = self.prompt_builder.build_system_prompt()
        prompt = f"{system_prompt}\n\n{instructions}\n\nCurrent time: {current_time}"
        logger.info(f"[HEARTBEAT] System prompt:\n{system_prompt[:500]}...")
        logger.debug(f"[HEARTBEAT] Full prompt: {prompt[:200]}...")
        return prompt

    def _parse_response(self, response: str) -> Optional[str]:
        """Parse response, handle HEARTBEAT_OK."""
        if self.HEARTBEAT_OK_TOKEN in response:
            stripped = response.replace(self.HEARTBEAT_OK_TOKEN, "").strip()
            # Return stripped content if meaningful, else None
            return stripped if len(stripped) > 5 else None
        return response.strip() or None

    async def _execute(self) -> None:
        """Execute heartbeat check. Yields if lane lane occupied."""
        if not self.lane._queue.empty():
            # Lane has pending work, yield to user messages
            logger.debug("[HEARTBEAT] Lane occupied, yielding")
            return

        self.running = True
        llm_called = False
        try:
            prompt = self._build_heartbeat_prompt()
            if not prompt:
                logger.warning("[HEARTBEAT] Empty prompt, skipping")
                return

            # Run LLM call via injected executor
            if self._llm_executor is None:
                logger.error("[HEARTBEAT] No LLM executor set")
                await self._output_queue.put("[heartbeat error: No LLM executor]")
                return

            response = await self._llm_executor(prompt, None)
            llm_called = True
            meaningful = self._parse_response(response)

            if meaningful is None:
                # HEARTBEAT_OK, send token if configured
                if self.config.show_ok:
                    await self._output_queue.put(self.HEARTBEAT_OK_TOKEN)
                    logger.debug("[HEARTBEAT] HEARTBEAT_OK")
                return

            # Deduplication check
            if meaningful.strip() == self._last_output:
                logger.debug("[HEARTBEAT] Duplicate output, skipping")
                return

            self._last_output = meaningful.strip()
            await self._output_queue.put(meaningful)
            logger.info(f"[HEARTBEAT] Output queued: {meaningful[:50]}...")

        except Exception as exc:
            logger.error(f"[HEARTBEAT] Execution error: {exc}")
            await self._output_queue.put(f"[heartbeat error: {exc}]")
        finally:
            self.running = False
            # Only update last_run_at if we successfully called LLM
            if llm_called:
                self.last_run_at = time.time()

    async def _loop(self) -> None:
        """Main heartbeat loop."""
        logger.info("[HEARTBEAT] Starting heartbeat loop")
        while not self._stopped:
            try:
                should_run, reason = self.should_run()
                if should_run:
                    logger.debug("[HEARTBEAT] Should run, executing")
                    await self._execute()
                else:
                    logger.debug(f"[HEARTBEAT] Skipping: {reason}")
            except asyncio.CancelledError:
                logger.info("[HEARTBEAT] Loop cancelled")
                break
            except Exception as exc:
                logger.error(f"[HEARTBEAT] Loop error: {exc}")
                # Don't crash the loop
            await asyncio.sleep(1.0)
        logger.info("[HEARTBEAT] Heartbeat loop stopped")

    async def start(self) -> None:
        """Start heartbeat runner."""
        if self._task is not None:
            logger.warning("[HEARTBEAT] Already started")
            return
        self._stopped = False
        self._task = asyncio.create_task(self._loop(), name="heartbeat")
        logger.info("[HEARTBEAT] Started")

    async def stop(self) -> None:
        """Stop heartbeat runner."""
        self._stopped = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[HEARTBEAT] Stopped")

    async def drain_output(self) -> List[str]:
        """Drain output queue."""
        outputs = []
        while not self._output_queue.empty():
            try:
                item = await asyncio.wait_for(self._output_queue.get(), timeout=0.1)
                outputs.append(item)
                self._output_queue.task_done()
            except asyncio.TimeoutError:
                break
        return outputs

    async def trigger(self) -> str:
        """Manually trigger heartbeat."""
        if not self.lane._queue.empty():
            return "main lane occupied, cannot trigger"

        self.running = True
        try:
            prompt = self._build_heartbeat_prompt()
            if not prompt:
                return "HEARTBEAT.md is empty"

            if self._llm_executor is None:
                return "No LLM executor set"

            response = await self._llm_executor(prompt, None)
            meaningful = self._parse_response(response)

            if meaningful is None:
                return "HEARTBEAT_OK (nothing to report)"

            if meaningful.strip() == self._last_output:
                return "duplicate content (skipped)"

            self._last_output = meaningful.strip()
            await self._output_queue.put(meaningful)
            return f"triggered, output queued ({len(meaningful)} chars)"
        except Exception as exc:
            return f"trigger failed: {exc}"
        finally:
            self.running = False
            self.last_run_at = time.time()

    def status(self) -> dict:
        """Get heartbeat status."""
        now = time.time()
        elapsed = now - self.last_run_at if self.last_run_at > 0 else None
        next_in = max(0.0, self.config.interval_seconds - elapsed) if elapsed is not None else self.config.interval_seconds
        should_run, reason = self.should_run()

        return {
            "enabled": self.config.enabled,
            "running": self.running,
            "should_run": should_run,
            "reason": reason,
            "last_run": datetime.fromtimestamp(self.last_run_at).isoformat() if self.last_run_at > 0 else "never",
            "next_in": f"{round(next_in)}s",
            "interval": f"{self.config.interval_seconds}s",
            "active_hours": f"{self.config.active_hours[0]}:00-{self.config.active_hours[1]}:00",
            "queue_size": self._output_queue.qsize(),
            "light_context": self.config.light_context,
            "isolated_session": self.config.isolated_session,
        }
