#!/usr/bin/env python3
"""TicTacLogic-Generator: erzeugt Rätsel mit genau einer Lösung als PNG-Karten.

Regeln:
  1. Nie mehr als zwei gleiche Zeichen direkt neben- oder untereinander.
  2. Jede Zeile und jede Spalte enthält gleich viele X wie O.
  3. Keine zwei Zeilen und keine zwei Spalten sind gleich.

Stufen (welche Logik zum Lösen reicht):
  1 Leicht   Paare, Lücken, Abzählen
  2 Mittel   zusätzlich alle Verteilungen einer Linie durchprobieren
  3 Schwer   zusätzlich die Regel "keine zwei Linien gleich"
  4 Experte  zusätzlich Widerspruchsbeweis an einem Feld

Beispiele:
  python3 tictaclogic.py                       # 8x8, Mittel, Zufallscode
  python3 tictaclogic.py --size 10 --level 3 --count 6 --out karten
  python3 tictaclogic.py --size 8 --level 2 --seed 271828 --lang en

Läuft auch in Pythonista (benötigt nur Pillow für die PNGs).
"""

import argparse
import os
import random

EMPTY, O, X = -1, 0, 1
_pat_cache = {}


def patterns(n):
    """Alle gültigen Belegungen einer Linie der Länge n als Bitmasken der X."""
    if n not in _pat_cache:
        full, res = (1 << n) - 1, []
        for m in range(full + 1):
            if bin(m).count("1") != n // 2:
                continue
            o = ~m & full
            if m & (m >> 1) & (m >> 2) or o & (o >> 1) & (o >> 2):
                continue
            res.append(m)
        _pat_cache[n] = res
    return _pat_cache[n]


def make_lines(w, h):
    rows = [("row", [r * w + c for c in range(w)]) for r in range(h)]
    cols = [("col", [r * w + c for r in range(h)]) for c in range(w)]
    return rows + cols


def line_state(g, cells):
    known = xs = 0
    for k, i in enumerate(cells):
        if g[i] >= 0:
            known |= 1 << k
            if g[i] == X:
                xs |= 1 << k
    return known, xs, known == (1 << len(cells)) - 1


def is_valid(g, w, h):
    seen = set()
    for kind, cells in make_lines(w, h):
        known, xs, full = line_state(g, cells)
        if not full or xs not in patterns(len(cells)) or (kind, xs) in seen:
            return False
        seen.add((kind, xs))
    return True


def propagate(g, w, h, level):
    """Zieht alle Folgerungen bis Stufe level (1..3). 1 gelöst, 0 fest, -1 Widerspruch."""
    lines = make_lines(w, h)
    changed = True
    while changed:
        changed = False
        inner = True
        while inner:  # Stufe 1
            inner = False
            for kind, c in lines:
                n, half = len(c), len(c) // 2
                nx = sum(1 for i in c if g[i] == X)
                no = sum(1 for i in c if g[i] == O)
                if nx > half or no > half:
                    return -1
                if nx + no < n and (nx == half or no == half):
                    fill = O if nx == half else X
                    for i in c:
                        if g[i] < 0:
                            g[i] = fill
                    inner = True
                    continue
                for k in range(n - 2):
                    a, b, d = g[c[k]], g[c[k + 1]], g[c[k + 2]]
                    if a >= 0 and a == b == d:
                        return -1
                    if a >= 0 and a == b and d < 0:
                        g[c[k + 2]] = 1 - a
                        inner = True
                    elif b >= 0 and b == d and a < 0:
                        g[c[k]] = 1 - b
                        inner = True
                    elif a >= 0 and a == d and b < 0:
                        g[c[k + 1]] = 1 - a
                        inner = True
        if level < 2:
            break
        done = {}
        for kind, c in lines:
            known, xs, full = line_state(g, c)
            if full:
                if level >= 3 and (kind, xs) in done:
                    return -1
                done[(kind, xs)] = True
        for kind, c in lines:  # Stufe 2/3
            known, xs, full = line_state(g, c)
            if full:
                continue
            and_m, or_m, cnt = -1, 0, 0
            for m in patterns(len(c)):
                if m & known != xs or (level >= 3 and (kind, m) in done):
                    continue
                and_m &= m
                or_m |= m
                cnt += 1
            if cnt == 0:
                return -1
            for k, i in enumerate(c):
                if known >> k & 1:
                    continue
                if and_m >> k & 1:
                    g[i] = X
                    changed = True
                elif not or_m >> k & 1:
                    g[i] = O
                    changed = True
            if changed:
                break
    if any(v < 0 for v in g):
        return 0
    return 1 if is_valid(g, w, h) else -1


def solve(clues, w, h, level):
    g = list(clues)
    while True:
        s = propagate(g, w, h, min(level, 3))
        if s != 0 or level < 4:
            return s, g
        found = False
        for i in range(len(g)):
            if g[i] >= 0:
                continue
            for v in (O, X):
                t = list(g)
                t[i] = v
                if propagate(t, w, h, 3) == -1:
                    g[i] = 1 - v
                    found = True
                    break
            if found:
                break
        if not found:
            return 0, g


def count_solutions(clues, w, h, limit=2):
    """Unabhängige Kontrolle: Feld raten, Folgerungen ziehen, beide Zweige zählen."""
    count = 0

    def rec(g):
        nonlocal count
        if count >= limit:
            return
        s = propagate(g, w, h, 3)
        if s == 1:
            count += 1
        elif s == 0:
            i = g.index(EMPTY)
            for v in (O, X):
                t = list(g)
                t[i] = v
                rec(t)

    rec(list(clues))
    return count


def random_solution(w, h, rnd):
    while True:
        g = [EMPTY] * (w * h)
        while EMPTY in g:
            cell = rnd.choice([i for i, v in enumerate(g) if v < 0])
            v = rnd.randint(0, 1)
            t = list(g)
            t[cell] = v
            if propagate(t, w, h, 3) == -1:
                t = list(g)
                t[cell] = 1 - v
                if propagate(t, w, h, 3) == -1:
                    break
            g = t
        if EMPTY not in g and is_valid(g, w, h):
            return g


def required_level(clues, w, h):
    for lv in range(1, 5):
        if solve(clues, w, h, lv)[0] == 1:
            return lv
    return 5


def generate(w, h, level, seed):
    rnd = random.Random(seed)
    best = None
    for _ in range(12):
        sol = random_solution(w, h, rnd)
        g = list(sol)
        order = list(range(w * h))
        rnd.shuffle(order)
        for i in order:
            keep, g[i] = g[i], EMPTY
            ok = solve(g, w, h, min(level, 3))[0] == 1 or (level == 4 and solve(g, w, h, 4)[0] == 1)
            if not ok:
                g[i] = keep
        req = required_level(g, w, h)
        cand = {"w": w, "h": h, "level": req, "seed": seed, "clues": g, "solution": sol}
        if req == level:
            return cand
        if best is None or req > best["level"]:
            best = cand
    return best


# ---------- Ausgabe ----------

TEXT = {
    "de": {"levels": ["", "Leicht", "Mittel", "Schwer", "Experte"], "solution": "Lösung",
           "rules": ["Nie mehr als zwei gleiche Zeichen neben- oder untereinander.",
                     "Jede Zeile und Spalte hat gleich viele X wie O.",
                     "Keine zwei Zeilen und keine zwei Spalten sind gleich."]},
    "en": {"levels": ["", "Easy", "Medium", "Hard", "Expert"], "solution": "Solution",
           "rules": ["Never more than two equal symbols side by side or one above the other.",
                     "Every row and column has as many X as O.",
                     "No two rows and no two columns are identical."]},
}


def to_text(g, w):
    sym = {EMPTY: ".", X: "X", O: "O"}
    return "\n".join(" ".join(sym[g[r * w + c]] for c in range(w)) for r in range(len(g) // w))


def _font(size, bold=False):
    from PIL import ImageFont
    names = (["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_png(p, path, lang="de", show_solution=False, cell=72):
    """Zeichnet eine Karte. Vorgaben schwarz und kräftig; Lösungsfelder blau."""
    from PIL import Image, ImageDraw
    t = TEXT[lang]
    w, h = p["w"], p["h"]
    margin, head = 48, 120
    foot = 0 if show_solution else 260
    W = max(w * cell + 2 * margin, 720)
    H = head + h * cell + margin + foot
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    ink, blue, grid = (24, 32, 44), (36, 86, 214), (180, 192, 206)
    x0 = (W - w * cell) // 2
    y0 = head

    code = "%dx%d-%d-%d" % (w, h, p["level"], p["seed"])
    title = "TicTacLogic" + (" – " + t["solution"] if show_solution else "")
    d.text((margin, 34), title, fill=ink, font=_font(40, True))
    d.text((margin, 82), "%s  ·  %s" % (t["levels"][p["level"]], code), fill=(90, 101, 119), font=_font(22))

    for r in range(h + 1):
        d.line([(x0, y0 + r * cell), (x0 + w * cell, y0 + r * cell)], fill=grid, width=2)
    for c in range(w + 1):
        d.line([(x0 + c * cell, y0), (x0 + c * cell, y0 + h * cell)], fill=grid, width=2)
    d.rectangle([x0, y0, x0 + w * cell, y0 + h * cell], outline=(110, 124, 142), width=4)

    grid_vals = p["solution"] if show_solution else p["clues"]
    for i, v in enumerate(grid_vals):
        if v < 0:
            continue
        given = p["clues"][i] >= 0
        col = ink if given else blue
        lw = 7 if given else 5
        cx = x0 + (i % w) * cell + cell / 2
        cy = y0 + (i // w) * cell + cell / 2
        s = cell * 0.24
        if v == X:
            d.line([(cx - s, cy - s), (cx + s, cy + s)], fill=col, width=lw)
            d.line([(cx + s, cy - s), (cx - s, cy + s)], fill=col, width=lw)
        else:
            d.ellipse([cx - s * 1.1, cy - s * 1.1, cx + s * 1.1, cy + s * 1.1], outline=col, width=lw)

    if not show_solution:
        font, fy = _font(22), y0 + h * cell + 40
        for k, rule in enumerate(t["rules"]):
            for n, part in enumerate(_wrap(d, "%d. %s" % (k + 1, rule), font, W - 2 * margin - 26)):
                d.text((margin + (26 if n else 0), fy), part, fill=ink, font=font)
                fy += 32
    img = img.crop((0, 0, W, min(H, fy + margin) if not show_solution else H))
    img.save(path)


def _wrap(d, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cur and d.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def main():
    ap = argparse.ArgumentParser(description="TicTacLogic-Rätsel erzeugen")
    ap.add_argument("--size", type=int, default=8, help="Kantenlänge (gerade, 4–14)")
    ap.add_argument("--height", type=int, help="abweichende Höhe für rechteckige Gitter")
    ap.add_argument("--level", type=int, default=2, choices=[1, 2, 3, 4])
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", type=int, help="Rätsel-Code (gleicher Code = gleiches Rätsel)")
    ap.add_argument("--lang", choices=["de", "en", "both"], default="both")
    ap.add_argument("--out", default="tictaclogic_out")
    ap.add_argument("--no-png", action="store_true", help="nur Text ausgeben")
    a = ap.parse_args()
    w, h = a.size, a.height or a.size
    if w % 2 or h % 2 or not (4 <= w <= 14 and 4 <= h <= 14):
        ap.error("Breite und Höhe müssen gerade sein und zwischen 4 und 14 liegen.")

    os.makedirs(a.out, exist_ok=True)
    langs = ["de", "en"] if a.lang == "both" else [a.lang]
    base = a.seed if a.seed is not None else random.randrange(100000, 1000000)
    for k in range(a.count):
        seed = base + k
        p = generate(w, h, a.level, seed)
        assert count_solutions(p["clues"], w, h) == 1, "Rätsel ist nicht eindeutig"
        code = "%dx%d-%d-%d" % (w, h, p["level"], seed)
        print("Rätsel %s (%d Vorgaben)\n%s\n" % (code, sum(v >= 0 for v in p["clues"]), to_text(p["clues"], w)))
        if a.no_png:
            continue
        for lang in langs:
            render_png(p, os.path.join(a.out, "%s_%s.png" % (code, lang)), lang)
            render_png(p, os.path.join(a.out, "%s_%s_loesung.png" % (code, lang) if lang == "de"
                                       else "%s_%s_solution.png" % (code, lang)), lang, show_solution=True)
    if not a.no_png:
        print("PNG-Karten gespeichert in:", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
