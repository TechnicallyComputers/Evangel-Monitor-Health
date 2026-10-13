"""Evangel Projector & Monitor Health Check — Dear ImGui edition.

Read-only: runs system_profiler / ioreg to see whether the projector and
confidence-monitor hardware is plugged in, then shows setup instructions.
"""
import argparse
import base64
import re
import subprocess
import threading
from io import BytesIO

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from embedded_images import IMAGE_CONFIDENCE, IMAGE_LIVESTREAM, IMAGE_PROJECTORS

VERSION_TEXT = "Version 2.0 - Written by Alex Vanderveen"

GREEN = imgui.ImVec4(0.40, 0.85, 0.45, 1.0)
RED = imgui.ImVec4(0.95, 0.40, 0.40, 1.0)
AMBER = imgui.ImVec4(0.95, 0.75, 0.30, 1.0)

# Detection strings (unchanged from the Tk version).
PROJECTOR_ADAPTER = "USB-C VGA Multiport Adapter"
VGA_DISPLAY = "Super Video Graphics Array"
TB_ENCLOSURE = "Device Name: TB31PCIEX16"

COMMANDS = {
    "ioreg": ["ioreg", "-p", "IOUSB", "-lw0"],
    "displays": ["system_profiler", "SPDisplaysDataType"],
    "thunderbolt": ["system_profiler", "SPThunderboltDataType"],
}

# Optional saved command output, for testing on machines without macOS tools.
fixtures: dict[str, str] = {}


def run_command(key):
    if key in fixtures:
        with open(fixtures[key], "r", errors="replace") as f:
            return f.read()
    try:
        return subprocess.run(
            COMMANDS[key], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        ).stdout
    except OSError:
        return ""  # tool missing (non-macOS): treated as "not detected"


def check_projectors():
    return PROJECTOR_ADAPTER in run_command("ioreg")


def check_monitors():
    return VGA_DISPLAY in run_command("displays")


def check_enclosure():
    return TB_ENCLOSURE in run_command("thunderbolt")


def decode_image(b64):
    img = Image.open(BytesIO(base64.b64decode(b64, validate=False))).convert("RGBA")
    return np.ascontiguousarray(np.asarray(img, dtype=np.uint8))


# --------------------------------------------------------------------------
# Pages. Each result is a list of (colour, text) lines plus an optional image
# and the label/target of the button at the bottom.
# --------------------------------------------------------------------------

def projectors_page(projectors, monitors):
    if not projectors:
        return dict(
            title="Projectors Check",
            lines=[(RED, "No projectors detected."),
                   (None, ""),
                   (None, "Please check the USB-C to VGA adapter.")],
            image=None, button=("OK", "home"))
    if not monitors:
        return dict(
            title="Projectors Check",
            lines=[(GREEN, "Projectors USB adapter is plugged in."),
                   (None, ""),
                   (AMBER, "But monitors aren't configured in the 'Screen Mirroring' widget."),
                   (None, ""),
                   (None, "If the screen mirroring widget isn't working, ensure the VGA cable is\n"
                          "securely connected to the USB-C adapter, or reboot the Mac.")],
            image="projectors", button=("OK", "home"))
    return dict(
        title="Projectors Check",
        lines=[(GREEN, "Projectors and monitors are plugged in and configured correctly."),
               (None, ""),
               (None, "You should see the display on the projectors.")],
        image=None, button=("OK", "home"))


def confidence_page(enclosure):
    if not enclosure:
        return dict(
            title="Confidence Monitors Check",
            lines=[(RED, "External Thunderbolt enclosure not detected."),
                   (None, ""),
                   (None, "Please check the black StarTech box is plugged in and powered on.")],
            image=None, button=("OK", "home"))
    return dict(
        title="Confidence Monitors Check",
        lines=[(GREEN, "Thunderbolt enclosure plugged in."),
               (None, ""),
               (None, "Confirm settings in ProPresenter:\n"
                      "Pro Presenter > Screens > Configure Screens... >\n"
                      "Stage Screen 1 > Select DeckLink Duo (2) > Select 1080i60"),
               (None, ""),
               (None, "If the issue persists, try another resolution, and verify the SDI cables\n"
                      "on the enclosure are secure on both ends.")],
        image="confidence", button=("Next", "livestream"))


LIVESTREAM_PAGE = dict(
    title="Live Stream Check",
    lines=[(None, "Make sure to also set the live stream video correctly:"),
           (None, ""),
           (None, "ProPresenter > Screens > Configure Screens... >\n"
                  "Online Video > Select DeckLink Duo (1) > Select 1080p60")],
    image="livestream", button=("OK", "home"))


class App:
    def __init__(self):
        self.page = "home"          # "home" or a page dict
        self.content = None
        self.busy = False           # a check is running in the background
        self.pending = None         # result handed from worker thread to GUI thread
        self.textures = {}
        self.encoded = {"projectors": IMAGE_PROJECTORS,
                        "confidence": IMAGE_CONFIDENCE,
                        "livestream": IMAGE_LIVESTREAM}

    # GL context exists once the first frame runs, so upload lazily.
    def texture(self, name):
        if name not in self.textures:
            self.textures[name] = hello_imgui.create_texture_gpu_from_rgba_data(
                decode_image(self.encoded[name]))
        return self.textures[name]

    def start_check(self, build_page):
        if self.busy:
            return
        self.busy = True

        def work():
            self.pending = build_page()

        threading.Thread(target=work, daemon=True).start()

    def goto(self, target):
        if target == "home":
            self.content = None
        elif target == "livestream":
            self.content = LIVESTREAM_PAGE

    # ---------------------------------------------------------------- UI
    def gui(self):
        if self.pending is not None:
            self.content, self.pending, self.busy = self.pending, None, False

        avail = imgui.get_content_region_avail()
        footer_h = imgui.get_text_line_height_with_spacing() + 8
        imgui.begin_child("body", imgui.ImVec2(0, avail.y - footer_h))
        if self.content is None:
            self.home()
        else:
            self.result(self.content)
        imgui.end_child()

        imgui.separator()
        imgui.text_disabled(VERSION_TEXT)

    def centered_button(self, label, width=360, height=40):
        imgui.set_cursor_pos_x((imgui.get_window_width() - width) / 2)
        return imgui.button(label, imgui.ImVec2(width, height))

    def home(self):
        imgui.dummy(imgui.ImVec2(0, 24))
        imgui.begin_disabled(self.busy)
        if self.centered_button("Check Projectors"):
            self.start_check(lambda: projectors_page(check_projectors(), check_monitors()))
        imgui.dummy(imgui.ImVec2(0, 8))
        if self.centered_button("Check Confidence Monitors & Livestream"):
            self.start_check(lambda: confidence_page(check_enclosure()))
        imgui.end_disabled()
        imgui.dummy(imgui.ImVec2(0, 8))
        if self.centered_button("Quit"):
            hello_imgui.get_runner_params().app_shall_exit = True
        if self.busy:
            imgui.dummy(imgui.ImVec2(0, 8))
            imgui.set_cursor_pos_x((imgui.get_window_width() - imgui.calc_text_size("Checking...").x) / 2)
            imgui.text_disabled("Checking...")

    def result(self, page):
        imgui.push_font(None, imgui.get_font_size() * 1.25)
        imgui.text_unformatted(page["title"])
        imgui.pop_font()
        imgui.separator()
        imgui.dummy(imgui.ImVec2(0, 4))

        for colour, text in page["lines"]:
            if colour is None:
                imgui.text_unformatted(text)
            else:
                imgui.text_colored(colour, text)

        label, target = page["button"]
        btn_h = 40
        if page["image"]:
            tex = self.texture(page["image"])
            avail = imgui.get_content_region_avail()
            room_h = avail.y - btn_h - imgui.get_style().item_spacing.y * 3
            scale = min(avail.x / tex.width, room_h / tex.height, 1.0)
            if scale > 0:
                size = imgui.ImVec2(tex.width * scale, tex.height * scale)
                imgui.dummy(imgui.ImVec2(0, 4))
                imgui.set_cursor_pos_x((imgui.get_window_width() - size.x) / 2)
                imgui.image(imgui.ImTextureRef(tex.texture_id()), size)

        imgui.set_cursor_pos_y(imgui.get_window_height() - btn_h - 4)
        if self.centered_button(label, 160, btn_h):
            self.goto(target)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ioreg-file", help="saved `ioreg -p IOUSB -lw0` output to use instead")
    ap.add_argument("--displays-file", help="saved `system_profiler SPDisplaysDataType` output")
    ap.add_argument("--thunderbolt-file", help="saved `system_profiler SPThunderboltDataType` output")
    args = ap.parse_args()
    for key, path in (("ioreg", args.ioreg_file), ("displays", args.displays_file),
                      ("thunderbolt", args.thunderbolt_file)):
        if path:
            fixtures[key] = path

    app = App()
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Evangel Projector & Monitor Health Check"
    params.app_window_params.window_geometry.size = (900, 760)
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_window)
    params.imgui_window_params.tweaked_theme.theme = hello_imgui.ImGuiTheme_.darcula_darker
    params.callbacks.show_gui = app.gui
    params.fps_idling.enable_idling = True
    hello_imgui.run(params)


if __name__ == "__main__":
    main()
