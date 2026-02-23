#!/usr/bin/env python3
# WebP to Video Converter - Enhanced Version
#
# Original project by iTroy0: https://github.com/iTroy0/WebP-Converter
# Original code inspired by Dunttus (as credited in the original project)
#
# This enhanced version includes significant new features and reliability fixes:
#   - Full command-line interface for batch/headless operation
#   - Overlay image support with position control
#   - Speed factor adjustment (slow-down/speed-up)
#   - Scale factor for enlarging video dimensions
#   - Core engine refactored for CLI/GUI separation
#   - Robust temp-dir handling (TemporaryDirectory)
#   - Wait for ThreadPoolExecutor tasks before encoding
#   - RGB conversion for video outputs to avoid alpha issues
#   - FFmpeg existence check and better logging
#
# Developed by: RIYADH ALI + DEEPSEEK(AI)
# Date: 2026-02-24 (v1.0.1)
# License: MIT (same as original)

import os
import sys
import uuid
import json
import threading
import subprocess
import argparse
import math
import logging
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageSequence, ImageTk
from moviepy import ImageSequenceClip

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("webp_converter")

# -------------------- Core Conversion Engine --------------------
class ConverterCore:
    """Conversion logic independent of GUI."""

    def __init__(self):
        self.resolution_preset = "Same Resolution"
        self.custom_width = None
        self.custom_height = None
        self.scale_factor = 1.0
        self.overlay_image_path = None
        self.overlay_position = "center"
        self.fps = 16
        self.crf = 22
        self.output_format = ".mp4"
        self.combine_videos = False
        self.webp_files = []
        self.output_folder = os.getcwd()
        self.speed_factor = 1.0
        self.max_workers = max(1, os.cpu_count() or 4)

        # Internal state
        self.temp_dir = None
        self.overlay_img = None

    def check_ffmpeg(self):
        """Ensure ffmpeg is installed and available."""
        if shutil.which("ffmpeg") is None:
            logger.warning("ffmpeg not found in PATH. MoviePy may fail to encode videos.")
            return False
        return True

    def load_overlay(self):
        """Load overlay image if path exists and is valid."""
        if not self.overlay_image_path or not os.path.exists(self.overlay_image_path):
            return False
        try:
            self.overlay_img = Image.open(self.overlay_image_path).convert("RGBA")
            return True
        except Exception as e:
            logger.error(f"Error loading overlay image: {e}")
            self.overlay_img = None
            return False

    def get_target_size(self, original_size):
        """
        Determine target dimensions based on:
        - scale_factor (if != 1.0)
        - custom width/height (if set)
        - resolution preset
        Otherwise return original size.
        """
        w, h = original_size

        # Priority 1: scale factor
        if self.scale_factor != 1.0 and self.scale_factor > 0:
            new_w = int(round(w * self.scale_factor))
            new_h = int(round(h * self.scale_factor))
            return (new_w, new_h)

        # Priority 2: custom resolution
        if str(self.resolution_preset).lower() == "custom" and self.custom_width and self.custom_height:
            return (self.custom_width, self.custom_height)

        # Priority 3: preset resolution (case-insensitive)
        preset = str(self.resolution_preset).lower()
        if preset in RESOLUTION_MAP:
            return RESOLUTION_MAP[preset]

        # Default: original size
        return original_size

    def apply_overlay(self, frame):
        """Apply overlay to frame if enabled."""
        if self.overlay_img is None:
            return frame
        frame = frame.convert("RGBA")
        overlay = self.overlay_img.copy()

        # Resize overlay if larger than frame
        if overlay.width > frame.width or overlay.height > frame.height:
            overlay.thumbnail((frame.width, frame.height), Image.LANCZOS)

        pos = self.overlay_position
        if pos == "center":
            x = (frame.width - overlay.width) // 2
            y = (frame.height - overlay.height) // 2
        elif pos == "top-left":
            x = y = 0
        elif pos == "top-right":
            x = frame.width - overlay.width
            y = 0
        elif pos == "bottom-left":
            x = 0
            y = frame.height - overlay.height
        elif pos == "bottom-right":
            x = frame.width - overlay.width
            y = frame.height - overlay.height
        else:
            x = y = 0

        combined = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        combined.paste(overlay, (x, y), overlay)
        return Image.alpha_composite(frame, combined)

    def save_frame(self, frame, path):
        """Resize (with scaling if needed), apply overlay, and save."""
        try:
            # Determine target size
            target_size = self.get_target_size(frame.size)
            if target_size != frame.size:
                frame = frame.resize(target_size, Image.LANCZOS)

            # Apply overlay
            if self.overlay_img is not None:
                frame = self.apply_overlay(frame)

            # Convert to appropriate mode before saving
            if self.output_format != ".gif":
                frame = frame.convert("RGB")
            else:
                frame = frame.convert("RGBA")

            frame.save(path, format="PNG")
        except Exception as e:
            logger.error(f"Error saving frame {path}: {e}")

    def extract_frames(self, webp_file, start_idx=0):
        """Extract frames, apply speed factor, and save. Returns list of frame paths."""
        frames = []
        try:
            # Read all frames from WebP
            all_frames = []
            with Image.open(webp_file) as im:
                for frame in ImageSequence.Iterator(im):
                    all_frames.append(frame.copy())

            # Apply speed factor by adjusting frame count
            if self.speed_factor != 1.0:
                original_count = len(all_frames)
                if original_count == 0:
                    return []
                new_count = max(1, int(round(original_count * self.speed_factor)))
                indices = [min(original_count - 1, int(i * original_count / new_count)) for i in range(new_count)]
                adjusted_frames = [all_frames[i] for i in indices]
            else:
                adjusted_frames = all_frames

            # Ensure temp dir exists
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

            # Submit frame saving tasks
            futures = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for i, frame in enumerate(adjusted_frames):
                    frame_idx = start_idx + i
                    frame_path = Path(self.temp_dir) / f"frame_{frame_idx:06d}.png"
                    futures.append(executor.submit(self.save_frame, frame, str(frame_path)))
                    frames.append(str(frame_path))

                # Wait for all saves to complete
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception as e:
                        logger.error(f"Frame save failed: {e}")

        except Exception as e:
            logger.error(f"Error extracting frames from {webp_file}: {e}")

        return frames

    def convert_to_video(self, frames, output_path):
        """Create video/GIF from list of frame paths."""
        if not frames:
            logger.warning("No frames to encode.")
            return

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if self.output_format == ".gif":
            try:
                images = [Image.open(f).convert("RGBA") for f in frames]
                images[0].save(
                    output_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=int(1000 / max(1, self.fps)),
                    loop=0,
                    optimize=True,
                    quality=95,
                    disposal=2
                )
                logger.info(f"GIF created: {output_path}")
            except Exception as e:
                logger.error(f"Error creating GIF: {e}")
        else:
            try:
                clip = ImageSequenceClip(frames, fps=self.fps)
                codec = {
                    ".mp4": "libx264",
                    ".mkv": "libx264",
                    ".webm": "libvpx-vp9"
                }.get(self.output_format, "libx264")
                crf = str(self.crf)
                clip.write_videofile(
                    output_path,
                    codec=codec,
                    audio=False,
                    preset="medium",
                    ffmpeg_params=["-crf", crf, "-pix_fmt", "yuv420p"],
                    verbose=False,
                    logger=None
                )
                clip.close()
                logger.info(f"Video created: {output_path}")
            except Exception as e:
                logger.error(f"Error creating video: {e}")

    def run(self, progress_callback=None, keep_temp=False):
        """Run conversion process. Uses TemporaryDirectory to avoid temp leaks."""
        self.check_ffmpeg()
        self.load_overlay()

        total_files = len(self.webp_files)
        if total_files == 0:
            logger.warning("No input files.")
            return

        steps_per_file = 2  # extract + encode
        total_steps = total_files * steps_per_file
        current_step = 0

        if self.combine_videos and self.output_format == ".gif":
            logger.error("Cannot combine multiple files into a GIF. Exiting.")
            return

        # Create temporary directory
        if keep_temp:
            temp_dir_obj = None
            self.temp_dir = Path(tempfile.mkdtemp(prefix="webp_conv_"))
        else:
            temp_dir_obj = tempfile.TemporaryDirectory(prefix="webp_conv_")
            self.temp_dir = Path(temp_dir_obj.name)

        try:
            if self.combine_videos:
                all_frames = []
                for idx, webp_file in enumerate(self.webp_files, 1):
                    if progress_callback:
                        progress_callback(f"Extracting {idx}/{total_files}")
                    extracted = self.extract_frames(webp_file, start_idx=len(all_frames))
                    all_frames.extend(extracted)
                    current_step += 1
                    if progress_callback:
                        progress_callback(None, current_step / total_steps)

                if all_frames:
                    output_path = os.path.join(
                        self.output_folder,
                        f"combined_{uuid.uuid4().hex[:6]}{self.output_format}"
                    )
                    if progress_callback:
                        progress_callback("Encoding combined video...")
                    self.convert_to_video(all_frames, output_path)
                    current_step += 1
                    if progress_callback:
                        progress_callback(None, current_step / total_steps)

                    # Clean per-file frames
                    for f in all_frames:
                        try:
                            Path(f).unlink(missing_ok=True)
                        except Exception:
                            pass
            else:
                for idx, webp_file in enumerate(self.webp_files, 1):
                    if progress_callback:
                        progress_callback(f"Extracting {idx}/{total_files}")
                    frames = self.extract_frames(webp_file)
                    current_step += 1
                    if progress_callback:
                        progress_callback(None, current_step / total_steps)

                    if frames:
                        output_path = os.path.join(
                            self.output_folder,
                            f"{Path(webp_file).stem}_{uuid.uuid4().hex[:6]}{self.output_format}"
                        )
                        if progress_callback:
                            progress_callback(f"Encoding {idx}/{total_files}")
                        self.convert_to_video(frames, output_path)
                        current_step += 1
                        if progress_callback:
                            progress_callback(None, current_step / total_steps)

                        for f in frames:
                            try:
                                Path(f).unlink(missing_ok=True)
                            except Exception:
                                pass
        finally:
            # Clean up temporary directory
            if not keep_temp and temp_dir_obj is not None:
                temp_dir_obj.cleanup()
            elif keep_temp:
                logger.info(f"Temporary frames kept at: {self.temp_dir}")

        if progress_callback:
            progress_callback("Done!")


# -------------------- GUI Application --------------------

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


SETTINGS_FILE = "config.json"

RESOLUTION_MAP = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160)
}

# Also include capitalized versions for display
RESOLUTION_PRESETS = ["Same Resolution", "480p", "720p", "1080p", "4K", "Custom"]


def load_settings():
    """Load settings from JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Failed to load settings: {e}")
        return {}


def save_settings(data):
    """Save settings to JSON file."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


class WebPConverterApp(ctk.CTk):
    """Main GUI application class."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.configure(bg="#212121")
        self.title("WebP to Video Converter")
        self.geometry("900x850")
        self.minsize(850, 700)
        self.resizable(True, True)

        # Set window icon
        self.icon_path = resource_path("app_icon.ico")
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

        self.core = ConverterCore()
        self.webp_files = []
        self.selected_file = None
        self.file_rows = {}
        self.output_folder = os.getcwd()
        self.output_format = ctk.StringVar(value=".mp4")
        self.fps_value = ctk.IntVar(value=16)
        self.combine_videos = ctk.BooleanVar(value=False)
        self.resolution_preset = ctk.StringVar(value="Same Resolution")
        self.crf_value = ctk.IntVar(value=22)
        self.speed_factor = ctk.DoubleVar(value=1.0)
        self.scale_factor = ctk.DoubleVar(value=1.0)
        self.use_scale = ctk.BooleanVar(value=False)

        self.overlay_enabled = ctk.BooleanVar(value=False)
        self.overlay_image_path = None
        self.overlay_position = ctk.StringVar(value="center")

        self.preview_frames = []          # list of PIL Images
        self.preview_images_tk = []       # list of ImageTk.PhotoImage
        self.preview_index = 0
        self.preview_running = False
        self.preview_thread = None

        self.scrollable_frame = ctk.CTkScrollableFrame(
            self,
            scrollbar_button_color="#3a3a3a",
            scrollbar_button_hover_color="#505050",
            fg_color="#212121",
            corner_radius=10
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.create_widgets()
        self.load_previous_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """Create all GUI widgets."""
        # Title
        title_frame = ctk.CTkFrame(self.scrollable_frame)
        title_frame.pack(pady=10)
        ctk.CTkLabel(title_frame, text="WebP to Video Converter", font=("Arial", 28, "bold")).pack()

        settings_frame = ctk.CTkFrame(self.scrollable_frame)
        settings_frame.pack(fill="x", pady=15)

        # File selection
        file_buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        file_buttons_frame.pack(pady=10)
        ctk.CTkButton(file_buttons_frame, text="Choose WebP File(s)", command=self.select_webps).pack(side="left", padx=10)
        ctk.CTkButton(file_buttons_frame, text="Select Output Folder", command=self.select_output_folder).pack(side="left", padx=10)

        # Format and Resolution
        format_res_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        format_res_frame.pack(pady=10)

        format_label = ctk.CTkLabel(format_res_frame, text="Format:", font=("Arial", 14))
        format_label.pack(side="left", padx=(0, 10))
        format_menu = ctk.CTkOptionMenu(
            format_res_frame,
            values=[".mp4", ".mkv", ".webm", ".gif"],
            variable=self.output_format
        )
        format_menu.pack(side="left", padx=(0, 30))

        res_label = ctk.CTkLabel(format_res_frame, text="Resolution:", font=("Arial", 14))
        res_label.pack(side="left", padx=(0, 10))
        res_menu = ctk.CTkOptionMenu(
            format_res_frame,
            values=RESOLUTION_PRESETS,
            variable=self.resolution_preset,
            command=self.toggle_custom_res_entry
        )
        res_menu.pack(side="left")

        self.custom_res_width = ctk.CTkEntry(
            format_res_frame, width=70, placeholder_text="Width",
            state='disabled', fg_color="#3a3a3a", placeholder_text_color="#999999"
        )
        self.custom_res_width.pack(side="left", padx=(10, 5))
        x_label = ctk.CTkLabel(format_res_frame, text="x", font=("Arial", 14))
        x_label.pack(side="left")
        self.custom_res_height = ctk.CTkEntry(
            format_res_frame, width=70, placeholder_text="Height",
            state='disabled', fg_color="#3a3a3a", placeholder_text_color="#999999"
        )
        self.custom_res_height.pack(side="left", padx=(5, 0))

        # Scale factor
        scale_frame = ctk.CTkFrame(settings_frame)
        scale_frame.pack(fill="x", pady=5)
        self.scale_checkbox = ctk.CTkCheckBox(
            scale_frame, text="Enable Scale Factor", variable=self.use_scale,
            command=self.toggle_scale_controls
        )
        self.scale_checkbox.pack(side="left", padx=10)

        self.scale_slider = ctk.CTkSlider(
            scale_frame, from_=1.0, to=4.0, number_of_steps=60,
            variable=self.scale_factor, state="disabled"
        )
        self.scale_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.scale_label = ctk.CTkLabel(scale_frame, text=f"{self.scale_factor.get():.2f}x", font=("Arial", 14))
        self.scale_label.pack(side="left", padx=10)

        def update_scale(value):
            self.scale_label.configure(text=f"{float(value):.2f}x")
        self.scale_slider.configure(command=update_scale)

        # FPS
        ctk.CTkLabel(settings_frame, text="Frames Per Second (FPS):", font=("Arial", 16)).pack(pady=(0, 5))
        ctk.CTkLabel(settings_frame, text="Range: 1 to 60", font=("Arial", 14)).pack(pady=(0, 5))
        fps_slider = ctk.CTkSlider(settings_frame, from_=1, to=60, number_of_steps=59, variable=self.fps_value)
        fps_slider.pack(pady=0, padx=50, fill="x")
        self.fps_label = ctk.CTkLabel(settings_frame, text=f"FPS: {self.fps_value.get()}", font=("Arial", 14))
        self.fps_label.pack(pady=(0, 5))

        def update_fps_label(value):
            self.fps_label.configure(text=f"FPS: {int(float(value))}")
        fps_slider.configure(command=update_fps_label)

        # CRF
        ctk.CTkLabel(settings_frame, text="Compression Quality (CRF):", font=("Arial", 16)).pack(pady=(1, 5))
        ctk.CTkLabel(settings_frame, text="Range: 18 (best) to 30 (smaller)", font=("Arial", 14)).pack(pady=(0, 5))
        crf_slider = ctk.CTkSlider(settings_frame, from_=18, to=30, number_of_steps=12, variable=self.crf_value)
        crf_slider.pack(pady=5, padx=50, fill="x")
        self.crf_label = ctk.CTkLabel(settings_frame, text=f"CRF: {self.crf_value.get()}", font=("Arial", 14))
        self.crf_label.pack(pady=(0, 5))

        def update_crf_label(value):
            self.crf_label.configure(text=f"CRF: {int(float(value))}")
        crf_slider.configure(command=update_crf_label)

        # Speed factor
        speed_frame = ctk.CTkFrame(settings_frame)
        speed_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(speed_frame, text="Speed Factor:", font=("Arial", 14)).pack(side="left", padx=10)
        ctk.CTkLabel(speed_frame, text="0.5 (faster) – 2.0 (slower)", font=("Arial", 12)).pack(side="left", padx=5)
        speed_slider = ctk.CTkSlider(speed_frame, from_=0.5, to=2.0, number_of_steps=30, variable=self.speed_factor)
        speed_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.speed_label = ctk.CTkLabel(speed_frame, text=f"{self.speed_factor.get():.2f}x", font=("Arial", 14))
        self.speed_label.pack(side="left", padx=10)

        def update_speed(value):
            self.speed_label.configure(text=f"{float(value):.2f}x")
        speed_slider.configure(command=update_speed)

        # Overlay section
        overlay_frame = ctk.CTkFrame(settings_frame)
        overlay_frame.pack(fill="x", pady=10)

        self.overlay_checkbox = ctk.CTkCheckBox(
            overlay_frame, text="Add overlay image", variable=self.overlay_enabled,
            command=self.toggle_overlay_controls
        )
        self.overlay_checkbox.pack(side="left", padx=10)

        self.overlay_select_btn = ctk.CTkButton(
            overlay_frame, text="Select Overlay Image",
            command=self.select_overlay_image, state="disabled"
        )
        self.overlay_select_btn.pack(side="left", padx=10)

        self.overlay_position_menu = ctk.CTkOptionMenu(
            overlay_frame,
            values=["center", "top-left", "top-right", "bottom-left", "bottom-right"],
            variable=self.overlay_position,
            state="disabled"
        )
        self.overlay_position_menu.pack(side="left", padx=10)

        self.overlay_status = ctk.CTkLabel(overlay_frame, text="", text_color="gray")
        self.overlay_status.pack(side="left", padx=10)

        # Combine checkbox
        ctk.CTkCheckBox(settings_frame, text="Combine all videos into one", variable=self.combine_videos).pack(pady=(1, 5))

        # Progress
        progress_frame = ctk.CTkFrame(self.scrollable_frame)
        progress_frame.pack(fill="x", pady=20)

        ctk.CTkButton(progress_frame, text="Start Conversion", command=self.start_conversion_thread, font=("Arial", 18)).pack(pady=10)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(pady=(0, 5), fill="x", padx=40)
        self.progress_bar.set(0)

        self.progress_text = ctk.CTkLabel(progress_frame, text="0%", font=("Arial", 14))
        self.progress_text.pack(pady=0)

        # Preview and file list
        preview_frame = ctk.CTkFrame(self.scrollable_frame)
        preview_frame.pack(fill="both", expand=True, pady=10)

        ctk.CTkLabel(preview_frame, text="Preview Selected Files:", font=("Arial", 16)).pack(pady=(0, 10))
        self.preview_label = ctk.CTkLabel(preview_frame, text="No preview")
        self.preview_label.pack(pady=(0, 10))

        preview_button_frame = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_button_frame.pack(pady=(10, 0))

        ctk.CTkButton(preview_button_frame, text="Clear List", command=self.clear_file_list).pack(side="left", padx=10)
        ctk.CTkButton(preview_button_frame, text="Open Output Folder", command=self.open_output_folder).pack(side="left", padx=10)

        self.files_list_frame = ctk.CTkScrollableFrame(preview_frame, height=200)
        self.files_list_frame.pack(pady=(15, 10), fill="both", expand=True, padx=20)

    # -------------------- GUI Helpers --------------------
    def toggle_custom_res_entry(self, choice):
        """Enable/disable custom resolution entry fields."""
        if choice == "Custom":
            self.custom_res_width.configure(state='normal', fg_color="#2b2b2b", placeholder_text_color="#cccccc")
            self.custom_res_height.configure(state='normal', fg_color="#2b2b2b", placeholder_text_color="#cccccc")
        else:
            self.custom_res_width.delete(0, 'end')
            self.custom_res_height.delete(0, 'end')
            self.custom_res_width.configure(state='disabled', fg_color="#3a3a3a", placeholder_text_color="#999999")
            self.custom_res_height.configure(state='disabled', fg_color="#3a3a3a", placeholder_text_color="#999999")

    def toggle_scale_controls(self):
        """Enable/disable scale slider based on checkbox."""
        self.scale_slider.configure(state="normal" if self.use_scale.get() else "disabled")

    def toggle_overlay_controls(self):
        """Enable/disable overlay controls based on checkbox."""
        state = "normal" if self.overlay_enabled.get() else "disabled"
        self.overlay_select_btn.configure(state=state)
        self.overlay_position_menu.configure(state=state)
        if not state == "normal":
            self.overlay_status.configure(text="")

    def select_overlay_image(self):
        """Open file dialog to choose overlay image."""
        file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff")])
        if file:
            self.overlay_image_path = file
            self.overlay_status.configure(text=os.path.basename(file), text_color="lightgreen")

    def select_webps(self):
        """Open file dialog to choose WebP files."""
        files = filedialog.askopenfilenames(filetypes=[("WebP files", "*.webp")])
        if files:
            self.webp_files = list(files)
            self.update_files_list()
            if self.webp_files:
                self.set_selected_file(self.webp_files[0])
                self.show_preview(self.webp_files[0])

    def select_output_folder(self):
        """Open directory dialog to choose output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.save_current_settings()

    def show_preview(self, filepath):
        """Load and display preview of selected WebP file."""
        # Stop any running preview
        self.preview_running = False
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread.join(timeout=0.5)

        try:
            with Image.open(filepath) as im:
                frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]

            # Resize frames for preview (max 480x270)
            max_w, max_h = 480, 270
            self.preview_frames = []
            self.preview_images_tk = []
            for f in frames:
                f.thumbnail((max_w, max_h), Image.LANCZOS)
                self.preview_frames.append(f)
                self.preview_images_tk.append(ImageTk.PhotoImage(f))

            if self.preview_images_tk:
                self.preview_index = 0
                self.preview_label.configure(image=self.preview_images_tk[0], text="")
                self.preview_running = True
                self.animate_preview()
        except Exception as e:
            logger.debug(f"Preview failed: {e}")
            self.preview_label.configure(image=None, text="No preview available")

    def animate_preview(self):
        """Run preview animation in a separate thread."""
        def run_preview():
            while self.preview_running and self.preview_images_tk:
                try:
                    img_tk = self.preview_images_tk[self.preview_index]
                    # Schedule UI update in main thread
                    self.after(0, lambda im=img_tk: self.preview_label.configure(image=im, text=""))
                    self.preview_index = (self.preview_index + 1) % len(self.preview_images_tk)
                    time.sleep(max(0.03, 1.0 / max(1, self.fps_value.get())))
                except Exception:
                    break

        self.preview_thread = threading.Thread(target=run_preview, daemon=True)
        self.preview_thread.start()

    def pause_preview(self):
        """Pause preview animation."""
        self.preview_running = False

    def resume_preview(self):
        """Resume preview animation."""
        if not self.preview_running:
            self.preview_running = True
            self.animate_preview()

    def update_files_list(self):
        """Refresh the list of selected WebP files in the GUI."""
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()
        self.file_rows.clear()

        for idx, path in enumerate(self.webp_files):
            frame = ctk.CTkFrame(self.files_list_frame)
            frame.pack(fill="x", pady=2, padx=5)

            lbl = ctk.CTkLabel(frame, text=os.path.basename(path))
            lbl.pack(side="left", padx=5)

            btn_preview = ctk.CTkButton(frame, text="Preview", width=80,
                                         command=lambda p=path: self.show_preview(p))
            btn_preview.pack(side="right", padx=5)

            btn_remove = ctk.CTkButton(frame, text="Remove", width=80,
                                       fg_color="#8b0000", hover_color="#a00000",
                                       command=lambda i=idx: self.remove_file(i))
            btn_remove.pack(side="right", padx=5)

            self.file_rows[idx] = frame

    def set_selected_file(self, path):
        """Mark the currently selected file."""
        self.selected_file = path

    def remove_file(self, index):
        """Remove a file from the list by index."""
        try:
            if 0 <= index < len(self.webp_files):
                del self.webp_files[index]
                self.update_files_list()
                if self.webp_files:
                    self.set_selected_file(self.webp_files[0])
                    self.show_preview(self.webp_files[0])
                else:
                    self.preview_label.configure(image=None, text="No preview")
        except Exception as e:
            logger.debug(f"remove_file error: {e}")

    def clear_file_list(self):
        """Clear all selected files."""
        self.webp_files = []
        self.update_files_list()
        self.preview_label.configure(image=None, text="No preview")

    def open_output_folder(self):
        """Open the output folder in system file explorer."""
        try:
            if os.path.exists(self.output_folder):
                if sys.platform.startswith("win"):
                    os.startfile(self.output_folder)
                elif sys.platform.startswith("darwin"):
                    subprocess.Popen(["open", self.output_folder])
                else:
                    subprocess.Popen(["xdg-open", self.output_folder])
        except Exception as e:
            logger.debug(f"open_output_folder failed: {e}")

    def start_conversion_thread(self):
        """Start conversion in a background thread."""
        t = threading.Thread(target=self.start_conversion, daemon=True)
        t.start()

    def start_conversion(self):
        """Prepare core settings and run conversion."""
        if not self.webp_files:
            self.show_toast("⚠️ Please select at least one WebP file.", bg="#882222")
            return

        self.progress_bar.set(0)
        self.progress_text.configure(text="Starting...")

        # Copy GUI settings to core
        self.core.webp_files = self.webp_files
        self.core.output_folder = self.output_folder
        self.core.output_format = self.output_format.get()
        self.core.fps = int(self.fps_value.get())
        self.core.crf = int(self.crf_value.get())
        self.core.combine_videos = self.combine_videos.get()
        self.core.resolution_preset = self.resolution_preset.get()
        self.core.speed_factor = float(self.speed_factor.get())
        self.core.max_workers = max(1, min(32, (os.cpu_count() or 4)))

        # Scale factor handling
        self.core.scale_factor = float(self.scale_factor.get()) if self.use_scale.get() else 1.0

        # Custom resolution
        if self.resolution_preset.get() == "Custom":
            w = self.custom_res_width.get()
            h = self.custom_res_height.get()
            if w.isdigit() and h.isdigit():
                self.core.custom_width = int(w)
                self.core.custom_height = int(h)
            else:
                self.core.custom_width = None
                self.core.custom_height = None
        else:
            self.core.custom_width = None
            self.core.custom_height = None

        # Overlay
        if self.overlay_enabled.get() and self.overlay_image_path:
            self.core.overlay_image_path = self.overlay_image_path
            self.core.overlay_position = self.overlay_position.get()
        else:
            self.core.overlay_image_path = None
            self.core.overlay_img = None

        def progress_callback(msg=None, fraction=None):
            try:
                if msg is not None:
                    self.progress_text.configure(text=msg)
                if fraction is not None:
                    self.progress_bar.set(fraction)
                    self.progress_text.configure(text=f"{int(fraction*100)}%")
                self.update_idletasks()
            except Exception:
                pass

        try:
            self.core.run(progress_callback)
            self.show_toast("✅ Conversion completed!", bg="#225522")
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            self.show_toast("Conversion failed — see logs", bg="#552222")

    def save_current_settings(self):
        """Save current settings to JSON."""
        data = {
            "output_folder": self.output_folder,
            "output_format": self.output_format.get(),
            "fps": int(self.fps_value.get()),
            "crf": int(self.crf_value.get()),
            "resolution": self.resolution_preset.get(),
            "scale_enabled": bool(self.use_scale.get()),
            "scale_factor": float(self.scale_factor.get()),
            "speed_factor": float(self.speed_factor.get()),
            "overlay_enabled": bool(self.overlay_enabled.get()),
            "overlay_image": self.overlay_image_path,
            "overlay_position": self.overlay_position.get()
        }
        save_settings(data)

    def load_previous_settings(self):
        """Load settings from JSON and apply to GUI."""
        data = load_settings()
        if not data:
            return

        try:
            self.output_folder = data.get("output_folder", self.output_folder)
            self.output_format.set(data.get("output_format", self.output_format.get()))
            self.fps_value.set(int(data.get("fps", self.fps_value.get())))
            self.crf_value.set(int(data.get("crf", self.crf_value.get())))
            self.resolution_preset.set(data.get("resolution", self.resolution_preset.get()))
            self.use_scale.set(bool(data.get("scale_enabled", self.use_scale.get())))
            self.scale_factor.set(float(data.get("scale_factor", self.scale_factor.get())))
            self.speed_factor.set(float(data.get("speed_factor", self.speed_factor.get())))
            self.overlay_enabled.set(bool(data.get("overlay_enabled", self.overlay_enabled.get())))
            self.overlay_image_path = data.get("overlay_image")
            if self.overlay_image_path and os.path.exists(self.overlay_image_path):
                self.overlay_status.configure(text=os.path.basename(self.overlay_image_path))
            else:
                self.overlay_image_path = None
            self.overlay_position.set(data.get("overlay_position", self.overlay_position.get()))

            # Enable/disable controls based on loaded values
            self.toggle_scale_controls()
            self.toggle_overlay_controls()
        except Exception as e:
            logger.debug(f"Failed to load previous settings: {e}")

    def show_toast(self, message, duration=2500, bg="#333333"):
        """Show a transient toast notification."""
        try:
            toast = ctk.CTkToplevel(self)
            toast.overrideredirect(True)
            toast.configure(fg_color=bg)
            toast.wm_attributes("-topmost", True)

            label = ctk.CTkLabel(toast, text=message, font=("Arial", 14), text_color="white")
            label.pack(padx=20, pady=10)

            # Position near bottom-right of main window
            x = self.winfo_x() + self.winfo_width() - 320
            y = self.winfo_y() + self.winfo_height() - 100
            toast.geometry(f"300x60+{x}+{y}")

            self.after(duration, toast.destroy)
        except Exception:
            pass

    def on_closing(self):
        """Handle window closing event."""
        self.preview_running = False
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread.join(timeout=1.0)
        self.destroy()


# -------------------- Batch Mode --------------------
def batch_convert(args):
    """Run conversion from command line without GUI."""
    core = ConverterCore()
    core.webp_files = args.input_files
    core.output_folder = args.output_dir
    core.output_format = args.format
    core.fps = args.fps
    core.crf = args.crf
    core.combine_videos = args.combine
    core.overlay_image_path = args.overlay_image
    core.overlay_position = args.overlay_position
    core.speed_factor = args.speed
    core.max_workers = args.workers or max(1, os.cpu_count() or 4)

    # Handle scale factor
    if args.scale:
        core.scale_factor = args.scale
    else:
        core.scale_factor = 1.0

    # Parse resolution (if scale is set, it overrides preset/custom)
    if args.resolution and args.scale is None:
        res_lower = args.resolution.lower()
        if res_lower in RESOLUTION_MAP:
            core.resolution_preset = res_lower
        elif 'x' in args.resolution:
            try:
                w, h = map(int, args.resolution.split('x'))
                core.custom_width = w
                core.custom_height = h
                core.resolution_preset = "Custom"
            except Exception:
                logger.warning("Invalid custom resolution format. Using original resolution.")
        else:
            logger.warning("Unknown resolution preset. Using original resolution.")

    def progress(msg=None, fraction=None):
        if msg:
            print(msg)
        if fraction is not None:
            print(f"Progress: {int(fraction*100)}%")

    core.run(progress, keep_temp=args.keep_temp)
    print("Batch conversion finished.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert WebP animated images to video with optional overlay.",
        epilog="Examples:\n"
               "  python converter.py animation.webp\n"
               "  python converter.py *.webp -o ./videos --fps 24 --format .mp4\n"
               "  python converter.py input.webp --scale 1.5 --overlay-image logo.png\n"
               "  python converter.py file1.webp file2.webp --combine --speed 2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_files", nargs="*", help="WebP file(s) to convert")
    parser.add_argument("-o", "--output-dir", default=os.getcwd(),
                        help="Output directory (default: current directory)")
    parser.add_argument("-f", "--format", choices=[".mp4", ".mkv", ".webm", ".gif"],
                        default=".mp4", help="Output video format")
    parser.add_argument("--fps", type=int, default=16,
                        help="Frames per second (default: 16)")
    parser.add_argument("--crf", type=int, default=22, choices=range(18, 31),
                        help="CRF value 18-30 (default: 22)")
    parser.add_argument("--resolution",
                        help="Resolution preset (480p,720p,1080p,4K) or custom WxH (e.g. 1280x720)")
    parser.add_argument("--combine", action="store_true",
                        help="Combine all input files into one video")
    parser.add_argument("--overlay-image",
                        help="Path to an image to overlay on the video")
    parser.add_argument("--overlay-position",
                        choices=["center", "top-left", "top-right", "bottom-left", "bottom-right"],
                        default="center", help="Position of overlay image")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Speed factor: 0.5 (faster) to 2.0 (slower) (default: 1.0)")
    parser.add_argument("--scale", type=float,
                        help="Scale factor for video dimensions (e.g., 1.5 for 50%% larger). Overrides --resolution if set.")
    parser.add_argument("--workers", type=int,
                        help="Number of worker threads to use for frame saving (default: CPU cores)")
    parser.add_argument("--keep-temp", action="store_true",
                        help="Keep temporary frames directory after completion (for debugging)")
    args = parser.parse_args()

    if args.input_files:
        batch_convert(args)
    else:
        app = WebPConverterApp()
        app.mainloop()


if __name__ == "__main__":
    main()
