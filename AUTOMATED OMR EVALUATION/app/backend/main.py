"""
FastAPI backend for OMR Evaluation System
Provides REST API endpoints for file upload, processing, and data management
"""
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import shutil
import uuid
from datetime import datetime
import json
import pandas as pd
from io import BytesIO

from ..database.database import get_db, init_database
from ..database.models import Student, Exam, ExamResult, AuditLog, ProcessingQueue
from ..database.crud import StudentCRUD, ExamCRUD, ExamResultCRUD, AuditLogCRUD, ProcessingQueueCRUD
from ..core.omr_processor import OMRProcessor
from .schemas import *
from .utils import *

# Initialize FastAPI app
app = FastAPI(
    title="OMR Evaluation System API",
    description="Automated OMR sheet evaluation and scoring system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OMR processor
omr_processor = OMRProcessor()

# Create upload directory
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize database and load configurations on startup"""
    init_database()
    
    # Load default answer keys if available
    answer_keys_file = "config/answer_keys.json"
    if os.path.exists(answer_keys_file):
        omr_processor.load_answer_keys(answer_keys_file)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Student management endpoints
@app.post("/students/", response_model=StudentResponse)
async def create_student(student: StudentCreate, db: Session = Depends(get_db)):
    """Create a new student"""
    try:
        # Check if student ID already exists
        existing = StudentCRUD.get_student_by_student_id(db, student.student_id)
        if existing:
            raise HTTPException(status_code=400, detail="Student ID already exists")
        
        db_student = StudentCRUD.create_student(db, student.dict())
        return db_student
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/students/", response_model=List[StudentResponse])
async def get_students(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get list of students"""
    students = StudentCRUD.get_students(db, skip=skip, limit=limit)
    return students


@app.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int, db: Session = Depends(get_db)):
    """Get student by ID"""
    student = StudentCRUD.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


# Exam management endpoints
@app.post("/exams/", response_model=ExamResponse)
async def create_exam(exam: ExamCreate, db: Session = Depends(get_db)):
    """Create a new exam"""
    try:
        db_exam = ExamCRUD.create_exam(db, exam.dict())
        
        # Set answer keys in processor
        for version, answers in exam.answer_keys.items():
            omr_processor.set_answer_key(version, answers)
        
        return db_exam
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/exams/", response_model=List[ExamResponse])
async def get_exams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get list of exams"""
    exams = ExamCRUD.get_exams(db, skip=skip, limit=limit)
    return exams


@app.get("/exams/{exam_id}", response_model=ExamResponse)
async def get_exam(exam_id: int, db: Session = Depends(get_db)):
    """Get exam by ID"""
    exam = ExamCRUD.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@app.get("/exams/{exam_id}/statistics")
async def get_exam_statistics(exam_id: int, db: Session = Depends(get_db)):
    """Get statistical summary for an exam"""
    exam = ExamCRUD.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    stats = ExamResultCRUD.get_exam_statistics(db, exam_id)
    return stats


# File upload and processing endpoints
@app.post("/upload/single")
async def upload_single_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    exam_id: int = None,
    student_id: str = None,
    sheet_version: str = None,
    db: Session = Depends(get_db)
):
    """Upload and process a single OMR sheet"""
    try:
        # Validate file type
        if not is_valid_file_type(file.filename):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = get_file_extension(file.filename)
        filename = f"{file_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Add to processing queue
        queue_data = {
            "exam_id": exam_id,
            "file_path": file_path,
            "student_identifier": student_id,
            "status": "queued"
        }
        
        queue_item = ProcessingQueueCRUD.add_to_queue(db, queue_data)
        
        # Process in background
        background_tasks.add_task(
            process_omr_file,
            file_path,
            exam_id,
            student_id,
            sheet_version,
            queue_item.id,
            db
        )
        
        return {
            "message": "File uploaded successfully",
            "file_id": file_id,
            "queue_id": queue_item.id,
            "status": "queued"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/batch")
async def upload_batch_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    exam_id: int = None,
    db: Session = Depends(get_db)
):
    """Upload and process multiple OMR sheets"""
    try:
        uploaded_files = []
        
        for file in files:
            if not is_valid_file_type(file.filename):
                continue  # Skip invalid files
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_extension = get_file_extension(file.filename)
            filename = f"{file_id}{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            # Save uploaded file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Add to processing queue
            queue_data = {
                "exam_id": exam_id,
                "file_path": file_path,
                "student_identifier": None,
                "status": "queued"
            }
            
            queue_item = ProcessingQueueCRUD.add_to_queue(db, queue_data)
            
            uploaded_files.append({
                "file_id": file_id,
                "original_name": file.filename,
                "queue_id": queue_item.id
            })
            
            # Process in background
            background_tasks.add_task(
                process_omr_file,
                file_path,
                exam_id,
                None,
                None,
                queue_item.id,
                db
            )
        
        return {
            "message": f"Uploaded {len(uploaded_files)} files",
            "files": uploaded_files,
            "status": "queued"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Processing status endpoints
@app.get("/processing/queue")
async def get_processing_queue(db: Session = Depends(get_db)):
    """Get processing queue status"""
    status = ProcessingQueueCRUD.get_queue_status(db)
    return status


@app.get("/processing/queue/{queue_id}")
async def get_queue_item_status(queue_id: int, db: Session = Depends(get_db)):
    """Get status of a specific queue item"""
    item = ProcessingQueueCRUD.update_queue_item(db, queue_id, {})  # Just to get current status
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    return {
        "queue_id": item.id,
        "status": item.status,
        "created_at": item.created_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "error_message": item.error_message
    }


# Results endpoints
@app.get("/results/exam/{exam_id}", response_model=List[ExamResultResponse])
async def get_exam_results(exam_id: int, db: Session = Depends(get_db)):
    """Get all results for an exam"""
    results = ExamResultCRUD.get_results_by_exam(db, exam_id)
    return results


@app.get("/results/student/{student_id}", response_model=List[ExamResultResponse])
async def get_student_results(student_id: int, db: Session = Depends(get_db)):
    """Get all results for a student"""
    results = ExamResultCRUD.get_results_by_student(db, student_id)
    return results


@app.get("/results/flagged")
async def get_flagged_results(exam_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get results that need manual review"""
    results = ExamResultCRUD.get_flagged_results(db, exam_id)
    return results


@app.get("/results/{result_id}", response_model=ExamResultResponse)
async def get_result(result_id: int, db: Session = Depends(get_db)):
    """Get specific result by ID"""
    result = ExamResultCRUD.get_result(db, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


# Export endpoints
@app.get("/export/exam/{exam_id}/csv")
async def export_exam_results_csv(exam_id: int, db: Session = Depends(get_db)):
    """Export exam results as CSV"""
    try:
        results = ExamResultCRUD.get_results_by_exam(db, exam_id)
        if not results:
            raise HTTPException(status_code=404, detail="No results found")
        
        # Create DataFrame
        data = []
        for result in results:
            row = {
                "Student_ID": result.student.student_id if result.student else "Unknown",
                "Student_Name": result.student.name if result.student else "Unknown",
                "Sheet_Version": result.sheet_version,
                "Subject_1_Score": result.subject_1_score,
                "Subject_2_Score": result.subject_2_score,
                "Subject_3_Score": result.subject_3_score,
                "Subject_4_Score": result.subject_4_score,
                "Subject_5_Score": result.subject_5_score,
                "Total_Score": result.total_score,
                "Processing_Status": result.processing_status,
                "Confidence_Score": result.confidence_score,
                "Processed_At": result.processed_at
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Save to CSV
        csv_filename = f"exam_{exam_id}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = os.path.join(PROCESSED_DIR, csv_filename)
        df.to_csv(csv_path, index=False)
        
        return FileResponse(
            path=csv_path,
            filename=csv_filename,
            media_type="text/csv"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/exam/{exam_id}/excel")
async def export_exam_results_excel(exam_id: int, db: Session = Depends(get_db)):
    """Export exam results as Excel"""
    try:
        results = ExamResultCRUD.get_results_by_exam(db, exam_id)
        if not results:
            raise HTTPException(status_code=404, detail="No results found")
        
        # Create DataFrame
        data = []
        for result in results:
            row = {
                "Student_ID": result.student.student_id if result.student else "Unknown",
                "Student_Name": result.student.name if result.student else "Unknown",
                "Sheet_Version": result.sheet_version,
                "Subject_1_Score": result.subject_1_score,
                "Subject_2_Score": result.subject_2_score,
                "Subject_3_Score": result.subject_3_score,
                "Subject_4_Score": result.subject_4_score,
                "Subject_5_Score": result.subject_5_score,
                "Total_Score": result.total_score,
                "Processing_Status": result.processing_status,
                "Confidence_Score": result.confidence_score,
                "Processed_At": result.processed_at
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Save to Excel
        excel_filename = f"exam_{exam_id}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_path = os.path.join(PROCESSED_DIR, excel_filename)
        df.to_excel(excel_path, index=False)
        
        return FileResponse(
            path=excel_path,
            filename=excel_filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/exam/{exam_id}/json")
async def export_exam_results_json(exam_id: int, db: Session = Depends(get_db)):
    """Export exam results as JSON"""
    try:
        results = ExamResultCRUD.get_results_by_exam(db, exam_id)
        if not results:
            raise HTTPException(status_code=404, detail="No results found")
        
        # Convert to JSON-serializable format
        data = []
        for result in results:
            result_data = {
                "student_id": result.student.student_id if result.student else "Unknown",
                "student_name": result.student.name if result.student else "Unknown",
                "sheet_version": result.sheet_version,
                "scores": {
                    "subject_1": result.subject_1_score,
                    "subject_2": result.subject_2_score,
                    "subject_3": result.subject_3_score,
                    "subject_4": result.subject_4_score,
                    "subject_5": result.subject_5_score,
                    "total": result.total_score
                },
                "student_responses": result.student_responses,
                "correct_answers": result.correct_answers,
                "processing_status": result.processing_status,
                "confidence_score": result.confidence_score,
                "flagged_questions": result.flagged_questions,
                "processed_at": result.processed_at.isoformat() if result.processed_at else None
            }
            data.append(result_data)
        
        # Save to JSON file
        json_filename = f"exam_{exam_id}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path = os.path.join(PROCESSED_DIR, json_filename)
        
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return FileResponse(
            path=json_path,
            filename=json_filename,
            media_type="application/json"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# File serving endpoints
@app.get("/files/processed/{filename}")
async def get_processed_file(filename: str):
    """Serve processed image files"""
    file_path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


@app.get("/files/overlay/{filename}")
async def get_overlay_file(filename: str):
    """Serve overlay image files"""
    file_path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


# Background processing function
async def process_omr_file(file_path: str, exam_id: int, student_id: str, 
                          sheet_version: str, queue_id: int, db: Session):
    """Background task to process OMR file"""
    try:
        # Update queue status
        ProcessingQueueCRUD.update_queue_item(db, queue_id, {
            "status": "processing",
            "started_at": datetime.utcnow()
        })
        
        # Process the OMR sheet
        result = omr_processor.process_omr_sheet(file_path, sheet_version, student_id)
        
        if result["success"]:
            # Find or create student
            student = None
            if student_id:
                student = StudentCRUD.get_student_by_student_id(db, student_id)
                if not student:
                    student_data = {"student_id": student_id, "name": f"Student {student_id}"}
                    student = StudentCRUD.create_student(db, student_data)
            
            # Create exam result record
            result_data = {
                "student_id": student.id if student else None,
                "exam_id": exam_id,
                "sheet_version": result["sheet_version"],
                "subject_1_score": result["scores"].get("subject_scores", {}).get("Mathematics", 0),
                "subject_2_score": result["scores"].get("subject_scores", {}).get("Physics", 0),
                "subject_3_score": result["scores"].get("subject_scores", {}).get("Chemistry", 0),
                "subject_4_score": result["scores"].get("subject_scores", {}).get("Biology", 0),
                "subject_5_score": result["scores"].get("subject_scores", {}).get("English", 0),
                "total_score": result["scores"].get("total_score", 0),
                "student_responses": result["student_answers"],
                "correct_answers": omr_processor.answer_keys.get(result["sheet_version"], {}),
                "processing_status": "completed",
                "confidence_score": result["confidence_metrics"].get("average_confidence", 0),
                "flagged_questions": result["flagged_questions"],
                "processed_at": datetime.utcnow()
            }
            
            exam_result = ExamResultCRUD.create_result(db, result_data)
            
            # Create audit log
            audit_data = {
                "exam_id": exam_id,
                "result_id": exam_result.id,
                "original_filename": os.path.basename(file_path),
                "original_file_path": file_path,
                "processed_file_path": result["file_paths"]["processed"],
                "overlay_file_path": result["file_paths"]["overlay"],
                "processing_stage": "completed",
                "processing_details": result["processing_info"],
                "image_dimensions": result["processing_info"].get("original_size"),
                "detected_bubbles": result["bubble_detection"],
                "skew_correction": result["processing_info"].get("skew_angle", 0)
            }
            
            AuditLogCRUD.create_audit_log(db, audit_data)
            
            # Update queue status
            ProcessingQueueCRUD.update_queue_item(db, queue_id, {
                "status": "completed",
                "completed_at": datetime.utcnow()
            })
            
        else:
            # Update queue with error
            ProcessingQueueCRUD.update_queue_item(db, queue_id, {
                "status": "failed",
                "completed_at": datetime.utcnow(),
                "error_message": result["error_message"]
            })
            
    except Exception as e:
        # Update queue with error
        ProcessingQueueCRUD.update_queue_item(db, queue_id, {
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "error_message": str(e)
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)