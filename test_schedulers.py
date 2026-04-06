#!/usr/bin/env python3
"""
Test heartbeat and cron schedulers.
"""

import asyncio
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
    """Main test."""
    print("=" * 60)
    print("  Testing Heartbeat & Cron Schedulers")
    print("=" * 60)

    # Load config
    config = AppConfig()

    # Initialize components
    lane_manager = NamedLaneManager()
    prompt_builder = PromptBuilder(Path("./workspace"))

    # Create provider
    provider = AnthropicProvider(config=config)

    # Create scheduler service
    scheduler = SchedulerService(
        config=config,
        workspace_dir=Path("./workspace"),
        prompt_builder=prompt_builder,
        lane_manager=lane_manager,
        provider=provider,
        on_message=on_message,
    )

    # Get initial status
    status = scheduler.get_status()
    print("\n--- Initial Status ---")
    print(f"Heartbeat enabled: {status['heartbeat']['enabled']}")
    print(f"Heartbeat interval: {status['heartbeat']['interval']}")
    print(f"Heartbeat active hours: {status['heartbeat']['active_hours']}")
    print(f"Cron enabled: {status['cron']['enabled']}")
    print(f"Cron jobs loaded: {status['cron']['jobs_count']}")

    if status['cron']['jobs']:
        print("\n--- Cron Jobs ---")
        for job in status['cron']['jobs']:
            state = "ON" if job['enabled'] else "OFF"
            print(f"  [{state}] {job['id']} - {job['name']}")
            print(f"      Schedule: {job['schedule_kind']}")
            print(f"      Next run: {job['next_run']}")

    # Start schedulers
    print("\n--- Starting Schedulers ---")
    await scheduler.start()

    # Let them run for 10 seconds
    print("\nRunning schedulers for 10 seconds...")
    print("(Check status updates below)\n")
    for i in range(10):
        await asyncio.sleep(1)

        # Show status every 2 seconds
        if i % 2 == 0:
            hb = scheduler.get_status()['heartbeat']
            print(f"[{i}s] Heartbeat running: {hb['running']}, queue: {hb['queue_size']}")

            # Drain any output
            outputs = await scheduler.drain_output()
            for output in outputs:
                print(f"[{i}s] {output}")

    # Stop schedulers
    print("\n--- Stopping Schedulers ---")
    await scheduler.stop()

    # Final status
    status = scheduler.get_status()
    print(f"\n--- Final Status ---")
    print(f"Heartbeat running: {status['heartbeat']['running']}")

    # Cleanup
    await lane_manager.stop_all()

    print("\nTest completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
