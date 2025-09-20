"""
Utility functions for the FastAPI backend
"""
import os
import mimetypes
from typing import List, Dict, Any, Optional
import hashlib
from datetime import datetime, timedelta
import json
import cv2
import numpy as np
from PIL import Image


# File handling utilities
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def is_valid_file_type(filename: str) -> bool:
    """Check if file type is allowed"""
    if not filename:
        return False
    
    ext = get_file_extension(filename).lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return os.path.splitext(filename)[1].lower()


def get_file_hash(file_path: str) -> str:
    """Generate MD5 hash of file for duplicate detection"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


def validate_file_size(file_path: str) -> bool:
    """Check if file size is within limits"""
    try:
        file_size = os.path.getsize(file_path)
        return file_size <= MAX_FILE_SIZE
    except Exception:
        return False


def get_image_info(file_path: str) -> Dict[str, Any]:
    """Get basic image information"""
    try:
        if file_path.lower().endswith('.pdf'):
            # For PDF files, we'll need to convert first page to image
            return {
                "format": "PDF",
                "width": None,
                "height": None,
                "channels": None,
                "size_bytes": os.path.getsize(file_path)
            }
        else:
            # For image files
            image = cv2.imread(file_path)
            if image is not None:
                height, width, channels = image.shape
                return {
                    "format": get_file_extension(file_path).upper().replace('.', ''),
                    "width": width,
                    "height": height,
                    "channels": channels,
                    "size_bytes": os.path.getsize(file_path)
                }
            else:
                # Try with PIL as fallback
                with Image.open(file_path) as img:
                    return {
                        "format": img.format,
                        "width": img.width,
                        "height": img.height,
                        "channels": len(img.getbands()) if hasattr(img, 'getbands') else 1,
                        "size_bytes": os.path.getsize(file_path)
                    }
    except Exception as e:
        return {
            "format": "Unknown",
            "width": None,
            "height": None,
            "channels": None,
            "size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "error": str(e)
        }


# Answer key utilities
def validate_answer_key(answer_key: Dict[str, str], total_questions: int = 100) -> Dict[str, Any]:
    """Validate answer key format and content"""
    errors = []
    warnings = []
    
    # Check total number of questions
    if len(answer_key) != total_questions:
        errors.append(f"Expected {total_questions} answers, got {len(answer_key)}")
    
    # Check question numbering and answer format
    valid_answers = {'A', 'B', 'C', 'D'}
    for q_num, answer in answer_key.items():
        try:
            q_int = int(q_num)
            if q_int < 1 or q_int > total_questions:
                errors.append(f"Question number {q_num} out of range (1-{total_questions})")
        except ValueError:
            errors.append(f"Invalid question number format: {q_num}")
        
        if answer not in valid_answers:
            errors.append(f"Invalid answer '{answer}' for question {q_num}. Must be A, B, C, or D")
    
    # Check for missing questions
    expected_questions = set(str(i) for i in range(1, total_questions + 1))
    provided_questions = set(answer_key.keys())
    missing_questions = expected_questions - provided_questions
    
    if missing_questions:
        errors.append(f"Missing answers for questions: {sorted(missing_questions, key=int)}")
    
    # Check answer distribution (warning if too skewed)
    answer_counts = {}
    for answer in answer_key.values():
        if answer in valid_answers:
            answer_counts[answer] = answer_counts.get(answer, 0) + 1
    
    if answer_counts:
        total_valid = sum(answer_counts.values())
        for answer, count in answer_counts.items():
            percentage = (count / total_valid) * 100
            if percentage > 40:  # More than 40% of one answer
                warnings.append(f"Answer '{answer}' appears {percentage:.1f}% of the time (unusually high)")
            elif percentage < 15:  # Less than 15% of one answer
                warnings.append(f"Answer '{answer}' appears {percentage:.1f}% of the time (unusually low)")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "answer_distribution": answer_counts,
        "total_questions": len(answer_key)
    }


def compare_answer_keys(key1: Dict[str, str], key2: Dict[str, str]) -> Dict[str, Any]:
    """Compare two answer keys and find differences"""
    differences = []
    common_questions = set(key1.keys()) & set(key2.keys())
    
    for q_num in sorted(common_questions, key=int):
        if key1[q_num] != key2[q_num]:
            differences.append({
                "question": q_num,
                "key1_answer": key1[q_num],
                "key2_answer": key2[q_num]
            })
    
    only_in_key1 = set(key1.keys()) - set(key2.keys())
    only_in_key2 = set(key2.keys()) - set(key1.keys())
    
    return {
        "total_differences": len(differences),
        "differences": differences,
        "only_in_key1": sorted(only_in_key1, key=int) if only_in_key1 else [],
        "only_in_key2": sorted(only_in_key2, key=int) if only_in_key2 else [],
        "similarity_percentage": ((len(common_questions) - len(differences)) / len(common_questions) * 100) if common_questions else 0
    }


# Score calculation utilities
def calculate_subject_scores(student_answers: Dict[str, str], 
                           correct_answers: Dict[str, str],
                           subjects: List[str] = None,
                           questions_per_subject: int = 20) -> Dict[str, Any]:
    """Calculate subject-wise scores"""
    if subjects is None:
        subjects = ["Mathematics", "Physics", "Chemistry", "Biology", "English"]
    
    subject_scores = {}
    total_score = 0
    total_correct = 0
    total_questions = 0
    
    for i, subject in enumerate(subjects):
        start_q = i * questions_per_subject + 1
        end_q = (i + 1) * questions_per_subject
        
        correct_count = 0
        subject_total = 0
        
        for q_num in range(start_q, end_q + 1):
            q_str = str(q_num)
            if q_str in student_answers and q_str in correct_answers:
                subject_total += 1
                if student_answers[q_str] == correct_answers[q_str]:
                    correct_count += 1
        
        subject_scores[subject] = {
            "score": correct_count,
            "total": subject_total,
            "percentage": (correct_count / subject_total * 100) if subject_total > 0 else 0
        }
        
        total_correct += correct_count
        total_questions += subject_total
    
    total_score = total_correct
    
    return {
        "subject_scores": subject_scores,
        "total_score": total_score,
        "total_questions": total_questions,
        "overall_percentage": (total_score / total_questions * 100) if total_questions > 0 else 0
    }


def identify_flagged_questions(student_answers: Dict[str, str],
                             confidence_scores: Dict[str, float],
                             confidence_threshold: float = 0.8) -> List[str]:
    """Identify questions that need manual review"""
    flagged = []
    
    for q_num, confidence in confidence_scores.items():
        if confidence < confidence_threshold:
            flagged.append(q_num)
    
    # Also flag questions with no detected answer
    for q_num in range(1, 101):
        q_str = str(q_num)
        if q_str not in student_answers or student_answers[q_str] == "":
            flagged.append(q_str)
    
    return sorted(set(flagged), key=int)


# Statistics utilities
def calculate_score_distribution(scores: List[int], bins: int = 10) -> Dict[str, int]:
    """Calculate score distribution for visualization"""
    if not scores:
        return {}
    
    min_score = min(scores)
    max_score = max(scores)
    bin_size = (max_score - min_score) / bins if max_score > min_score else 1
    
    distribution = {}
    for i in range(bins):
        bin_start = min_score + i * bin_size
        bin_end = min_score + (i + 1) * bin_size
        
        if i == bins - 1:  # Last bin includes max value
            bin_label = f"{int(bin_start)}-{int(bin_end)}"
            count = sum(1 for score in scores if bin_start <= score <= bin_end)
        else:
            bin_label = f"{int(bin_start)}-{int(bin_end-1)}"
            count = sum(1 for score in scores if bin_start <= score < bin_end)
        
        distribution[bin_label] = count
    
    return distribution


def calculate_pass_rate(scores: List[int], passing_score: int = 50) -> float:
    """Calculate pass rate percentage"""
    if not scores:
        return 0.0
    
    passed = sum(1 for score in scores if score >= passing_score)
    return (passed / len(scores)) * 100


# File cleanup utilities
def cleanup_old_files(directory: str, max_age_days: int = 7) -> int:
    """Clean up files older than specified days"""
    if not os.path.exists(directory):
        return 0
    
    cutoff_time = datetime.now() - timedelta(days=max_age_days)
    deleted_count = 0
    
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    return deleted_count


# Configuration utilities
def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_config_to_file(config: Dict[str, Any], config_path: str) -> bool:
    """Save configuration to JSON file"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


# Validation utilities
def validate_student_id(student_id: str) -> Dict[str, Any]:
    """Validate student ID format"""
    errors = []
    
    if not student_id:
        errors.append("Student ID cannot be empty")
    elif len(student_id) < 3:
        errors.append("Student ID must be at least 3 characters long")
    elif len(student_id) > 20:
        errors.append("Student ID cannot exceed 20 characters")
    elif not student_id.replace('-', '').replace('_', '').isalnum():
        errors.append("Student ID can only contain letters, numbers, hyphens, and underscores")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def validate_exam_name(exam_name: str) -> Dict[str, Any]:
    """Validate exam name format"""
    errors = []
    
    if not exam_name:
        errors.append("Exam name cannot be empty")
    elif len(exam_name) < 3:
        errors.append("Exam name must be at least 3 characters long")
    elif len(exam_name) > 100:
        errors.append("Exam name cannot exceed 100 characters")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


# Image processing utilities
def get_image_quality_metrics(image_path: str) -> Dict[str, Any]:
    """Calculate basic image quality metrics"""
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"error": "Could not load image"}
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculate metrics
        height, width = gray.shape
        
        # Brightness (mean intensity)
        brightness = np.mean(gray)
        
        # Contrast (standard deviation)
        contrast = np.std(gray)
        
        # Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()
        
        # Noise estimation (using high-frequency content)
        noise = np.std(cv2.GaussianBlur(gray, (5, 5), 0) - gray)
        
        return {
            "width": width,
            "height": height,
            "brightness": float(brightness),
            "contrast": float(contrast),
            "sharpness": float(sharpness),
            "noise": float(noise),
            "quality_score": min(100, max(0, (sharpness / 100) * (contrast / 50) * 100))
        }
        
    except Exception as e:
        return {"error": str(e)}