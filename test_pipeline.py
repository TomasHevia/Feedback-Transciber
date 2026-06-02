import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.services import transcribe_audio, analyze_complaint
from app.models import Complaint

def run_test():
    app = create_app()
    with app.app_context():
        audio_path = os.path.join(app.config["UPLOAD_FOLDER"], "grabacion.webm")
        if not os.path.exists(audio_path):
            print(f"Error: Archivo de audio de prueba no encontrado en: {audio_path}")
            sys.exit(1)

        print("--- Iniciando prueba del pipeline completo ---")
        print(f"Archivo de audio: {audio_path}")

        filename = os.path.basename(audio_path)
        complaint = Complaint(
            audio_filename=filename,
            session_label="Prueba automatica de pipeline",
            status="pending"
        )
        db.session.add(complaint)
        db.session.commit()
        print(f"Registro creado en base de datos. ID asignado: #{complaint.id}")

        try:
            # Transcripcion 
            print("Transcribiendo audio con Gemini...")
            transcription, t_cost = transcribe_audio(audio_path)
            complaint.transcription = transcription
            db.session.commit()
            print("Transcripcion exitosa.")

            #Analisis de queja 
            print("Analizando texto con Gemini...")
            analysis, a_cost = analyze_complaint(transcription)

 
            complaint.category = analysis.get("categoria", "otro")
            complaint.problem = analysis.get("problema", "")
            complaint.applied_solution = analysis.get("solucion_aplicada", "")
            complaint.suggested_action = analysis.get("accion_sugerida", "")
            complaint.ai_cost_usd = round(t_cost + a_cost, 6)
            complaint.status = "processed"
            db.session.commit()

            print("\nPrueba completada con exito!")
            print(f"ID de queja en BD: #{complaint.id}")
            print(f"Transcripcion: {complaint.transcription}")
            print(f"Categoria: {complaint.category}")
            print(f"Problema: {complaint.problem}")
            print(f"Solucion Aplicada: {complaint.applied_solution}")
            print(f"Accion Sugerida: {complaint.suggested_action}")
            print(f"Costo total del analisis: ${complaint.ai_cost_usd} USD")

        except Exception as e:
            complaint.status = "error"
            complaint.processing_error = str(e)
            db.session.commit()
            print(f"\nError durante el pipeline: {e}")
            print(f"El estado de la queja #{complaint.id} se actualizo a 'error'.")
            sys.exit(1)


run_test()
