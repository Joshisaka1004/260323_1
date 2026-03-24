import os
from textwrap import wrap

OUT_DIR = 'docs'
os.makedirs(OUT_DIR, exist_ok=True)
PDF_PATH = os.path.join(OUT_DIR, 'geometry_puzzle_book_concept.pdf')
SVG_PATH = os.path.join(OUT_DIR, 'puzzle_01_geometry.svg')

# --------- SVG diagram ---------
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="860" viewBox="0 0 700 860">
  <rect width="100%" height="100%" fill="white"/>
  <g stroke="#163A85" stroke-width="5" fill="none" stroke-linecap="round">
    <line x1="350" y1="90" x2="120" y2="420"/>
    <line x1="350" y1="90" x2="560" y2="420"/>
    <line x1="120" y1="420" x2="560" y2="420"/>
    <line x1="560" y1="420" x2="630" y2="760"/>
    <line x1="300" y1="420" x2="630" y2="760"/>

    <line x1="230" y1="275" x2="245" y2="265"/>
    <line x1="455" y1="270" x2="470" y2="280"/>

    <line x1="430" y1="412" x2="430" y2="432"/>
    <line x1="445" y1="412" x2="445" y2="432"/>

    <line x1="585" y1="575" x2="602" y2="583"/>
    <line x1="579" y1="558" x2="596" y2="566"/>
  </g>

  <path d="M 320 140 A 40 30 0 0 0 380 140" stroke="black" stroke-width="4" fill="none"/>
  <path d="M 275 422 A 50 36 0 0 0 338 452" stroke="black" stroke-width="4" fill="none"/>

  <text x="337" y="230" font-size="48" font-weight="bold" font-family="Arial" fill="black">40°</text>
  <text x="245" y="530" font-size="60" font-weight="bold" font-family="Arial" fill="black">x</text>
  <text x="110" y="780" font-size="70" font-weight="bold" font-family="Arial" fill="black">x = ?</text>
</svg>'''

with open(SVG_PATH, 'w', encoding='utf-8') as f:
    f.write(svg)

# --------- Minimal PDF writer ---------

def esc(text: str) -> str:
    return text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')


def text_block(x, y, lines, size=12, leading=None):
    if leading is None:
        leading = size + 3
    out = ["BT", f"/F1 {size} Tf", f"1 0 0 1 {x} {y} Tm"]
    first = True
    for line in lines:
        if not first:
            out.append(f"0 -{leading} Td")
        out.append(f"({esc(line)}) Tj")
        first = False
    out.append("ET")
    return "\n".join(out)


def wrap_lines(paragraphs, width=90):
    lines = []
    for p in paragraphs:
        if p == "":
            lines.append("")
        else:
            lines.extend(wrap(p, width=width))
    return lines

# Page 1 content
page1_lines = [
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
    "4) Repeatable Puzzle Template:",
    "Difficulty tag | clean diagram | short English prompt | optional hints | full solution later.",
    "",
    "5) Didactic Flow:",
    "Observe -> Infer -> Verify. This keeps motivation high while building proof skills.",
    "",
    "6) Design Rules:",
    "One puzzle per page, high contrast, consistent symbols, separate answer section.",
    "",
    "7) Production Workflow:",
    "Draft 50 puzzles -> remove ambiguity -> pilot with test readers -> finalize print-ready edition.",
]

page1 = []
page1.append("0.97 0.98 1 rg 0 0 595 842 re f")
page1.append("0.09 0.23 0.52 rg")
page1.append(text_block(70, 790, ["Geometry Puzzle Book Blueprint"], size=26, leading=30))
page1.append("0.28 0.34 0.45 rg")
page1.append(text_block(70, 760, ["A structured concept for an engaging math and geometry puzzle book"], size=12, leading=16))
page1.append("0 0 0 rg")
page1.append(text_block(70, 725, page1_lines, size=11, leading=15))
page1_stream = "\n".join(page1)

# Page 2 content + vector drawing
problem_text = [
    "Task (English):",
    "In the figure, the top triangle is isosceles and the apex angle is 40 degrees.",
    "Segments marked with identical tick marks are equal in length.",
    "Find the angle x near the lower-left side of the base extension.",
    "Give your final answer in degrees and show your geometric reasoning.",
]

# vector diagram directly in PDF coordinates
# Coordinates chosen for page 2
shapes = []
shapes.append("0 0 0 rg")
shapes.append("0.09 0.23 0.52 RG 3 w")
# points
A=(300,700); L=(120,450); R=(470,450); P=(265,450); Q=(520,220)
shapes += [
    f"{A[0]} {A[1]} m {L[0]} {L[1]} l S",
    f"{A[0]} {A[1]} m {R[0]} {R[1]} l S",
    f"{L[0]} {L[1]} m {R[0]} {R[1]} l S",
    f"{R[0]} {R[1]} m {Q[0]} {Q[1]} l S",
    f"{P[0]} {P[1]} m {Q[0]} {Q[1]} l S",
]
# simple ticks
shapes += [
    "205 575 m 217 567 l S",
    "393 567 m 405 575 l S",
    "368 444 m 368 458 l S",
    "380 444 m 380 458 l S",
    "486 347 m 500 353 l S",
    "482 336 m 496 342 l S",
]

page2 = []
page2.append(text_block(65, 800, ["Puzzle 1 - Isosceles Triangle Angle Chase"], size=24, leading=28))
page2 += shapes
page2.append(text_block(282, 640, ["40°"], size=24, leading=26))
page2.append(text_block(223, 390, ["x"], size=36, leading=38))
page2.append(text_block(100, 180, ["x = ?"], size=38, leading=40))
page2.append(text_block(65, 150, problem_text, size=12, leading=16))
page2_stream = "\n".join(page2)

# build PDF objects
objects = []

def add_obj(s):
    objects.append(s)

add_obj("<< /Type /Catalog /Pages 2 0 R >>")           #1
add_obj("<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>") #2
add_obj("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>") #3
add_obj("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>") #4
add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>") #5
add_obj(f"<< /Length {len(page1_stream.encode('latin-1'))} >>\nstream\n{page1_stream}\nendstream") #6
add_obj(f"<< /Length {len(page2_stream.encode('latin-1'))} >>\nstream\n{page2_stream}\nendstream") #7

pdf = ["%PDF-1.4\n"]
offsets = [0]
for i, obj in enumerate(objects, start=1):
    offsets.append(sum(len(p.encode('latin-1')) for p in pdf))
    pdf.append(f"{i} 0 obj\n{obj}\nendobj\n")

xref_pos = sum(len(p.encode('latin-1')) for p in pdf)
pdf.append(f"xref\n0 {len(objects)+1}\n")
pdf.append("0000000000 65535 f \n")
for i in range(1, len(objects)+1):
    pdf.append(f"{offsets[i]:010d} 00000 n \n")
pdf.append(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n")

with open(PDF_PATH, 'wb') as f:
    data = ''.join(pdf).encode('latin-1')
    f.write(data)

# also create a markdown concept (editable)
md_path = os.path.join(OUT_DIR, 'geometry_puzzle_book_concept.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write("""# Geometry Puzzle Book Blueprint\n\n## Concept Overview\n1. **Book Vision**: Build a progression from simple geometry puzzles to reasoning-heavy tasks.\n2. **Audience**: Students (11-16), puzzle fans, teachers, and parents.\n3. **Chapter Plan**: Warm-up, shape logic, strategy/proof-lite, challenge arena.\n4. **Puzzle Format**: Difficulty tag, image, concise English task, optional hints, full solution section.\n5. **Design**: High contrast visuals, one puzzle per page, consistent symbols.\n\n## Puzzle 1 (English prompt)\nIn the figure, the top triangle is isosceles and the apex angle is **40°**.\nSegments marked with identical tick marks are equal in length.\nDetermine the value of **x**.\n\n![Puzzle 1 Diagram](./puzzle_01_geometry.svg)\n""")

print(f"Created: {PDF_PATH}")
print(f"Created: {SVG_PATH}")
print(f"Created: {md_path}")

