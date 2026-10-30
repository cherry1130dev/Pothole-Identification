import cv2
from pothole_fallback import ClassicalPotholeDetector

detector = ClassicalPotholeDetector()
cap = cv2.VideoCapture("pothole_video.mp4")

frame_count = 0
pothole_frames = 0
sample_detections = []

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_count += 1
    detections, _ = detector.detect(frame)
    if detections:
        pothole_frames += 1
        if len(sample_detections) < 5:
            sample_detections.append((frame_count, detections))

cap.release()
print(f"Total video frames: {frame_count}")
print(f"Frames with detected potholes: {pothole_frames} ({(pothole_frames/frame_count)*100:.1f}%)")
for f_idx, dets in sample_detections:
    print(f"  Frame {f_idx}: {len(dets)} detection(s) -> BBox: {dets[0]['bbox']}, Conf: {dets[0]['confidence']}")
