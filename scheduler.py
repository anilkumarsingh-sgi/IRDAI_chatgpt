"""
IRDAI Compliance GPT – Background Scheduler
Runs periodic crawl + ingestion in a background thread on Streamlit Cloud.
"""

import os
import time
import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("irdai.scheduler")

# ─── Config ────────────────────────────────────────────────────────────────────
_ON_CLOUD = Path("/mount/src").exists()
_DATA_ROOT = Path("/tmp/irdai_data") if _ON_CLOUD else Path("data")
STATE_FILE = _DATA_ROOT / "scheduler_state.json"

# Default: scrape every 12 hours (in seconds)
UPDATE_INTERVAL = int(os.getenv("IRDAI_UPDATE_INTERVAL", str(12 * 3600)))

# ─── State Management ─────────────────────────────────────────────────────────
def _read_state() -> dict:
    """Read scheduler state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _write_state(state: dict):
    """Persist scheduler state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, default=str))


def get_last_update() -> dict:
    """Return last update info for display in the UI."""
    state = _read_state()
    return {
        "last_crawl":     state.get("last_crawl"),
        "last_ingestion": state.get("last_ingestion"),
        "last_summary":   state.get("last_summary", {}),
        "is_running":     state.get("is_running", False),
        "last_error":     state.get("last_error"),
    }


# ─── Background Update Logic ──────────────────────────────────────────────────
_lock = threading.Lock()
_scheduler_started = False


def _run_update():
    """Execute crawl + ingestion. Called by the background thread."""
    state = _read_state()
    state["is_running"] = True
    state["last_error"] = None
    _write_state(state)

    try:
        # --- Phase 1: Crawl ---
        logger.info("Scheduled crawl starting…")
        from crawler import run_crawl
        crawl_summary = run_crawl()
        state["last_crawl"] = datetime.now(timezone.utc).isoformat()
        state["crawl_summary"] = crawl_summary
        _write_state(state)
        logger.info("Scheduled crawl complete: %s", crawl_summary)

        # --- Phase 2: Ingest ---
        logger.info("Scheduled ingestion starting…")
        from ingestion import run_ingestion
        ingest_summary = run_ingestion()
        state["last_ingestion"] = datetime.now(timezone.utc).isoformat()
        state["last_summary"] = {
            "crawl": crawl_summary,
            "ingestion": ingest_summary,
        }
        _write_state(state)
        logger.info("Scheduled ingestion complete: %s", ingest_summary)

    except Exception as exc:
        logger.error("Scheduled update failed: %s", exc, exc_info=True)
        state["last_error"] = str(exc)
        _write_state(state)
    finally:
        state["is_running"] = False
        _write_state(state)


def _needs_update() -> bool:
    """Check if enough time has passed since the last update."""
    state = _read_state()
    last = state.get("last_crawl")
    if not last:
        return True  # Never crawled → need initial update
    try:
        last_dt = datetime.fromisoformat(last)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        return elapsed >= UPDATE_INTERVAL
    except Exception:
        return True


def _scheduler_loop():
    """Runs in a background daemon thread. Checks periodically and triggers updates."""
    # Small initial delay to let the app boot fully
    time.sleep(10)

    while True:
        try:
            if _needs_update():
                with _lock:
                    # Double-check after acquiring lock
                    if _needs_update():
                        logger.info("Update interval reached — starting scheduled update")
                        _run_update()
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)

        # Sleep for 5 minutes before checking again
        time.sleep(300)


def start_scheduler():
    """Start the background scheduler thread (idempotent — only starts once)."""
    global _scheduler_started
    if _scheduler_started:
        return

    _scheduler_started = True
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)

    thread = threading.Thread(target=_scheduler_loop, daemon=True, name="irdai-scheduler")
    thread.start()
    logger.info(
        "Background scheduler started (interval=%ds, cloud=%s)",
        UPDATE_INTERVAL, _ON_CLOUD,
    )


def trigger_manual_update():
    """Trigger an immediate update (non-blocking). Returns True if started."""
    state = _read_state()
    if state.get("is_running"):
        return False  # Already running

    thread = threading.Thread(target=_run_update, daemon=True, name="irdai-manual-update")
    thread.start()
    return True
