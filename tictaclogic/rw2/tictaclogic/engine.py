"""TicTacLogic – Engine für die Rätselwerkstatt 2 (ohne Oberfläche, ohne Werkstatt-Code).

Regeln (wie Conceptis „Tic-Tac-Logic“):
  1. Nie mehr als zwei gleiche Zeichen direkt neben- oder untereinander.
  2. Jede Zeile und jede Spalte enthält gleich viele X wie O.
  3. Keine zwei Zeilen und keine zwei Spalten sind gleich.

Human Logic: Der Löser wendet immer die einfachste Technik an, die etwas bewirkt,
und beginnt danach wieder bei T1. Es gibt kein Probieren; die einzigen Annahmen sind
die kurzen Wenn-dann-Schlüsse der Stufe Extrem nach der Werkstatt-Regel (höchstens
5 Tests, jeder höchstens 3 Runden). Die Stufe eines Rätsels ist die niedrigste,
deren Techniken es vollständig lösen.

Darstellung: Felder 0 … w·h−1 zeilenweise, Wert −1 leer, 0 = O, 1 = X. Eine Linie
(Zeile oder Spalte) wird als Bitmaske ihrer X kodiert.
"""

import math
import time

VERSION = "tictaclogic 1.0"
EMPTY, O, X = -1, 0, 1

LEVELS = [("easy", "Leicht"), ("medium", "Mittel"), ("hard", "Schwer"),
          ("veryhard", "Sehr schwer"), ("extreme", "Extrem")]
LEVEL_NAMES_EN = {"easy": "Easy", "medium": "Medium", "hard": "Hard",
                  "veryhard": "Very hard", "extreme": "Extreme"}
RANK = {key: i + 1 for i, (key, _) in enumerate(LEVELS)}

# Die Leiter. Schwellen und Einordnung sind Daten: werden sie geändert, meldet die
# Prüfung gespeicherter Rätsel eine abweichende Stufe, statt sie still umzudeuten.
#  Taste, Stufe, Name, h (Schwere innerhalb der Stufe, für die Punkte), Erklärung
TECHNIQUES = [
    ("T1", "easy", "Paar", 0.0,
     "Neben zwei gleichen Zeichen steht das andere."),
    ("T2", "easy", "Lücke", 0.2,
     "Zwischen zwei gleichen Zeichen steht das andere."),
    ("T3", "easy", "Abzählen", 0.3,
     "Hat eine Linie schon alle X (O), bekommen die freien Felder O (X)."),
    ("T4", "medium", "Einzelrest", 0.0,
     "Fehlt in einer Linie nur noch ein Zeichen einer Sorte, scheiden die Felder aus, "
     "an denen es drei gleiche der anderen Sorte erzwingen würde."),
    ("T5", "medium", "Zwilling", 0.3,
     "Zwei freie Felder: eine der beiden Belegungen machte die Linie gleich einer fertigen."),
    ("T6", "hard", "Linienanalyse", 0.0,
     "Alle Verteilungen der fehlenden Zeichen einer Linie durchgehen."),
    ("T7", "hard", "Linienanalyse mit Einzigartigkeit", 0.4,
     "Wie T6, dazu dürfen keine fertigen Linien doppelt entstehen."),
    ("T8", "veryhard", "Linienpaar", 0.0,
     "Zwei parallele Linien im Abstand 1 oder 2 gemeinsam: Dreierregel und Anzahl quer dazu."),
    ("T9", "extreme", "Wenn-dann", 0.0,
     "Annahme in einem Feld, höchstens 3 Runden Linienlogik (T1–T7) bis zum Widerspruch."),
]
TECH = {t[0]: t for t in TECHNIQUES}
TECH_RANK = {t[0]: RANK[t[1]] for t in TECHNIQUES}

LIMITS = {
    "pair_combos": 4000,   # T8: höchstens so viele Kandidatenpaare je Linienpaar
    "tests": 5,            # T9: Wenn-dann-Schlüsse je Rätsel (Werkstatt-Regel)
    "rounds": 3,           # T9: Schlussrunden je Wenn-dann-Schluss (Werkstatt-Regel)
}


class Contradiction(Exception):
    pass


# ---------------------------------------------------------------- Linien

_pat_cache = {}


def patterns(n):
    """Alle gültigen Belegungen einer Linie: gleich viele X und O, nie drei gleiche."""
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


_line_cache = {}


class Line:
    __slots__ = ("kind", "idx", "cells", "n")

    def __init__(self, kind, idx, cells):
        self.kind, self.idx, self.cells, self.n = kind, idx, cells, len(cells)

    def name(self, lang="de"):
        if lang == "en":
            return ("Row " if self.kind == "row" else "Column ") + str(self.idx + 1)
        return ("Zeile " if self.kind == "row" else "Spalte ") + str(self.idx + 1)


def lines_of(w, h):
    key = (w, h)
    if key not in _line_cache:
        ls = [Line("row", r, [r * w + c for c in range(w)]) for r in range(h)]
        ls += [Line("col", c, [r * w + c for r in range(h)]) for c in range(w)]
        by_cell = [[] for _ in range(w * h)]
        for L in ls:
            for i in L.cells:
                by_cell[i].append(L)
        _line_cache[key] = (ls, by_cell)
    return _line_cache[key]


def state(g, L):
    known = xs = 0
    for k, i in enumerate(L.cells):
        v = g[i]
        if v >= 0:
            known |= 1 << k
            if v:
                xs |= 1 << k
    return known, xs


def is_full(known, n):
    return known == (1 << n) - 1


def completed_masks(g, ls, kind, exclude=None):
    out = {}
    for M in ls:
        if M.kind != kind or M is exclude:
            continue
        known, xs = state(g, M)
        if is_full(known, M.n):
            out[xs] = M
    return out


def candidates(g, ls, L, uniq):
    known, xs = state(g, L)
    excl = completed_masks(g, ls, L.kind, L) if uniq else {}
    return [m for m in patterns(L.n) if m & known == xs and m not in excl], known, xs


def forced_from(cands, known, L):
    """Felder, die in allen Kandidaten gleich sind: [(feld, wert), …]."""
    if not cands:
        raise Contradiction(L.name())
    and_m, or_m = -1, 0
    for m in cands:
        and_m &= m
        or_m |= m
    out = []
    for k, i in enumerate(L.cells):
        if known >> k & 1:
            continue
        if and_m >> k & 1:
            out.append((i, X))
        elif not or_m >> k & 1:
            out.append((i, O))
    return out


# ---------------------------------------------------------------- Techniken je Linie

def t1_t2(g, L):
    """Paar (T1) und Lücke (T2). Rückgabe getrennt, damit der Löser T1 vor T2 nimmt."""
    c, pair, gap = L.cells, [], []
    for k in range(L.n - 2):
        a, b, d = g[c[k]], g[c[k + 1]], g[c[k + 2]]
        if a >= 0 and a == b == d:
            raise Contradiction(L.name())
        if a >= 0 and a == b and d < 0:
            pair.append((c[k + 2], 1 - a))
        if b >= 0 and b == d and a < 0:
            pair.append((c[k], 1 - b))
        if a >= 0 and a == d and b < 0:
            gap.append((c[k + 1], 1 - a))
    return pair, gap


def t3(g, L):
    half = L.n // 2
    nx = sum(1 for i in L.cells if g[i] == X)
    no = sum(1 for i in L.cells if g[i] == O)
    if nx > half or no > half:
        raise Contradiction(L.name())
    if nx + no == L.n:
        return []
    if nx == half:
        return [(i, O) for i in L.cells if g[i] < 0]
    if no == half:
        return [(i, X) for i in L.cells if g[i] < 0]
    return []


def missing(g, L):
    half = L.n // 2
    nx = sum(1 for i in L.cells if g[i] == X)
    no = sum(1 for i in L.cells if g[i] == O)
    return half - nx, half - no


def t4(g, ls, L):
    mx, mo = missing(g, L)
    if min(mx, mo) != 1:
        return []
    cands, known, _ = candidates(g, ls, L, False)
    return forced_from(cands, known, L)


def t5(g, ls, L):
    mx, mo = missing(g, L)
    if mx != 1 or mo != 1:
        return []
    cands, known, _ = candidates(g, ls, L, True)
    return forced_from(cands, known, L)


def t6(g, ls, L, uniq):
    known, xs = state(g, L)
    if is_full(known, L.n):
        return []
    cands, known, _ = candidates(g, ls, L, uniq)
    return forced_from(cands, known, L)


def _dedupe(found):
    out, seen = [], {}
    for i, v in found:
        if i in seen:
            if seen[i] != v:
                raise Contradiction("Feld %d" % i)
            continue
        seen[i] = v
        out.append((i, v))
    return out


# ---------------------------------------------------------------- T8 Linienpaar

def _pair_lines(ls, kind):
    return [L for L in ls if L.kind == kind]


def t8_pair(g, ls, A, B, limit):
    """Zwei parallele Linien A, B (Abstand 1 oder 2) gemeinsam auswerten."""
    par = _pair_lines(ls, A.kind)
    m = len(par)              # Anzahl paralleler Linien = Länge der Querlinien
    n = A.n
    full = (1 << n) - 1
    ka, _ = state(g, A)
    kb, _ = state(g, B)
    if is_full(ka, n) or is_full(kb, n):
        return []
    ca, ka, _ = candidates(g, ls, A, True)
    cb, kb, _ = candidates(g, ls, B, True)
    if not ca or not cb:
        raise Contradiction(A.name())
    if len(ca) * len(cb) > limit or (len(ca) == 1 and len(cb) == 1):
        return []
    st = [state(g, M) for M in par]
    a, b = A.idx, B.idx
    half = m // 2
    # Anzahl X/O je Querlinie ohne A und B
    cntx = [0] * n
    cnto = [0] * n
    for j, (k, x) in enumerate(st):
        if j in (a, b):
            continue
        for q in range(n):
            if k >> q & 1:
                if x >> q & 1:
                    cntx[q] += 1
                else:
                    cnto[q] += 1
    room1x = room2x = room1o = room2o = 0
    for q in range(n):
        if cntx[q] <= half - 1:
            room1x |= 1 << q
        if cntx[q] <= half - 2:
            room2x |= 1 << q
        if cnto[q] <= half - 1:
            room1o |= 1 << q
        if cnto[q] <= half - 2:
            room2o |= 1 << q
    windows = [s for s in range(m - 2) if a in (s, s + 1, s + 2) or b in (s, s + 1, s + 2)]
    ok_a, ok_b = set(), set()
    for pa in ca:
        for pb in cb:
            if pa == pb:
                continue
            oa, ob = ~pa & full, ~pb & full
            if pa & pb & ~room2x or (pa | pb) & ~room1x:
                continue
            if oa & ob & ~room2o or (oa | ob) & ~room1o:
                continue
            bad = False
            for s in windows:
                kk, xx = full, full
                oo = full
                for j in (s, s + 1, s + 2):
                    if j == a:
                        kj, xj = full, pa
                    elif j == b:
                        kj, xj = full, pb
                    else:
                        kj, xj = st[j]
                    kk &= kj
                    xx &= xj
                    oo &= ~xj
                if kk & (xx | (oo & full)):
                    bad = True
                    break
            if bad:
                continue
            ok_a.add(pa)
            ok_b.add(pb)
    if not ok_a:
        raise Contradiction(A.name() + "/" + B.name())
    return _dedupe(forced_from(list(ok_a), ka, A) + forced_from(list(ok_b), kb, B))


def t8(g, ls, limit):
    for kind in ("row", "col"):
        par = _pair_lines(ls, kind)
        for i in range(len(par)):
            for d in (1, 2):
                if i + d < len(par):
                    found = t8_pair(g, ls, par[i], par[i + d], limit)
                    if found:
                        return found, (par[i], par[i + d])
    return [], None


# ---------------------------------------------------------------- Fixpunkt (schnell, für den Generator)

def fixpoint(g, w, h, level, limits=LIMITS):
    """Wendet alle Techniken bis Stufe level (Rang 1–4) bis zum Stillstand an.

    Alle Techniken bis T8 sind monoton: der Endstand hängt nicht von der Reihenfolge
    ab, also löst der Fixpunkt genau dann, wenn der schrittweise Löser löst.
    Rückgabe 1 gelöst, 0 steckt fest, −1 Widerspruch; g wird verändert.
    """
    ls, by_cell = lines_of(w, h)
    dirty = set(range(len(ls)))
    index = {id(L): k for k, L in enumerate(ls)}
    try:
        while True:
            while dirty:
                k = dirty.pop()
                L = ls[k]
                found = []
                pair, gap = t1_t2(g, L)
                found = pair + gap + t3(g, L)
                if not found and level >= 2:
                    found = t4(g, ls, L) or t5(g, ls, L)
                if not found and level >= 3:
                    found = t6(g, ls, L, True)
                for i, v in _dedupe(found):
                    if g[i] >= 0:
                        if g[i] != v:
                            return -1
                        continue
                    g[i] = v
                    for M in by_cell[i]:
                        dirty.add(index[id(M)])
                        # T5/T7 hängen von fertigen Linien ab
                        if level >= 2 and is_full(state(g, M)[0], M.n):
                            dirty.update(index[id(P)] for P in ls if P.kind == M.kind)
                if found:
                    dirty.add(k)
            if level < 4:
                break
            found, _ = t8(g, ls, limits["pair_combos"])
            if not found:
                break
            for i, v in found:
                g[i] = v
                for M in by_cell[i]:
                    dirty.add(index[id(M)])
    except Contradiction:
        return -1
    if EMPTY in g:
        return 0
    return 1 if valid_solution(g, w, h) else -1


def valid_solution(g, w, h):
    ls, _ = lines_of(w, h)
    seen = set()
    for L in ls:
        known, xs = state(g, L)
        if not is_full(known, L.n) or xs not in patterns(L.n) or (L.kind, xs) in seen:
            return False
        seen.add((L.kind, xs))
    return True


# ---------------------------------------------------------------- T9 Wenn-dann (Werkstatt-Regel)

def bounded_test(g, w, h, cell, value, rounds):
    """Annahme g[cell] = value; Runde 1 = die Linien durch das Feld, Runde k+1 = die
    Linien durch die in Runde k gesetzten Felder; je Linie T1–T7. Widerspruch innerhalb
    von `rounds` Runden → Rückgabe Anzahl der benutzten Runden, sonst None."""
    ls, by_cell = lines_of(w, h)
    t = list(g)
    t[cell] = value
    todo = list(by_cell[cell])
    for r in range(1, rounds + 1):
        changed = []
        try:
            for L in todo:
                pair, gap = t1_t2(t, L)
                found = _dedupe(pair + gap + t3(t, L) + t6(t, ls, L, True))
                for i, v in found:
                    if t[i] < 0:
                        t[i] = v
                        changed.append(i)
        except Contradiction:
            return r
        if EMPTY not in t and not valid_solution(t, w, h):
            return r
        if not changed:
            return None
        seen, todo = set(), []
        for i in changed:
            for L in by_cell[i]:
                if id(L) not in seen:
                    seen.add(id(L))
                    todo.append(L)
    return None


def find_test(g, w, h, rounds):
    """Erster Wenn-dann-Schluss: (feld, wert, runden) oder None. Kurze Ketten zuerst."""
    empties = [i for i, v in enumerate(g) if v < 0]
    for r in range(1, rounds + 1):
        for i in empties:
            for v in (O, X):
                used = bounded_test(g, w, h, i, v, r)
                if used is not None:
                    return i, 1 - v, used
    return None


# ---------------------------------------------------------------- Stufe

def required_level(clues, w, h, limits=LIMITS):
    """Niedrigste Stufe (Rang 1–5), deren Techniken lösen; 6 = nur mit Raten."""
    for lv in range(1, 5):
        if fixpoint(list(clues), w, h, lv, limits) == 1:
            return lv
    ok, _, _ = solve_with_tests(clues, w, h, limits)
    return 5 if ok else 6


def solve_with_tests(clues, w, h, limits=LIMITS):
    """T1–T8 bis zum Stillstand, dann ein Wenn-dann-Schluss, wieder von vorn.
    Rückgabe (gelöst, gitter, liste der kettenlängen)."""
    g = list(clues)
    chains = []
    while True:
        s = fixpoint(g, w, h, 4, limits)
        if s == 1:
            return True, g, chains
        if s == -1 or len(chains) >= limits["tests"]:
            return False, g, chains
        t = find_test(g, w, h, limits["rounds"])
        if t is None:
            return False, g, chains
        i, v, used = t
        g[i] = v
        chains.append(used)


# ---------------------------------------------------------------- Lösungsweg (schrittweise)

def solve_path(clues, w, h, limits=LIMITS):
    """Schrittweiser Löser: immer die einfachste Technik, die etwas bewirkt, dann
    zurück zu T1. Jeder Schritt setzt die Felder einer Linie (eines Linienpaars,
    eines Wenn-dann-Schlusses). Rückgabe (gelöst, gitter, schritte)."""
    ls, _ = lines_of(w, h)
    g = list(clues)
    steps = []
    tests = 0
    try:
        while EMPTY in g:
            step = None
            for key in ("T1", "T2", "T3", "T4", "T5", "T6", "T7"):
                for L in ls:
                    if key in ("T1", "T2"):
                        pair, gap = t1_t2(g, L)
                        found = pair if key == "T1" else gap
                    elif key == "T3":
                        found = t3(g, L)
                    elif key == "T4":
                        found = t4(g, ls, L)
                    elif key == "T5":
                        found = t5(g, ls, L)
                    else:
                        found = t6(g, ls, L, key == "T7")
                    found = [(i, v) for i, v in _dedupe(found) if g[i] < 0]
                    if found:
                        step = (key, found, L.name())
                        break
                if step:
                    break
            if not step:
                found, pair = t8(g, ls, limits["pair_combos"])
                if found:
                    step = ("T8", found, pair[0].name() + " + " + pair[1].name())
            if not step:
                if tests >= limits["tests"]:
                    break
                t = find_test(g, w, h, limits["rounds"])
                if t is None:
                    break
                tests += 1
                i, v, used = t
                step = ("T9", [(i, v)], "%d Runden" % used)
            for i, v in step[1]:
                g[i] = v
            steps.append({"tech": step[0], "cells": step[1], "where": step[2]})
    except Contradiction:
        return False, g, steps
    return (EMPTY not in g and valid_solution(g, w, h)), g, steps


def level_of_path(steps):
    return max((TECH_RANK[s["tech"]] for s in steps), default=1)


# ---------------------------------------------------------------- Punkte (Werkstatt-Formel)

# Halbwerte: Median der Last je Stufe, 25 Rätsel 8 × 8 je Stufe (13.10.2026); vorläufig.
HALF = {1: 27.5, 2: 8.6, 3: 2.5, 4: 0.9, 5: 1.75}


def load(steps, rank):
    """Last = Σ Hürden (1 + h) − 1 + log2(1 + Kleinarbeit).

    Hürde = Schritt der Rätselstufe; Kleinarbeit 0,1 je Schritt eine Stufe tiefer,
    0,02 noch tiefer. Leicht hat keine Stufe darunter: dort zählen Lücke und
    Abzählen als Hürden (schwerer zu sehen als ein Paar)."""
    hurdles, small = 0.0, 0.0
    for s in steps:
        r = TECH_RANK[s["tech"]]
        hval = TECH[s["tech"]][3]
        if rank == 1:
            if s["tech"] != "T1":
                hurdles += 1 + hval
            else:
                small += 0.1
        elif r == rank:
            hurdles += 1 + hval
        elif r == rank - 1:
            small += 0.1
        else:
            small += 0.02
    return max(0.0, hurdles - 1) + math.log2(1 + small)


def points(steps, rank):
    last = load(steps, rank)
    half = HALF.get(rank, 1.0)
    bonus = min(99, int(round(99 * last / (last + half)))) if last > 0 else 0
    return 100 * rank + bonus, last


# ---------------------------------------------------------------- Erzeugen

def random_solution(w, h, rnd):
    while True:
        g = [EMPTY] * (w * h)
        dead = False
        while EMPTY in g and not dead:
            cell = rnd.choice([i for i, v in enumerate(g) if v < 0])
            v = rnd.randint(0, 1)
            t = list(g)
            t[cell] = v
            if fixpoint(t, w, h, 3) == -1:
                t = list(g)
                t[cell] = 1 - v
                if fixpoint(t, w, h, 3) == -1:
                    dead = True
                    continue
            g = t
        if not dead and valid_solution(g, w, h):
            return g


def solvable_at(g, w, h, rank, limits=LIMITS):
    if fixpoint(list(g), w, h, min(rank, 4), limits) == 1:
        return True
    if rank >= 5:
        return solve_with_tests(g, w, h, limits)[0]
    return False


def generate(w, h, level, rnd, deadline=None, progress=None, limits=LIMITS):
    """Ein Rätsel genau der Stufe `level` (Schlüssel aus LEVELS) oder None nach Ablauf.

    1. Zufällige Lösung. 2. Jede Vorgabe in zufälliger Reihenfolge streichen, wenn das
    Rätsel ohne sie noch auf der Zielstufe lösbar ist (ein Durchgang genügt: weniger
    Vorgaben erlauben nie mehr Schlüsse). 3. Nur bei exakt passender Stufe behalten.
    Die Eindeutigkeit beweist danach der unabhängige Prüfer (pruefer.py)."""
    target = RANK[level]
    attempt = 0
    while deadline is None or time.monotonic() < deadline:
        attempt += 1
        if progress:
            progress("Versuch %d" % attempt)
        sol = random_solution(w, h, rnd)
        g = list(sol)
        order = list(range(w * h))
        rnd.shuffle(order)
        for i in order:
            keep, g[i] = g[i], EMPTY
            if not solvable_at(g, w, h, target, limits):
                g[i] = keep
        if required_level(g, w, h, limits) == target:
            return {"clues": g, "solution": sol, "attempts": attempt}
    return None


# ---------------------------------------------------------------- Identität

def _transforms(w, h):
    """Abbildungen Feld → Feld (Drehung/Spiegelung); bei Rechtecken nur die vier,
    die das Format erhalten."""
    res = []
    for t in range(8):
        f = []
        tw, th = (h, w) if t in (1, 3, 4, 6) else (w, h)
        if (tw, th) != (w, h) and w != h:
            continue
        for r in range(h):
            for c in range(w):
                if t == 0:
                    rr, cc = r, c
                elif t == 1:
                    rr, cc = c, h - 1 - r
                elif t == 2:
                    rr, cc = h - 1 - r, w - 1 - c
                elif t == 3:
                    rr, cc = w - 1 - c, r
                elif t == 4:
                    rr, cc = c, r
                elif t == 5:
                    rr, cc = r, w - 1 - c
                elif t == 6:
                    rr, cc = w - 1 - c, h - 1 - r
                else:
                    rr, cc = h - 1 - r, c
                f.append(rr * tw + cc)
        res.append(f)
    return res


def identity(clues, w, h):
    """Gleich bis auf Drehung, Spiegelung und Tausch von X und O."""
    best = None
    for f in _transforms(w, h):
        for swap in (False, True):
            out = [EMPTY] * (w * h)
            for i, v in enumerate(clues):
                out[f[i]] = v if v < 0 or not swap else 1 - v
            s = "".join(".OX"[v + 1] for v in out)
            if best is None or s < best:
                best = s
    return best


# ---------------------------------------------------------------- Ein-/Ausgabe

def to_rows(g, w):
    return ["".join(".OX"[v + 1] for v in g[r * w:(r + 1) * w]) for r in range(len(g) // w)]


def from_rows(rows):
    m = {".": EMPTY, "O": O, "X": X, "o": O, "x": X, "0": O, "1": X}
    return [m[ch] for row in rows for ch in row]
