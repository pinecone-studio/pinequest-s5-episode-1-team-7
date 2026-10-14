# Technical Design Document — pinequest-s5-episode-1-team-7


1.1 Overview
The Open-Source AI Pathology Triage System is an offline-first software solution designed to democratize digital pathology triage in low-resource clinics. By replacing expensive Whole Slide Imaging (WSI) hardware with off-the-shelf smartphones clipped to optical microscope eyepieces, the platform captures magnified tissue imagery and streams it to a local clinic PC.
A lightweight, local machine learning model scans the image feed, identifies cellular indicators of malignancy, auto-prioritizes high-risk cases in a shared clinical worklist, and generates visual heatmaps over suspicious tissue regions to combat pathologist eye and brain fatigue.
+------------------+         USB / Local Wi-Fi RTSP          +-----------------------------------+
|  Smartphone +    | -------------------------------------->     |       Local Clinic PC            |
| Microscope Clip  | (High-Res Image / Optical Feed) |                                           |+------------------+                                               	  |  +-----------------------------+  |
                                                             | React/Electron Front-End |
                                                             |  +-----------------------------+  |
                                                             |                     |                     |
                                                             |  +-----------------------------+  |
                                                             |  | FastAPI Core Backend  |
                                                             |  +-----------------------------+  |
                                                             |                     |                     |
                                                             |  +-----------------------------+  |
                                                             |  | ONNX Runtime Engine  |
  |          (CPU/GPU)| |           |
                                                             |  +-----------------------------+  |
                                                             |                     |                     |
                                                             |  +-----------------------------+  |
                                                             |  | SQLite Local Database  |
                                                             |  +-----------------------------+  |
                                                             +-----------------------------------+

1.2 Core Goals & Scope
Zero Internet Dependency: Complete end-to-end inference, data storage, and UI rendering execute entirely on local hardware (standard consumer PC).
Zero Hardware Lock-In: Uses standard optical microscopes, smartphone optics, and consumer PC hardware.
Free & Open-Source (FOSS): Permissive licensing (MIT/Apache 2.0) to encourage global deployment, local clinical auditing, and community enhancements.
Non-Diagnostic Triage: Functions strictly as a triage and queue-management tool, directing pathologist attention to potential malignancies first without auto-issuing clinical diagnoses.
2. System Architecture & Components
The system consists of three main modules: the Edge Acquisition Layer, the Local Desktop Application Core, and the AI Inference & Heatmap Engine.
+---------------------------------------------------------------------------------------+
|                                    SYSTEM MODULES                                     |
+--------------------------+---------------------------------+--------------------------+
| 1. Acquisition Layer | 2. Local Desktop Core    |3. AI Inference Engine|
|                    	           |                           	     |                                    |
|  Optical Microscope | Electron UI (Desktop)     | ONNX Engine Execution |
| Eyepiece Adapter    | FastAPI Core Server      | - Tiling Pipeline   	       |
| Mobile Capture App |   -SQLite Database        | - Heatmap Generator  |
|    RTSP Stream        |  Local Queue Manager  | Grad-CAM / Patch Map |
+--------------------------+---------------------------------+--------------------------+

2.1 Edge Acquisition Layer (Smartphone & Microscope)
Device Setup: A mid-range smartphone is attached via an optical universal eyepiece adapter aligned with the microscope's optical axis.
Transmission Protocol:
Option A (Wired USB): Android ADB/Media Transport Protocol (MTP) / Direct WebCam Emulation (UVC) for zero-latency frame streaming.
Option B (Local Wireless): Local RTSP/HTTP video stream over an isolated, offline Wi-Fi router (no WAN access required).
Resolution Requirement: Minimum 1080p resolution at 30fps or still image capture at 12MP.
Note: live capture (UVC / RTSP streaming and snapshots) was later dropped in favour of photo upload — technicians photograph the slide with the phone and upload the file, which flows through the same ingest, blur check, calibration and AI scoring. The streaming protocol above is kept for reference only.
2.2 Local Desktop Core Application
Front-End Framework: Electron + React + TailwindCSS (packaged for offline installation via .exe/.AppImage).
Back-End Application Service: FastAPI (Python 3.11+) packaged as an offline executable via PyInstaller.
Database & Storage: SQLite for metadata, patient queue state, and slide records. Local file system for raw images and generated heatmaps.
2.3 AI Inference & Heatmap Engine
Inference Runtime: ONNX Runtime executing on CPU (using OpenVINO / DirectML acceleration) or local consumer GPU (CUDA / ROCm).
Model Pipeline: Patch-based Convolutional Neural Network (e.g., MobileNetV3 / EfficientNet-B0 fine-tuned on histopathology datasets) or lightweight Vision Transformer (ViT).
Visual Cue Generator: Patch-level probability mapping or Grad-CAM overlay rendered onto the original image as a multi-tier opacity canvas (Green/Yellow/Red).
3. Data Flow & Workflows
3.1 Ingestion & Analysis Workflow
Sample Acquisition: Technicians load a physical glass slide onto the optical microscope and capture high-field regions using the smartphone camera interface.
Local Transport: Captured image files are transmitted via local USB/Wi-Fi to the PC app's /ingest endpoint.
Pre-Processing & Tiling: The FastAPI backend resizes and tiles the high-resolution tissue image into uniform patches (e.g., 224224 pixels), dropping blank/background areas via Otsu thresholding.
Local Model Inference: ONNX Runtime executes patch classification to compute probability of malignancy (Pmalignant[0,1]).
Slide-Level Aggregation & Triage Score: The system calculates a unified risk score Sslide=(Ppatch)w1+Mean(Ptopk)w2.
Queue Reordering: SQLite updates the slide status and auto-sorts the shared worklist descending by Sslide.
Heatmap Overlay Generation: A color-mapped heatmap layer is saved to local storage for instant UI overlay when the slide is inspected.
3.2 Triage Queue State Diagram
+---------------+     Image Upload      +------------------+
|   New Slide   | --------------------> | Image Processing |
+---------------+                       +------------------+
                                                 |
                                                 v
                                        +------------------+
                                        | AI Model Running |
                                        +------------------+
                                                 |
                                                 v
                                        +------------------+
                                        | Risk Score Calculated
                                        +------------------+
                                                 |
                                                 v
+---------------+     Doctor Selection  +------------------+
| Under Review  | <-------------------- | Priority Queue   |
+---------------+                       +------------------+
        |                                (Sorted High->Low)
        v
+---------------+
| Reviewed &    |
| Archived      |
+---------------+

4. Technical Specifications & Stack
Component
Selected Technology
Rationale / Trade-offs
Mobile Capture
Native WebRTC / Android UVC / RTSP
Low latency, wide device compatibility across cheap phones. Note: dropped — photo upload only (see 2.1).
Desktop Shell
Electron
Cross-platform desktop executable with native file-system access.
Core Backend
Python (FastAPI) + PyInstaller
Rapid ML integration, native Python ONNX bindings, single-binary distribution.
Inference Framework
ONNX Runtime (CPU/DirectML)
Highly optimized cross-platform execution without requiring CUDA/NVIDIA GPUs.
Model Architecture
Patch-based MobileNetV3 / ResNet-18
Small memory footprint (50MB), fast CPU inference times.
Database
SQLite3
Zero-configuration, file-based, serverless, reliable local storage.
Distribution
Docker / Portable .zip / Native Installers
Offline installation via USB flash drive without internet dependencies.



5. Offline Infrastructure & Edge AI Strategy
5.1 Local Hardware Requirements
To ensure deployment on standard clinic PCs, minimum requirements are strictly targeted:
CPU: Intel Core i3 (8th Gen+) or AMD Ryzen 3 (or equivalent Quad-Core x86_64 CPU).
RAM: 8 GB DDR4.
Storage: 256 GB SSD (sufficient for local OS + software + temporary image cache).
GPU: Optional (Integrated Intel UHD/Iris Xe graphics utilized via DirectML/OpenVINO execution providers).
5.2 Inference Optimization Strategies
Quantization: Weights quantized from FP32 to INT8, reducing model size by $75\%$ and enabling execution in under 1.5seconds per slide on CPU.
Background Masking: Pre-filtering tissue regions using simple RGB-to-HSV color space thresholding ensures the model runs inference only on actual tissue sections, ignoring blank microscope background.
Batch Processing: Dynamic batching (N=8 or N=16) to maximize multi-core CPU thread utilization.
6. UI/UX Specifications for Pathologist Workflow
6.1 Priority Worklist Interface
Queue View: Displays patient ID, time ingested, initial clinical indication ("Routine" vs "Urgent"), and the AI Risk Flag (Red: High Probability, Yellow: Moderate Risk, Green: Low Risk).
Auto-Sorting Toggle: Defaults to "Sort by AI Risk Score" to push hidden malignant cases in routine samples to the top.
6.2 Heatmap & Guided Viewer
Dual-Layer Canvas: Displays the high-resolution tissue photo with a toggleable visual heatmap overlay ($0\%$ to $100\%$ opacity slider).
Visual Bounding/Focus Cues: Hotspots highlighted with bright region contours to guide the pathologist's eyes immediately to critical cellular structures, mitigating brain/eye fatigue.
Pathologist Action Controls: Simple status triggers: [ Confirm Malignancy ], [ Mark Benign ], [ Request Formal Biopsy ], [ Re-assign Priority ].
7. Open-Source Architecture & Data Privacy
7.1 Security & HIPAA/GDPR Compliance in Offline Environments
Zero Cloud Telemetry: Default build configuration disables all network telemetry, analytics, and phone-home pings.
Local Data Encryption: Patient metadata and stored tissue captures encrypted at rest via SQLite extensions (e.g., SQLCipher) using a clinic-managed local master key.
On-Premise Anonymization: Option to strip EXIF metadata and generate local hash IDs for patient samples before saving to local disk.
7.2 Open-Source Repository Layout
/
├── .github/                # CI/CD pipelines (packaging builds)
├── apps/
│   ├── desktop-ui/         # Electron + React interface
│   └── mobile-capture/     # Lightweight Android capture client
├── services/
│   └── backend-api/        # FastAPI core service & SQLite ORM
├── engine/
│   ├── model/              # ONNX model files & INT8 weights
│   └── pipeline/           # Image tiling, HSV masking, and inference scripts
├── docs/                   # Setup guides, microscope mounting guides, API docs
├── docker-compose.yml      # Local containerized deployment option
└── LICENSE                 # MIT License

8. Verification, Testing & Risk Mitigation
8.1 Technical Risks & Mitigations
Risk / Failure Mode
Severity
Impact
Mitigation Strategy
Optical Distortion / Out-of-Focus Photos
High
False negatives / inaccurate AI scoring
Integrated sharpness detection (Laplacian Variance test) rejecting blurry images at capture time.
Uneven Microscope Lighting
Medium
Heatmap false positives
Real-time adaptive histogram equalization (CLAHE) during image pre-processing.
Local PC Hardware Overheating/Lag
Medium
Slow queue updates
INT8 quantization, background-tissue filtering, and background processing thread throttling.
Over-reliance on AI Triage
Critical
Clinical misdiagnosis
UI explicitly warns: "AI Triage System is an prioritization assistant, not a diagnostic engine. All slides must be manually reviewed."


8.2 Test Plan
Unit Tests: Test pre-processing tiling logic, HSV background removal, and SQLite queue ordering algorithms.t
Integration Tests: Verify image upload via local HTTP endpoint, complete ONNX inference pipeline execution, and heatmap file rendering within 3seconds.
Hardware Compatibility Matrix: Test electron desktop app build across Windows 10/11, Ubuntu 22.04 LTS, and macOS on low-spec dual-core and quad-core CPUs without dedicated GPUs.
