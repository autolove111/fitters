from backend_client import BackendClient


def collect_plan_context(days: int, authorization: str) -> dict:
    client = BackendClient(authorization)
    return {
        "goals": client.get("/api/goals"),
        "history": client.get("/api/stats/history", params={"days": days}),
        "weekly": client.get("/api/stats/weekly"),
        "today": client.get("/api/stats/today"),
        "workouts": client.get("/api/workouts"),
    }
