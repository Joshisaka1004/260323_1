"""Unabhängiger Prüfer für TicTacLogic: eigenes CP-SAT-Modell allein aus den Regeln.

Benutzt keinen Code der Engine. Eindeutig heißt: genau eine Lösung, Suche vollständig,
gleich der gespeicherten Lösung.
"""

from ortools.sat.python import cp_model


def _model(w, h, givens):
    m = cp_model.CpModel()
    x = [[m.NewBoolVar("x%d_%d" % (r, c)) for c in range(w)] for r in range(h)]
    for r in range(h):
        for c in range(w):
            v = givens[r * w + c]
            if v in (0, 1):
                m.Add(x[r][c] == v)
    rows = [[x[r][c] for c in range(w)] for r in range(h)]
    cols = [[x[r][c] for r in range(h)] for c in range(w)]
    for line in rows + cols:
        m.Add(sum(line) == len(line) // 2)                 # gleich viele X wie O
        for k in range(len(line) - 2):                      # nie drei gleiche
            m.Add(sum(line[k:k + 3]) >= 1)
            m.Add(sum(line[k:k + 3]) <= 2)
    for group in (rows, cols):                              # keine zwei Linien gleich
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                diffs = []
                for p, q in zip(group[a], group[b]):
                    d = m.NewBoolVar("")
                    m.AddBoolXOr([p, q, d.Not()])           # d = p xor q
                    diffs.append(d)
                m.AddBoolOr(diffs)
    return m, x


def count_solutions(w, h, givens, limit=2, seconds=60.0):
    """(anzahl bis limit, erste lösung als liste, vollständig)."""
    m, x = _model(w, h, givens)
    found = []
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = 1
    while len(found) < limit:
        st = solver.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return len(found), (found[0] if found else None), st == cp_model.INFEASIBLE
        sol = [int(solver.Value(x[r][c])) for r in range(h) for c in range(w)]
        found.append(sol)
        # nächste Lösung muss sich in mindestens einem Feld unterscheiden
        m.AddBoolOr([x[r][c].Not() if sol[r * w + c] else x[r][c] for r in range(h) for c in range(w)])
    return len(found), found[0], True


def unique(w, h, givens, solution, seconds=60.0):
    n, first, complete = count_solutions(w, h, givens, 2, seconds)
    return n == 1 and complete and list(first) == list(solution)
