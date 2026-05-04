import json
import os
import time
import threading
import logging

logger = logging.getLogger("cococat.scheduler")

SCHEDULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents", "schedule.json")

def load_schedule():
    if not os.path.exists(SCHEDULE_PATH):
        return {"tasks": []}
    with open(SCHEDULE_PATH, "r") as f:
        return json.load(f)

def _scheduler_loop():
    while True:
        time.sleep(30)
        try:
            schedule = load_schedule()
            for task in schedule.get("tasks", []):
                if task.get("status") == "pending":
                    logger.info(f"Scheduler: executing task {task.get('id')}")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")

def start_scheduler():
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
    logger.info("Scheduler started")
