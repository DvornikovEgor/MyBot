"""
Веб-интерфейс MyBot AI: рисуете цифру мышкой — нейросеть (с нуля на NumPy!)
распознаёт её в реальном времени. Плюс опциональный чат с LLM-ассистентом.

Запуск:
    python -m src.server            # http://0.0.0.0:8000

Ассистент включается переменными окружения (см. src/llm.py):
    LLM_API_KEY=sk-... python -m src.server
"""
from __future__ import annotations

import os

import numpy as np
from flask import Flask, jsonify, render_template, request

from .llm import chat, is_configured
from .nn import Model
from .predict import model_side
from .preprocess import from_data_url, to_ascii

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.environ.get(
    "MODEL_PATH", os.path.join(_ROOT, "models", "digits_model.npz")
)
app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT, "templates"),
    static_folder=os.path.join(_ROOT, "static"),
)
_model: Model | None = None


def get_model() -> Model:
    global _model
    if _model is None:
        _model = Model.load(MODEL_PATH)
    return _model


# --------------------------------------------------------------------------- #
#  Страницы
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return render_template("index.html", llm_ready=is_configured())


# --------------------------------------------------------------------------- #
#  API: распознавание цифры
# --------------------------------------------------------------------------- #
@app.post("/api/predict")
def api_predict():
    data = request.get_json(silent=True) or {}
    image_url = data.get("image")
    if not image_url:
        return jsonify({"error": "нет поля image"}), 400
    model = get_model()
    try:
        x = from_data_url(image_url, side=model_side(model))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"не удалось разобрать картинку: {exc}"}), 400

    probs = model.predict_proba(x)[0]
    pred = int(probs.argmax())
    return jsonify({
        "prediction": pred,
        "probs": [round(float(p), 4) for p in probs],
        "confidence": round(float(probs[pred]), 4),
    })


# --------------------------------------------------------------------------- #
#  API: пример из датасета (показывает картинку обучающих данных)
# --------------------------------------------------------------------------- #
@app.get("/api/sample")
def api_sample():
    idx = request.args.get("idx", type=int)
    samples_path = os.path.join("data", "digits_samples.npz")
    if not os.path.exists(samples_path):
        # файла нет — соберём при первом обращении
        from .data import load_digits_data
        load_digits_data()
    samples = np.load(samples_path)
    images, labels = samples["images"], samples["y"]
    if idx is None or not (0 <= idx < len(images)):
        idx = int(np.random.default_rng().integers(len(images)))
    img = images[idx]  # [8, 8], 0..16
    x = img.reshape(1, -1) / 16.0
    probs = get_model().predict_proba(x)[0]
    # масштабируем 8×8 до 64×64 для показа (nearest, чтобы не мылить)
    import base64
    from io import BytesIO

    from PIL import Image

    im = Image.fromarray((img / 16.0 * 255).astype(np.uint8))
    im = im.resize((160, 160), Image.Resampling.NEAREST)
    buf = BytesIO()
    im.save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({
        "idx": int(idx),
        "true": int(labels[idx]),
        "image": "data:image/png;base64," + png_b64,
        "prediction": int(probs.argmax()),
        "probs": [round(float(p), 4) for p in probs],
    })


# --------------------------------------------------------------------------- #
#  API: LLM-ассистент (опционально, нужен ключ)
# --------------------------------------------------------------------------- #
@app.post("/api/chat")
def api_chat():
    if not is_configured():
        return jsonify({
            "error": "Ассистент не настроен. Задайте переменную окружения "
                     "LLM_API_KEY (или OPENAI_API_KEY) и перезапустите сервер."
        }), 503
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "нет сообщений"}), 400
    # держим историю в разумных пределах
    messages = messages[-12:]
    try:
        answer = chat(messages)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"answer": answer})


# --------------------------------------------------------------------------- #
#  API: ASCII-превью того, что видит модель (для отладки и интереса)
# --------------------------------------------------------------------------- #
@app.post("/api/see")
def api_see():
    data = request.get_json(silent=True) or {}
    if not data.get("image"):
        return jsonify({"error": "нет поля image"}), 400
    try:
        x = from_data_url(data["image"])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ascii": to_ascii(x[0], width=24)})


def main() -> None:
    port = int(os.environ.get("PORT", 8000))
    get_model()  # упадём сразу, если модель не обучена
    print(f"\n  MyBot AI запущен:  http://0.0.0.0:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
