from flask import Flask, jsonify

app = Flask(__name__)


@app.get('/health')
def health():
    return jsonify({"status": "ok", "service": "ai-service", "integrated": False})


@app.get('/')
def index():
    return jsonify({
        "message": "AI service is running but not integrated yet",
        "next_step": "connect backend to this service when needed"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
