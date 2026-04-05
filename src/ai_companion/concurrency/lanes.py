"""
Named lanes for concurrency control.
From claw0 s10: Each session gets its own named lane, FIFO queuing,
so no concurrent processing for the same session.
"""

import asyncio
from typing import Dict, Callable, Coroutine, Any
from ai_companion.logging.logger import get_logger

logger = get_logger(__name__)


class NamedLane:
    """A single named lane that processes tasks FIFO."""

    def __init__(self, lane_name: str):
        self.lane_name = lane_name
        self._queue: asyncio.Queue[Callable[[], Coroutine[Any, Any, Any]]] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    async def _worker(self) -> None:
        """Worker coroutine that processes tasks from the queue."""
        while self._running:
            try:
                task = await self._queue.get()
                try:
                    await task()
                except Exception as e:
                    logger.error(f"Error in lane {self.lane_name}: {e}")
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break

    def start(self) -> None:
        """Start the lane worker."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._worker())

    def stop(self) -> None:
        """Stop the lane worker."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def join(self) -> None:
        """Wait for all queued tasks to complete."""
        await self._queue.join()

    def enqueue(self, coro: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """Enqueue a task to be processed."""
        self._queue.put_nowait(coro)

    @property
    def size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()


class NamedLaneManager:
    """
    Manager for named lanes.
    From claw0 s10: Each session gets its own lane, ensures FIFO execution,
    prevents concurrent processing for the same session.
    """

    def __init__(self):
        self._lanes: Dict[str, NamedLane] = {}

    def get_or_create(self, lane_name: str) -> NamedLane:
        """Get an existing lane or create a new one."""
        if lane_name not in self._lanes:
            lane = NamedLane(lane_name)
            lane.start()
            self._lanes[lane_name] = lane
        return self._lanes[lane_name]

    def enqueue(self, lane_name: str, coro: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """Enqueue a task to a named lane."""
        lane = self.get_or_create(lane_name)
        lane.enqueue(coro)

    async def stop_lane(self, lane_name: str) -> None:
        """Stop a named lane."""
        if lane_name in self._lanes:
            lane = self._lanes[lane_name]
            lane.stop()
            await lane.join()
            del self._lanes[lane_name]

    async def stop_all(self) -> None:
        """Stop all lanes."""
        for lane_name in list(self._lanes.keys()):
            await self.stop_lane(lane_name)

    def stats(self) -> Dict[str, int]:
        """Get statistics about lanes."""
        return {
            name: lane.size
            for name, lane in self._lanes.items()
        }
