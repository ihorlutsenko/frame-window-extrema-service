from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from frame_window_service.analysis import AnalysisError, analyze_text


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def landing() -> str:
        return render_template("landing.html")

    def render_mode_page(*, mode: str, title: str, eyebrow: str, lead: str, api_path: str) -> str:
        return render_template(
            "index.html",
            page_title=title,
            eyebrow=eyebrow,
            lead=lead,
            api_path=api_path,
            mode=mode,
        )

    @app.get("/patent/")
    def patent_page() -> str:
        return render_mode_page(
            mode="patent",
            title="Патентна версія аналізу",
            eyebrow="Версія за патентом",
            lead=(
                "Ця сторінка використовує патентну логіку через ряди "
                "<code>A[i + 2<sup>k</sup>] - A[i]</code>, зміни знака і часові інтервали."
            ),
            api_path="/api/analyze/patent",
        )

    @app.get("/article/")
    def article_page() -> str:
        return render_mode_page(
            mode="article",
            title="Статейна версія аналізу",
            eyebrow="Версія за статтями",
            lead=(
                "Ця сторінка використовує статейну логіку: сусідні екстремуми, "
                "рекурсивне прорідження масиву та нові екстремуми на кожному рівні."
            ),
            api_path="/api/analyze/article",
        )

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    def handle_analyze(*, mode: str):
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
                mode=mode,
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

    @app.post("/api/analyze")
    def api_analyze():
        return handle_analyze(mode="patent")

    @app.post("/api/analyze/patent")
    def api_analyze_patent():
        return handle_analyze(mode="patent")

    @app.post("/api/analyze/article")
    def api_analyze_article():
        return handle_analyze(mode="article")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
