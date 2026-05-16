from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from frame_window_service.analysis import AnalysisError, analyze_text


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/api/analyze")
    def api_analyze():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"error": "Не вибрано файл."}), 400

        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify({"error": "Файл має бути текстовим UTF-8."}), 400

        try:
            result = analyze_text(
                text,
                frame_size=request.form.get("frame_size"),
                frame_number=request.form.get("frame_number"),
                manual_start=request.form.get("manual_start"),
                manual_end=request.form.get("manual_end"),
                max_k=request.form.get("max_k"),
                filename=upload.filename,
            )
        except AnalysisError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
