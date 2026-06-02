import os
import uuid
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename
from app import db
from app.models import Complaint
from app.services import transcribe_audio, analyze_complaint, generate_report
from app.auth import login_required, roles_expected
import traceback

main = Blueprint("main", __name__)
api = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "webm"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Frontend routes ────────────────────────────────────────────────────────────

@main.route("/")
@login_required
@roles_expected("supervisor")
def index():
    complaints = Complaint.query.filter(Complaint.status != "error").order_by(Complaint.created_at.desc()).all()
    return render_template("dashboard.html", complaints=complaints)


@main.route("/nueva-queja")
@login_required
@roles_expected("receptionist", "supervisor")
def nueva_queja():
    return render_template("index.html")


@main.route("/complaint/<int:complaint_id>")
@login_required
@roles_expected("supervisor")
def complaint_detail(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    return render_template("complaint_detail.html", complaint=complaint)


@main.route("/report", methods=["GET", "POST"])
@login_required
@roles_expected("supervisor")
def report():
    from datetime import datetime, timedelta

    categories = [
        "ruido","limpieza","facturacion","temperatura","mantenimiento","internet_wifi",
        "television","electricidad","agua","plomeria","check_in","check_out","reserva",
        "sobreventa","habitacion_incorrecta","llaves_acceso","equipaje","estacionamiento",
        "transporte","restaurante","desayuno","room_service","servicio_no_atendido",
        "personal","seguridad","cobro_indebido","reembolso","amenidades","piscina",
        "gimnasio","accesibilidad","otro",
    ]

    if request.method == "GET":
        return render_template("report.html", categories=categories)

    selected_categories = request.form.getlist("category")
    status     = request.form.get("status", "").strip()
    date_from  = request.form.get("date_from", "").strip()
    date_to    = request.form.get("date_to", "").strip()

    query = Complaint.query.filter(Complaint.status != "error")
    if selected_categories:
        query = query.filter(Complaint.category.in_(selected_categories))
    if status:
        query = query.filter(Complaint.status == status)
    if date_from:
        query = query.filter(Complaint.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        query = query.filter(Complaint.created_at < datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))

    complaints = query.order_by(Complaint.created_at.asc()).limit(50).all()

    if not complaints:
        return render_template("report.html", categories=categories,
                               error="No hay quejas que coincidan con los filtros seleccionados.")

    try:
        report_data, cost = generate_report(complaints)
    except Exception as e:
        return render_template("report.html", categories=categories,
                               error=f"Error al generar el reporte con Gemini: {e}")

    filters_summary = {
        "categoria": ", ".join(selected_categories) if selected_categories else "Todas",
        "estado": status,
        "desde": date_from, "hasta": date_to,
    }
    return render_template("report.html", categories=categories,
                           report=report_data, complaints=complaints,
                           filters_summary=filters_summary,
                           selected_categories=selected_categories,
                           generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
                           cost=round(cost, 4))


@main.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# ── API routes ─────────────────────────────────────────────────────────────────

@api.route("/upload", methods=["POST"])
@login_required
@roles_expected("receptionist", "supervisor")
def upload_audio():
    """Receives audio file, saves it, and triggers processing pipeline."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    file = request.files["audio"]
    if file.filename == "" or not _allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    session_label = request.form.get("session_label", "")
    raw_name = secure_filename(file.filename)
    stem, ext = os.path.splitext(raw_name)
    filename = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    complaint = Complaint(audio_filename=filename, session_label=session_label, status="pending")
    db.session.add(complaint)
    db.session.commit()

    try:
        transcription, t_cost = transcribe_audio(save_path)
        
        
        complaint.transcription = transcription
        db.session.commit()

        analysis, a_cost = analyze_complaint(transcription)

        complaint.category = analysis.get("categoria", "otro")
        complaint.problem = analysis.get("problema", "")
        complaint.applied_solution = analysis.get("solucion_aplicada", "")
        complaint.suggested_action = analysis.get("accion_sugerida", "")
        complaint.ai_cost_usd = round(t_cost + a_cost, 6)
        complaint.status = "processed"
        db.session.commit()
    except Exception as err:
        traceback.print_exc()
        complaint.status = "error"
        complaint.processing_error = str(err)
        db.session.commit()
        return jsonify({"error": str(err), "complaint_id": complaint.id}), 500

    return jsonify(complaint.to_dict()), 201


@api.route("/complaints", methods=["GET"])
@login_required
@roles_expected("supervisor")
def list_complaints():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in complaints])


@api.route("/complaints/<int:complaint_id>", methods=["GET"])
@login_required
@roles_expected("supervisor")
def get_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    return jsonify(complaint.to_dict())


@api.route("/complaints/<int:complaint_id>/status", methods=["PATCH"])
@login_required
@roles_expected("supervisor")
def update_status(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ("pending", "processed", "reviewed"):
        return jsonify({"error": "Invalid status"}), 400
    complaint.status = new_status
    applied_solution = data.get("applied_solution")
    if applied_solution is not None:
        complaint.applied_solution = applied_solution
    db.session.commit()
    return jsonify(complaint.to_dict())


@api.route("/complaints/<int:complaint_id>", methods=["DELETE"])
@login_required
@roles_expected("supervisor", "receptionist")
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.status not in ("error", "pending"):
        return jsonify({"error": "Solo se pueden eliminar quejas con error o pendientes"}), 400
    if complaint.audio_filename:
        audio_path = os.path.join(current_app.config["UPLOAD_FOLDER"], complaint.audio_filename)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    db.session.delete(complaint)
    db.session.commit()
    return jsonify({"ok": True}), 200


@api.route("/complaints/<int:complaint_id>/analyze-manual", methods=["POST"])
@login_required
@roles_expected("supervisor", "receptionist")
def analyze_manual(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.status not in ("error", "pending"):
        return jsonify({"error": "Estado inválido para análisis manual"}), 400
    data_in = request.get_json(silent=True) or {}
    transcription = data_in.get("transcription", "").strip()
    if not transcription:
        return jsonify({"error": "La transcripción no puede estar vacía"}), 400

    complaint.transcription = transcription
    complaint.status = "pending"
    complaint.processing_error = None
    db.session.commit()

    try:
        analysis, a_cost = analyze_complaint(transcription)
        complaint.category = analysis.get("categoria", "otro")
        complaint.problem = analysis.get("problema", "")
        complaint.applied_solution = analysis.get("solucion_aplicada", "")
        complaint.suggested_action = analysis.get("accion_sugerida", "")
        complaint.ai_cost_usd = round(a_cost, 6)
        complaint.status = "processed"
        db.session.commit()
    except Exception as err:
        traceback.print_exc()
        complaint.status = "error"
        complaint.processing_error = str(err)
        db.session.commit()
        return jsonify({"error": str(err), "complaint_id": complaint.id}), 500

    return jsonify(complaint.to_dict()), 200


@api.route("/complaints/<int:complaint_id>/retry", methods=["POST"])
@login_required
@roles_expected("supervisor", "receptionist")
def retry_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.status != "error":
        return jsonify({"error": "Solo se pueden reintentar quejas con error"}), 400
    if not complaint.audio_filename:
        return jsonify({"error": "No hay archivo de audio para reprocesar"}), 400

    audio_path = os.path.join(current_app.config["UPLOAD_FOLDER"], complaint.audio_filename)
    if not os.path.exists(audio_path):
        return jsonify({"error": "Archivo de audio no encontrado"}), 404

    complaint.status = "pending"
    complaint.processing_error = None
    db.session.commit()

    try:
        transcription, t_cost = transcribe_audio(audio_path)
        complaint.transcription = transcription
        db.session.commit()

        analysis, a_cost = analyze_complaint(transcription)
        complaint.category = analysis.get("categoria", "otro")
        complaint.problem = analysis.get("problema", "")
        complaint.applied_solution = analysis.get("solucion_aplicada", "")
        complaint.suggested_action = analysis.get("accion_sugerida", "")
        complaint.ai_cost_usd = round(t_cost + a_cost, 6)
        complaint.status = "processed"
        db.session.commit()
    except Exception as err:
        traceback.print_exc()
        complaint.status = "error"
        complaint.processing_error = str(err)
        db.session.commit()
        return jsonify({"error": str(err), "complaint_id": complaint.id}), 500

    return jsonify(complaint.to_dict()), 200


@api.route("/stats", methods=["GET"])
@login_required
@roles_expected("supervisor")
def stats():
    from sqlalchemy import func
    total = Complaint.query.filter(Complaint.status != "error").count()
    by_category = (
        db.session.query(Complaint.category, func.count(Complaint.id))
        .filter(Complaint.status != "error")
        .group_by(Complaint.category)
        .all()
    )
    unresolved_by_category = (
        db.session.query(Complaint.category, func.count(Complaint.id))
        .filter(Complaint.status.in_(["pending", "processed"]))
        .group_by(Complaint.category)
        .all()
    )
    return jsonify({
        "total": total,
        "by_category": {(cat or "sin_categoria"): count for cat, count in by_category},
        "unresolved_by_category": {(cat or "sin_categoria"): count for cat, count in unresolved_by_category},
    })
