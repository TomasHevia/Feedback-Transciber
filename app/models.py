from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'receptionist' | 'supervisor'


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    session_label = db.Column(db.String(100))

    audio_filename = db.Column(db.String(255))
    transcription = db.Column(db.Text)
    transcription_score = db.Column(db.Float)

    category = db.Column(db.String(100))
    problem = db.Column(db.Text)
    applied_solution = db.Column(db.Text)
    suggested_action = db.Column(db.Text)
    ai_cost_usd = db.Column(db.Float)

    status = db.Column(db.String(50), default="pending")  # pending | processed | reviewed+
    processing_error = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "session_label": self.session_label,
            "audio_filename": self.audio_filename,
            "transcription": self.transcription,
            "transcription_score": self.transcription_score,
            "category": self.category,
            "problem": self.problem,
            "applied_solution": self.applied_solution,
            "suggested_action": self.suggested_action,
            "ai_cost_usd": self.ai_cost_usd,
            "status": self.status,
        }
