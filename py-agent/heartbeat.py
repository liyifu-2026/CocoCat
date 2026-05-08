"""Heartbeat — deprecated.

All tasks (including recurring) are now delivered through the central
DispatchEngine via stdin JSON-RPC. The file-based schedule.json is no
longer used. This file is kept as a stub for backwards compatibility.
"""
def start_heartbeat(*args, **kwargs):
    pass

def get_pending_tasks(*args, **kwargs):
    return []

def update_task_status(*args, **kwargs):
    pass
