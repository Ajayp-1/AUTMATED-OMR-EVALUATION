"""
CRUD operations for database models
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from .models import Student, Exam, ExamResult, AuditLog, SystemConfig, ProcessingQueue


class StudentCRUD:
    @staticmethod
    def create_student(db: Session, student_data: Dict[str, Any]) -> Student:
        """Create a new student"""
        student = Student(**student_data)
        db.add(student)
        db.commit()
        db.refresh(student)
        return student
    
    @staticmethod
    def get_student(db: Session, student_id: int) -> Optional[Student]:
        """Get student by ID"""
        return db.query(Student).filter(Student.id == student_id).first()
    
    @staticmethod
    def get_student_by_student_id(db: Session, student_id: str) -> Optional[Student]:
        """Get student by student ID"""
        return db.query(Student).filter(Student.student_id == student_id).first()
    
    @staticmethod
    def get_students(db: Session, skip: int = 0, limit: int = 100) -> List[Student]:
        """Get list of students"""
        return db.query(Student).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_student(db: Session, student_id: int, student_data: Dict[str, Any]) -> Optional[Student]:
        """Update student information"""
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            for key, value in student_data.items():
                setattr(student, key, value)
            student.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(student)
        return student


class ExamCRUD:
    @staticmethod
    def create_exam(db: Session, exam_data: Dict[str, Any]) -> Exam:
        """Create a new exam"""
        exam = Exam(**exam_data)
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return exam
    
    @staticmethod
    def get_exam(db: Session, exam_id: int) -> Optional[Exam]:
        """Get exam by ID"""
        return db.query(Exam).filter(Exam.id == exam_id).first()
    
    @staticmethod
    def get_exams(db: Session, skip: int = 0, limit: int = 100) -> List[Exam]:
        """Get list of exams"""
        return db.query(Exam).order_by(desc(Exam.exam_date)).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_exam(db: Session, exam_id: int, exam_data: Dict[str, Any]) -> Optional[Exam]:
        """Update exam information"""
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if exam:
            for key, value in exam_data.items():
                setattr(exam, key, value)
            exam.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(exam)
        return exam


class ExamResultCRUD:
    @staticmethod
    def create_result(db: Session, result_data: Dict[str, Any]) -> ExamResult:
        """Create a new exam result"""
        result = ExamResult(**result_data)
        db.add(result)
        db.commit()
        db.refresh(result)
        return result
    
    @staticmethod
    def get_result(db: Session, result_id: int) -> Optional[ExamResult]:
        """Get result by ID"""
        return db.query(ExamResult).filter(ExamResult.id == result_id).first()
    
    @staticmethod
    def get_results_by_exam(db: Session, exam_id: int) -> List[ExamResult]:
        """Get all results for an exam"""
        return db.query(ExamResult).filter(ExamResult.exam_id == exam_id).all()
    
    @staticmethod
    def get_results_by_student(db: Session, student_id: int) -> List[ExamResult]:
        """Get all results for a student"""
        return db.query(ExamResult).filter(ExamResult.student_id == student_id).all()
    
    @staticmethod
    def get_flagged_results(db: Session, exam_id: Optional[int] = None) -> List[ExamResult]:
        """Get results that need manual review"""
        query = db.query(ExamResult).filter(ExamResult.flagged_questions.isnot(None))
        if exam_id:
            query = query.filter(ExamResult.exam_id == exam_id)
        return query.all()
    
    @staticmethod
    def update_result(db: Session, result_id: int, result_data: Dict[str, Any]) -> Optional[ExamResult]:
        """Update exam result"""
        result = db.query(ExamResult).filter(ExamResult.id == result_id).first()
        if result:
            for key, value in result_data.items():
                setattr(result, key, value)
            result.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(result)
        return result
    
    @staticmethod
    def get_exam_statistics(db: Session, exam_id: int) -> Dict[str, Any]:
        """Get statistical summary for an exam"""
        results = db.query(ExamResult).filter(ExamResult.exam_id == exam_id).all()
        
        if not results:
            return {}
        
        total_students = len(results)
        scores = [r.total_score for r in results]
        
        stats = {
            "total_students": total_students,
            "average_score": sum(scores) / total_students,
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "pass_rate": len([s for s in scores if s >= 40]) / total_students * 100,  # Assuming 40% pass mark
            "subject_averages": {
                "subject_1": sum([r.subject_1_score for r in results]) / total_students,
                "subject_2": sum([r.subject_2_score for r in results]) / total_students,
                "subject_3": sum([r.subject_3_score for r in results]) / total_students,
                "subject_4": sum([r.subject_4_score for r in results]) / total_students,
                "subject_5": sum([r.subject_5_score for r in results]) / total_students,
            }
        }
        
        return stats


class AuditLogCRUD:
    @staticmethod
    def create_audit_log(db: Session, audit_data: Dict[str, Any]) -> AuditLog:
        """Create a new audit log entry"""
        audit_log = AuditLog(**audit_data)
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log
    
    @staticmethod
    def get_audit_logs(db: Session, exam_id: Optional[int] = None, 
                      result_id: Optional[int] = None) -> List[AuditLog]:
        """Get audit logs with optional filtering"""
        query = db.query(AuditLog)
        if exam_id:
            query = query.filter(AuditLog.exam_id == exam_id)
        if result_id:
            query = query.filter(AuditLog.result_id == result_id)
        return query.order_by(desc(AuditLog.created_at)).all()


class SystemConfigCRUD:
    @staticmethod
    def get_config(db: Session, config_key: str) -> Optional[SystemConfig]:
        """Get system configuration by key"""
        return db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()
    
    @staticmethod
    def set_config(db: Session, config_key: str, config_value: str, 
                   description: str = "") -> SystemConfig:
        """Set system configuration"""
        config = db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()
        if config:
            config.config_value = config_value
            config.description = description
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                config_key=config_key,
                config_value=config_value,
                description=description
            )
            db.add(config)
        
        db.commit()
        db.refresh(config)
        return config
    
    @staticmethod
    def get_all_configs(db: Session) -> List[SystemConfig]:
        """Get all system configurations"""
        return db.query(SystemConfig).all()


class ProcessingQueueCRUD:
    @staticmethod
    def add_to_queue(db: Session, queue_data: Dict[str, Any]) -> ProcessingQueue:
        """Add item to processing queue"""
        queue_item = ProcessingQueue(**queue_data)
        db.add(queue_item)
        db.commit()
        db.refresh(queue_item)
        return queue_item
    
    @staticmethod
    def get_next_item(db: Session) -> Optional[ProcessingQueue]:
        """Get next item from queue for processing"""
        return db.query(ProcessingQueue).filter(
            ProcessingQueue.status == "queued"
        ).order_by(desc(ProcessingQueue.priority), ProcessingQueue.created_at).first()
    
    @staticmethod
    def update_queue_item(db: Session, item_id: int, 
                         update_data: Dict[str, Any]) -> Optional[ProcessingQueue]:
        """Update queue item status"""
        item = db.query(ProcessingQueue).filter(ProcessingQueue.id == item_id).first()
        if item:
            for key, value in update_data.items():
                setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(item)
        return item
    
    @staticmethod
    def get_queue_status(db: Session) -> Dict[str, int]:
        """Get queue status summary"""
        from sqlalchemy import func
        
        status_counts = db.query(
            ProcessingQueue.status,
            func.count(ProcessingQueue.id)
        ).group_by(ProcessingQueue.status).all()
        
        return {status: count for status, count in status_counts}