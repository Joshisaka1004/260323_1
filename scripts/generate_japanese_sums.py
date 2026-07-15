"""
Unified Japanese Sums generator (sizes 3x3 through 20x20 and rectangles) with export options.

This variant biases clue generation toward a wider mix of small, medium, and
large sums while keeping uniqueness checks intact. For sizes 16x16 and above
the digit set extends to 1-10, and for 18x18 or larger the digit set extends
further to 1-12 to keep uniqueness feasible on longer lines.

Mac/PyCharm export enhancements:
- Automatic higher render scale + DPI on macOS (non-Pythonista)
- High-resolution PNG/PDF output while remaining Pythonista compatible
- Optional environment overrides: JAPSUM_EXPORT_SCALE, JAPSUM_EXPORT_DPI
"""
from __future__ import annotations

import os
import random
import sys
import unicodedata
from copy import deepcopy
from functools import lru_cache
from itertools import combinations, permutations
from typing import Iterable, List, Optional, Sequence, Tuple, Union

Image = None  # type: ignore
ImageDraw = None  # type: ignore
ImageFont = None  # type: ignore


def _try_import_pillow() -> bool:
    global Image, ImageDraw, ImageFont
    try:
        from PIL import Image as PILImage, ImageDraw as PILImageDraw, ImageFont as PILImageFont

        Image = PILImage  # type: ignore
        ImageDraw = PILImageDraw  # type: ignore
        ImageFont = PILImageFont  # type: ignore
        return True
    except Exception:
        Image = None  # type: ignore
        ImageDraw = None  # type: ignore
        ImageFont = None  # type: ignore
        return False


_try_import_pillow()


Digit = int
CellValue = int  # 0 for black, 1-9/1-10/1-12 for digits
Pattern = Tuple[CellValue, ...]
ClueToken = Union[int, str]  # int, "?", "??"
LineClues = Optional[List[ClueToken]]

_ONE_DIGIT_UNKNOWN = -1
_TWO_DIGIT_UNKNOWN = -2


# ----------------------------- Solver utilities -----------------------------

def _min_cells_for_groups(groups_remaining: int) -> int:
    if groups_remaining <= 0:
        return 0
    return groups_remaining + (groups_remaining - 1)


@lru_cache(maxsize=None)
def _digit_sequences_for_sum_cached(
    target: int, length: int, used_tuple: Tuple[int, ...], max_digit: int
) -> List[Tuple[Digit, ...]]:
    """Return ordered digit tuples of given length that sum to target without reusing used digits."""
    candidates: List[Tuple[Digit, ...]] = []
    used = set(used_tuple)
    available = [d for d in range(1, max_digit + 1) if d not in used]
    for combo in combinations(available, length):
        if sum(combo) != target:
            continue
        for perm in permutations(combo):
            candidates.append(perm)
    return candidates


def _digit_sequences_for_sum(target: int, length: int, used: set[int], max_digit: int) -> List[Tuple[Digit, ...]]:
    return _digit_sequences_for_sum_cached(target, length, tuple(sorted(used)), max_digit)


@lru_cache(maxsize=None)
def _digit_sequences_for_sum_range_cached(
    min_target: int, max_target: int, length: int, used_tuple: Tuple[int, ...], max_digit: int
) -> List[Tuple[Digit, ...]]:
    candidates: List[Tuple[Digit, ...]] = []
    used = set(used_tuple)
    available = [d for d in range(1, max_digit + 1) if d not in used]
    for combo in combinations(available, length):
        s = sum(combo)
        if s < min_target or s > max_target:
            continue
        for perm in permutations(combo):
            candidates.append(perm)
    return candidates


def _digit_sequences_for_sum_range(
    min_target: int, max_target: int, length: int, used: set[int], max_digit: int
) -> List[Tuple[Digit, ...]]:
    return _digit_sequences_for_sum_range_cached(min_target, max_target, length, tuple(sorted(used)), max_digit)


def _normalize_line_clues(clues: LineClues) -> Tuple[int, ...] | None:
    if clues is None:
        return None
    normalized: List[int] = []
    for clue in clues:
        if isinstance(clue, int):
            if clue <= 0:
                raise ValueError(f"Invalid clue value: {clue}")
            normalized.append(clue)
        elif clue == "?":
            normalized.append(_ONE_DIGIT_UNKNOWN)
        elif clue == "??":
            normalized.append(_TWO_DIGIT_UNKNOWN)
        else:
            raise ValueError(f"Unsupported clue token: {clue}")
    return tuple(normalized)


@lru_cache(maxsize=None)
def _build_line_patterns_cached(size: int, clues_key: Tuple[int, ...], max_digit: int) -> List[Pattern]:
    clues = list(clues_key)
    results: List[Pattern] = []

    def backtrack(clue_idx: int, pos: int, used: set[int], current: List[CellValue]) -> None:
        if clue_idx == len(clues):
            if len(current) < size:
                current.extend([0] * (size - len(current)))
            results.append(tuple(current))
            for _ in range(size - pos):
                current.pop()
            return

        remaining_groups = len(clues) - clue_idx
        min_needed = _min_cells_for_groups(remaining_groups)
        max_lead = size - pos - min_needed
        for lead in range(max_lead + 1):
            current.extend([0] * lead)
            pos_after_lead = pos + lead
            remaining_slots = size - pos_after_lead
            min_after_group = _min_cells_for_groups(remaining_groups - 1)
            for length in range(1, remaining_slots - min_after_group + 1):
                for digits in _digit_sequences_for_sum(clues[clue_idx], length, used, max_digit):
                    used.update(digits)
                    current.extend(digits)
                    new_pos = pos_after_lead + length
                    if clue_idx < len(clues) - 1:
                        if new_pos >= size:
                            current[:] = current[:pos_after_lead]
                            used.difference_update(digits)
                            continue
                        current.append(0)
                        backtrack(clue_idx + 1, new_pos + 1, used, current)
                        current.pop()
                    else:
                        backtrack(clue_idx + 1, new_pos, used, current)
                    current[:] = current[:pos_after_lead]
                    used.difference_update(digits)
            current[:] = current[:pos]

    backtrack(0, 0, set(), [])
    return results


@lru_cache(maxsize=None)
def _build_any_line_patterns_cached(size: int, max_digit: int) -> List[Pattern]:
    """All lines with unique non-zero digits and at least one black and one digit."""
    if size > 8:
        raise RuntimeError("Sparse line clues without sums are currently limited to board side <= 8.")

    results: List[Pattern] = []
    digits = list(range(1, max_digit + 1))

    def backtrack(pos: int, used: set[int], current: List[CellValue], has_black: bool, has_digit: bool) -> None:
        if pos == size:
            if has_black and has_digit:
                results.append(tuple(current))
            return

        current.append(0)
        backtrack(pos + 1, used, current, True, has_digit)
        current.pop()

        for d in digits:
            if d in used:
                continue
            used.add(d)
            current.append(d)
            backtrack(pos + 1, used, current, has_black, True)
            current.pop()
            used.remove(d)

    backtrack(0, set(), [], False, False)
    return results


def build_line_patterns(size: int, clues: LineClues, max_digit: int) -> List[Pattern]:
    """Generate all row/column patterns matching an exact, masked, or omitted clue list."""
    clues_key = _normalize_line_clues(clues)
    if clues_key is None:
        return list(_build_any_line_patterns_cached(size, max_digit))

    if _ONE_DIGIT_UNKNOWN not in clues_key and _TWO_DIGIT_UNKNOWN not in clues_key:
        return list(_build_line_patterns_cached(size, clues_key, max_digit))

    results: List[Pattern] = []

    def backtrack(clue_idx: int, pos: int, used: set[int], current: List[CellValue]) -> None:
        if clue_idx == len(clues_key):
            if len(current) < size:
                current.extend([0] * (size - len(current)))
            results.append(tuple(current))
            for _ in range(size - pos):
                current.pop()
            return

        remaining_groups = len(clues_key) - clue_idx
        min_needed = _min_cells_for_groups(remaining_groups)
        max_lead = size - pos - min_needed
        for lead in range(max_lead + 1):
            current.extend([0] * lead)
            pos_after_lead = pos + lead
            remaining_slots = size - pos_after_lead
            min_after_group = _min_cells_for_groups(remaining_groups - 1)
            for length in range(1, remaining_slots - min_after_group + 1):
                clue_val = clues_key[clue_idx]
                if clue_val == _ONE_DIGIT_UNKNOWN:
                    digit_runs = _digit_sequences_for_sum_range(1, 9, length, used, max_digit)
                elif clue_val == _TWO_DIGIT_UNKNOWN:
                    digit_runs = _digit_sequences_for_sum_range(10, 99, length, used, max_digit)
                else:
                    digit_runs = _digit_sequences_for_sum(clue_val, length, used, max_digit)
                for digits in digit_runs:
                    used.update(digits)
                    current.extend(digits)
                    new_pos = pos_after_lead + length
                    if clue_idx < len(clues_key) - 1:
                        if new_pos >= size:
                            current[:] = current[:pos_after_lead]
                            used.difference_update(digits)
                            continue
                        current.append(0)
                        backtrack(clue_idx + 1, new_pos + 1, used, current)
                        current.pop()
                    else:
                        backtrack(clue_idx + 1, new_pos, used, current)
                    current[:] = current[:pos_after_lead]
                    used.difference_update(digits)
            current[:] = current[:pos]

    backtrack(0, 0, set(), [])
    return results


def _derive_clues_from_pattern(pattern: Sequence[CellValue]) -> List[int]:
    clues = []
    acc = 0
    for val in pattern + (0,):
        if val == 0:
            if acc:
                clues.append(acc)
            acc = 0
        else:
            acc += val
    return clues


def solve_japanese_sums(
    rows: int,
    cols: int,
    row_clues: List[LineClues],
    col_clues: List[LineClues],
    max_solutions: int = 2,
    max_digit: int = 9,
    branch_mode: str = "min",
) -> Tuple[int, List[List[CellValue]] | None]:
    """Return (solution_count, solution_grid_or_None). Stops after max_solutions."""
    row_domains = [build_line_patterns(cols, clues, max_digit) for clues in row_clues]
    col_domains = [build_line_patterns(rows, clues, max_digit) for clues in col_clues]

    if any(not opts for opts in row_domains) or any(not opts for opts in col_domains):
        return 0, None

    def propagate(r_dom: List[List[Pattern]], c_dom: List[List[Pattern]]) -> bool:
        changed = True
        while changed:
            changed = False
            for r in range(rows):
                for c in range(cols):
                    row_vals = {p[c] for p in r_dom[r]}
                    col_vals = {p[r] for p in c_dom[c]}
                    allowed = row_vals & col_vals
                    if not allowed:
                        return False
                    new_r = [p for p in r_dom[r] if p[c] in allowed]
                    if len(new_r) != len(r_dom[r]):
                        r_dom[r] = new_r
                        changed = True
                    new_c = [p for p in c_dom[c] if p[r] in allowed]
                    if len(new_c) != len(c_dom[c]):
                        c_dom[c] = new_c
                        changed = True
            if any(len(opts) == 0 for opts in r_dom) or any(len(opts) == 0 for opts in c_dom):
                return False
        return True

    def search(r_dom: List[List[Pattern]], c_dom: List[List[Pattern]], solutions: List[List[List[CellValue]]]) -> None:
        if len(solutions) >= max_solutions:
            return
        if not propagate(r_dom, c_dom):
            return
        if all(len(opts) == 1 for opts in r_dom) and all(len(opts) == 1 for opts in c_dom):
            grid = [list(opts[0]) for opts in r_dom]
            solutions.append(grid)
            return
        candidates = [(len(r_dom[i]), ('r', i)) for i in range(rows) if len(r_dom[i]) > 1] + [
            (len(c_dom[j]), ('c', j)) for j in range(cols) if len(c_dom[j]) > 1
        ]
        if branch_mode == "max":
            candidates.sort(key=lambda x: (x[0], x[1][0], x[1][1]), reverse=True)
        else:
            candidates.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
        _, (axis, idx) = candidates[0]
        patterns = r_dom[idx] if axis == 'r' else c_dom[idx]
        if branch_mode == "max":
            patterns = list(reversed(patterns))
        for pat in patterns:
            new_r = deepcopy(r_dom)
            new_c = deepcopy(c_dom)
            if axis == 'r':
                new_r[idx] = [pat]
            else:
                new_c[idx] = [pat]
            search(new_r, new_c, solutions)
            if len(solutions) >= max_solutions:
                return

    collected: List[List[List[CellValue]]] = []
    search(row_domains, col_domains, collected)
    return len(collected), (collected[0] if collected else None)


def _is_uniquely_solved_robust(
    rows: int,
    cols: int,
    row_clues: List[LineClues],
    col_clues: List[LineClues],
    max_digit: int,
    require_double_check: bool = True,
) -> Tuple[bool, List[List[CellValue]] | None]:
    """
    Robust uniqueness check via two independent search orders.
    Accept only if both checks confirm exactly one identical solution.
    """
    count_a, grid_a = solve_japanese_sums(
        rows, cols, row_clues, col_clues, max_solutions=2, max_digit=max_digit, branch_mode="min"
    )
    if count_a != 1 or grid_a is None:
        return False, None
    if not require_double_check:
        return True, grid_a

    count_b, grid_b = solve_japanese_sums(
        rows, cols, row_clues, col_clues, max_solutions=2, max_digit=max_digit, branch_mode="max"
    )
    if count_b != 1 or grid_b is None:
        return False, None
    if grid_a != grid_b:
        return False, None
    return True, grid_a


# --------------------------- Puzzle construction ---------------------------

def random_solution_grid(rows: int, cols: int, black_prob: float, max_digit: int) -> List[List[CellValue]]:
    """Create a random fully-specified grid with blacks and digits obeying row/column uniqueness."""
    grid = [[None for _ in range(cols)] for _ in range(rows)]

    def backtrack(pos: int) -> bool:
        if pos == rows * cols:
            return True
        r, c = divmod(pos, cols)
        if random.random() < black_prob:
            grid[r][c] = 0
            if backtrack(pos + 1):
                return True
            grid[r][c] = None
        used_row = {grid[r][k] for k in range(cols) if isinstance(grid[r][k], int) and grid[r][k] != 0}
        used_col = {grid[k][c] for k in range(rows) if isinstance(grid[k][c], int) and grid[k][c] != 0}
        candidates = [d for d in range(1, max_digit + 1) if d not in used_row and d not in used_col]
        random.shuffle(candidates)
        for d in candidates:
            grid[r][c] = d
            if backtrack(pos + 1):
                return True
        grid[r][c] = None
        return False

    for _ in range(150):
        if backtrack(0):
            row_ok = all(any(cell == 0 for cell in row) and any(cell != 0 for cell in row) for row in grid)
            col_ok = all(
                any(grid[r][c] == 0 for r in range(rows)) and any(grid[r][c] != 0 for r in range(rows))
                for c in range(cols)
            )
            max_row_whites = max(sum(1 for cell in row if cell != 0) for row in grid)
            max_col_whites = max(sum(1 for r in range(rows) if grid[r][c] != 0) for c in range(cols))
            if row_ok and col_ok and max_row_whites <= max_digit and max_col_whites <= max_digit:
                return grid
        grid = [[None for _ in range(cols)] for _ in range(rows)]
    raise RuntimeError("Failed to build random solution grid")


def _sample_black_prob(rows: int, cols: int, attempt: int, hard_mode: bool = False) -> float:
    """Vary black density to encourage a mix of clue sizes."""
    longest = max(rows, cols)
    # Three bands: low density (long runs), mid, and legacy high density.
    band = attempt % 3
    if band == 0:
        low = 0.18 + 0.01 * max(0, longest - 5)
        high = 0.32 + 0.01 * max(0, longest - 5)
    elif band == 1:
        low = 0.26 + 0.012 * max(0, longest - 5)
        high = 0.44 + 0.014 * max(0, longest - 5)
    else:
        low = 0.34 + 0.015 * max(0, longest - 5)
        high = 0.52 + 0.02 * max(0, longest - 5)
    if hard_mode:
        low = max(0.12, low - 0.05)
        high = max(0.18, high - 0.07)
    return random.uniform(min(low, 0.6), min(high, 0.7))


def _clue_spread_ok(row_clues: List[List[int]], col_clues: List[List[int]], rows: int, cols: int) -> bool:
    flat = [v for sub in row_clues + col_clues for v in sub]
    if not flat:
        return False
    small = sum(1 for v in flat if v <= 10)
    medium = sum(1 for v in flat if 11 <= v <= 17)
    large = sum(1 for v in flat if v >= 18)
    total = len(flat)
    medium_large = medium + large
    # Accept trivially small grids without forcing distribution.
    if total < 4:
        return True
    # Require at least a few mid/large clues to avoid overwhelming single digits.
    min_ml = max(2, total // 6)
    if medium_large < min_ml:
        return False
    # Avoid cases dominated by tiny sums.
    if small / total > 0.8:
        return False
    # Encourage at least one large clue on bigger boards.
    if max(rows, cols) >= 9 and large == 0:
        return False
    return True


def _hard_clue_profile_ok(
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    rows: int,
    cols: int,
    relaxed: bool = False,
) -> bool:
    flat = [v for sub in row_clues + col_clues for v in sub]
    if not flat:
        return False
    total = len(flat)
    max_allowed = int((rows + cols) * (1.7 if relaxed else 1.5))
    if total > max_allowed:
        return False
    small = sum(1 for v in flat if v <= 10)
    if small / total > (0.9 if relaxed else 0.8):
        return False
    max_clue = max(flat)
    target = 6 + max(rows, cols) if relaxed else 8 + max(rows, cols)
    if max_clue < target:
        return False
    return True


def _normalize_difficulty(level: str) -> str:
    val = (level or "").strip().lower()
    if val in {"easy", "e"}:
        return "easy"
    if val in {"medium", "m", "normal"}:
        return "medium"
    if val in {"hard", "h"}:
        return "hard"
    if val in {"veryhard", "very_hard", "very-hard", "vh"}:
        return "veryhard"
    if val in {"inhuman", "i"}:
        return "inhuman"
    return "medium"


def _difficulty_attempt_factor(difficulty: str) -> float:
    diff = _normalize_difficulty(difficulty)
    if diff == "easy":
        return 1.0
    if diff == "medium":
        return 1.15
    if diff == "hard":
        return 1.8
    if diff == "veryhard":
        return 2.5
    return 3.2


def _difficulty_uses_hard_black_bias(difficulty: str) -> bool:
    return _normalize_difficulty(difficulty) in {"hard", "veryhard", "inhuman"}


def _default_max_digit_for_longest(longest: int) -> int:
    if longest >= 18:
        return 12
    if longest >= 16:
        return 10
    return 9


def _default_attempts_for_longest(longest: int) -> int:
    if longest >= 20:
        return 2500
    if longest >= 18:
        return 2150
    if longest >= 16:
        return 1800
    if longest >= 14:
        return 1450
    if longest >= 11:
        return 1125
    if longest >= 9:
        return 900
    return 700


def _digit_policy_text() -> str:
    return "Digit range policy: up to 15x15 -> 1-9, 16x16-17x17 -> 1-10, 18x18-20x20 -> 1-12."


def _difficulty_hard_profile_gate(
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    rows: int,
    cols: int,
    attempt: int,
    max_attempts: int,
    difficulty: str,
    relax_level: int = 0,
) -> bool:
    diff = _normalize_difficulty(difficulty)
    if relax_level >= 2:
        if diff == "inhuman":
            diff = "hard"
        elif diff == "veryhard":
            diff = "medium"
        elif diff == "hard":
            diff = "easy"
    elif relax_level == 1:
        if diff == "inhuman":
            diff = "veryhard"
        elif diff == "veryhard":
            diff = "hard"
        elif diff == "hard":
            diff = "medium"

    progress = attempt / max(1, max_attempts)

    if diff in {"easy", "medium"}:
        return True
    if diff == "hard":
        if progress <= 0.6:
            return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=False)
        if progress <= 0.85:
            return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=True)
        return True
    if diff == "veryhard":
        if progress <= 0.65:
            return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=False)
        if progress <= 0.9:
            return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=True)
        return True
    # inhuman
    if progress <= 0.75:
        return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=False)
    if progress <= 0.95:
        return _hard_clue_profile_ok(row_clues, col_clues, rows, cols, relaxed=True)
    return True


def _few_one_two_clues_ok(
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    rows: int,
    cols: int,
    attempt: int,
    max_attempts: int,
    difficulty: str,
    relax_level: int = 0,
) -> bool:
    """
    Strongly discourage tiny clues (1/2) for classic Japanese Sums.
    Starts very strict, then relaxes late to avoid generation dead-ends.
    """
    flat = [v for sub in row_clues + col_clues for v in sub]
    if not flat:
        return False

    tiny = sum(1 for v in flat if v in (1, 2))
    total = len(flat)
    progress = attempt / max(1, max_attempts)
    diff = _normalize_difficulty(difficulty)
    longest = max(rows, cols)

    # On large boards (13x13+), tiny clues occur naturally much more often.
    # Use softer caps so generation remains feasible while still penalizing too many 1/2 clues.
    if longest >= 13:
        if diff == "easy":
            ratio_cap = 0.24
        elif diff == "medium":
            ratio_cap = 0.20
        elif diff == "hard":
            ratio_cap = 0.15
        elif diff == "veryhard":
            ratio_cap = 0.12
        else:  # inhuman
            ratio_cap = 0.10
        if progress > 0.85:
            ratio_cap += 0.03
        abs_cap = max(2, int(total * ratio_cap) + 1)
        return tiny <= abs_cap and (tiny / total) <= ratio_cap

    if relax_level >= 2:
        if diff == "inhuman":
            diff = "hard"
        elif diff == "veryhard":
            diff = "medium"
        elif diff == "hard":
            diff = "easy"
    elif relax_level == 1:
        if diff == "inhuman":
            diff = "veryhard"
        elif diff == "veryhard":
            diff = "hard"
        elif diff == "hard":
            diff = "medium"

    if diff == "easy":
        if progress <= 0.7:
            return tiny <= 2 and (tiny / total) <= 0.14
        return tiny <= 3 and (tiny / total) <= 0.2
    if diff == "medium":
        if progress <= 0.75:
            return tiny <= 1 and (tiny / total) <= 0.08
        return tiny <= 2 and (tiny / total) <= 0.12
    if diff == "hard":
        if progress <= 0.9:
            return tiny == 0
        return tiny <= 2 and (tiny / total) <= 0.08
    if diff == "veryhard":
        if progress <= 0.8:
            return tiny == 0
        return tiny <= 2 and (tiny / total) <= 0.07
    # inhuman
    if progress <= 0.9:
        return tiny == 0
    return tiny <= 2 and (tiny / total) <= 0.06


def derive_clues(grid: List[List[CellValue]]) -> Tuple[List[List[int]], List[List[int]]]:
    rows = [list(row) for row in grid]
    cols = [[grid[r][c] for r in range(len(grid))] for c in range(len(grid[0]))]
    return [
        _derive_clues_from_pattern(tuple(row)) for row in rows
    ], [
        _derive_clues_from_pattern(tuple(col)) for col in cols
    ]


def _clone_clue_specs(
    row_clues: List[List[int]],
    col_clues: List[List[int]],
) -> Tuple[List[LineClues], List[LineClues]]:
    return [list(rc) for rc in row_clues], [list(cc) for cc in col_clues]


def _make_sparse_variant_clues(
    rows: int,
    cols: int,
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    max_digit: int,
    robust_check: bool = True,
) -> Tuple[List[LineClues], List[LineClues]] | None:
    """
    Remove complete clue lines (set to None) while keeping uniqueness.
    Limited to side length <= 8 to keep unconstrained line domains manageable.
    """
    if max(rows, cols) > 8:
        return None

    row_candidates = list(range(rows))
    col_candidates = list(range(cols))
    random.shuffle(row_candidates)
    random.shuffle(col_candidates)

    for r_idx in row_candidates:
        trial_rows, trial_cols = _clone_clue_specs(row_clues, col_clues)
        trial_rows[r_idx] = None
        ok_row, _ = _is_uniquely_solved_robust(
            rows, cols, trial_rows, trial_cols, max_digit=max_digit, require_double_check=robust_check
        )
        if not ok_row:
            continue
        for c_idx in col_candidates:
            trial2_rows = deepcopy(trial_rows)
            trial2_cols = deepcopy(trial_cols)
            trial2_cols[c_idx] = None
            ok_both, _ = _is_uniquely_solved_robust(
                rows, cols, trial2_rows, trial2_cols, max_digit=max_digit, require_double_check=robust_check
            )
            if ok_both:
                return trial2_rows, trial2_cols
    return None


def _make_question_variant_clues(
    rows: int,
    cols: int,
    base_rows: List[LineClues],
    base_cols: List[LineClues],
    max_digit: int,
    max_masks: int = 8,
    robust_check: bool = True,
) -> Tuple[List[LineClues], List[LineClues]] | None:
    """Mask clue sums as ? / ?? while preserving uniqueness."""
    trial_rows = deepcopy(base_rows)
    trial_cols = deepcopy(base_cols)

    one_digit_candidates: List[Tuple[str, int, int]] = []
    two_digit_candidates: List[Tuple[str, int, int]] = []
    for r, clues in enumerate(trial_rows):
        if clues is None:
            continue
        for i, val in enumerate(clues):
            if isinstance(val, int):
                if val <= 9:
                    one_digit_candidates.append(("r", r, i))
                else:
                    two_digit_candidates.append(("r", r, i))
    for c, clues in enumerate(trial_cols):
        if clues is None:
            continue
        for i, val in enumerate(clues):
            if isinstance(val, int):
                if val <= 9:
                    one_digit_candidates.append(("c", c, i))
                else:
                    two_digit_candidates.append(("c", c, i))
    random.shuffle(one_digit_candidates)
    random.shuffle(two_digit_candidates)
    candidates = two_digit_candidates + one_digit_candidates

    target_masks = max(2, min(max_masks, len(candidates) // 5 if candidates else 0))
    applied = 0
    masked_one_digit = 0
    masked_two_digit = 0
    require_one_digit = len(one_digit_candidates) > 0
    require_two_digit = len(two_digit_candidates) > 0

    for axis, line_idx, clue_idx in candidates:
        if applied >= target_masks:
            break
        new_rows = deepcopy(trial_rows)
        new_cols = deepcopy(trial_cols)

        if axis == "r":
            current = new_rows[line_idx]
            if current is None:
                continue
            raw = current[clue_idx]
            if not isinstance(raw, int):
                continue
            if raw <= 9:
                current[clue_idx] = "?"
            else:
                current[clue_idx] = "??"
        else:
            current = new_cols[line_idx]
            if current is None:
                continue
            raw = current[clue_idx]
            if not isinstance(raw, int):
                continue
            if raw <= 9:
                current[clue_idx] = "?"
            else:
                current[clue_idx] = "??"

        ok_unique, _ = _is_uniquely_solved_robust(
            rows, cols, new_rows, new_cols, max_digit=max_digit, require_double_check=robust_check
        )
        if ok_unique:
            trial_rows = new_rows
            trial_cols = new_cols
            applied += 1
            if (axis == "r" and base_rows[line_idx] and isinstance(base_rows[line_idx][clue_idx], int) and base_rows[line_idx][clue_idx] <= 9) or (
                axis == "c" and base_cols[line_idx] and isinstance(base_cols[line_idx][clue_idx], int) and base_cols[line_idx][clue_idx] <= 9
            ):
                masked_one_digit += 1
            else:
                masked_two_digit += 1

    if applied == 0:
        return None
    if require_one_digit and masked_one_digit == 0:
        return None
    if require_two_digit and masked_two_digit == 0:
        return None
    return trial_rows, trial_cols


def generate_unique_puzzle(
    rows: int = 5,
    cols: int = 5,
    max_attempts: int = 800,
    max_digit: int | None = None,
    hard_mode: bool = False,
    variant: str = "classic",
    robust_unique_check: bool = True,
    difficulty: str = "medium",
) -> Tuple[List[LineClues], List[LineClues], List[List[CellValue]]]:
    """Generate a Japanese Sums puzzle (row clues, col clues, solution grid)."""
    longest = max(rows, cols)
    if variant == "sparse" and longest > 8:
        raise RuntimeError("Sparse-Variante ohne komplette Zeilen/Spalten-Clues ist aktuell auf max. 8x8 begrenzt.")
    diff = _normalize_difficulty(difficulty)
    # Backward compatibility with older callers using hard_mode.
    if hard_mode and diff in {"easy", "medium"}:
        diff = "hard"
    digits = max_digit or _default_max_digit_for_longest(longest)
    # Multi-phase search: strict first, then controlled relaxation for reliability.
    phase_attempts = [
        max_attempts,
        max(220, int(max_attempts * 0.45)),
        max(220, int(max_attempts * 0.45)),
    ]
    for relax_level, attempts_in_phase in enumerate(phase_attempts):
        for attempt in range(1, attempts_in_phase + 1):
            black_prob = _sample_black_prob(
                rows, cols, attempt, hard_mode=_difficulty_uses_hard_black_bias(diff)
            )
            try:
                solution = random_solution_grid(rows, cols, black_prob, digits)
            except RuntimeError:
                continue
            row_clues, col_clues = derive_clues(solution)
            if any(len(rc) == 0 for rc in row_clues) or any(len(cc) == 0 for cc in col_clues):
                continue
            if not _clue_spread_ok(row_clues, col_clues, rows, cols):
                continue
            if variant == "classic":
                if not _few_one_two_clues_ok(
                    row_clues,
                    col_clues,
                    rows,
                    cols,
                    attempt=attempt,
                    max_attempts=attempts_in_phase,
                    difficulty=diff,
                    relax_level=relax_level,
                ):
                    continue
            if not _difficulty_hard_profile_gate(
                row_clues,
                col_clues,
                rows,
                cols,
                attempt=attempt,
                max_attempts=attempts_in_phase,
                difficulty=diff,
                relax_level=relax_level,
            ):
                continue
            is_unique, solved_grid = _is_uniquely_solved_robust(
                rows,
                cols,
                row_clues,
                col_clues,
                max_digit=digits,
                require_double_check=robust_unique_check,
            )
            if not is_unique:
                continue

            if variant == "classic":
                return [list(rc) for rc in row_clues], [list(cc) for cc in col_clues], solved_grid

            if variant == "sparse":
                sparse_variant = _make_sparse_variant_clues(
                    rows, cols, row_clues, col_clues, digits, robust_check=robust_unique_check
                )
                if sparse_variant is None:
                    continue
                v_rows, v_cols = sparse_variant
                return v_rows, v_cols, solved_grid

            if variant == "question":
                sparse_variant = _make_sparse_variant_clues(
                    rows, cols, row_clues, col_clues, digits, robust_check=robust_unique_check
                )
                if sparse_variant is None:
                    base_rows, base_cols = _clone_clue_specs(row_clues, col_clues)
                else:
                    base_rows, base_cols = sparse_variant
                masked_variant = _make_question_variant_clues(
                    rows, cols, base_rows, base_cols, digits, robust_check=robust_unique_check
                )
                if masked_variant is None:
                    continue
                v_rows, v_cols = masked_variant
                return v_rows, v_cols, solved_grid

            raise RuntimeError(f"Unknown variant: {variant}")
    raise RuntimeError("Failed to generate a unique puzzle after multiple attempts")


# ------------------------------ Render helpers -----------------------------

def _load_font(size: int) -> ImageFont.ImageFont:
    """Load a TrueType font when possible, falling back to Pillow defaults."""
    if ImageFont is None:
        raise RuntimeError("Pillow not available")

    preferred = []
    env_font = os.environ.get("JAPSUM_FONT")
    if env_font:
        preferred.append(env_font)
    preferred.extend(
        [
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
    )

    for name in preferred:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _font_size(font: ImageFont.ImageFont) -> int:
    if hasattr(font, "size"):
        try:
            return int(getattr(font, "size"))
        except Exception:
            pass
    try:
        bbox = font.getbbox("0")
        return bbox[3] - bbox[1]
    except Exception:
        try:
            _, h = font.getsize("0")
            return h
        except Exception:
            return 20


def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int, int, int]:
    try:
        return draw.textbbox((0, 0), text, font=font)
    except Exception:
        w, h = draw.textsize(text, font=font)
        return (0, 0, w, h)


def _latin1_safe(text: str) -> str:
    """Return text reduced to Latin-1 friendly characters for PDF/image backends."""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("latin-1", errors="ignore").decode("latin-1")


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, center: Tuple[int, int], font: ImageFont.ImageFont, fill: str = "black") -> None:
    bbox = _text_bbox(draw, text, font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((center[0] - w // 2, center[1] - h // 2), text, font=font, fill=fill)


def _wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = _text_bbox(draw, candidate, font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _scale_px(v: int, scale: float) -> int:
    return max(1, int(round(v * scale)))


def _default_export_profile() -> tuple[float, int]:
    """Choose conservative defaults for Pythonista, high-res defaults for macOS desktop."""
    is_pythonista = "pythonista" in sys.executable.lower() or bool(os.environ.get("PYTHONISTA_HOME"))
    if sys.platform == "darwin" and not is_pythonista:
        return 2.0, 300
    return 1.0, 150


def _resolve_export_settings(
    render_scale: float | None,
    dpi: int | None,
    platform_hint: str = "auto",
) -> tuple[float, int]:
    if platform_hint == "mac":
        profile_scale, profile_dpi = 2.0, 300
    elif platform_hint == "ipad":
        profile_scale, profile_dpi = 1.0, 150
    else:
        profile_scale, profile_dpi = _default_export_profile()

    if render_scale is None:
        render_scale = profile_scale
    if dpi is None:
        dpi = profile_dpi

    env_scale = os.environ.get("JAPSUM_EXPORT_SCALE")
    if env_scale:
        try:
            render_scale = float(env_scale)
        except Exception:
            pass

    env_dpi = os.environ.get("JAPSUM_EXPORT_DPI")
    if env_dpi:
        try:
            dpi = int(env_dpi)
        except Exception:
            pass

    render_scale = max(0.5, float(render_scale))
    dpi = max(72, int(dpi))
    return render_scale, dpi


def _ensure_pillow_available(platform_hint: str = "auto") -> bool:
    if _try_import_pillow():
        return True

    print("Pillow (PIL) wurde in diesem Python-Interpreter nicht gefunden.")
    print(f"Aktueller Interpreter: {sys.executable}")

    is_pythonista = "pythonista" in sys.executable.lower() or bool(os.environ.get("PYTHONISTA_HOME"))
    is_mac_desktop = platform_hint == "mac" or (platform_hint == "auto" and sys.platform == "darwin" and not is_pythonista)

    if is_mac_desktop:
        install_now = input("Pillow jetzt fuer diesen Interpreter installieren? (j/n): ").strip().lower().startswith("j")
        if install_now:
            try:
                import subprocess

                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "Pillow"]
                print("Installiere:", " ".join(cmd))
                result = subprocess.run(cmd, check=False)
                if result.returncode == 0 and _try_import_pillow():
                    print("Pillow erfolgreich installiert.")
                    return True
                print("Installation fehlgeschlagen oder Pillow weiterhin nicht verfuegbar.")
            except Exception as exc:
                print(f"Automatische Installation fehlgeschlagen: {exc}")

    print("Export uebersprungen. Manuelle Installation:")
    print(f"{sys.executable} -m pip install Pillow")
    return False


def _contains_question_tokens(row_clues: List[LineClues], col_clues: List[LineClues]) -> bool:
    for clues in row_clues + col_clues:
        if not clues:
            continue
        for val in clues:
            if val in {"?", "??"}:
                return True
    return False


def _contains_hidden_lines(row_clues: List[LineClues], col_clues: List[LineClues]) -> bool:
    return any(clues is None for clues in (row_clues + col_clues))


def _format_clue_list(clues: LineClues) -> str:
    if clues is None:
        return "(ausgeblendet)"
    return "[" + ", ".join(str(v) for v in clues) + "]"


def render_image(
    rows: int,
    cols: int,
    row_clues: List[LineClues],
    col_clues: List[LineClues],
    solution: List[List[CellValue]] | None,
    title: str,
    scale: float = 1.0,
    include_rules: bool = False,
    digit_max: Optional[int] = None,
) -> Image.Image:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow ist erforderlich, um Bilder zu speichern.")

    s = max(0.5, scale)

    cell = _scale_px(56, s)
    padding = _scale_px(110, s)
    header_font = _load_font(_scale_px(36, s))
    clue_font = _load_font(_scale_px(32, s))
    cell_font = _load_font(_scale_px(32, s))
    clue_gap = max(_scale_px(10, s), _font_size(clue_font) // 2 + _scale_px(2, s))
    rules_title_font = _load_font(_scale_px(24, s))
    rules_font = _load_font(_scale_px(20, s))

    # Use a tiny scratch canvas to measure text before final canvas sizing.
    probe_img = Image.new("RGB", (16, 16), "white")
    probe_draw = ImageDraw.Draw(probe_img)

    row_widths = []
    for clues in row_clues:
        clues_vals = clues or []
        widths = [_text_bbox(probe_draw, str(v), clue_font)[2] for v in clues_vals]
        total_w = sum(widths) + clue_gap * (len(widths) - 1 if widths else 0)
        row_widths.append(total_w)
    max_row_width = max(row_widths, default=0)

    # Ensure enough vertical space for stacked column clues
    clue_step = _font_size(clue_font) + _scale_px(8, s)
    max_col_height = max((len(clues) if clues else 0 for clues in col_clues), default=0)
    top_clue_space = max(_font_size(header_font) + _scale_px(40, s), max_col_height * clue_step + _scale_px(40, s))

    # Dynamic horizontal layout so row clues never run outside the image.
    left_edge = _scale_px(20, s)
    row_to_grid_gap = _scale_px(28, s)
    grid_origin_x = left_edge + max_row_width + row_to_grid_gap
    width = grid_origin_x + cols * cell + padding
    rules_lines: List[str] = []
    rules_height = 0
    if include_rules:
        rules_raw = [
            "Rules (short):",
            "Each clue is the sum of one contiguous block of white cells.",
            "Multiple clues in one row/column describe multiple blocks in that exact order.",
            "Blocks are separated by at least one black cell.",
            "Block lengths are unknown; only sums and order are given.",
        ]
        if digit_max is not None:
            rules_raw.append(f"Allowed digit range for this puzzle: 1-{digit_max}.")
            rules_raw.append(_digit_policy_text())
        if _contains_question_tokens(row_clues, col_clues):
            rules_raw.extend(
                [
                    "? means: unknown single-digit clue value.",
                    "?? means: unknown two-digit clue value.",
                ]
            )
        if _contains_hidden_lines(row_clues, col_clues):
            rules_raw.append("Hidden row/column clue lists are still valid and must be deduced logically.")
        rules_max_width = max(_scale_px(200, s), width - left_edge - padding)
        for idx, line in enumerate(rules_raw):
            if idx == 0:
                rules_lines.append(line)
            else:
                rules_lines.extend(_wrap_text_to_width(probe_draw, line, rules_font, rules_max_width))
        rules_title_h = _font_size(rules_title_font)
        rules_line_h = _font_size(rules_font) + _scale_px(6, s)
        body_lines = max(0, len(rules_lines) - 1)
        rules_height = _scale_px(30, s) + rules_title_h + body_lines * rules_line_h + _scale_px(26, s)

    height = padding + rows * cell + padding + top_clue_space + rules_height
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    safe_title = _latin1_safe(title)
    _draw_centered(draw, safe_title, (width // 2, _scale_px(24, s)), header_font)

    # Column clues
    start_x = grid_origin_x
    for idx, clues in enumerate(col_clues):
        if clues is None:
            continue
        cx = start_x + idx * cell + cell // 2
        cy = padding
        for clue in clues:
            _draw_centered(draw, str(clue), (cx, cy), clue_font)
            cy += clue_step

    # Row clues
    start_y = padding + top_clue_space
    left_clue_start = grid_origin_x - max_row_width - row_to_grid_gap

    for idx, clues in enumerate(row_clues):
        if clues is None:
            continue
        cy = start_y + idx * cell + cell // 2
        x = left_clue_start
        for clue in clues:
            bbox = _text_bbox(draw, str(clue), clue_font)
            w = bbox[2] - bbox[0]
            _draw_centered(draw, str(clue), (x + w // 2, cy), clue_font)
            x += w + clue_gap

    grid_origin_y = padding + top_clue_space

    # Grid lines
    major_w = _scale_px(3, s)
    minor_w = _scale_px(2, s)
    for i in range(rows + 1):
        y = grid_origin_y + i * cell
        draw.line([(grid_origin_x, y), (grid_origin_x + cols * cell, y)], fill="black", width=major_w if i % 3 == 0 else minor_w)
    for j in range(cols + 1):
        x = grid_origin_x + j * cell
        draw.line([(x, grid_origin_y + rows * cell), (x, grid_origin_y)], fill="black", width=major_w if j % 3 == 0 else minor_w)

    # Cells content (solution if provided)
    if solution:
        for r in range(rows):
            for c in range(cols):
                x0 = grid_origin_x + c * cell
                y0 = grid_origin_y + r * cell
                x1 = x0 + cell
                y1 = y0 + cell
                val = solution[r][c]
                if val == 0:
                    draw.rectangle([(x0 + 1, y0 + 1), (x1 - 1, y1 - 1)], fill="#111111")
                else:
                    _draw_centered(draw, str(val), ((x0 + x1) // 2, (y0 + y1) // 2), cell_font)

    if include_rules and rules_lines:
        rules_x = left_edge
        rules_y = grid_origin_y + rows * cell + _scale_px(32, s)
        draw.text((rules_x, rules_y), _latin1_safe(rules_lines[0]), font=rules_title_font, fill="black")
        rules_y += _font_size(rules_title_font) + _scale_px(8, s)
        for line in rules_lines[1:]:
            draw.text((rules_x, rules_y), _latin1_safe(f"- {line}"), font=rules_font, fill="black")
            rules_y += _font_size(rules_font) + _scale_px(6, s)

    return img


# ------------------------------ CLI workflow -------------------------------

def prompt_save(base_default: str = "japsum") -> tuple[bool, str, str]:
    choice = input("Speichern? (n=nein, i=Bild, p=PDF, b=beides): ").strip().lower()
    if choice not in {"i", "p", "b"}:
        return False, "", ""
    base = input(f"Dateiname ohne Endung (Standard {base_default}): ").strip() or base_default
    puzzle_name = base + "_puzzle"
    solution_name = base + "_solution"
    return True, puzzle_name, solution_name


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "j/n, Standard j" if default else "j/n, Standard n"
    raw = input(f"{prompt} ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw.startswith(("j", "y"))


def _mzn_line_clues(clues: LineClues) -> str:
    if clues is None:
        return "hidden"
    return " ".join(str(v) for v in clues)


def _mzn_flat(values: Iterable[int], width: int = 20) -> str:
    vals = [str(v) for v in values]
    lines = []
    for i in range(0, len(vals), width):
        lines.append("  " + ", ".join(vals[i:i + width]))
    return ",\n".join(lines)


def write_minizinc_model(
    rows: int,
    cols: int,
    row_clues: List[LineClues],
    col_clues: List[LineClues],
    solution: List[List[CellValue]] | None,
    filename: str,
    digit_max: Optional[int] = None,
) -> str:
    if digit_max is None:
        digit_max = _default_max_digit_for_longest(max(rows, cols))

    row_patterns = [build_line_patterns(cols, clues, digit_max) for clues in row_clues]
    col_patterns = [build_line_patterns(rows, clues, digit_max) for clues in col_clues]
    if any(not patterns for patterns in row_patterns) or any(not patterns for patterns in col_patterns):
        raise RuntimeError("MiniZinc-Modell konnte nicht erstellt werden: leere Zeilen-/Spaltenmuster.")

    row_constraints = []
    for r, patterns in enumerate(row_patterns, 1):
        flat = [v for pat in patterns for v in pat]
        row_constraints.append(
            "constraint table([cell[{r}, c] | c in COLS], array2d(1..{n}, COLS, [\n{vals}\n]));".format(
                r=r,
                n=len(patterns),
                vals=_mzn_flat(flat),
            )
        )

    col_constraints = []
    for c, patterns in enumerate(col_patterns, 1):
        flat = [v for pat in patterns for v in pat]
        col_constraints.append(
            "constraint table([cell[r, {c}] | r in ROWS], array2d(1..{n}, ROWS, [\n{vals}\n]));".format(
                c=c,
                n=len(patterns),
                vals=_mzn_flat(flat),
            )
        )

    row_notes = "\n".join(f"%   R{idx}: {_mzn_line_clues(clues)}" for idx, clues in enumerate(row_clues, 1))
    col_notes = "\n".join(f"%   C{idx}: {_mzn_line_clues(clues)}" for idx, clues in enumerate(col_clues, 1))

    content = f"""% Self-contained MiniZinc all-solutions checker for Japanese Sums.
% Run:
%   minizinc --all-solutions {os.path.basename(filename)}
%
% The puzzle is unique iff MiniZinc prints exactly one solution.
% Values: 0 = black cell, 1..{digit_max} = digit.
% Row clues, left to right:
{row_notes}
% Column clues, top to bottom:
{col_notes}

int: R = {rows};
int: C = {cols};
int: MAX_DIGIT = {digit_max};
include "globals.mzn";
set of int: ROWS = 1..R;
set of int: COLS = 1..C;

array[ROWS, COLS] of var 0..MAX_DIGIT: cell;

% Allowed row patterns
{chr(10).join(row_constraints)}

% Allowed column patterns
{chr(10).join(col_constraints)}

solve satisfy;

output [
    if c = 1 then "" else " " endif ++ show(cell[r, c]) ++
    if c = C then "\\n" else "" endif
    | r in ROWS, c in COLS
];
"""

    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(content)
    return os.path.abspath(filename)


def save_exports(
    rows: int,
    cols: int,
    row_clues: List[LineClues],
    col_clues: List[LineClues],
    solution: List[List[CellValue]] | None,
    include_puzzle: bool,
    include_solution: bool,
    as_image: bool,
    as_pdf: bool,
    puzzle_name: str,
    solution_name: str,
    render_scale: float | None = None,
    dpi: int | None = None,
    platform_hint: str = "auto",
    digit_max: Optional[int] = None,
    write_mzn: bool = False,
    mzn_name: Optional[str] = None,
) -> None:
    if write_mzn:
        target = mzn_name or f"{puzzle_name}_uniqueness_check.mzn"
        try:
            mzn_path = write_minizinc_model(rows, cols, row_clues, col_clues, solution, target, digit_max=digit_max)
            print(f"MiniZinc-Datei gespeichert: {mzn_path}")
        except Exception as exc:
            print(f"MiniZinc-Export uebersprungen: {exc}")

    if not as_image and not as_pdf:
        return
    if not _ensure_pillow_available(platform_hint=platform_hint):
        return

    render_scale, dpi = _resolve_export_settings(render_scale, dpi, platform_hint=platform_hint)

    try:
        puzzle_img = (
            render_image(
                rows,
                cols,
                row_clues,
                col_clues,
                None,
                f"Japanese Sums {rows}x{cols} (Puzzle)",
                scale=render_scale,
                include_rules=True,
                digit_max=digit_max,
            )
            if include_puzzle
            else None
        )
        sol_img = (
            render_image(
                rows,
                cols,
                row_clues,
                col_clues,
                solution,
                f"Japanese Sums {rows}x{cols} (Solution)",
                scale=render_scale,
                include_rules=False,
                digit_max=digit_max,
            )
            if include_solution and solution
            else None
        )
    except Exception as exc:
        print(f"Konnte Bilder nicht erstellen: {exc}")
        return

    print(f"Export-Einstellungen: scale={render_scale:.2f}x, dpi={dpi}")

    if as_image:
        if puzzle_img:
            puzzle_path = f"{puzzle_name}.png"
            puzzle_img.save(puzzle_path, dpi=(dpi, dpi), optimize=True)
            print(f"Raetsel als PNG gespeichert: {os.path.abspath(puzzle_path)}")
        if sol_img:
            sol_path = f"{solution_name}.png"
            sol_img.save(sol_path, dpi=(dpi, dpi), optimize=True)
            print(f"Loesung als PNG gespeichert: {os.path.abspath(sol_path)}")

    if as_pdf:
        if puzzle_img:
            puzzle_pdf = f"{puzzle_name}.pdf"
            puzzle_img.convert("RGB").save(puzzle_pdf, "PDF", resolution=float(dpi))
            print(f"Raetsel als PDF gespeichert: {os.path.abspath(puzzle_pdf)}")
        if sol_img:
            sol_pdf = f"{solution_name}.pdf"
            sol_img.convert("RGB").save(sol_pdf, "PDF", resolution=float(dpi))
            print(f"Loesung als PDF gespeichert: {os.path.abspath(sol_pdf)}")


def print_puzzle(row_clues: List[LineClues], col_clues: List[LineClues]) -> None:
    rows = len(row_clues)
    cols = len(col_clues)
    print("Row clues (left-to-right):")
    for idx, clues in enumerate(row_clues, 1):
        print(f"  R{idx}: {_format_clue_list(clues)}")
    print("\nColumn clues (top-to-bottom):")
    for idx, clues in enumerate(col_clues, 1):
        print(f"  C{idx}: {_format_clue_list(clues)}")
    print("\nGitter-Skizze (leere Zellen, schwarze Felder unbekannt):")
    print("   " + " ".join(f"C{c+1}".ljust(3) for c in range(cols)))
    for r in range(rows):
        print(f"R{r+1} " + " . " * cols)


def print_solution(grid: List[List[CellValue]]) -> None:
    print("Solution (0 = black cell):")
    for row in grid:
        print(" ".join(str(cell) if cell != 0 else "#" for cell in row))


def main() -> None:
    print("Japanese Sums Generator (eindeutige Loesungen, Groessen 3-20, auch Rechtecke)")
    try:
        size_in = input("Waehle die Groesse (z.B. 3x4 oder 6, Standard 5x5): ").strip().lower()
        if "x" in size_in:
            parts = size_in.replace(" ", "").split("x")
            rows = int(parts[0]) if parts[0] else 5
            cols = int(parts[1]) if len(parts) > 1 and parts[1] else rows
        elif size_in:
            rows = cols = int(size_in)
        else:
            rows = cols = 5
    except Exception:
        rows = cols = 5
    valid_range = range(3, 21)
    if rows not in valid_range or cols not in valid_range:
        print("Ungueltige Groesse, verwende 5x5.")
        rows = cols = 5

    level_in = input("Level waehlen: easy, medium, hard, veryhard, inhuman (Standard medium): ").strip().lower()
    difficulty = _normalize_difficulty(level_in or "medium")

    variant_choice = input("Variante: klassisch (k), fies-sparse (f), fies mit ?/?? (q): ").strip().lower()
    if variant_choice == "f":
        variant_mode = "sparse"
    elif variant_choice == "q":
        variant_mode = "question"
    else:
        variant_mode = "classic"

    robust_choice = input("Doppelpruefung der Eindeutigkeit aktivieren? (j/n, Standard j): ").strip().lower()
    robust_unique_check = robust_choice != "n"

    while True:
        try:
            longest = max(rows, cols)
            digits = _default_max_digit_for_longest(longest)
            attempts = _default_attempts_for_longest(longest)
            attempts = int(attempts * _difficulty_attempt_factor(difficulty))
            print(_digit_policy_text())
            print(f"Current puzzle digit range: 1-{digits}")
            if variant_mode in {"sparse", "question"} and longest > 8:
                print("Hinweis: 'fies-sparse' ohne komplette Zeilen/Spalten-Clues ist aktuell bis 8x8 stabil.")
                print("Es wird automatisch die klassische Variante verwendet.")
                active_variant = "classic"
            else:
                active_variant = variant_mode
            row_clues, col_clues, solution = generate_unique_puzzle(
                rows,
                cols,
                max_attempts=attempts,
                max_digit=digits,
                variant=active_variant,
                robust_unique_check=robust_unique_check,
                difficulty=difficulty,
            )
        except RuntimeError as exc:
            print(f"Konnte kein eindeutiges Raetsel erzeugen: {exc}")
            return

        print_puzzle(row_clues, col_clues)
        show_solution = input("Loesung anzeigen? (j/n): ").strip().lower().startswith("j")
        if show_solution and solution:
            print_solution(solution)

        save_choice = input("Nur Raetsel speichern (r), nur Loesung (l), beides (b), nichts (n)? ").strip().lower()
        if save_choice in {"r", "l", "b"}:
            do_save, puzzle_name, solution_name = prompt_save()
            if do_save:
                platform_choice = input("Export-Plattform: automatisch (a), Mac/PyCharm (m), iPad/Pythonista (i): ").strip().lower()
                if platform_choice == "m":
                    platform_hint = "mac"
                elif platform_choice == "i":
                    platform_hint = "ipad"
                else:
                    platform_hint = "auto"

                as_image = False
                as_pdf = False
                export_mode = input("Als Bild (i), als PDF (p) oder beides (b)? ").strip().lower()
                if export_mode == "i":
                    as_image = True
                elif export_mode == "p":
                    as_pdf = True
                elif export_mode == "b":
                    as_image = True
                    as_pdf = True
                include_puzzle = save_choice in {"r", "b"}
                include_solution = save_choice in {"l", "b"}
                write_mzn = _ask_yes_no("MiniZinc-Datei zur Eindeutigkeitspruefung miterstellen?", default=False)
                save_exports(
                    rows,
                    cols,
                    row_clues,
                    col_clues,
                    solution,
                    include_puzzle,
                    include_solution,
                    as_image,
                    as_pdf,
                    puzzle_name,
                    solution_name,
                    platform_hint=platform_hint,
                    digit_max=digits,
                    write_mzn=write_mzn,
                )

        again = input("Noch ein Raetsel erzeugen? (j/n): ").strip().lower()
        if again == "j":
            size_in = input("Neue Groesse (leer = gleich lassen, z.B. 5x7): ").strip().lower()
            if size_in:
                prev_rows, prev_cols = rows, cols
                try:
                    if "x" in size_in:
                        parts = size_in.replace(" ", "").split("x")
                        rows = int(parts[0]) if parts[0] else rows
                        cols = int(parts[1]) if len(parts) > 1 and parts[1] else rows
                    else:
                        rows = cols = int(size_in)
                    if rows not in valid_range or cols not in valid_range:
                        print("Ungueltige Groesse, behalte vorherige bei.")
                        rows, cols = prev_rows, prev_cols
                except Exception:
                    print("Konnte Eingabe nicht lesen, behalte vorherige Groesse.")
                    rows, cols = prev_rows, prev_cols
            level_in = input("Level beibehalten oder wechseln? easy, medium, hard, veryhard, inhuman (leer=beibehalten): ").strip().lower()
            if level_in:
                difficulty = _normalize_difficulty(level_in)

            variant_choice = input("Variante beibehalten oder wechseln? klassisch (k), fies-sparse (f), fies mit ?/?? (q), leer=beibehalten: ").strip().lower()
            if variant_choice == "k":
                variant_mode = "classic"
            elif variant_choice == "f":
                variant_mode = "sparse"
            elif variant_choice == "q":
                variant_mode = "question"
            robust_choice = input("Doppelpruefung beibehalten? (j=an, n=aus, leer=beibehalten): ").strip().lower()
            if robust_choice == "j":
                robust_unique_check = True
            elif robust_choice == "n":
                robust_unique_check = False
            continue
        break


if __name__ == "__main__":
    random.seed()
    main()
