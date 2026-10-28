from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database.database import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    google_connected = Column(Boolean, default=False, nullable=True)
    google_sub = Column(String(255), nullable=True, index=True)
    google_email = Column(String(255), nullable=True)
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SessionRecord(Base):
    __tablename__ = 'sessions'
    
    session_id = Column(String(255), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    status = Column(String(50), default="active")
    meeting_link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TranscriptChunk(Base):
    __tablename__ = 'transcripts'
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey('sessions.session_id', ondelete='CASCADE'), index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SessionRequirement(Base):
    __tablename__ = 'requirements'
    
    session_id = Column(String(255), ForeignKey('sessions.session_id', ondelete='CASCADE'), primary_key=True)
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class GeneratedProject(Base):
    __tablename__ = 'generated_projects'
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey('sessions.session_id', ondelete='CASCADE'), index=True)
    project_name = Column(String(255), nullable=False)
    project_path = Column(String(500), nullable=False)
    file_tree = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MeetingSummary(Base):
    __tablename__ = 'summaries'
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey('sessions.session_id', ondelete='CASCADE'), index=True)
    summary_text = Column(Text, nullable=False)
    key_points = Column(JSON, nullable=True)
    action_items = Column(JSON, nullable=True)
    decisions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
