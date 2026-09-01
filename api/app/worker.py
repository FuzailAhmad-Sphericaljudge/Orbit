import asyncio
import json
import logging
import socket

from .database import SessionLocal
from .coordination import CoordinationBusy, coordination
from .job_queue import GROUP, STREAM, job_queue
from .production_learning_service import run_learning_cycle
from .retention import apply_retention


logger = logging.getLogger("orbit.worker")


def run_retention(payload: dict) -> dict:
    with SessionLocal() as db:
        return apply_retention(db, int(payload["retention_days"]), bool(payload.get("confirm", False)))


HANDLERS = {"retention_cleanup": run_retention}


async def process(message_id: str, fields: dict) -> None:
    client = await job_queue.redis()
    job_id = fields.get("job_id", message_id)
    if await client.exists(f"orbit:job:done:{job_id}"):
        await client.xack(STREAM, GROUP, message_id)
        return
    attempt = int(fields.get("attempt", "0"))
    try:
        handler = HANDLERS[fields["kind"]]
        payload = json.loads(fields.get("payload", "{}"))
        await asyncio.to_thread(handler, payload)
        await client.set(f"orbit:job:done:{job_id}", "1", ex=7 * 24 * 3600)
        await client.xack(STREAM, GROUP, message_id)
    except Exception as exc:
        await client.xack(STREAM, GROUP, message_id)
        if attempt + 1 >= job_queue.settings.job_max_retries:
            await job_queue.dead_letter(fields, str(exc))
            logger.exception("Job moved to dead-letter stream: %s", job_id)
        else:
            delay = min(2 ** attempt, 60)
            await job_queue.schedule_retry({**fields, "attempt": str(attempt + 1), "last_error": str(exc)[:1000]}, delay)
            logger.warning("Job retry scheduled: id=%s attempt=%s delay=%ss", job_id, attempt + 1, delay)


async def recover_stale(consumer: str) -> None:
    client = await job_queue.redis()
    claimed = await client.xautoclaim(STREAM, GROUP, consumer, min_idle_time=60_000, start_id="0-0", count=10)
    messages = claimed[1] if claimed and len(claimed) > 1 else []
    for message_id, fields in messages:
        await process(message_id, fields)


async def run() -> None:
    await job_queue.ensure_group()
    consumer = f"{socket.gethostname()}-{id(asyncio.current_task())}"
    client = await job_queue.redis()
    logger.info("ORBIT worker started: %s", consumer)
    while True:
        await job_queue.promote_due_retries()
        await recover_stale(consumer)
        batches = await client.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=10, block=5000)
        for _, messages in batches:
            for message_id, fields in messages:
                await process(message_id, fields)


async def learning_scheduler() -> None:
    settings = job_queue.settings
    if not settings.production_learning_enabled:
        logger.info("Production learning scheduler is disabled")
        return
    logger.info("Production learning scheduler started: interval=%ss", settings.telemetry_collection_interval_seconds)
    while True:
        try:
            async with coordination.lock("production-learning-cycle", ttl_seconds=max(120, settings.telemetry_collection_interval_seconds)):
                result = await run_learning_cycle()
                logger.info("Production learning cycle completed: %s", result["run_id"])
        except CoordinationBusy:
            logger.info("Production learning cycle already owned by another worker")
        except Exception:
            logger.exception("Production learning cycle failed")
        await asyncio.sleep(settings.telemetry_collection_interval_seconds)


async def main() -> None:
    try:
        await asyncio.gather(run(), learning_scheduler())
    finally:
        await job_queue.close()
        await coordination.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
