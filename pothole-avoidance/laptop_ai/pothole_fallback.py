"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Classical OpenCV Fallback Pothole Detector
FILE:    pothole_fallback.py
======================================================================================

DESCRIPTION:
Classical computer-vision based detector designed to identify roadway potholes
without requiring neural network weights.
Operates via:
1. Road Region-of-Interest (ROI) segmentation (bottom 50% of camera FOV).
2. Bilateral noise filtering to preserve asphalt edge discontinuities.
3. Adaptive edge & dark-region crater intensity thresholding.
4. Morphological closure with elliptical structural elements.
5. Geometric contour filtering (area, aspect ratio, solidity).
======================================================================================
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Any
from config import (
    ROI_Y_MIN_RATIO,
    ROI_Y_MAX_RATIO,
    ROI_X_MIN_RATIO,
    ROI_X_MAX_RATIO,
    MIN_POTHOLE_AREA_PX,
    MAX_POTHOLE_AREA_PX,
    OPENCV_BLUR_KERNEL,
    CANNY_THRESH_LOW,
    CANNY_THRESH_HIGH,
    DARK_REGION_INTENSITY_FACTOR,
    MIN_CONTOUR_SOLIDITY
)


class ClassicalPotholeDetector:
    """Robust road defect and crater detector utilizing classical OpenCV operations."""

    def __init__(self):
        self.kernel_ellipse = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    def detect(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """
        Processes a single BGR video frame and returns a list of detected potholes
        along with an annotated debug mask.

        Returns:
            detections: List of dicts with keys ['bbox', 'confidence', 'area', 'centroid']
                        where bbox is (x, y, w, h) in original frame coordinates.
            debug_mask: Grayscale binary mask for visualization and troubleshooting.
        """
        frame_h, frame_w = frame.shape[:2]
        
        # 1. Define Road Region of Interest (ROI)
        roi_y1 = int(frame_h * ROI_Y_MIN_RATIO)
        roi_y2 = int(frame_h * ROI_Y_MAX_RATIO)
        roi_x1 = int(frame_w * ROI_X_MIN_RATIO)
        roi_x2 = int(frame_w * ROI_X_MAX_RATIO)

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        if roi.size == 0:
            return [], np.zeros((frame_h, frame_w), dtype=np.uint8)

        # 2. Convert to Grayscale & Filter High-Frequency Grain Noise
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray_roi, d=9, sigmaColor=75, sigmaSpace=75)

        # 3. Edge Detection on ROI
        edges = cv2.Canny(blurred, CANNY_THRESH_LOW, CANNY_THRESH_HIGH)

        # 4. Dark-Region Shadow Crater Analysis
        # Road surfaces are typically lighter than the shadowed crater interior of a pothole
        median_lum = np.median(blurred)
        dark_thresh_val = int(median_lum * DARK_REGION_INTENSITY_FACTOR)
        _, dark_mask = cv2.threshold(blurred, dark_thresh_val, 255, cv2.THRESH_BINARY_INV)

        # 5. Combine Edge Boundaries with Dark Crater Regions
        combined = cv2.bitwise_and(dark_mask, dark_mask, mask=cv2.dilate(edges, self.kernel_ellipse, iterations=1))
        # Morphological Closing to merge broken crater contours into unified blobs
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, self.kernel_ellipse, iterations=2)
        closed = cv2.dilate(closed, self.kernel_ellipse, iterations=1)

        # 6. Extract Contours
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_POTHOLE_AREA_PX or area > MAX_POTHOLE_AREA_PX:
                continue

            # Bounding box in ROI coordinates
            bx, by, bw, bh = cv2.boundingRect(cnt)

            # Filter unrealistic aspect ratios (potholes are roughly rounded/elliptical, not razor-thin lines)
            aspect_ratio = float(bw) / float(bh) if bh > 0 else 0
            if aspect_ratio < 0.35 or aspect_ratio > 3.0:
                continue

            # Check solidity (Area / Convex Hull Area)
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            if hull_area == 0:
                continue
            solidity = float(area) / hull_area
            if solidity < MIN_CONTOUR_SOLIDITY:
                continue

            # Estimate heuristic confidence score based on area and solidity
            confidence = min(0.95, max(0.45, 0.40 + (solidity * 0.3) + (min(area, 4000) / 4000.0) * 0.25))

            # Map coordinates back to full frame
            orig_x = roi_x1 + bx
            orig_y = roi_y1 + by
            cx = orig_x + bw // 2
            cy = orig_y + bh // 2

            detections.append({
                "bbox": (orig_x, orig_y, bw, bh),
                "confidence": round(confidence, 2),
                "area": int(area),
                "centroid": (cx, cy)
            })

        # Assemble full-size debug mask for HUD
        full_debug_mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
        full_debug_mask[roi_y1:roi_y2, roi_x1:roi_x2] = closed

        return detections, full_debug_mask
