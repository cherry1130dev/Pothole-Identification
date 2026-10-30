"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  YOLOv8n Training & ONNX CPU Export Pipeline
FILE:    train_model.py
======================================================================================

DESCRIPTION:
Automates training of a lightweight YOLOv8n (nano) pothole detection model.
- Tuned for fast, CPU-only real-time inference at 320x320 resolution.
- Exports the final trained checkpoint to ONNX format (with ONNX simplifier).
- Automatically deploys the exported model into the 'laptop_ai/models/' directory.

DATASET ACQUISITION INSTRUCTIONS:
--------------------------------------------------------------------------------------
1. ROBOFLOW UNIVERSE (Recommended):
   - Visit: https://universe.roboflow.com/search?q=pothole+detection
   - Select a popular dataset (e.g. "pothole-detection-6hpt7" or "Potholes-Detection")
   - Click "Download Dataset" -> Select "YOLOv8" format.
   - Extract the downloaded ZIP into: 'laptop_ai/dataset/'

2. KAGGLE:
   - Visit: https://www.kaggle.com/datasets/chitholian/annotated-potholes-dataset
   - Download and arrange into YOLO format:
     laptop_ai/dataset/
       ├── images/
       │   ├── train/
       │   └── val/
       └── labels/
           ├── train/
           └── val/

3. RUNNING THIS SCRIPT:
   python train_model.py --epochs 30 --imgsz 320 --export-onnx
======================================================================================
"""

import os
import sys
import shutil
import argparse
from pathlib import Path


def create_sample_data_yaml(target_path: Path) -> Path:
    """Creates a default dataset configuration file if none exists."""
    dataset_dir = target_path.parent
    yaml_content = f"""# Pothole Detection Dataset Configuration
path: {dataset_dir.as_posix()}  # dataset root dir
train: images/train  # train images (relative to 'path')
val: images/val      # val images (relative to 'path')
test: images/test    # optional test images

# Classes
names:
  0: pothole
"""
    target_path.write_text(yaml_content, encoding="utf-8")
    print(f"[DATASET] Generated template YAML at: {target_path}")
    return target_path


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8n Pothole Detection Model & Export to ONNX")
    parser.add_argument("--data", type=str, default=None, help="Path to data.yaml dataset configuration file")
    parser.add_argument("--epochs", type=int, default=30, help="Number of training epochs (default: 30)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument("--imgsz", type=int, default=320, help="Input resolution (default: 320 for CPU inference)")
    parser.add_argument("--export-onnx", action="store_true", default=True, help="Export to ONNX after training")
    parser.add_argument("--device", type=str, default="cpu", help="Inference / training device ('cpu' or '0')")
    args = parser.parse_args()

    # Verify Ultralytics installation
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics is not installed. Run: pip install ultralytics")
        sys.exit(1)

    base_dir = Path(__file__).resolve().parent
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Determine dataset YAML path
    if args.data:
        data_yaml = Path(args.data).resolve()
    else:
        dataset_dir = base_dir / "dataset"
        data_yaml = dataset_dir / "data.yaml"
        if not data_yaml.exists():
            dataset_dir.mkdir(parents=True, exist_ok=True)
            create_sample_data_yaml(data_yaml)
            print("=" * 70)
            print("[NOTICE] No dataset found! Please populate images and labels inside:")
            print(f"         {dataset_dir}")
            print("         Refer to the instructions at the top of this script.")
            print("=" * 70)

    print(f"\n[TRAINING] Initializing YOLOv8n base model...")
    model = YOLO("yolov8n.pt")

    print(f"[TRAINING] Starting fine-tuning for {args.epochs} epochs with input size {args.imgsz}x{args.imgsz}...")
    try:
        results = model.train(
            data=str(data_yaml),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=2,
            project=str(base_dir / "runs"),
            name="pothole_yolov8n",
            exist_ok=True,
            verbose=True
        )
        print("[TRAINING] Model training finished successfully!")
    except Exception as exc:
        print(f"[ERROR] Training failed or was interrupted: {exc}")
        print("[TIP] You can still run 'detect_stream.py' immediately using the classical OpenCV fallback!")
        sys.exit(1)

    # Locate best.pt
    best_weights = base_dir / "runs" / "pothole_yolov8n" / "weights" / "best.pt"
    dest_pt = models_dir / "best.pt"
    if best_weights.exists():
        shutil.copy(best_weights, dest_pt)
        print(f"[DEPLOY] Saved best PyTorch weights to: {dest_pt}")

    # Export to ONNX for CPU acceleration
    if args.export_onnx:
        print(f"\n[EXPORT] Exporting model to ONNX (imgsz={args.imgsz}, simplify=True)...")
        try:
            exported_path = model.export(
                format="onnx",
                imgsz=args.imgsz,
                dynamic=False,
                simplify=True
            )
            dest_onnx = models_dir / "pothole_yolov8n.onnx"
            if Path(exported_path).exists():
                shutil.copy(exported_path, dest_onnx)
                print(f"[DEPLOY] Successfully deployed ONNX model to: {dest_onnx}")
                print("[SUCCESS] Real-time inference ready! Run: python detect_stream.py")
        except Exception as exc:
            print(f"[WARNING] ONNX export encountered an issue: {exc}")
            print(f"PyTorch model is saved at {dest_pt} and can be used directly.")


if __name__ == "__main__":
    main()
