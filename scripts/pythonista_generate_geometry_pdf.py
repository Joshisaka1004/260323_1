#!/usr/bin/env python3
"""
Pythonista-friendly script:
Creates a formatted geometry puzzle PDF without external dependencies.

How to use in Pythonista (iPad):
1) Copy this file into Pythonista.
2) Run it.
3) The output PDF is saved to your Pythonista Documents folder.
"""

import os


def _escape_pdf_text(text: str) -> str:
    return text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')


def _text_block(x, y, lines, size=12, leading=None):
    if leading is None:
        leading = size + 3
    chunks = ["BT", f"/F1 {size} Tf", f"1 0 0 1 {x} {y} Tm"]
    first = True
    for line in lines:
        if not first:
            chunks.append(f"0 -{leading} Td")
        chunks.append(f"({_escape_pdf_text(line)}) Tj")
        first = False
    chunks.append("ET")
    return "\n".join(chunks)


def build_geometry_puzzle_pdf(output_pdf: str):
    # ---------- Page 1: concept ----------
    concept_lines = [
        "1) Book Vision:",
        "Create a progressive puzzle journey from basic angle intuition to deeper geometric reasoning.",
        "",
        "2) Audience:",
        "Main: learners aged 11-16 and puzzle enthusiasts. Secondary: teachers and parents.",
        "",
        "3) Structure (4 parts):",
        "A. Warm-Up Geometry (angles, triangles, parallel lines)",
        "B. Shape Logic (quadrilaterals, circles, symmetry)",
        "C. Strategy & Proof Lite (multi-step deductions)",
        "D. Challenge Arena (mixed harder puzzles)",
        "",
        "4) Puzzle Template:",
        "Difficulty tag | clear diagram | short English prompt | optional hints | full solution later.",
        "",
        "5) Didactic Flow:",
        "Observe -> Infer -> Verify.",
    ]

    page1_parts = [
        "0.97 0.98 1 rg 0 0 595 842 re f",
        "0.09 0.23 0.52 rg",
        _text_block(70, 790, ["Geometry Puzzle Book Blueprint"], size=26, leading=30),
        "0.28 0.34 0.45 rg",
        _text_block(70, 760, ["A structured concept for an engaging math and geometry puzzle book"], size=12, leading=16),
        "0 0 0 rg",
        _text_block(70, 725, concept_lines, size=11, leading=15),
    ]
    page1_stream = "\n".join(page1_parts)

    # ---------- Page 2: puzzle ----------
    problem_lines = [
        "Task (English):",
        "In the figure, the top triangle is isosceles and the apex angle is 40 degrees.",
        "Segments marked with identical tick marks are equal in length.",
        "Find the angle x near the lower-left side of the base extension.",
        "Give your final answer in degrees and show your geometric reasoning.",
    ]

    # Drawing coordinates
    A = (300, 700)
    L = (120, 450)
    R = (470, 450)
    P = (265, 450)
    Q = (520, 220)

    shape_commands = [
        "0 0 0 rg",
        "0.09 0.23 0.52 RG 3 w",
        f"{A[0]} {A[1]} m {L[0]} {L[1]} l S",
        f"{A[0]} {A[1]} m {R[0]} {R[1]} l S",
        f"{L[0]} {L[1]} m {R[0]} {R[1]} l S",
        f"{R[0]} {R[1]} m {Q[0]} {Q[1]} l S",
        f"{P[0]} {P[1]} m {Q[0]} {Q[1]} l S",
        # side tick marks
        "205 575 m 217 567 l S",
        "393 567 m 405 575 l S",
        # equal segment double ticks
        "368 444 m 368 458 l S",
        "380 444 m 380 458 l S",
        "486 347 m 500 353 l S",
        "482 336 m 496 342 l S",
    ]

    page2_parts = [
        _text_block(65, 800, ["Puzzle 1 - Isosceles Triangle Angle Chase"], size=24, leading=28),
        "\n".join(shape_commands),
        _text_block(282, 640, ["40\260"], size=24, leading=26),
        _text_block(223, 390, ["x"], size=36, leading=38),
        _text_block(100, 180, ["x = ?"], size=38, leading=40),
        _text_block(65, 150, problem_lines, size=12, leading=16),
    ]
    page2_stream = "\n".join(page2_parts)

    # ---------- Minimal PDF objects ----------
    objects = []

    def add_obj(s):
        objects.append(s)

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    add_obj("<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>")
    add_obj("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>")
    add_obj("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>")
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add_obj(f"<< /Length {len(page1_stream.encode('latin-1'))} >>\nstream\n{page1_stream}\nendstream")
    add_obj(f"<< /Length {len(page2_stream.encode('latin-1'))} >>\nstream\n{page2_stream}\nendstream")

    parts = ["%PDF-1.4\n"]
    offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offsets.append(sum(len(p.encode('latin-1')) for p in parts))
        parts.append(f"{i} 0 obj\n{obj}\nendobj\n")

    xref_pos = sum(len(p.encode('latin-1')) for p in parts)
    parts.append(f"xref\n0 {len(objects) + 1}\n")
    parts.append("0000000000 65535 f \n")
    for i in range(1, len(objects) + 1):
        parts.append(f"{offsets[i]:010d} 00000 n \n")
    parts.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n")

    with open(output_pdf, 'wb') as f:
        f.write(''.join(parts).encode('latin-1'))


def main():
    # Pythonista usually runs with cwd inside Documents.
    out_name = 'geometry_puzzle_book_concept.pdf'
    output_pdf = os.path.join(os.getcwd(), out_name)
    build_geometry_puzzle_pdf(output_pdf)
    print('Done! PDF created at:')
    print(output_pdf)


if __name__ == '__main__':
    main()
