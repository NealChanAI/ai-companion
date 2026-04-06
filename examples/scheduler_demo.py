#!/usr/bin/env python3
"""
Demonstrates heartbeat and cron scheduler usage.
"""

import asyncio
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_companion.config.schema import AppConfig
from ai_companion.services.scheduler_service import SchedulerService
from ai_companion.concurrency.lanes import NamedLaneManager
from ai_companion.intelligence.builder import PromptBuilder
from ai_companion.providers.anthropic import AnthropicProvider


async def on_message(msg):
    """Handle outbound messages."""
    print(f"[OUTBOUND] To {msg.target_channel}/{msg.target_peer}: {msg.content[:100]}...")


async def main():
    """Main demo."""
    print("=" * 60)
    print("  AI Companion - Heartbeat & Cron Scheduler Demo")
    print("=" * 60)

    # Load config
    config = AppConfig()

    # Initialize components
    lane_manager = NamedLaneManager()
    prompt_builder = PromptBuilder(Path("./workspace"))

    # Create provider (requires ANTHROPIC_API_KEY)
    if not config.anthropic_api_key:
        print("\nWarning: ANTHROPIC_API_KEY not set")
        print("Set it in .env file to enable LLM calls\n")
        print("Demo will continue with status checks only...")

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

    # Interactive prompt
    print("\n--- Commands ---")
    print("  status - Show scheduler status")
    print("  heartbeat - Show heartbeat details")
    print("  cron - List cron jobs")
    print("  trigger - Manually trigger heartbeat")
    print("  start - Start schedulers")
    print("  stop  - Stop schedulers")
    print("  quit  - Exit")

    running = True
    schedulers_started = False

    while running:
        try:
            cmd = input("\n> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            cmd = "quit"

        if cmd == "quit":
            running = False
            break

        elif cmd == "status":
            status = scheduler.get_status()
            print("\n--- Status ---")
            hb = status['heartbeat']
            print(f"Heartbeat:")
            print(f"  Enabled: {hb['enabled']}")
            print(f"  Running: {hb['running']}")
            print(f"  Should run: {hb['should_run']} ({hb['reason']})")
            print(f"  Last run: {hb['last_run']}")
            print(f"  Next in: {hb['next_in']}")
            print(f"  Queue: {hb['queue_size']}")

            print(f"\nCron:")
            print(f"  Enabled: {status['cron']['enabled']}")
            print(f"  Jobs: {status['cron']['jobs_count']}")

        elif cmd == "heartbeat":
            status = scheduler.get_status()['heartbeat']
            print("\n--- Heartbeat ---")
            for k, v in status.items():
                print(f"  {k}: {v}")

        elif cmd == "cron":
            jobs = scheduler.get_status()['cron']['jobs']
            print("\n--- Cron Jobs ---")
            if not jobs:
                print("  No cron jobs configured")
            for job in jobs:
                state = "ON" if job['enabled'] else "OFF"
                err = f" err:{job['consecutive_errors']}" if job['consecutive_errors'] else ""
                next = f" in {job['next_in']}s" if job['next_in'] else ""
                print(f"  [{state}] {job['id']} - {job['name']}{err}{next}")
                print(f"      Schedule: {job['schedule_kind']}")
                print(f"      Last run: {job['last_run']}")
                print(f"      Next run: {job['next_run']}")

        elif cmd == "trigger":
            result = await scheduler.heartbeat.trigger()
            print(f"\n[TRIGGER] {result}")

            # Drain any output
            outputs = await scheduler.drain_output()
            for output in outputs:
                print(f"[HEARTBEAT] {output}")

        elif cmd == "start":
            if schedulers_started:
                print("Schedulers already started")
            else:
                print("Starting schedulers...")
                await scheduler.start()
                schedulers_started = True
                print("Schedulers started!")
                print("\nTip: Check status in a few seconds")

        elif cmd == "stop":
            if schedulers_started:
                print("Stopping schedulers...")
                await scheduler.stop()
                schedulers_started = False
                print("Schedulers stopped")
            else:
                print("Schedulers not running")

        else:
            print(f"Unknown command: {cmd}")

    # Cleanup
    if schedulers_started:
        await scheduler.stop()
    await lane_manager.stop_all()

    print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
