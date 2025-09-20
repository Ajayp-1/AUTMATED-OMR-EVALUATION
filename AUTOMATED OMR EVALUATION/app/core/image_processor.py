"""
Image preprocessing module for OMR sheets
Handles rotation, skew correction, perspective correction, and illumination normalization
"""
import cv2
import numpy as np
from typing import Tuple, Optional, List
import math
from scipy import ndimage
from skimage import filters, morphology
from PIL import Image


class ImageProcessor:
    """Handles all image preprocessing operations for OMR sheets"""
    
    def __init__(self):
        self.debug_mode = False
        
    def set_debug_mode(self, debug: bool):
        """Enable/disable debug mode for visualization"""
        self.debug_mode = debug
    
    def load_image(self, image_path: str) -> np.ndarray:
        """Load image from file path"""
        try:
            # Try loading with OpenCV first
            image = cv2.imread(image_path)
            if image is None:
                # Fallback to PIL for other formats
                pil_image = Image.open(image_path)
                image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return image
        except Exception as e:
            raise ValueError(f"Could not load image from {image_path}: {str(e)}")
    
    def resize_image(self, image: np.ndarray, max_width: int = 1200, 
                    max_height: int = 1600) -> Tuple[np.ndarray, float]:
        """Resize image while maintaining aspect ratio"""
        height, width = image.shape[:2]
        
        # Calculate scaling factor
        scale_w = max_width / width
        scale_h = max_height / height
        scale = min(scale_w, scale_h, 1.0)  # Don't upscale
        
        if scale < 1.0:
            new_width = int(width * scale)
            new_height = int(height * scale)
            resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            return resized, scale
        
        return image, 1.0
    
    def convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast using CLAHE"""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    
    def correct_illumination(self, image: np.ndarray) -> np.ndarray:
        """Correct uneven illumination using morphological operations"""
        # Create morphological kernel
        kernel_size = max(image.shape) // 20
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        # Apply morphological opening to get background
        background = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
        
        # Subtract background and normalize
        corrected = cv2.subtract(image, background)
        corrected = cv2.add(corrected, 50)  # Add offset to avoid too dark regions
        
        return corrected
    
    def detect_skew_angle(self, image: np.ndarray) -> float:
        """Detect skew angle using Hough line transform"""
        # Apply edge detection
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Apply Hough line transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is None:
            return 0.0
        
        # Calculate angles
        angles = []
        for rho, theta in lines[:, 0]:
            angle = theta * 180 / np.pi
            # Convert to skew angle (-45 to 45 degrees)
            if angle > 90:
                angle = angle - 180
            elif angle > 45:
                angle = angle - 90
            elif angle < -45:
                angle = angle + 90
            
            if abs(angle) < 45:  # Only consider reasonable skew angles
                angles.append(angle)
        
        if not angles:
            return 0.0
        
        # Return median angle to avoid outliers
        return np.median(angles)
    
    def correct_skew(self, image: np.ndarray, angle: Optional[float] = None) -> Tuple[np.ndarray, float]:
        """Correct image skew"""
        if angle is None:
            angle = self.detect_skew_angle(image)
        
        if abs(angle) < 0.5:  # Skip correction for very small angles
            return image, 0.0
        
        # Get image center
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        # Create rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Apply rotation
        corrected = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                  flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
        return corrected, angle
    
    def detect_document_contour(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Detect the main document contour for perspective correction"""
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        
        # Apply adaptive threshold
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find the largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Approximate contour to polygon
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # Check if we have a quadrilateral
        if len(approx) == 4:
            return approx.reshape(4, 2)
        
        # If not a perfect quadrilateral, use bounding rectangle
        rect = cv2.minAreaRect(largest_contour)
        box = cv2.boxPoints(rect)
        return np.int0(box)
    
    def order_points(self, pts: np.ndarray) -> np.ndarray:
        """Order points in clockwise order: top-left, top-right, bottom-right, bottom-left"""
        # Sort by y-coordinate
        y_sorted = pts[np.argsort(pts[:, 1])]
        
        # Get top and bottom pairs
        top = y_sorted[:2]
        bottom = y_sorted[2:]
        
        # Sort top pair by x-coordinate (left to right)
        top_sorted = top[np.argsort(top[:, 0])]
        top_left, top_right = top_sorted
        
        # Sort bottom pair by x-coordinate (left to right)
        bottom_sorted = bottom[np.argsort(bottom[:, 0])]
        bottom_left, bottom_right = bottom_sorted
        
        return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
    
    def apply_perspective_correction(self, image: np.ndarray, 
                                   contour: Optional[np.ndarray] = None) -> Tuple[np.ndarray, bool]:
        """Apply perspective correction to straighten the document"""
        if contour is None:
            contour = self.detect_document_contour(image)
        
        if contour is None:
            return image, False
        
        # Order the points
        ordered_pts = self.order_points(contour)
        
        # Calculate the width and height of the corrected image
        width_top = np.linalg.norm(ordered_pts[1] - ordered_pts[0])
        width_bottom = np.linalg.norm(ordered_pts[2] - ordered_pts[3])
        width = max(int(width_top), int(width_bottom))
        
        height_left = np.linalg.norm(ordered_pts[3] - ordered_pts[0])
        height_right = np.linalg.norm(ordered_pts[2] - ordered_pts[1])
        height = max(int(height_left), int(height_right))
        
        # Define destination points
        dst_pts = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)
        
        # Calculate perspective transform matrix
        transform_matrix = cv2.getPerspectiveTransform(ordered_pts, dst_pts)
        
        # Apply perspective correction
        corrected = cv2.warpPerspective(image, transform_matrix, (width, height))
        
        return corrected, True
    
    def remove_noise(self, image: np.ndarray) -> np.ndarray:
        """Remove noise from the image"""
        # Apply median filter to remove salt and pepper noise
        denoised = cv2.medianBlur(image, 3)
        
        # Apply morphological opening to remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)
        
        return denoised
    
    def binarize_image(self, image: np.ndarray) -> np.ndarray:
        """Convert image to binary using adaptive thresholding"""
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(image, (3, 3), 0)
        
        # Apply adaptive threshold
        binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        return binary
    
    def preprocess_image(self, image_path: str) -> Tuple[np.ndarray, dict]:
        """Complete preprocessing pipeline for OMR sheet"""
        processing_info = {
            "original_size": None,
            "final_size": None,
            "scale_factor": 1.0,
            "skew_angle": 0.0,
            "perspective_corrected": False,
            "processing_steps": []
        }
        
        try:
            # Load image
            image = self.load_image(image_path)
            processing_info["original_size"] = image.shape[:2]
            processing_info["processing_steps"].append("loaded")
            
            # Resize if too large
            image, scale = self.resize_image(image)
            processing_info["scale_factor"] = scale
            processing_info["processing_steps"].append("resized")
            
            # Convert to grayscale
            gray = self.convert_to_grayscale(image)
            processing_info["processing_steps"].append("grayscale")
            
            # Correct illumination
            illumination_corrected = self.correct_illumination(gray)
            processing_info["processing_steps"].append("illumination_corrected")
            
            # Enhance contrast
            contrast_enhanced = self.enhance_contrast(illumination_corrected)
            processing_info["processing_steps"].append("contrast_enhanced")
            
            # Correct skew
            skew_corrected, skew_angle = self.correct_skew(contrast_enhanced)
            processing_info["skew_angle"] = skew_angle
            processing_info["processing_steps"].append("skew_corrected")
            
            # Apply perspective correction
            perspective_corrected, perspective_success = self.apply_perspective_correction(skew_corrected)
            processing_info["perspective_corrected"] = perspective_success
            if perspective_success:
                processing_info["processing_steps"].append("perspective_corrected")
                final_image = perspective_corrected
            else:
                final_image = skew_corrected
            
            # Remove noise
            denoised = self.remove_noise(final_image)
            processing_info["processing_steps"].append("denoised")
            
            # Final binarization
            binary = self.binarize_image(denoised)
            processing_info["processing_steps"].append("binarized")
            
            processing_info["final_size"] = binary.shape[:2]
            
            return binary, processing_info
            
        except Exception as e:
            raise RuntimeError(f"Error in preprocessing pipeline: {str(e)}")


if __name__ == "__main__":
    # Test the image processor
    processor = ImageProcessor()
    processor.set_debug_mode(True)
    
    # Example usage
    try:
        processed_image, info = processor.preprocess_image("sample_omr.jpg")
        print("Processing completed successfully!")
        print(f"Processing info: {info}")
    except Exception as e:
        print(f"Error: {e}")