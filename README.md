# 🎬 WebP to Video Converter  

A powerful tool to convert animated WebP images to popular video formats.

---

## 📖 About This Project  

This tool converts animated WebP images into widely used video formats such as **MP4, MKV, WebM, and GIF**.

It builds upon the excellent work of **iTroy0's WebP-Converter** (which itself was originally based on code by Dunttus).

### 🚀 What’s Different in This Version?

- ✅ Full **Command-Line Interface (CLI)** for batch processing and automation  
- ✅ **Scale factor** – enlarge video dimensions proportionally (e.g., 1.5×, 2×)  
- ✅ **Speed control** – make videos faster or slower (0.5× to 2.0×)  
- ✅ **Overlay images** – add watermarks or logos with position control  
- ✅ Improved performance and stability  
- ✅ Enhanced GUI with additional controls  

> ⚠️ This version has diverged significantly from the original.  
> It is **not a direct fork**, but a heavily modified derivative.  
> If you'd like to contribute to the original project, please visit:  
> https://github.com/iTroy0/WebP-Converter

---

## ✨ Features  

- Convert animated WebP to `.mp4`, `.mkv`, `.webm`, `.gif`  
- Batch processing – convert multiple files at once  
- Combine multiple WebPs into a single video  
- Resolution control:
  - Presets: 480p, 720p, 1080p, 4K  
  - Custom dimensions (width × height)  
- Scale factor – enlarge by multiplier (overrides presets)  
- FPS adjustment (1–60)  
- CRF quality control (18 = best quality, 30 = smallest size)  
- Speed adjustment – 0.5× (faster) to 2.0× (slower)  
- Overlay image – PNG, JPG, etc. with position options:
  - center  
  - top-left  
  - top-right  
  - bottom-left  
  - bottom-right  
- Live preview of selected WebP in GUI  
- Multithreaded frame extraction – uses all CPU cores  
- Modern dark theme GUI built with **CustomTkinter**  
- Command-line interface – ideal for servers and scripting  

---

## 🛠️ Requirements  

- Python 3.12+  
- FFmpeg (must be installed and available in your system PATH)  
- Python packages (see `requirements.txt`)  

---

## 📦 Installation  

### 1️⃣ Clone the Repository  

    git clone https://github.com/riyadhali/webp-to-video-converter.git
    cd webp-to-video-converter

### 2️⃣ (Optional) Create a Virtual Environment  

    python -m venv venv
    source venv/bin/activate      # Linux/macOS
    venv\Scripts\activate         # Windows

### 3️⃣ Install Dependencies  

    pip install -r requirements.txt

If you don't have `requirements.txt`, install manually:

    pip install customtkinter Pillow moviepy

---

## 🚀 Usage  

---

## 🖥️ Graphical User Interface (GUI)

Run without arguments:

    python converter.py

The GUI window will open.

1. Click **Choose WebP File(s)** to select files  
2. Adjust settings (format, resolution, FPS, CRF, speed, scale, overlay)  
3. Click **Start Conversion**  
4. Track progress in the progress bar  
5. Click any file in the list to preview its animation  

---

## ⌨️ Command Line Interface (CLI)

Run with input file(s) and options:

    python converter.py [input_files ...] [options]

---

### ⚙️ Options  

| Option | Description |
|--------|-------------|
| `-o, --output-dir DIR` | Output directory (default: current directory) |
| `-f, --format {.mp4,.mkv,.webm,.gif}` | Output format (default: .mp4) |
| `--fps FPS` | Frames per second (1–60, default: 16) |
| `--crf {18..30}` | Quality: lower = better (default: 22) |
| `--resolution RES` | Preset (480p, 720p, 1080p, 4K) or custom `WxH` (e.g., 1280x720) |
| `--scale FACTOR` | Scale video dimensions (e.g., 1.5 for 50% larger). Overrides `--resolution` |
| `--speed FACTOR` | Speed factor: 0.5 = faster, 2.0 = slower (default: 1.0) |
| `--combine` | Combine all input files into one video |
| `--overlay-image PATH` | Path to image to overlay on video |
| `--overlay-position POS` | center, top-left, top-right, bottom-left, bottom-right (default: center) |
| `-h, --help` | Show help message |

---

## 📌 Examples  

### Simple Conversion  

    python converter.py animation.webp

### Custom FPS and Format  

    python converter.py input.webp -o ./videos --fps 24 --format .mp4

### Scale to 150%  

    python converter.py input.webp --scale 1.5

### Combine Two Files, Slow Them Down, Add Watermark  

    python converter.py file1.webp file2.webp --combine --speed 2.0 --overlay-image logo.png --overlay-position bottom-right

### Custom Resolution  

    python converter.py input.webp --resolution 1920x1080

---

## ⚠️ Notes  

- When `--scale` is used, the final dimensions are calculated as:  

      round(original_width × scale) × round(original_height × scale)

  This overrides any resolution preset or custom dimensions.  

- For GIF output, `--combine` is **not supported**.  

- Overlay images are resized proportionally if larger than the video frame.  

- A temporary folder `temp_frames` is created during processing and automatically removed after conversion.  

---

## 🙏 Credits  

This project is a derivative work based on:

- **iTroy0/WebP-Converter** – Original project by Troy  
- Inspired by initial code from Dunttus  

Built with:

- CustomTkinter – modern UI  
- MoviePy – video processing  
- Pillow – image handling  

We sincerely thank all original authors for their contributions to the open-source community.

---

## 📜 License  

This project is licensed under the **MIT License**.  
See the `LICENSE` file for details.

---

## 🤝 Contributing  

Contributions, issues, and feature requests are welcome!  
Feel free to open an issue or submit a pull request.

If you wish to contribute to the original project, please visit:  
https://github.com/iTroy0/WebP-Converter  

This repository is a separate fork with substantial modifications.

---
