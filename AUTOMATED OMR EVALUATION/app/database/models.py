"""
Database models for OMR Evaluation System
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Student(Base):
    """Student information table"""
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    results = relationship("ExamResult", back_populates="student")


class Exam(Base):
    """Exam metadata table"""
    __tablename__ = "exams"
    
    id = Column(Integer, primary_key=True, index=True)
    exam_name = Column(String(100), nullable=False)
    exam_date = Column(DateTime, nullable=False)
    total_questions = Column(Integer, default=100)
    subjects = Column(JSON)  # Store subject names and question counts
    sheet_versions = Column(JSON)  # Store different sheet version info
    answer_keys = Column(JSON)  # Store answer keys for each version
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    results = relationship("ExamResult", back_populates="exam")
    audit_logs = relationship("AuditLog", back_populates="exam")


class ExamResult(Base):
    """Student exam results table"""
    __tablename__ = "exam_results"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    sheet_version = Column(String(10), nullable=False)
    
    # Subject-wise scores (0-20 each)
    subject_1_score = Column(Float, default=0.0)
    subject_2_score = Column(Float, default=0.0)
    subject_3_score = Column(Float, default=0.0)
    subject_4_score = Column(Float, default=0.0)
    subject_5_score = Column(Float, default=0.0)
    
    # Total score (0-100)
    total_score = Column(Float, default=0.0)
    
    # Response data
    student_responses = Column(JSON)  # Store all student responses
    correct_answers = Column(JSON)    # Store correct answers for comparison
    
    # Processing metadata
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    confidence_score = Column(Float, default=0.0)  # Overall confidence in detection
    flagged_questions = Column(JSON)  # Questions that need manual review
    
    # Timestamps
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="results")
    exam = relationship("Exam", back_populates="results")
    audit_logs = relationship("AuditLog", back_populates="result")


class AuditLog(Base):
    """Audit trail for OMR processing"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    result_id = Column(Integer, ForeignKey("exam_results.id"))
    
    # File information
    original_filename = Column(String(255), nullable=False)
    original_file_path = Column(String(500), nullable=False)
    processed_file_path = Column(String(500))
    overlay_file_path = Column(String(500))  # Path to processed image with overlays
    
    # Processing details
    processing_stage = Column(String(50))  # preprocessing, detection, scoring, etc.
    processing_details = Column(JSON)      # Detailed processing information
    error_details = Column(Text)           # Any errors encountered
    
    # Image metadata
    image_dimensions = Column(JSON)        # Original image dimensions
    detected_bubbles = Column(JSON)        # Bubble detection results
    skew_correction = Column(Float)        # Skew correction angle applied
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    exam = relationship("Exam", back_populates="audit_logs")
    result = relationship("ExamResult", back_populates="audit_logs")


class SystemConfig(Base):
    """System configuration table"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessingQueue(Base):
    """Queue for OMR processing jobs"""
    __tablename__ = "processing_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    student_identifier = Column(String(100))  # Student ID or name from sheet
    
    # Queue status
    status = Column(String(20), default="queued")  # queued, processing, completed, failed
    priority = Column(Integer, default=1)  # Higher number = higher priority
    
    # Processing details
    assigned_worker = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)