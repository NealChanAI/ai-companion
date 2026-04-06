#!/usr/bin/env python3
"""
Simple heartbeat interval test.
"""

import asyncio
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.ai_companion.config.schema import AppConfig
from src.ai_companion.concurrency.lanes import NamedLaneManager
from src.ai_companion.intelligence.builder import PromptBuilder


async def main():
    print("Testing Heartbeat Interval\n")

    config = AppConfig()
    print(f"Config interval: {config.heartbeat.interval_seconds}s")

    lane_manager = NamedLaneManager()
    heartbeat_lane = lane_manager.get_or_create("heartbeat")
    prompt_builder = PromptBuilder(Path("./workspace"))

    # Import HeartbeatRunner here to avoid import issues
    from src.ai_companion.heartbeat.runner import HeartbeatRunner

    def dummy_on_message(msg):
        pass

    runner = HeartbeatRunner(
        workspace_dir=Path("./workspace"),
        lane=heartbeat_lane,
        config=config.heartbeat,
        prompt_builder=prompt_builder,
        on_message=dummy_on_message,
    )

    # Initial should_run
    should_run, reason = runner.should_run()
    print(f"\nInitial should_run: {should_run}, reason: '{reason}'")
    print(f"  last_run_at: {runner.last_run_at}")
    print(f"  lane queue size: {heartbeat_lane._queue.qsize()}")

    # Start
    await runner.start()
    print("\nStarted. Waiting 65 seconds to trigger heartbeat...")

    for i in range(65):
        await asyncio.sleep(1)
        if i % 10 == 0:
            status = runner.status()
            print(f"[{i}s] running={status['running']}, should_run={status['should_run']}, next_in={status['next_in']}")

            # Check queue
            outputs = await runner.drain_output()
            if outputs:
                print(f"  -> Output: {outputs}")

    await runner.stop()
    await lane_manager.stop_all()
    print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(main())
