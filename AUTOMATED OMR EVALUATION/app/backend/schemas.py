"""
Pydantic schemas for API request/response models
"""
from pydantic import BaseModel, validator
from typing import Optional, Dict, List, Any
from datetime import datetime


# Student schemas
class StudentBase(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    batch: Optional[str] = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    batch: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Exam schemas
class ExamBase(BaseModel):
    exam_name: str
    exam_date: datetime
    total_questions: int = 100
    subjects: List[str] = ["Mathematics", "Physics", "Chemistry", "Biology", "English"]
    questions_per_subject: int = 20
    sheet_versions: List[str] = ["A", "B", "C", "D"]
    answer_keys: Dict[str, Dict[str, str]]  # version -> question_number -> correct_answer
    
    @validator('answer_keys')
    def validate_answer_keys(cls, v):
        """Validate answer keys format"""
        for version, answers in v.items():
            if len(answers) != 100:
                raise ValueError(f"Answer key for version {version} must have exactly 100 answers")
            for q_num, answer in answers.items():
                if answer not in ['A', 'B', 'C', 'D']:
                    raise ValueError(f"Invalid answer '{answer}' for question {q_num}")
        return v


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    exam_name: Optional[str] = None
    exam_date: Optional[datetime] = None
    answer_keys: Optional[Dict[str, Dict[str, str]]] = None


class ExamResponse(ExamBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Exam Result schemas
class ExamResultBase(BaseModel):
    sheet_version: str
    subject_1_score: int = 0
    subject_2_score: int = 0
    subject_3_score: int = 0
    subject_4_score: int = 0
    subject_5_score: int = 0
    total_score: int = 0
    student_responses: Dict[str, str] = {}
    correct_answers: Dict[str, str] = {}
    processing_status: str = "pending"
    confidence_score: float = 0.0
    flagged_questions: List[str] = []


class ExamResultCreate(ExamResultBase):
    student_id: Optional[int] = None
    exam_id: int


class ExamResultUpdate(BaseModel):
    processing_status: Optional[str] = None
    confidence_score: Optional[float] = None
    flagged_questions: Optional[List[str]] = None


class ExamResultResponse(ExamResultBase):
    id: int
    student_id: Optional[int] = None
    exam_id: int
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Related objects
    student: Optional[StudentResponse] = None
    exam: Optional[ExamResponse] = None
    
    class Config:
        from_attributes = True


# Processing Queue schemas
class ProcessingQueueResponse(BaseModel):
    id: int
    exam_id: Optional[int] = None
    file_path: str
    student_identifier: Optional[str] = None
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


# Audit Log schemas
class AuditLogResponse(BaseModel):
    id: int
    exam_id: Optional[int] = None
    result_id: Optional[int] = None
    original_filename: str
    original_file_path: str
    processed_file_path: Optional[str] = None
    overlay_file_path: Optional[str] = None
    processing_stage: str
    processing_details: Dict[str, Any] = {}
    image_dimensions: Optional[str] = None
    detected_bubbles: Optional[int] = None
    skew_correction: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# File upload schemas
class FileUploadResponse(BaseModel):
    message: str
    file_id: str
    queue_id: int
    status: str


class BatchUploadResponse(BaseModel):
    message: str
    files: List[Dict[str, Any]]
    status: str


# Statistics schemas
class SubjectStatistics(BaseModel):
    subject_name: str
    average_score: float
    max_score: int
    min_score: int
    pass_rate: float  # percentage of students scoring >= 50%


class ExamStatistics(BaseModel):
    exam_id: int
    exam_name: str
    total_students: int
    average_total_score: float
    max_total_score: int
    min_total_score: int
    overall_pass_rate: float
    subject_statistics: List[SubjectStatistics]
    score_distribution: Dict[str, int]  # score_range -> count
    processing_summary: Dict[str, int]  # status -> count


# Configuration schemas
class SystemConfigResponse(BaseModel):
    id: int
    config_key: str
    config_value: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    config_value: str


# Error response schemas
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = datetime.utcnow()


# Health check schema
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"
    database_status: str = "connected"
    processing_queue_size: int = 0


# Answer key validation schema
class AnswerKeyValidation(BaseModel):
    version: str
    answers: Dict[str, str]
    
    @validator('answers')
    def validate_answers(cls, v):
        """Validate answer format"""
        if len(v) != 100:
            raise ValueError("Answer key must have exactly 100 answers")
        
        for q_num, answer in v.items():
            try:
                q_int = int(q_num)
                if q_int < 1 or q_int > 100:
                    raise ValueError(f"Question number {q_num} out of range (1-100)")
            except ValueError:
                raise ValueError(f"Invalid question number format: {q_num}")
            
            if answer not in ['A', 'B', 'C', 'D']:
                raise ValueError(f"Invalid answer '{answer}' for question {q_num}")
        
        return v


# Bulk processing schemas
class BulkProcessingRequest(BaseModel):
    exam_id: int
    sheet_version: Optional[str] = None
    auto_detect_version: bool = True
    confidence_threshold: float = 0.8


class BulkProcessingResponse(BaseModel):
    message: str
    total_files: int
    queued_files: int
    skipped_files: int
    queue_ids: List[int]


# Review and flagging schemas
class ReviewRequest(BaseModel):
    result_id: int
    reviewer_notes: Optional[str] = None
    manual_corrections: Optional[Dict[str, str]] = None  # question_number -> corrected_answer
    approve: bool = True


class ReviewResponse(BaseModel):
    message: str
    result_id: int
    updated_score: Optional[int] = None
    changes_made: List[str] = []


# Export request schemas
class ExportRequest(BaseModel):
    exam_id: int
    format: str  # csv, excel, json
    include_flagged_only: bool = False
    include_student_details: bool = True
    include_answer_breakdown: bool = False


class ExportResponse(BaseModel):
    message: str
    download_url: str
    filename: str
    file_size: int
    expires_at: datetime