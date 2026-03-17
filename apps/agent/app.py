import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.shared import config
from apps.agent.routes import router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_scheduler = None


def _scheduled_scan_job():
    """Job del scheduler: executa scan diari."""
    try:
        logger.info("daily_scan_triggered source=scheduler")
        from packages.runtime.scan_runner import run_daily_scan
        result = run_daily_scan()
        logger.info(
            "scheduled_scan_completed new_signals=%s settled=%s errors=%s",
            len(result.get("new_signals", [])),
            len(result.get("settled_trades", [])),
            len(result.get("errors", [])),
        )
    except Exception as e:
        logger.exception("scheduled_scan_failed error=%s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: scheduler. Shutdown: aturar scheduler."""
    global _scheduler
    host = "0.0.0.0"
    port = 8090
    logger.info("agent_started host=%s port=%s mode=paper assets=%s", host, port, ",".join(config.ASSETS))

    if config.SCHEDULER_ENABLED:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _scheduled_scan_job,
            CronTrigger(hour=config.SCHEDULER_HOUR_UTC, minute=0),
            id="daily_scan",
        )
        _scheduler.start()
        next_run = _scheduler.get_job("daily_scan").next_run_time
        next_utc = next_run.isoformat() if next_run else "unknown"
        logger.info(
            "daily_scheduler_registered next_run_utc=%s schedule=post_close_d1 hour_utc=%s",
            next_utc,
            config.SCHEDULER_HOUR_UTC,
        )
    else:
        logger.info("daily_scheduler_disabled SCHEDULER_ENABLED=false")

    yield

    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("daily_scheduler_stopped")


app = FastAPI(title="TradingAgent Paper Probe", version="0.1.0", lifespan=lifespan)
app.include_router(router)
