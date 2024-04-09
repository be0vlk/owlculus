"""
Contains the SQLAlchemy models for the application.
The models are used to define the structure of the database tables.
Do not alter unless you really know what you are doing.
"""

from utils.db import db
from datetime import datetime

# Association tables for many-to-many relationships
case_evidence_association = db.Table(
    "case_evidence",
    db.Column("case_id", db.Integer, db.ForeignKey("cases.id"), primary_key=True),
    db.Column(
        "evidence_id", db.Integer, db.ForeignKey("evidence.id"), primary_key=True
    ),
)

user_case_association = db.Table(
    "user_cases",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("case_id", db.Integer, db.ForeignKey("cases.id"), primary_key=True),
)


class Invitation(db.Model):
    __tablename__ = "invitations"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    role = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    def serialize(self):
        return {
            "id": self.id,
            "token": self.token,
            "role": self.role,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": self.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "used": self.used,
        }


class Client(db.Model):
    __tablename__ = "clients"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=True)
    email = db.Column(db.String(128), unique=False, nullable=True)
    phone = db.Column(db.String(128), unique=False, nullable=True)
    cases = db.relationship("Case", backref="client", lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    def serialize(self):
        created_at = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        updated_at = self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": created_at,
            "updated_at": updated_at,
        }


class Case(db.Model):
    __tablename__ = "cases"
    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=True, index=True
    )
    case_type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(64), nullable=True)
    created_by = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    evidence = db.relationship(
        "Evidence",
        secondary=case_evidence_association,
        backref=db.backref("cases", lazy=True),
    )
    authorized_users = db.relationship(
        "User",
        secondary=user_case_association,
        backref=db.backref("authorized_cases", lazy=True),
        overlaps="authorized_cases,authorized_users",
    )
    archived = db.Column(db.Boolean, nullable=False, default=False)

    def serialize(self):
        created_at = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        updated_at = (
            self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        )
        evidence_list = [
            self.serialize_evidence(evidence) for evidence in self.evidence
        ]

        authorized_user_list = [user.id for user in self.authorized_users]

        return {
            "id": self.id,
            "authorized_users": authorized_user_list,
            "case_number": self.case_number,
            "client_id": self.client_id,
            "case_type": self.case_type,
            "description": self.description,
            "evidence": evidence_list,
            "created_at": created_at,
            "created_by": self.created_by,
            "updated_at": updated_at,
            "archived": self.archived,
        }

    @staticmethod
    def serialize_evidence(evidence):
        """Serialize an evidence instance into a dictionary."""
        return {
            "id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "value": evidence.value,
            "description": evidence.description,
            "created_at": evidence.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    logged_in_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    last_password_change = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    role = db.Column(db.String(32), unique=False, nullable=False, default="analyst")
    active = db.Column(db.Boolean, nullable=True, default=True)
    cases = db.relationship(
        "Case",
        secondary=user_case_association,
        backref=db.backref("associated_users", lazy=True),
        overlaps="authorized_cases,authorized_users",
        cascade="all, delete",
    )

    def serialize(self):
        created_at = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        logged_in_at = (
            self.logged_in_at.strftime("%Y-%m-%d %H:%M:%S")
            if self.logged_in_at
            else None
        )
        updated_at = (
            self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        )
        last_password_change = (
            self.last_password_change.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_password_change
            else None
        )

        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": created_at,
            "logged_in_at": logged_in_at,
            "last_password_change": last_password_change,
            "updated_at": updated_at,
            "active": self.active,
        }


class Evidence(db.Model):
    __tablename__ = "evidence"
    id = db.Column(db.Integer, primary_key=True)
    evidence_type = db.Column(
        db.String(64), nullable=False
    )  # e.g., 'phone_number', 'email', 'name'
    value = db.Column(
        db.String(256), nullable=False
    )  # The actual evidence, e.g., the phone number or email address
    description = db.Column(db.String(256), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "evidence_type": self.evidence_type,
            "value": self.value,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (
                self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.updated_at
                else None
            ),
        }


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    case = db.relationship(
        "Case", backref=db.backref("notes", lazy=True, cascade="delete, delete-orphan")
    )

    def serialize(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "category": self.category,
            "data": self.data,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (
                self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.updated_at
                else None
            ),
        }
