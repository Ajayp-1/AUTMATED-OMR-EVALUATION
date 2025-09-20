"""
Main OMR processing module that orchestrates the complete evaluation pipeline
"""
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json
import os
from datetime import datetime
import logging

from .image_processor import ImageProcessor
from .bubble_detector import BubbleDetector


class OMRProcessor:
    """Main class for processing OMR sheets and calculating scores"""
    
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.bubble_detector = BubbleDetector()
        self.answer_keys = {}
        self.subject_config = {
            "subjects": ["Mathematics", "Physics", "Chemistry", "Biology", "English"],
            "questions_per_subject": 20,
            "total_questions": 100
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def set_answer_key(self, sheet_version: str, answer_key: Dict[str, str]):
        """Set answer key for a specific sheet version"""
        self.answer_keys[sheet_version] = answer_key
        self.logger.info(f"Answer key set for version {sheet_version}")
    
    def load_answer_keys(self, answer_keys_file: str):
        """Load answer keys from JSON file"""
        try:
            with open(answer_keys_file, 'r') as f:
                self.answer_keys = json.load(f)
            self.logger.info(f"Answer keys loaded from {answer_keys_file}")
        except Exception as e:
            self.logger.error(f"Error loading answer keys: {e}")
            raise
    
    def detect_sheet_version(self, image: np.ndarray) -> str:
        """Detect sheet version from image (placeholder implementation)"""
        # This is a simplified implementation
        # In practice, you might look for version markers, QR codes, or specific patterns
        
        # For now, return a default version
        # You can enhance this by detecting version markers in the image
        return "A"
    
    def calculate_subject_scores(self, student_answers: Dict[str, str], 
                               correct_answers: Dict[str, str]) -> Dict[str, Any]:
        """Calculate subject-wise and total scores"""
        scores = {
            "subject_scores": {},
            "total_score": 0,
            "correct_answers": 0,
            "total_questions": 0,
            "subject_breakdown": {}
        }
        
        questions_per_subject = self.subject_config["questions_per_subject"]
        subjects = self.subject_config["subjects"]
        
        # Initialize subject scores
        for subject in subjects:
            scores["subject_scores"][subject] = 0
            scores["subject_breakdown"][subject] = {
                "correct": 0,
                "total": questions_per_subject,
                "percentage": 0
            }
        
        total_correct = 0
        total_questions = 0
        
        # Calculate scores for each question
        for question_key, student_answer in student_answers.items():
            if question_key not in correct_answers:
                continue
            
            # Extract question number
            question_num = int(question_key.replace('Q', ''))
            
            # Determine subject (questions 1-20: subject 1, 21-40: subject 2, etc.)
            subject_index = (question_num - 1) // questions_per_subject
            if subject_index >= len(subjects):
                continue
            
            subject = subjects[subject_index]
            total_questions += 1
            scores["subject_breakdown"][subject]["total"] = questions_per_subject
            
            # Check if answer is correct
            correct_answer = correct_answers[question_key]
            
            # Handle multiple answers (flagged questions)
            if isinstance(student_answer, list):
                # If multiple answers, consider it incorrect
                is_correct = False
            elif student_answer is None:
                # No answer provided
                is_correct = False
            else:
                is_correct = student_answer.upper() == correct_answer.upper()
            
            if is_correct:
                scores["subject_scores"][subject] += 1
                scores["subject_breakdown"][subject]["correct"] += 1
                total_correct += 1
        
        # Calculate percentages and final scores
        for subject in subjects:
            breakdown = scores["subject_breakdown"][subject]
            if breakdown["total"] > 0:
                breakdown["percentage"] = (breakdown["correct"] / breakdown["total"]) * 100
                # Convert to 20-point scale
                scores["subject_scores"][subject] = (breakdown["correct"] / breakdown["total"]) * 20
        
        scores["correct_answers"] = total_correct
        scores["total_questions"] = total_questions
        scores["total_score"] = sum(scores["subject_scores"].values())
        
        return scores
    
    def create_overlay_image(self, original_image: np.ndarray, 
                           bubble_results: Dict[str, Any],
                           student_answers: Dict[str, str]) -> np.ndarray:
        """Create overlay image showing detected bubbles and answers"""
        # Convert to color if grayscale
        if len(original_image.shape) == 2:
            overlay = cv2.cvtColor(original_image, cv2.COLOR_GRAY2BGR)
        else:
            overlay = original_image.copy()
        
        if not bubble_results.get("grid_structure") or not bubble_results["grid_structure"]["rows"]:
            return overlay
        
        try:
            rows = bubble_results["grid_structure"]["rows"]
            classifications = bubble_results["classifications"]
            
            question_num = 1
            options_per_question = 4
            
            for row in rows:
                for i in range(0, len(row), options_per_question):
                    question_bubbles = row[i:i + options_per_question]
                    
                    if len(question_bubbles) < options_per_question:
                        continue
                    
                    # Draw bubbles for this question
                    for j, bubble_info in enumerate(question_bubbles):
                        bubble = bubble_info["bubble"]
                        bubble_index = bubble_info["index"]
                        
                        # Determine color based on classification
                        if bubble_index < len(classifications):
                            is_filled = classifications[bubble_index]
                            
                            if is_filled:
                                color = (0, 255, 0)  # Green for filled
                                thickness = 3
                            else:
                                color = (255, 0, 0)  # Red for unfilled
                                thickness = 1
                        else:
                            color = (128, 128, 128)  # Gray for unprocessed
                            thickness = 1
                        
                        # Draw bubble outline
                        if len(bubble) == 3:  # Circular
                            x, y, r = bubble
                            cv2.circle(overlay, (x, y), r, color, thickness)
                        else:  # Rectangular
                            x, y, w, h = bubble
                            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, thickness)
                    
                    # Add question number label
                    if question_bubbles:
                        first_bubble = question_bubbles[0]["bubble"]
                        if len(first_bubble) == 3:
                            label_x, label_y = first_bubble[0] - 30, first_bubble[1]
                        else:
                            label_x, label_y = first_bubble[0] - 30, first_bubble[1] + first_bubble[3] // 2
                        
                        cv2.putText(overlay, f"Q{question_num}", (label_x, label_y),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    
                    question_num += 1
            
            return overlay
            
        except Exception as e:
            self.logger.error(f"Error creating overlay: {e}")
            return overlay
    
    def process_omr_sheet(self, image_path: str, sheet_version: Optional[str] = None,
                         student_id: Optional[str] = None) -> Dict[str, Any]:
        """Complete OMR processing pipeline"""
        results = {
            "success": False,
            "student_id": student_id,
            "sheet_version": sheet_version,
            "processing_info": {},
            "bubble_detection": {},
            "student_answers": {},
            "scores": {},
            "flagged_questions": [],
            "confidence_metrics": {},
            "file_paths": {
                "original": image_path,
                "processed": None,
                "overlay": None
            },
            "timestamp": datetime.utcnow().isoformat(),
            "error_message": None
        }
        
        try:
            self.logger.info(f"Starting OMR processing for {image_path}")
            
            # Step 1: Image preprocessing
            self.logger.info("Step 1: Image preprocessing")
            processed_image, processing_info = self.image_processor.preprocess_image(image_path)
            results["processing_info"] = processing_info
            
            # Save processed image
            processed_path = image_path.replace('.', '_processed.')
            cv2.imwrite(processed_path, processed_image)
            results["file_paths"]["processed"] = processed_path
            
            # Step 2: Detect sheet version if not provided
            if sheet_version is None:
                sheet_version = self.detect_sheet_version(processed_image)
                results["sheet_version"] = sheet_version
            
            # Step 3: Bubble detection and classification
            self.logger.info("Step 2: Bubble detection and classification")
            bubble_results = self.bubble_detector.detect_and_classify_bubbles(processed_image)
            results["bubble_detection"] = bubble_results
            
            if bubble_results["bubbles_detected"] == 0:
                raise ValueError("No bubbles detected in the image")
            
            # Step 4: Map bubbles to answers
            self.logger.info("Step 3: Mapping bubbles to answers")
            answer_mapping = self.bubble_detector.map_bubbles_to_answers(
                bubble_results["grid_structure"],
                bubble_results["classifications"]
            )
            
            results["student_answers"] = answer_mapping["answers"]
            results["flagged_questions"] = answer_mapping["flagged_questions"]
            
            # Step 5: Calculate scores
            self.logger.info("Step 4: Calculating scores")
            if sheet_version in self.answer_keys:
                correct_answers = self.answer_keys[sheet_version]
                scores = self.calculate_subject_scores(
                    answer_mapping["answers"],
                    correct_answers
                )
                results["scores"] = scores
            else:
                self.logger.warning(f"No answer key found for version {sheet_version}")
                results["scores"] = {"error": f"No answer key for version {sheet_version}"}
            
            # Step 6: Calculate confidence metrics
            confidence_scores = bubble_results.get("confidence_scores", [])
            if confidence_scores:
                results["confidence_metrics"] = {
                    "average_confidence": np.mean(confidence_scores),
                    "min_confidence": np.min(confidence_scores),
                    "max_confidence": np.max(confidence_scores),
                    "low_confidence_count": len([c for c in confidence_scores if c < 0.7])
                }
            
            # Step 7: Create overlay image
            self.logger.info("Step 5: Creating overlay image")
            original_image = self.image_processor.load_image(image_path)
            overlay_image = self.create_overlay_image(
                original_image,
                bubble_results,
                answer_mapping["answers"]
            )
            
            # Save overlay image
            overlay_path = image_path.replace('.', '_overlay.')
            cv2.imwrite(overlay_path, overlay_image)
            results["file_paths"]["overlay"] = overlay_path
            
            results["success"] = True
            self.logger.info("OMR processing completed successfully")
            
        except Exception as e:
            error_msg = f"Error processing OMR sheet: {str(e)}"
            self.logger.error(error_msg)
            results["error_message"] = error_msg
            results["success"] = False
        
        return results
    
    def batch_process_omr_sheets(self, image_paths: List[str], 
                                sheet_versions: Optional[List[str]] = None,
                                student_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Process multiple OMR sheets in batch"""
        results = []
        
        for i, image_path in enumerate(image_paths):
            sheet_version = sheet_versions[i] if sheet_versions and i < len(sheet_versions) else None
            student_id = student_ids[i] if student_ids and i < len(student_ids) else None
            
            self.logger.info(f"Processing sheet {i+1}/{len(image_paths)}: {image_path}")
            
            result = self.process_omr_sheet(image_path, sheet_version, student_id)
            results.append(result)
        
        return results
    
    def generate_summary_report(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary report for batch processing"""
        summary = {
            "total_sheets": len(batch_results),
            "successful_processing": 0,
            "failed_processing": 0,
            "average_score": 0,
            "score_distribution": {},
            "common_issues": {},
            "processing_time": None,
            "confidence_summary": {}
        }
        
        successful_results = [r for r in batch_results if r["success"]]
        summary["successful_processing"] = len(successful_results)
        summary["failed_processing"] = summary["total_sheets"] - summary["successful_processing"]
        
        if successful_results:
            # Calculate average score
            total_scores = [r["scores"].get("total_score", 0) for r in successful_results 
                          if "total_score" in r.get("scores", {})]
            if total_scores:
                summary["average_score"] = np.mean(total_scores)
            
            # Analyze common issues
            all_flagged = []
            for result in successful_results:
                all_flagged.extend(result.get("flagged_questions", []))
            
            issue_counts = {}
            for flag in all_flagged:
                issue = flag.get("issue", "unknown")
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            summary["common_issues"] = issue_counts
        
        return summary


if __name__ == "__main__":
    # Test the OMR processor
    processor = OMRProcessor()
    
    # Set up sample answer key
    sample_answer_key = {f"Q{i}": chr(ord('A') + (i % 4)) for i in range(1, 101)}
    processor.set_answer_key("A", sample_answer_key)
    
    # Test processing
    try:
        result = processor.process_omr_sheet("sample_omr.jpg", "A", "STUDENT001")
        print(f"Processing result: {result}")
    except Exception as e:
        print(f"Error in testing: {e}")