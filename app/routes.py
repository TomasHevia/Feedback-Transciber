import os
from flask import Blueprint, request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import Complaint
from app.services import transcribe_audio, analyze_complaint

main = Blueprint("main", __name__)
api = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "webm"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Frontend routes ────────────────────────────────────────────────────────────

@main.route("/")
def index():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("dashboard.html", complaints=complaints)


@main.route("/nueva-queja")
def nueva_queja():
    return render_template("index.html")


@main.route("/complaint/<int:complaint_id>")
def complaint_detail(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    return render_template("complaint_detail.html", complaint=complaint)


# ── API routes ─────────────────────────────────────────────────────────────────

@api.route("/upload", methods=["POST"])
def upload_audio():
    """Receives audio file, saves it, and triggers processing pipeline."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    file = request.files["audio"]
    if file.filename == "" or not _allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    session_label = request.form.get("session_label", "")
    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    complaint = Complaint(audio_filename=filename, session_label=session_label, status="pending")
    db.session.add(complaint)
    db.session.commit()

    try:
        transcription, t_cost = transcribe_audio(save_path)
        analysis, a_cost = analyze_complaint(transcription)

        complaint.transcription = transcription
        complaint.category = analysis.get("categoria", "otro")
        complaint.problem = analysis.get("problema", "")
        complaint.applied_solution = analysis.get("solucion_aplicada", "")
        complaint.suggested_action = analysis.get("accion_sugerida", "")
        complaint.ai_cost_usd = round(t_cost + a_cost, 6)
        complaint.status = "processed"
        db.session.commit()
    except Exception as err:
        complaint.status = "error"
        db.session.commit()
        return jsonify({"error": str(err), "complaint_id": complaint.id}), 500

    return jsonify(complaint.to_dict()), 201


@api.route("/complaints", methods=["GET"])
def list_complaints():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in complaints])


@api.route("/complaints/<int:complaint_id>", methods=["GET"])
def get_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    return jsonify(complaint.to_dict())


@api.route("/complaints/<int:complaint_id>/status", methods=["PATCH"])
def update_status(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ("pending", "processed", "reviewed"):
        return jsonify({"error": "Invalid status"}), 400
    complaint.status = new_status
    db.session.commit()
    return jsonify(complaint.to_dict())


@api.route("/stats", methods=["GET"])
def stats():
    from sqlalchemy import func
    total = Complaint.query.count()
    by_category = (
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category)
        .all()
    )
    return jsonify({
        "total": total,
        "by_category": {cat: count for cat, count in by_category},
    })
