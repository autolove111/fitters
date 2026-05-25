import os

from flask import Flask, jsonify, request

from planner import build_today_workout_plan

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ai-service", "integrated": True})


@app.get("/")
def index():
    return jsonify(
        {
            "message": "AI service is running",
            "capabilities": ["today_workout_plan"],
        }
    )


@app.post("/plans/today-workout")
def today_workout_plan():
    internal_secret = request.headers.get("X-Internal-Secret", "")
    expected_secret = os.getenv("AI_SERVICE_SECRET", "fitters-ai-internal-secret")
    if internal_secret != expected_secret:
        return jsonify({"code": 403, "message": "Forbidden", "data": None}), 403

    authorization = request.headers.get("Authorization", "").strip()
    if not authorization:
        return jsonify({"code": 401, "message": "Missing authorization token", "data": None}), 401

    payload = request.get_json(silent=True) or {}
    try:
        plan = build_today_workout_plan(payload, authorization)
    except Exception as error:
        return jsonify({"code": 500, "message": str(error), "data": None}), 500
    return jsonify({"code": 0, "message": "ok", "data": plan})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
