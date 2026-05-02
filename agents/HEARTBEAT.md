# Team Heartbeat

Agents periodically check this schedule for pending work.

## Process
1. Wake up every N minutes
2. Check schedule.json for tasks assigned to you
3. Execute pending tasks
4. Update status to completed/failed
5. Log results
