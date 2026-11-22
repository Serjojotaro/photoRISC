from __future__ import annotations

import logging
import signal
import time
from types import FrameType

from app import db
from app.config import Settings
from app.rendering import process_render_job
from app.thumbnails import process_thumbnail_job


logger = logging.getLogger(__name__)
_running = True


def _stop(_signum: int, _frame: FrameType | None) -> None:
    global _running
    _running = False


def process_next_job(settings: Settings) -> bool:
    job = db.claim_next_job(settings)
    if job is None:
        return False

    try:
        if job["kind"] == "thumbnail":
            process_thumbnail_job(settings, job)
        elif job["kind"] in {"preview", "render", "export"}:
            process_render_job(settings, job)
        else:
            raise ValueError(f"Unsupported job kind: {job['kind']}")
    except Exception:
        logger.exception(
            "Job failed: job_id=%s kind=%s asset_id=%s",
            job["id"],
            job["kind"],
            job["asset_id"],
        )
        db.fail_job(
            settings,
            job_id=job["id"],
            asset_id=job["asset_id"],
            error_code="render_failed",
        )
    return True


def run_worker(settings: Settings) -> None:
    settings.ensure_directories()
    db.init_db(settings)
    recovered = db.recover_interrupted_jobs(settings)
    if recovered:
        logger.info("Recovered %s interrupted job(s)", recovered)

    while _running:
        if not process_next_job(settings):
            time.sleep(settings.worker_poll_interval)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    run_worker(Settings.from_env())


if __name__ == "__main__":
    main()
