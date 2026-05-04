"""APScheduler — runs in-process inside the FastAPI app."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.workers.email_ingest import run_all as ingest_emails
from app.workers.email_categorize import categorize_batch
from app.workers.email_sender import send_approved
from app.workers.briefing_generate import generate_all_briefings
from app.email.thread_stitcher import recompute_all_open_loops

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def start():
    global _scheduler
    if _scheduler:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="Asia/Dubai")

    _scheduler.add_job(
        ingest_emails,
        IntervalTrigger(minutes=5),
        id="email_ingest",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        categorize_batch,
        IntervalTrigger(minutes=10),
        id="email_categorize",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        recompute_all_open_loops,
        CronTrigger(hour="*/1"),
        id="open_loop_sweep",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        send_approved,
        IntervalTrigger(minutes=2),
        id="email_sender",
        replace_existing=True,
        max_instances=1,
    )
    # Phase 1A.2 — daily morning brief at 04:30 Asia/Dubai (deterministic)
    _scheduler.add_job(
        generate_all_briefings,
        CronTrigger(hour=4, minute=30),
        id="briefing_generate",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started: email_ingest (5m), categorize (10m), sender (2m), "
        "open_loop_sweep (hourly), briefing_generate (daily 04:30 GST)"
    )
    return _scheduler


def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
