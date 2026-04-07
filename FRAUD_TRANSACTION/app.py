import json
from urllib.error import URLError
from urllib.request import urlopen

from flask import Flask, jsonify, redirect, request

# ML imports
try:
    import numpy as np
except Exception as e:
    np = None
    print("NumPy not available (GAN endpoints disabled):", e)

try:
    from tensorflow.keras.models import load_model
except Exception as e:
    load_model = None
    print("TensorFlow not available (GAN endpoints disabled):", e)

app = Flask(__name__)

# -----------------------------
# URLs for other services
# -----------------------------
WEB1_URL = "http://127.0.0.1:5000"
WEB2_URL = "http://127.0.0.1:8000"

# -----------------------------
# Load Models
# -----------------------------
generator = None
discriminator = None
if load_model is not None:
    try:
        generator = load_model("generator.h5")
        discriminator = load_model("discriminator.h5")
        print("Models loaded successfully")
    except Exception as e:
        print("Error loading models:", e)


# -----------------------------
# Service Status Checker
# -----------------------------
def is_service_up(url):
    try:
        with urlopen(url, timeout=1.5) as response:
            return response.status < 500
    except URLError:
        return False
    except Exception:
        return False


# -----------------------------
# Home Page
# -----------------------------
@app.route("/")
def home():
    web1_up = is_service_up(WEB1_URL)
    web2_up = is_service_up(WEB2_URL)

    return f"""
    <html>
    <head>
        <title>Fraud + GAN Connector</title>
        <style>
            body {{ font-family: Segoe UI, sans-serif; margin: 30px; }}
            .ok {{ color: #0b7a0b; }}
            .down {{ color: #b00020; }}
            a {{ display: inline-block; margin-right: 12px; }}
        </style>
    </head>
    <body>
        <h2>Fraud + GAN Multi App Connector</h2>

        <h3>Service Status</h3>
        <p>Web 1 (5000): <strong class="{ 'ok' if web1_up else 'down' }">{ 'UP' if web1_up else 'DOWN' }</strong></p>
        <p>Web 2 (8000): <strong class="{ 'ok' if web2_up else 'down' }">{ 'UP' if web2_up else 'DOWN' }</strong></p>

        <h3>Navigation</h3>
        <p>
            <a href="/web1">Open Web 1</a>
            <a href="/web2">Open Web 2</a>
            <a href="/status">JSON Status</a>
        </p>

        <h3>GAN APIs</h3>
        <p>
            <a href="/generate">Generate Sample</a>
        </p>

        <p>Use POST /check for fraud detection</p>

        <pre>
Run services:
python "web 1/app.py"    # port 5000
python "web 2/app.py"    # port 8000
python "app.py"          # connector on port 9000
        </pre>
    </body>
    </html>
    """


# -----------------------------
# JSON Status API
# -----------------------------
@app.route("/status")
def status():
    data = {
        "web1": {"url": WEB1_URL, "up": is_service_up(WEB1_URL)},
        "web2": {"url": WEB2_URL, "up": is_service_up(WEB2_URL)},
        "models": {
            "generator_loaded": generator is not None,
            "discriminator_loaded": discriminator is not None
        }
    }
    return jsonify(data)


# -----------------------------
# Redirect Routes
# -----------------------------
@app.route("/web1")
@app.route("/web1/<path:subpath>")
def open_web1(subpath=""):
    target = WEB1_URL if not subpath else f"{WEB1_URL}/{subpath}"
    return redirect(target)


@app.route("/web2")
@app.route("/web2/<path:subpath>")
def open_web2(subpath=""):
    target = WEB2_URL if not subpath else f"{WEB2_URL}/{subpath}"
    return redirect(target)


# -----------------------------
# GAN: Generate Data
# -----------------------------
@app.route("/generate", methods=["GET"])
def generate():
    if generator is None:
        return jsonify({"error": "Generator model not loaded"}), 500
    if np is None:
        return jsonify({"error": "NumPy not installed"}), 500

    try:
        # Change noise dimension based on your model
        noise = np.random.normal(0, 1, (1, 100))

        generated_data = generator.predict(noise)
        return jsonify({
            "generated_sample": generated_data.tolist()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# GAN: Discriminator Check
# -----------------------------
@app.route("/check", methods=["POST"])
def check():
    if discriminator is None:
        return jsonify({"error": "Discriminator model not loaded"}), 500

    try:
        data = request.json.get("input")

        if data is None:
            return jsonify({"error": "No input data provided"}), 400

        input_data = np.array(data).reshape(1, -1)

        prediction = discriminator.predict(input_data)

        return jsonify({
            "prediction_score": float(prediction[0][0]),
            "result": "Fake" if prediction[0][0] < 0.5 else "Real"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Run App
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=9000, use_reloader=False)
