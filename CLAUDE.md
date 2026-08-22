# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A concept project for a **geometry puzzle book** aimed at learners aged 11–16. It contains dependency-free Python scripts that generate the book's assets (an SVG puzzle diagram, a concept PDF, and a markdown blueprint) into `docs/`. There is no application, package, or test suite.

## Commands

Generate all assets (SVG diagram, concept PDF, and markdown blueprint) into `docs/`:

```bash
python3 scripts/generate_puzzle_book_assets.py
```

Run from the repository root — the script writes to a relative `docs/` directory.

The Pythonista variant writes the PDF to the current working directory instead (intended to be run on an iPad inside the Pythonista app):

```bash
python3 scripts/pythonista_generate_geometry_pdf.py
```

Both scripts use only the Python standard library — do not add third-party dependencies (no reportlab, no svgwrite). The Pythonista script in particular must stay dependency-free so it runs on iOS.

## Architecture

- `scripts/generate_puzzle_book_assets.py` — the main generator. Builds the SVG as a string, and builds the PDF by hand-writing raw PDF 1.4 objects (catalog, pages, Helvetica font, content streams with `BT/Tj/ET` text blocks and `m/l/S` path operators), then computing the xref table byte offsets. It also regenerates `docs/geometry_puzzle_book_concept.md`.
- `scripts/pythonista_generate_geometry_pdf.py` — a self-contained copy of the PDF-writing logic for Pythonista on iPad. It duplicates the page content and the minimal PDF writer; changes to puzzle text, diagram coordinates, or concept copy generally need to be applied in **both** scripts to keep them in sync.
- `docs/` — generated output plus the checked-in `geometry_puzzle_book_concept.md` and `puzzle_01_geometry.svg`. Edit these by changing the generator script and re-running it, not by hand, or the next generator run will overwrite manual edits.

Key details of the hand-rolled PDF writer:

- All content streams are encoded as latin-1; keep text ASCII-safe (the Pythonista script encodes the degree sign as the octal escape `\260` for this reason).
- Text in content streams must be escaped via the provided `esc` / `_escape_pdf_text` helpers (backslashes and parentheses).
- Object numbering, `/Length` values, and xref offsets are computed from byte lengths — adding a page means adding a page object, a content-stream object, and updating the `/Kids` array and `/Count` in the Pages object.
- Page size is A4 in points (`MediaBox [0 0 595 842]`); PDF coordinates have the origin at the bottom-left, while the SVG uses top-left origin, so the same diagram uses different coordinate sets in each format.

## Conventions

- Puzzle content follows the template defined in `docs/geometry_puzzle_book_concept.md`: difficulty tag, clean diagram, short English prompt, optional hints, solution in a separate section.
- Design rules from the concept: one puzzle per page, high contrast, consistent symbols (tick marks denote equal segments), separate answer section.
- Diagram styling: dark blue strokes (`#163A85` in SVG, `0.09 0.23 0.52 RG` in PDF), black labels, white/near-white background.
