#!/usr/bin/env python3

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "project-skysports.html"
BG_PATH = ROOT / "source/picture/skysports/synthesis board.jpg"
OUT_PATH = ROOT / "source/picture/skysports/insight-board-rendered.svg"
OVERLAY_OUT_PATH = ROOT / "source/picture/skysports/insight-board-overlay.svg"

MARGIN_X = 40
TOP_PADDING = 24
TITLE_Y = 74
BOARD_Y = 102
SECTION_GAP = 60
NOTE_SIZE = 94
NOTE_GAP = 8
NOTE_STEP = NOTE_SIZE + NOTE_GAP
COLUMN_WIDTH = NOTE_SIZE * 3 + NOTE_GAP * 2
NOTE_FONT_SIZE = 7.2
NOTE_LINE_HEIGHT = 9.1
NOTE_TEXT_WIDTH = NOTE_SIZE - 12
NOTE_TEXT_X_PAD = 6
NOTE_TEXT_Y_PAD = 10
TITLE_FONT_SIZE = 28
TITLE_COLOR = "rgba(13, 13, 13, 0.86)"
GRID_COLOR = "rgba(13, 13, 13, 0.05)"


@dataclass
class Note:
    classes: list[str]
    text: str


class BoardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.div_stack: list[list[str]] = []
        self.in_header = False
        self.capture_span = False
        self.current_span: list[str] = []
        self.headers: list[str] = []
        self.in_columns = False
        self.current_col: list[Note] | None = None
        self.columns: list[list[Note]] = []
        self.current_note_classes: list[str] | None = None
        self.current_note_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = dict(attrs)
        classes = attr_map.get("class", "").split()

        if tag == "div":
            self.div_stack.append(classes)
            if "research-board-header" in classes:
                self.in_header = True
            elif "research-board-columns" in classes:
                self.in_columns = True
            elif self.in_columns and "research-board-col" in classes:
                self.current_col = []
            elif self.current_col is not None and "research-note" in classes:
                self.current_note_classes = classes
                self.current_note_text = []

        if tag == "span" and self.in_header:
            self.capture_span = True
            self.current_span = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.capture_span:
            text = normalize("".join(self.current_span))
            if text:
                self.headers.append(text)
            self.capture_span = False
            self.current_span = []
            return

        if tag != "div" or not self.div_stack:
            return

        classes = self.div_stack.pop()

        if self.current_note_text is not None and "research-note" in classes:
            text = normalize("".join(self.current_note_text))
            if self.current_col is not None:
                self.current_col.append(Note(classes=classes, text=text))
            self.current_note_classes = None
            self.current_note_text = None
            return

        if self.current_col is not None and "research-board-col" in classes:
            self.columns.append(self.current_col)
            self.current_col = None
            return

        if "research-board-columns" in classes:
            self.in_columns = False
            return

        if "research-board-header" in classes:
            self.in_header = False

    def handle_data(self, data: str) -> None:
        if self.capture_span:
            self.current_span.append(data)
        elif self.current_note_text is not None:
            self.current_note_text.append(data)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def char_width(ch: str, font_size: float) -> float:
    if ch == " ":
        return font_size * 0.34
    if ch in "ilI.,'":
        return font_size * 0.28
    if ch in "mwMW@#%&":
        return font_size * 0.78
    if ch.isupper():
        return font_size * 0.63
    return font_size * 0.52


def measure_text(text: str, font_size: float) -> float:
    return sum(char_width(ch, font_size) for ch in text)


def wrap_text(text: str, max_width: float, font_size: float) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure_text(candidate, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def note_fill(classes: list[str]) -> str:
    if "research-note--quote" in classes:
        return "rgb(255, 205, 0)"
    if "research-note--green" in classes:
        return "rgb(190, 207, 200)"
    return "rgb(248, 227, 177)"


def note_text_fill(classes: list[str]) -> str:
    return "rgba(13,13,13,0.52)"


def note_offset(classes: list[str]) -> tuple[int, int]:
    dx = -12 if "research-note--push-right" in classes else 0
    if "research-note--overlap" in classes:
        dy = -24
    elif "research-note--push-down" in classes:
        dy = -16
    else:
        dy = 0
    return dx, dy


def board_dimensions(columns: list[list[Note]]) -> tuple[int, int]:
    width = MARGIN_X * 2 + COLUMN_WIDTH * len(columns) + SECTION_GAP * (len(columns) - 1)

    max_bottom = 0
    for col_idx, notes in enumerate(columns):
        base_x = MARGIN_X + col_idx * (COLUMN_WIDTH + SECTION_GAP)
        for idx, note in enumerate(notes):
            row = idx // 3
            col = idx % 3
            x = base_x + col * NOTE_STEP
            y = BOARD_Y + row * NOTE_STEP
            dx, dy = note_offset(note.classes)
            bottom = y + dy + NOTE_SIZE
            max_bottom = max(max_bottom, bottom)

    height = max_bottom + 36
    return width, height


def render_note(x: int, y: int, note: Note) -> str:
    fill = note_fill(note.classes)
    text_fill = note_text_fill(note.classes)
    lines = wrap_text(note.text, NOTE_TEXT_WIDTH, NOTE_FONT_SIZE)
    text_y = y + NOTE_TEXT_Y_PAD
    text_parts = []

    for idx, line in enumerate(lines):
        dy = NOTE_LINE_HEIGHT if idx else 0
        text_parts.append(
            f'<tspan x="{x + NOTE_TEXT_X_PAD}" dy="{dy}">{html.escape(line)}</tspan>'
        )

    return (
        f'<g>'
        f'<rect x="{x}" y="{y}" width="{NOTE_SIZE}" height="{NOTE_SIZE}" rx="6" '
        f'fill="{fill}" stroke="rgba(0, 0, 0, 0.08)" stroke-width="1"/>'
        f'<text x="{x + NOTE_TEXT_X_PAD}" y="{text_y}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{NOTE_FONT_SIZE}" '
        f'fill="{text_fill}">' + "".join(text_parts) + "</text></g>"
    )


def main() -> None:
    parser = BoardParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    headers = parser.headers or ["What was heard?", "What it Means", "Why it matters", "Findings"]
    columns = parser.columns

    if len(columns) != 4:
        raise RuntimeError(f"Expected 4 board columns, found {len(columns)}")

    width, height = board_dimensions(columns)
    def build_svg(with_background: bool) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        ]

        if with_background:
            bg_uri = "data:image/jpeg;base64," + base64.b64encode(BG_PATH.read_bytes()).decode("ascii")
            parts.extend(
                [
                    f'<image href="{bg_uri}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice"/>',
                    f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfaf6" opacity="0.78"/>',
                ]
            )

            grid_step = NOTE_STEP
            x = 0
            while x <= width:
                parts.append(
                    f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="{GRID_COLOR}" stroke-width="1"/>'
                )
                x += grid_step
            y = 0
            while y <= height:
                parts.append(
                    f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="{GRID_COLOR}" stroke-width="1"/>'
                )
                y += grid_step

        for col_idx, title in enumerate(headers):
            base_x = MARGIN_X + col_idx * (COLUMN_WIDTH + SECTION_GAP)
            parts.append(
                f'<text x="{base_x}" y="{TITLE_Y}" font-family="Georgia, Times New Roman, serif" '
                f'font-size="{TITLE_FONT_SIZE}" fill="{TITLE_COLOR}">{html.escape(title)}</text>'
            )

            for idx, note in enumerate(columns[col_idx]):
                row = idx // 3
                col = idx % 3
                note_x = base_x + col * NOTE_STEP
                note_y = BOARD_Y + row * NOTE_STEP
                dx, dy = note_offset(note.classes)
                parts.append(render_note(note_x + dx, note_y + dy, note))

        parts.append("</svg>")
        return "\n".join(parts)

    OUT_PATH.write_text(build_svg(with_background=True), encoding="utf-8")
    OVERLAY_OUT_PATH.write_text(build_svg(with_background=False), encoding="utf-8")
    print(OUT_PATH)
    print(OVERLAY_OUT_PATH)


if __name__ == "__main__":
    main()
