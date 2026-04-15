from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "docs" / "project_technical_handbook.md"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "project_technical_handbook.pdf"

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_X = 52
MARGIN_TOP = 54
MARGIN_BOTTOM = 44
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN_X)


@dataclass
class Block:
    kind: str
    text: str


@dataclass
class Line:
    text: str
    x: int
    y: int
    font: str
    size: int


def strip_markdown_markup(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text.strip()


def parse_markdown(markdown_text: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            blocks.append(Block("paragraph", " ".join(line.strip() for line in paragraph_lines if line.strip())))
            paragraph_lines.clear()

    def flush_code() -> None:
        if code_lines:
            blocks.append(Block("code", "\n".join(code_lines)))
            code_lines.clear()

    for line in markdown_text.splitlines():
        raw = line.rstrip()
        stripped = raw.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(raw)
            continue

        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            blocks.append(Block("title", strip_markdown_markup(stripped[2:])))
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            blocks.append(Block("heading1", strip_markdown_markup(stripped[3:])))
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            blocks.append(Block("heading2", strip_markdown_markup(stripped[4:])))
            continue

        if stripped.startswith("#### "):
            flush_paragraph()
            blocks.append(Block("heading3", strip_markdown_markup(stripped[5:])))
            continue

        bullet_match = re.match(r"^- (.+)$", stripped)
        if bullet_match:
            flush_paragraph()
            blocks.append(Block("bullet", strip_markdown_markup(bullet_match.group(1))))
            continue

        numbered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered_match:
            flush_paragraph()
            blocks.append(Block("numbered", strip_markdown_markup(numbered_match.group(1))))
            continue

        paragraph_lines.append(strip_markdown_markup(raw))

    flush_paragraph()
    flush_code()
    return blocks


def wrap_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=max_chars, break_long_words=False, break_on_hyphens=False) or [text]


def layout_blocks(blocks: list[Block]) -> list[list[Line]]:
    pages: list[list[Line]] = [[]]
    y = PAGE_HEIGHT - MARGIN_TOP

    def new_page() -> None:
        nonlocal y
        pages.append([])
        y = PAGE_HEIGHT - MARGIN_TOP

    def ensure_space(required_height: int) -> None:
        nonlocal y
        if y - required_height < MARGIN_BOTTOM:
            new_page()

    def add_wrapped_lines(
        text: str,
        *,
        font: str,
        size: int,
        x: int,
        max_chars: int,
        line_gap: int,
        space_after: int,
    ) -> None:
        nonlocal y
        lines = wrap_text(text, max_chars)
        ensure_space((len(lines) * line_gap) + space_after)
        for line in lines:
            pages[-1].append(Line(text=line, x=x, y=y, font=font, size=size))
            y -= line_gap
        y -= space_after

    for index, block in enumerate(blocks):
        if block.kind == "title":
            if index != 0:
                new_page()
            add_wrapped_lines(block.text, font="F2", size=22, x=MARGIN_X, max_chars=46, line_gap=28, space_after=8)
            add_wrapped_lines(
                "Technical handbook covering pipeline steps, candidate generation, models, scores, technologies, and file responsibilities.",
                font="F1",
                size=11,
                x=MARGIN_X,
                max_chars=78,
                line_gap=16,
                space_after=16,
            )
            continue

        if block.kind == "heading1":
            ensure_space(42)
            pages[-1].append(Line(text=block.text, x=MARGIN_X, y=y, font="F2", size=16))
            y -= 24
            continue

        if block.kind == "heading2":
            ensure_space(30)
            pages[-1].append(Line(text=block.text, x=MARGIN_X, y=y, font="F2", size=13))
            y -= 20
            continue

        if block.kind == "heading3":
            ensure_space(24)
            pages[-1].append(Line(text=block.text, x=MARGIN_X, y=y, font="F2", size=11))
            y -= 17
            continue

        if block.kind == "paragraph":
            add_wrapped_lines(block.text, font="F1", size=10, x=MARGIN_X, max_chars=92, line_gap=14, space_after=3)
            continue

        if block.kind == "bullet":
            add_wrapped_lines(f"- {block.text}", font="F1", size=10, x=MARGIN_X + 8, max_chars=88, line_gap=14, space_after=2)
            continue

        if block.kind == "numbered":
            add_wrapped_lines(f"- {block.text}", font="F1", size=10, x=MARGIN_X + 8, max_chars=88, line_gap=14, space_after=2)
            continue

        if block.kind == "code":
            code_lines = block.text.splitlines() or [""]
            ensure_space((len(code_lines) * 11) + 10)
            for code_line in code_lines:
                pages[-1].append(Line(text=code_line, x=MARGIN_X + 10, y=y, font="F3", size=8))
                y -= 11
            y -= 6

    return [page for page in pages if page]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_content_stream(lines: list[Line], page_number: int) -> bytes:
    commands = [
        "0.12 0.18 0.25 RG",
        f"{MARGIN_X} {PAGE_HEIGHT - 30} m {PAGE_WIDTH - MARGIN_X} {PAGE_HEIGHT - 30} l S",
    ]
    for line in lines:
        commands.append(
            f"BT /{line.font} {line.size} Tf 0.12 0.16 0.22 rg 1 0 0 1 {line.x} {line.y} Tm ({pdf_escape(line.text)}) Tj ET"
        )
    commands.append(
        f"BT /F1 9 Tf 0.37 0.42 0.48 rg 1 0 0 1 {MARGIN_X} 18 Tm (Legal Argument-Aware Summarization MVP Handbook) Tj ET"
    )
    commands.append(
        f"BT /F1 9 Tf 0.37 0.42 0.48 rg 1 0 0 1 {PAGE_WIDTH - MARGIN_X - 38} 18 Tm (Page {page_number}) Tj ET"
    )
    return "\n".join(commands).encode("latin-1", errors="replace")


def write_pdf(pages: list[list[Line]], output_path: Path) -> None:
    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"<< /Type /Pages /Count 0 /Kids [] >>")
    font1_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font2_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font3_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids: list[int] = []
    content_ids: list[int] = []
    for page_index, lines in enumerate(pages, start=1):
        content_stream = build_content_stream(lines, page_index)
        content_id = add_object(
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream"
        )
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font1_id} 0 R /F2 {font2_id} 0 R /F3 {font3_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        content_ids.append(content_id)
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [ {kids} ] >>".encode("ascii")
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    output_path.write_bytes(pdf)


def build_pdf() -> None:
    markdown_text = SOURCE_PATH.read_text(encoding="utf-8")
    blocks = parse_markdown(markdown_text)
    pages = layout_blocks(blocks)
    write_pdf(pages, OUTPUT_PATH)
    print(f"Created {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
