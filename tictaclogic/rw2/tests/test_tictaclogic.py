"""Tests für die TicTacLogic-Engine (python -m unittest discover -s tests -t .)."""

import random
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tictaclogic import engine as E          # noqa: E402
from tictaclogic import pruefer, pruefung     # noqa: E402


def make(w, level, seed):
    res = E.generate(w, w, level, random.Random(seed))
    puzzle = {"rows": w, "cols": w, "givens": E.to_rows(res["clues"], w)}
    solution = {"grid": E.to_rows(res["solution"], w)}
    return res, puzzle, solution


class Stufen(unittest.TestCase):
    def test_jede_stufe_exakt_eindeutig_minimal(self):
        for level, _ in E.LEVELS:
            for seed in (1, 2):
                res, puzzle, solution = make(6 if level != "extreme" else 8, level, seed)
                w = puzzle["cols"]
                meta = pruefung.verify(puzzle, solution, {"level": level})
                self.assertEqual(meta["level"], level)
                # Stufe darunter löst nicht
                rank = E.RANK[level]
                if rank > 1:
                    self.assertFalse(E.solvable_at(res["clues"], w, w, rank - 1))
                # jede Vorgabe ist nötig (auf der Zielstufe)
                for i, v in enumerate(res["clues"]):
                    if v >= 0:
                        g = list(res["clues"])
                        g[i] = E.EMPTY
                        self.assertFalse(E.solvable_at(g, w, w, rank), "Vorgabe %d überflüssig" % i)
                # Punkte im Band der Stufe
                self.assertTrue(100 * rank <= meta["score"] <= 100 * rank + 99)

    def test_werkstatt_regel_wenn_dann(self):
        res, puzzle, solution = make(8, "extreme", 7)
        ok, g, chains = E.solve_with_tests(res["clues"], 8, 8)
        self.assertTrue(ok)
        self.assertTrue(1 <= len(chains) <= 5)
        self.assertTrue(all(c <= 3 for c in chains))


class Korrektheit(unittest.TestCase):
    def test_keine_technik_verliert_die_loesung(self):
        """Zufällige Teilbelegungen echter Lösungen: jede Folgerung stimmt mit der Lösung."""
        rnd = random.Random(5)
        for _ in range(60):
            w = rnd.choice([6, 8, 10])
            sol = E.random_solution(w, w, rnd)
            g = [v if rnd.random() < rnd.uniform(0.2, 0.6) else E.EMPTY for v in sol]
            for lv in (1, 2, 3, 4):
                t = list(g)
                self.assertNotEqual(E.fixpoint(t, w, w, lv), -1)
                self.assertTrue(all(a < 0 or a == b for a, b in zip(t, sol)))
            ok, path_grid, steps = E.solve_path(g, w, w)
            self.assertTrue(all(a < 0 or a == b for a, b in zip(path_grid, sol)))

    def test_manipulation_wird_erkannt(self):
        res, puzzle, solution = make(6, "hard", 3)
        bad = dict(solution, grid=list(solution["grid"]))
        row = bad["grid"][0]
        bad["grid"][0] = row[::-1]
        with self.assertRaises(ValueError):
            pruefung.verify(puzzle, bad, {"level": "hard"})
        with self.assertRaises(ValueError):
            pruefung.verify(puzzle, solution, {"level": "easy"})
        # eine Vorgabe weniger als nötig → mehrdeutig oder Stufe weicht ab
        g = E.from_rows(puzzle["givens"])
        i = next(k for k, v in enumerate(g) if v >= 0)
        g[i] = E.EMPTY
        with self.assertRaises(ValueError):
            pruefung.verify({"rows": 6, "cols": 6, "givens": E.to_rows(g, 6)}, solution, {"level": "hard"})

    def test_pruefer_erkennt_mehrdeutig(self):
        empty = [E.EMPTY] * 36
        n, _, complete = pruefer.count_solutions(6, 6, empty, 2)
        self.assertEqual(n, 2)


class Identitaet(unittest.TestCase):
    def test_drehung_spiegelung_tausch(self):
        res, puzzle, _ = make(6, "medium", 11)
        g, w = res["clues"], 6
        base = E.identity(g, w, w)
        rot = [g[(w - 1 - c) * w + r] for r in range(w) for c in range(w)]       # 90°
        mir = [g[r * w + (w - 1 - c)] for r in range(w) for c in range(w)]
        swp = [v if v < 0 else 1 - v for v in g]
        for other in (rot, mir, swp):
            self.assertEqual(E.identity(other, w, w), base)


if __name__ == "__main__":
    unittest.main()
