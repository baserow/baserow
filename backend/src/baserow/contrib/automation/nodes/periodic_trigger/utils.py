from datetime import datetime


def get_periodic_trigger_payload(now: datetime):
    return {"triggered_at": now.isoformat()}
