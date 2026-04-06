"""
Async cron scheduler supporting at, every, and cron schedules.
Includes retry policies and timezone support.
"""

import asyncio
import time
import json
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime, timezone

try:
    from croniter import croniter
    import pytz
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False
    croniter = None
    pytz = None

from ai_companion.config.cron import (
    CronConfig, CronJobConfig,
    ScheduleAt, ScheduleEvery, ScheduleCron,
    PayloadAgentTurn, PayloadSystemEvent,
)
from ai_companion.cron.types import CronJob, CronRunResult, CronRunLog
from ai_companion.types.message import OutboundMessage
from ai_companion.logging.logger import get_logger

logger = get_logger(__name__)


class CronScheduler:
    """
    Async cron scheduler.

    Supports three schedule types: at, every, cron.
    Includes retry policies and timezone support.
    """

    def __init__(
        self,
        workspace_dir: Path,
        config: CronConfig,
        on_message: Callable[[OutboundMessage], None],
    ):
        self.workspace_dir = workspace_dir
        self.config = config
        self.on_message = on_message

        self.cron_file = workspace_dir / "CRON.json"
        self.cron_dir = workspace_dir / "cron"
        self.run_log_path = self.cron_dir / "runs.jsonl"
        self.sessions_dir = self.cron_dir / "sessions"

        self.jobs: List[CronJob] = []
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._stopped: bool = False
        self._task: asyncio.Task | None = None
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()

        # LLM execution callback (injected by SchedulerService)
        self._llm_executor: Callable[[str, str | None, str | None], str] | None = None

        # Ensure directories exist
        self.cron_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.load_jobs()

    def set_llm_executor(self, executor: Callable[[str, str | None, str | None], str]) -> None:
        """Set LLM execution callback."""
        self._llm_executor = executor

    def load_jobs(self) -> None:
        """Load jobs from CRON.json."""
        self.jobs.clear()
        if not self.cron_file.exists():
            logger.info("[CRON] CRON.json not found, no jobs loaded")
            return

        try:
            data = json.loads(self.cron_file.read_text(encoding="utf-8"))
            jobs_list = data.get("jobs", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(f"[CRON] Failed to load CRON.json: {exc}")
            return

        now = time.time()
        for job_data in jobs_list:
            try:
                job_config = CronJobConfig(**job_data)
                job = CronJob(id=job_config.id, config=job_config)
                job.next_run_at = self._compute_next_run(job, now)
                self.jobs.append(job)
                logger.info(f"[CRON] Loaded job: {job_config.id}")
            except Exception as exc:
                logger.error(f"[CRON] Failed to load job {job_data.get('id', 'unknown')}: {exc}")

        logger.info(f"[CRON] Loaded {len(self.jobs)} jobs")

    def _compute_next_run(self, job: CronJob, now: float) -> float:
        """Compute next run timestamp."""
        if not HAS_CRONITER:
            logger.error("[CRON] croniter not installed, schedule disabled")
            return 0.0

        schedule = job.config.schedule

        if isinstance(schedule, ScheduleAt):
            try:
                ts = datetime.fromisoformat(schedule.at).timestamp()
                return ts if ts > now else 0.0
            except (ValueError, OSError):
                logger.error(f"[CRON] Invalid 'at' timestamp: {schedule.at}")
                return 0.0

        elif isinstance(schedule, ScheduleEvery):
            every = schedule.every_seconds
            try:
                anchor = datetime.fromisoformat(schedule.anchor).timestamp()
            except (ValueError, TypeError):
                anchor = now

            if now < anchor:
                return anchor

            steps = int((now - anchor) / every) + 1
            return anchor + steps * every

        elif isinstance(schedule, ScheduleCron):
            try:
                tz_name = schedule.timezone or "UTC"
                tz = pytz.timezone(tz_name)
                dt = datetime.fromtimestamp(now, tz=timezone.utc).astimezone(tz)
                cron = croniter(schedule.expr, dt)
                next_dt = cron.get_next(datetime)
                return next_dt.timestamp()
            except Exception as exc:
                logger.error(f"[CRON] Invalid cron expression '{schedule.expr}': {exc}")
                return 0.0

        return 0.0

    async def _run_job(self, job: CronJob) -> CronRunResult:
        """Execute a single cron job."""
        start_time = time.time()
        result = CronRunResult(job_id=job.id)

        try:
            # Execute based on payload type
            payload = job.config
            if isinstance(payload, PayloadAgentTurn):
                result.output = await self._run_agent_turn(job, payload)
                result.status = "ok"
            elif isinstance(payload, PayloadSystemEvent):
                result.output = payload.text
                result.status = "ok" if payload.text else "skipped"
            else:
                result.status = "skipped"
                result.error = f"unknown payload type: {type(payload)}"

        except Exception as exc:
            result.status = "error"
            result.error = str(exc)
            result.output = f"[error: {exc}]"

        result.duration_seconds = time.time() - start_time
        return result

    async def _run_agent_turn(self, job: CronJob, payload: PayloadAgentTurn) -> str:
        """Run agent turn for cron job."""
        if self._llm_executor is None:
            return "[error: No LLM executor set]"

        # Execute with injected LLM executor
        return await self._llm_executor(
            payload.message,
            None,  # system prompt
            payload.model
        )

    def _log_run(self, job: CronJob, result: CronRunResult) -> None:
        """Persist run log entry."""
        log_entry = CronRunLog(
            job_id=job.id,
            run_at=datetime.fromtimestamp(result.run_at, tz=timezone.utc).isoformat(),
            status=result.status,
            output_preview=result.output[:200],
            error=result.error,
            duration_seconds=result.duration_seconds,
        )

        try:
            with open(self.run_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry.__dict__, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error(f"[CRON] Failed to write run log: {exc}")

        # Log rotation (simple implementation)
        self._rotate_run_log()

    def _rotate_run_log(self) -> None:
        """Rotate run log if exceeds size/line limits."""
        try:
            if not self.run_log_path.exists():
                return

            # Check file size
            if self.run_log_path.stat().st_size > self.config.run_log_max_bytes:
                # Keep only last N lines
                lines = []
                with open(self.run_log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                keep_lines = lines[-self.config.run_log_keep_lines:]
                with open(self.run_log_path, "w", encoding="utf-8") as f:
                    f.writelines(keep_lines)

                logger.info(f"[CRON] Rotated run log, kept {len(keep_lines)} lines")
        except Exception as exc:
            logger.error(f"[CRON] Failed to rotate run log: {exc}")

    def _should_auto_disable(self, job: CronJob) -> bool:
        """Check if job should be auto-disabled."""
        max_attempts = job.config.retry.max_attempts
        return job.consecutive_errors >= max_attempts

    async def _process_ready_jobs(self) -> None:
        """Process all jobs ready to run."""
        now = time.time()
        to_remove: List[str] = []

        # Limit concurrent runs
        running_count = sum(1 for t in self._running_tasks.values() if not t.done())
        if running_count >= self.config.max_concurrent_runs:
            logger.debug(f"[CRON] Max concurrent runs ({self.config.max_concurrent_runs}) reached")
            return

        for job in self.jobs:
            if not job.config.enabled:
                continue

            if job.next_run_at <= 0 or now < job.next_run_at:
                continue

            # Skip if already running
            if job.id in self._running_tasks and not self._running_tasks[job.id].done():
                logger.debug(f"[CRON] Job {job.id} already running")
                continue

            # Create and run task
            task = asyncio.create_task(self._execute_job_wrapper(job))
            self._running_tasks[job.id] = task
            logger.info(f"[CRON] Triggered job: {job.id}")

            # Remove 'at' jobs after run
            if job.config.delete_after_run and isinstance(job.config.schedule, ScheduleAt):
                to_remove.append(job.id)

        # Clean up completed tasks
        for job_id, task in list(self._running_tasks.items()):
            if task.done():
                try:
                    result = task.result()
                    job = next((j for j in self.jobs if j.id == job_id), None)

                    if result.status == "error":
                        # Increment error count
                        if job:
                            job.consecutive_errors += 1
                            job.last_error = result.error

                            if self._should_auto_disable(job):
                                job.config.enabled = False
                                logger.warning(f"[CRON] Job {job_id} auto-disabled after {job.consecutive_errors} errors")
                    else:
                        # Reset error count on success
                        if job:
                            job.consecutive_errors = 0
                            job.last_error = None
                            job.last_run_at = result.run_at
                            job.next_run_at = self._compute_next_run(job, time.time())

                except Exception as exc:
                    logger.error(f"[CRON] Error processing job {job_id} result: {exc}")
                finally:
                    del self._running_tasks[job_id]

        # Remove deleted jobs
        if to_remove:
            self.jobs = [j for j in self.jobs if j.id not in to_remove]
            logger.info(f"[CRON] Removed {len(to_remove)} one-time jobs")

    async def _execute_job_wrapper(self, job: CronJob) -> CronRunResult:
        """Wrapper for job execution with error handling."""
        try:
            result = await self._run_job(job)
            self._log_run(job, result)

            # Queue output
            if result.output and result.status != "skipped":
                await self._output_queue.put(f"[{job.config.name}] {result.output}")

            # Send to delivery if configured
            if result.status == "ok" and result.output:
                await self._deliver_result(job, result)

            return result
        except Exception as exc:
            result = CronRunResult(
                job_id=job.id,
                status="error",
                error=str(exc),
                output=f"[execution error: {exc}]"
            )
            self._log_run(job, result)
            return result

    async def _deliver_result(self, job: CronJob, result: CronRunResult) -> None:
        """Deliver job result based on delivery config."""
        delivery = job.config.delivery

        if delivery.mode == "none":
            return

        if delivery.mode == "webhook" and delivery.webhook_url:
            # Send webhook (implement with httpx/aiohttp)
            logger.info(f"[CRON] Would send webhook to {delivery.webhook_url}")
            pass

        if delivery.mode == "announce":
            # Send message via on_message callback
            target_channel = delivery.channel or "default"
            target_peer = delivery.to or "system"
            message = OutboundMessage(
                target_channel=target_channel,
                target_peer=target_peer,
                content=result.output
            )
            self.on_message(message)

    async def _loop(self) -> None:
        """Main scheduler loop."""
        logger.info("[CRON] Starting scheduler loop")
        while not self._stopped:
            try:
                await self._process_ready_jobs()
            except asyncio.CancelledError:
                logger.info("[CRON] Loop cancelled")
                break
            except Exception as exc:
                logger.error(f"[CRON] Loop error: {exc}")
            await asyncio.sleep(1.0)
        logger.info("[CRON] Scheduler loop stopped")

    async def start(self) -> None:
        """Start scheduler."""
        if not self.config.enabled:
            logger.info("[CRON] Cron disabled in config")
            return
        if self._task is not None:
            logger.warning("[CRON] Already started")
            return
        self._stopped = False
        self._task = asyncio.create_task(self._loop(), name="cron-scheduler")
        logger.info("[CRON] Started")

    async def stop(self) -> None:
        """Stop scheduler."""
        self._stopped = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Wait for running jobs
        if self._running_tasks:
            logger.info(f"[CRON] Waiting for {len(self._running_tasks)} running jobs")
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

        logger.info("[CRON] Stopped")

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

    def trigger_job(self, job_id: str) -> str:
        """Manually trigger a job."""
        job = next((j for j in self.jobs if j.id == job_id), None)
        if not job:
            return f"Job '{job_id}' not found"

        if not job.config.enabled:
            return f"Job '{job_id}' is disabled"

        # Create immediate task
        task = asyncio.create_task(self._execute_job_wrapper(job))
        self._running_tasks[job_id] = task
        return f"Triggered job '{job_id}'"

    def list_jobs(self) -> List[dict]:
        """List all jobs with status."""
        now = time.time()
        result = []

        for job in self.jobs:
            next_in = job.next_run_at - now if job.next_run_at > 0 else None
            result.append({
                "id": job.id,
                "name": job.config.name,
                "enabled": job.config.enabled,
                "schedule_kind": job.config.schedule.kind,
                "consecutive_errors": job.consecutive_errors,
                "last_run": datetime.fromtimestamp(job.last_run_at).isoformat() if job.last_run_at > 0 else "never",
                "next_run": datetime.fromtimestamp(job.next_run_at).isoformat() if job.next_run_at > 0 else "n/a",
                "next_in": round(next_in) if next_in is not None else None,
            })

        return result

    def reload_jobs(self) -> None:
        """Reload jobs from file."""
        self.load_jobs()
