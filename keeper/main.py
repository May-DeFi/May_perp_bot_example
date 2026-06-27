"""
main.py — keeper entry point.

Starts two concurrent tasks:
  1. WebSocket event listener (events.py) — reacts to hook events instantly
  2. Hourly scheduler (scheduler.py)      — pushes volume data, checks migration

Usage:
  pip install -r requirements.txt
  cp .env.example .env   # fill in values
  python main.py
"""

import asyncio
import logging
import sys

from events import listen_for_events
from scheduler import run_scheduler

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("keeper.log"),
    ],
)

log = logging.getLogger("main")


# ============================================================
# Entry point
# ============================================================

async def main() -> None:
    log.info("MAY9 keeper starting...")

    await asyncio.gather(
        listen_for_events(),
        run_scheduler(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Keeper stopped.")
