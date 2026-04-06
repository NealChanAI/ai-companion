#!/usr/bin/env python3
"""
Debug heartbeat execution timing.
"""

import asyncio
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.ai_companion.config.schema import AppConfig
from src.ai_companion.services.scheduler_service import SchedulerService
from src.ai_companion.concurrency.lanes import NamedLaneManager
from src.ai_companion.intelligence.builder import PromptBuilder
from src.ai_companion.providers.anthropic import AnthropicProvider


async def on_message(msg):
    """Handle outbound messages."""
    print(f"[OUTBOUND] {msg.content[:200]}...")


async def main():
    print("=" * 60)
    print("  Heartbeat Debug")
    print("=" * 60)

    config = AppConfig()
    print(f"\n[CONFIG] Interval: {config.heartbeat.interval_seconds}s")

    lane_manager = NamedLaneManager()
    prompt_builder = PromptBuilder(Path("./workspace"))
    provider = AnthropicProvider(config=config)

    scheduler = SchedulerService(
        config=config,
        workspace_dir=Path("./workspace"),
        prompt_builder=prompt_builder,
        lane_manager=lane_manager,
        provider=provider,
        on_message=on_message,
    )

    # Track last_run_at
    last_run = 0.0

    await scheduler.start()

    print("\n--- Monitoring ---")

    for i in range(75):
        await asyncio.sleep(1)

        current_run = scheduler.heartbeat.last_run_at
        if current_run != last_run:
            print(f"[{i}s] ⚠️ last_run_at CHANGED: {last_run} -> {current_run}")
            last_run = current_run

        if i % 10 == 0 or 58 <= i <= 62:
            status = scheduler.get_status()['heartbeat']
            print(f"[{i}s] last_run={status['last_run']}, should_run={status['should_run']}, next_in={status['next_in']}")

        outputs = await scheduler.drain_output()
        for output in outputs:
            print(f"[{i}s] >>> {output[:200]}")

    await scheduler.stop()
    await lane_manager.stop_all()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
