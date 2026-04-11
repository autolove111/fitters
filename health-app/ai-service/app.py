from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Minimal mock knowledge. Replace with CV/LLM model call later.
FOOD_CALORIE_DB = {
    "salad": 220,
    "chicken breast": 280,
    "rice": 230,
    "noodles": 420,
    "apple": 95,
    "banana": 110,
    "egg": 80,
}


@app.get("/health")
def health():
    return jsonify({"success": True, "service": "ai-service"})


@app.post("/v1/calorie/recognize")
def recognize_calorie():
    body = request.get_json(silent=True) or {}

    # textHint/imageUrl are placeholders for future OCR or CV pipeline.
    text_hint = str(body.get("textHint", "")).strip().lower()
    image_url = str(body.get("imageUrl", "")).strip()

    food_name = "mixed meal"
    calories = 380

    for key, value in FOOD_CALORIE_DB.items():
        if key in text_hint:
            food_name = key
            calories = value
            break

    if image_url and food_name == "mixed meal":
        # Keep deterministic placeholder logic for local demos.
        calories = 360

    return jsonify({
        "success": True,
        "data": {
            "foodName": food_name,
            "estimatedCalories": calories,
            "confidence": 0.62,
            "source": "mock-rules"
        }
    })


@app.post("/v1/recommend/meal")
def recommend_meal():
    body = request.get_json(silent=True) or {}

    burned = float(body.get("todayCaloriesBurned", 0) or 0)
    sleep_score = int(body.get("lastSleepScore", 60) or 60)

    # Simple recommendation rules; easy to replace with LLM strategy layer.
    if sleep_score < 55:
        meal = "light congee + boiled egg + steamed vegetables"
        kcal = 330
        advice = "Low sleep score: keep meal light and reduce sugar."
    elif burned > 500:
        meal = "beef rice bowl + extra vegetables"
        kcal = 520
        advice = "High activity today: add quality protein."
    else:
        meal = "grilled chicken salad + corn"
        kcal = 420
        advice = "Balanced intake for steady fat loss."

    return jsonify({
        "success": True,
        "source": "ai-service-rules",
        "meal": meal,
        "estimatedCalories": kcal,
        "advice": advice
    })


if __name__ == "__main__":
    port = int(os.getenv("AI_SERVICE_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
