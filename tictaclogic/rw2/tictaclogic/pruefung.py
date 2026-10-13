"""Vollständige Prüfung eines TicTacLogic-Rätsels (vor dem Speichern und vor jedem Export).

1. Regeln: Lösung vollständig und regelgerecht, Vorgaben passen zur Lösung.
2. Logikweg: die Leiter löst ohne Raten genau zur gespeicherten Lösung.
3. Stufe: die niedrigste lösende Stufe ist die gespeicherte (sonst Meldung).
4. Eindeutigkeit: unabhängiges CP-SAT-Modell (pruefer.py).
Jeder Fehler ist ein ValueError mit deutscher Meldung.
"""

from . import engine as E
from . import pruefer


def verify(puzzle, solution, meta):
    w, h = puzzle["cols"], puzzle["rows"]
    clues = E.from_rows(puzzle["givens"])
    sol = E.from_rows(solution["grid"])
    if w % 2 or h % 2 or len(clues) != w * h or len(sol) != w * h:
        raise ValueError("Format: Breite und Höhe müssen gerade sein und zu den Zeilen passen.")
    if not E.valid_solution(sol, w, h):
        raise ValueError("Die Lösung verletzt eine Regel.")
    if any(c >= 0 and c != s for c, s in zip(clues, sol)):
        raise ValueError("Eine Vorgabe widerspricht der Lösung.")
    solved, grid, steps = E.solve_path(clues, w, h)
    if not solved:
        raise ValueError("Ohne Raten nicht lösbar (Leiter T1–T9 nach Werkstatt-Regel).")
    if grid != sol:
        raise ValueError("Der Logikweg führt zu einer anderen Lösung.")
    rank = E.level_of_path(steps)
    key = E.LEVELS[rank - 1][0]
    tests = [s for s in steps if s["tech"] == "T9"]
    if len(tests) > E.LIMITS["tests"]:
        raise ValueError("Mehr als %d Wenn-dann-Schlüsse." % E.LIMITS["tests"])
    if meta.get("level") and meta["level"] != key:
        raise ValueError("Stufe weicht ab: gespeichert %s, die Leiter ergibt %s."
                         % (meta["level"], key))
    if not pruefer.unique(w, h, clues, sol):
        raise ValueError("Nicht eindeutig (unabhängige Prüfung mit CP-SAT).")
    pts, last = E.points(steps, rank)
    out = dict(meta)
    techs = {}
    for s in steps:
        techs[s["tech"]] = techs.get(s["tech"], 0) + 1
    out.update({"level": key, "size": "%d × %d" % (w, h), "clues": sum(c >= 0 for c in clues),
                "techniques": techs, "tests": len(tests), "score": pts,
                "engine": E.VERSION})
    return out
