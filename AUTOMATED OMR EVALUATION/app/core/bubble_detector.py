"""
Bubble detection and classification module for OMR sheets
Detects bubble grids and classifies filled/unfilled bubbles using OpenCV and ML
"""
import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
import math
from sklearn.cluster import DBSCAN
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os


class BubbleDetector:
    """Detects and classifies bubbles in OMR sheets"""
    
    def __init__(self):
        self.bubble_classifier = None
        self.bubble_templates = []
        self.grid_config = {
            "questions_per_subject": 20,
            "subjects": 5,
            "options_per_question": 4,  # A, B, C, D
            "expected_bubbles": 400  # 100 questions * 4 options
        }
        
    def set_grid_config(self, config: Dict[str, Any]):
        """Set OMR grid configuration"""
        self.grid_config.update(config)
    
    def detect_circles(self, image: np.ndarray, min_radius: int = 8, 
                      max_radius: int = 25) -> List[Tuple[int, int, int]]:
        """Detect circular bubbles using HoughCircles"""
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(image, (3, 3), 0)
        
        # Detect circles
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=min_radius * 2,
            param1=50,
            param2=30,
            minRadius=min_radius,
            maxRadius=max_radius
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            return [(x, y, r) for x, y, r in circles]
        
        return []
    
    def detect_rectangular_bubbles(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect rectangular bubbles using contour detection"""
        # Find contours
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bubbles = []
        for contour in contours:
            # Calculate contour area and bounding rectangle
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter based on size and aspect ratio
            if 50 < area < 1000:  # Reasonable bubble size
                aspect_ratio = w / h
                if 0.5 < aspect_ratio < 2.0:  # Roughly square/rectangular
                    bubbles.append((x, y, w, h))
        
        return bubbles
    
    def cluster_bubbles_into_grid(self, bubbles: List[Tuple], tolerance: int = 10) -> Dict[str, List]:
        """Organize detected bubbles into a grid structure"""
        if not bubbles:
            return {"rows": [], "columns": [], "grid": []}
        
        # Extract coordinates
        if len(bubbles[0]) == 3:  # Circular bubbles (x, y, r)
            coords = [(x, y) for x, y, r in bubbles]
        else:  # Rectangular bubbles (x, y, w, h)
            coords = [(x + w//2, y + h//2) for x, y, w, h in bubbles]
        
        coords = np.array(coords)
        
        # Cluster by Y coordinates to find rows
        y_coords = coords[:, 1].reshape(-1, 1)
        y_clustering = DBSCAN(eps=tolerance, min_samples=2).fit(y_coords)
        
        # Cluster by X coordinates to find columns
        x_coords = coords[:, 0].reshape(-1, 1)
        x_clustering = DBSCAN(eps=tolerance, min_samples=2).fit(x_coords)
        
        # Group bubbles by row and column
        rows = {}
        columns = {}
        
        for i, (coord, y_label, x_label) in enumerate(zip(coords, y_clustering.labels_, x_clustering.labels_)):
            if y_label not in rows:
                rows[y_label] = []
            if x_label not in columns:
                columns[x_label] = []
            
            bubble_info = {
                "index": i,
                "coord": coord,
                "bubble": bubbles[i],
                "row": y_label,
                "column": x_label
            }
            
            rows[y_label].append(bubble_info)
            columns[x_label].append(bubble_info)
        
        # Sort rows and columns
        sorted_rows = []
        for row_label in sorted(rows.keys()):
            if row_label != -1:  # Ignore noise points
                row_bubbles = sorted(rows[row_label], key=lambda x: x["coord"][0])
                sorted_rows.append(row_bubbles)
        
        sorted_columns = []
        for col_label in sorted(columns.keys()):
            if col_label != -1:  # Ignore noise points
                col_bubbles = sorted(columns[col_label], key=lambda x: x["coord"][1])
                sorted_columns.append(col_bubbles)
        
        return {
            "rows": sorted_rows,
            "columns": sorted_columns,
            "total_bubbles": len([b for row in sorted_rows for b in row])
        }
    
    def extract_bubble_features(self, image: np.ndarray, bubble: Tuple) -> np.ndarray:
        """Extract features from a bubble region for classification"""
        if len(bubble) == 3:  # Circular bubble (x, y, r)
            x, y, r = bubble
            # Create circular mask
            mask = np.zeros(image.shape, dtype=np.uint8)
            cv2.circle(mask, (x, y), r, 255, -1)
            
            # Extract region
            x1, y1 = max(0, x - r), max(0, y - r)
            x2, y2 = min(image.shape[1], x + r), min(image.shape[0], y + r)
            region = image[y1:y2, x1:x2]
            mask_region = mask[y1:y2, x1:x2]
            
        else:  # Rectangular bubble (x, y, w, h)
            x, y, w, h = bubble
            region = image[y:y+h, x:x+w]
            mask_region = np.ones_like(region) * 255
        
        if region.size == 0:
            return np.zeros(10)  # Return default features if region is empty
        
        # Calculate features
        features = []
        
        # 1. Mean intensity
        mean_intensity = np.mean(region[mask_region > 0]) if np.any(mask_region > 0) else 0
        features.append(mean_intensity)
        
        # 2. Standard deviation of intensity
        std_intensity = np.std(region[mask_region > 0]) if np.any(mask_region > 0) else 0
        features.append(std_intensity)
        
        # 3. Percentage of dark pixels (below threshold)
        dark_threshold = 100
        dark_pixels = np.sum((region < dark_threshold) & (mask_region > 0))
        total_pixels = np.sum(mask_region > 0)
        dark_percentage = dark_pixels / total_pixels if total_pixels > 0 else 0
        features.append(dark_percentage)
        
        # 4. Edge density
        edges = cv2.Canny(region, 50, 150)
        edge_density = np.sum(edges > 0) / region.size if region.size > 0 else 0
        features.append(edge_density)
        
        # 5. Contour area ratio
        contours, _ = cv2.findContours(
            cv2.threshold(region, 127, 255, cv2.THRESH_BINARY_INV)[1],
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            contour_area = cv2.contourArea(largest_contour)
            area_ratio = contour_area / region.size if region.size > 0 else 0
        else:
            area_ratio = 0
        features.append(area_ratio)
        
        # 6-10. Histogram features (5 bins)
        hist = cv2.calcHist([region], [0], mask_region, [5], [0, 256])
        hist_features = hist.flatten() / np.sum(hist) if np.sum(hist) > 0 else np.zeros(5)
        features.extend(hist_features)
        
        return np.array(features)
    
    def classify_bubble(self, image: np.ndarray, bubble: Tuple) -> Tuple[bool, float]:
        """Classify if a bubble is filled or not"""
        features = self.extract_bubble_features(image, bubble)
        
        if self.bubble_classifier is not None:
            # Use trained classifier
            prediction = self.bubble_classifier.predict([features])[0]
            confidence = max(self.bubble_classifier.predict_proba([features])[0])
            return bool(prediction), confidence
        else:
            # Use rule-based classification as fallback
            mean_intensity = features[0]
            dark_percentage = features[2]
            
            # Simple threshold-based classification
            is_filled = (mean_intensity < 150) and (dark_percentage > 0.3)
            confidence = min(1.0, abs(dark_percentage - 0.5) * 2)  # Simple confidence measure
            
            return is_filled, confidence
    
    def train_bubble_classifier(self, training_data: List[Dict[str, Any]]):
        """Train a machine learning classifier for bubble detection"""
        if not training_data:
            print("No training data provided. Using rule-based classification.")
            return
        
        # Extract features and labels
        X = []
        y = []
        
        for sample in training_data:
            image = sample["image"]
            bubble = sample["bubble"]
            is_filled = sample["is_filled"]
            
            features = self.extract_bubble_features(image, bubble)
            X.append(features)
            y.append(1 if is_filled else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # Train classifier
        self.bubble_classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            class_weight="balanced"
        )
        
        # Split data for validation
        if len(X) > 10:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            self.bubble_classifier.fit(X_train, y_train)
            
            # Evaluate
            train_score = self.bubble_classifier.score(X_train, y_train)
            test_score = self.bubble_classifier.score(X_test, y_test)
            
            print(f"Classifier trained. Train accuracy: {train_score:.3f}, Test accuracy: {test_score:.3f}")
        else:
            self.bubble_classifier.fit(X, y)
            print("Classifier trained with limited data.")
    
    def save_classifier(self, filepath: str):
        """Save trained classifier to file"""
        if self.bubble_classifier is not None:
            joblib.dump(self.bubble_classifier, filepath)
            print(f"Classifier saved to {filepath}")
    
    def load_classifier(self, filepath: str):
        """Load trained classifier from file"""
        if os.path.exists(filepath):
            self.bubble_classifier = joblib.load(filepath)
            print(f"Classifier loaded from {filepath}")
        else:
            print(f"Classifier file not found: {filepath}")
    
    def detect_and_classify_bubbles(self, image: np.ndarray) -> Dict[str, Any]:
        """Complete bubble detection and classification pipeline"""
        results = {
            "bubbles_detected": 0,
            "bubbles_filled": 0,
            "grid_structure": None,
            "classifications": [],
            "confidence_scores": [],
            "processing_info": {}
        }
        
        try:
            # Detect bubbles (try both circular and rectangular)
            circular_bubbles = self.detect_circles(image)
            rectangular_bubbles = self.detect_rectangular_bubbles(image)
            
            # Use the detection method that found more bubbles
            if len(circular_bubbles) >= len(rectangular_bubbles):
                bubbles = circular_bubbles
                bubble_type = "circular"
            else:
                bubbles = rectangular_bubbles
                bubble_type = "rectangular"
            
            results["bubbles_detected"] = len(bubbles)
            results["processing_info"]["bubble_type"] = bubble_type
            
            if not bubbles:
                return results
            
            # Organize into grid
            grid_structure = self.cluster_bubbles_into_grid(bubbles)
            results["grid_structure"] = grid_structure
            
            # Classify each bubble
            classifications = []
            confidence_scores = []
            filled_count = 0
            
            for bubble in bubbles:
                is_filled, confidence = self.classify_bubble(image, bubble)
                classifications.append(is_filled)
                confidence_scores.append(confidence)
                
                if is_filled:
                    filled_count += 1
            
            results["bubbles_filled"] = filled_count
            results["classifications"] = classifications
            results["confidence_scores"] = confidence_scores
            results["processing_info"]["average_confidence"] = np.mean(confidence_scores) if confidence_scores else 0
            
            return results
            
        except Exception as e:
            results["processing_info"]["error"] = str(e)
            return results
    
    def map_bubbles_to_answers(self, grid_structure: Dict, classifications: List[bool]) -> Dict[str, Any]:
        """Map detected bubbles to question answers based on grid structure"""
        if not grid_structure or not grid_structure["rows"]:
            return {"answers": {}, "flagged_questions": [], "mapping_info": {}}
        
        answers = {}
        flagged_questions = []
        mapping_info = {
            "total_questions": 0,
            "answered_questions": 0,
            "multiple_answers": 0,
            "no_answers": 0
        }
        
        try:
            rows = grid_structure["rows"]
            options_per_question = self.grid_config["options_per_question"]
            
            question_num = 1
            
            for row in rows:
                # Group bubbles in this row by question (every 4 bubbles = 1 question)
                for i in range(0, len(row), options_per_question):
                    question_bubbles = row[i:i + options_per_question]
                    
                    if len(question_bubbles) < options_per_question:
                        continue  # Skip incomplete questions
                    
                    # Check which options are filled for this question
                    filled_options = []
                    for j, bubble_info in enumerate(question_bubbles):
                        bubble_index = bubble_info["index"]
                        if bubble_index < len(classifications) and classifications[bubble_index]:
                            filled_options.append(chr(ord('A') + j))  # A, B, C, D
                    
                    mapping_info["total_questions"] += 1
                    
                    if len(filled_options) == 0:
                        # No answer selected
                        answers[f"Q{question_num}"] = None
                        flagged_questions.append({
                            "question": question_num,
                            "issue": "no_answer",
                            "details": "No option selected"
                        })
                        mapping_info["no_answers"] += 1
                        
                    elif len(filled_options) == 1:
                        # Single answer (normal case)
                        answers[f"Q{question_num}"] = filled_options[0]
                        mapping_info["answered_questions"] += 1
                        
                    else:
                        # Multiple answers (ambiguous)
                        answers[f"Q{question_num}"] = filled_options
                        flagged_questions.append({
                            "question": question_num,
                            "issue": "multiple_answers",
                            "details": f"Multiple options selected: {', '.join(filled_options)}"
                        })
                        mapping_info["multiple_answers"] += 1
                    
                    question_num += 1
            
            return {
                "answers": answers,
                "flagged_questions": flagged_questions,
                "mapping_info": mapping_info
            }
            
        except Exception as e:
            return {
                "answers": {},
                "flagged_questions": [{"question": 0, "issue": "mapping_error", "details": str(e)}],
                "mapping_info": mapping_info
            }


if __name__ == "__main__":
    # Test the bubble detector
    detector = BubbleDetector()
    
    # Example usage
    try:
        # Load a test image
        test_image = cv2.imread("sample_omr.jpg", cv2.IMREAD_GRAYSCALE)
        if test_image is not None:
            results = detector.detect_and_classify_bubbles(test_image)
            print(f"Detection results: {results}")
            
            # Map to answers
            if results["grid_structure"]:
                answer_mapping = detector.map_bubbles_to_answers(
                    results["grid_structure"], 
                    results["classifications"]
                )
                print(f"Answer mapping: {answer_mapping}")
        else:
            print("Test image not found")
            
    except Exception as e:
        print(f"Error in testing: {e}")