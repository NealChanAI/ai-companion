#!/usr/bin/env python3
"""
Debug heartbeat scheduler.
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
    print(f"[OUTBOUND] To {msg.target_channel}/{msg.target_peer}: {msg.content[:100]}...")


async def main():
    print("=" * 60)
    print("  Debug: Heartbeat Scheduler")
    print("=" * 60)

    # Load config
    config = AppConfig()
    print(f"\n[CONFIG] Heartbeat interval: {config.heartbeat.interval_seconds}s")
    print(f"[CONFIG] Heartbeat enabled: {config.heartbeat.enabled}")

    # Check heartbeat file
    hb_file = Path("./workspace/HEARTBEAT.md")
    print(f"[FILE] HEARTBEAT.md exists: {hb_file.exists()}")
    if hb_file.exists():
        content = hb_file.read_text()
        print(f"[FILE] HEARTBEAT.md size: {len(content)} bytes")
        print(f"[FILE] HEARTBEAT.md empty: {not content.strip()}")

    # Initialize components
    lane_manager = NamedLaneManager()
    prompt_builder = PromptBuilder(Path("./workspace"))
    provider = AnthropicProvider(config=config)

    # Create scheduler
    scheduler = SchedulerService(
        config=config,
        workspace_dir=Path("./workspace"),
        prompt_builder=prompt_builder,
        lane_manager=lane_manager,
        provider=provider,
        on_message=on_message,
    )

    # Check should_run
    should_run, reason = scheduler.heartbeat.should_run()
    print(f"\n[SHOULD_RUN] should_run={should_run}, reason='{reason}'")

    # Start and monitor
    print("\n--- Starting ---")
    await scheduler.start()

    print("Monitoring for 15 seconds...")
    for i in range(15):
        await asyncio.sleep(1)

        # Check should_run every second
        should_run, reason = scheduler.heartbeat.should_run()
        if i % 3 == 0:
            print(f"[{i}s] should_run={should_run}, reason='{reason}', running={scheduler.heartbeat.running}")

        # Drain output
        outputs = await scheduler.drain_output()
        for output in outputs:
            print(f"[{i}saring] {output}")

    await scheduler.stop()
    await lane_manager.stop_all()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
