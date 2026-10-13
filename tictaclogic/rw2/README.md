# TicTacLogic für die Rätselwerkstatt 2

Engine ohne Oberfläche, gebaut nach `ENTSTEHUNG.md` §16 („zuerst Engine ohne Oberfläche
schreiben und testen, dann Plugin“). Der Ordner `tictaclogic/` wird später zu
`raetselwerk/plugins/tictaclogic/`; das Plugin-Objekt (`PLUGIN` mit Optionen, `scene`,
`texts`, `identity`, `score`) folgt, sobald der Werkstatt-Kern (`core/plugin.py`,
`scene.py`, `grids.py`, `score.py`) vorliegt.

## Regeln

1. Nie mehr als zwei gleiche Zeichen direkt neben- oder untereinander.
2. Jede Zeile und jede Spalte enthält gleich viele X wie O.
3. Keine zwei Zeilen und keine zwei Spalten sind gleich.

## Leiter (`TECHNIQUES` in `engine.py`, Vorschlag von Claude)

Der Löser nimmt immer die einfachste Technik, die etwas bewirkt, und beginnt danach wieder
bei T1. Die Stufe ist die niedrigste, deren Techniken das Rätsel lösen. **Kein Probieren:**
Annahmen gibt es nur in Extrem, und nur nach der Werkstatt-Regel.

| Taste | Stufe | Technik |
|---|---|---|
| T1 | Leicht | Paar: neben zwei gleichen Zeichen steht das andere |
| T2 | Leicht | Lücke: zwischen zwei gleichen Zeichen steht das andere |
| T3 | Leicht | Abzählen: Linie hat alle X (O) → Rest O (X) |
| T4 | Mittel | Einzelrest: fehlt nur noch ein Zeichen einer Sorte, scheiden die Felder aus, an denen es drei gleiche der anderen erzwingt |
| T5 | Mittel | Zwilling: zwei freie Felder, eine Belegung machte die Linie gleich einer fertigen |
| T6 | Schwer | Linienanalyse: alle Verteilungen einer Linie |
| T7 | Schwer | Linienanalyse mit Einzigartigkeit |
| T8 | Sehr schwer | Linienpaar: zwei parallele Linien (Abstand 1 oder 2) gemeinsam, Dreierregel und Anzahl quer dazu; höchstens 4000 Kandidatenpaare |
| T9 | Extrem | Wenn-dann: Annahme, höchstens 3 Runden Linienlogik (T1–T7) bis zum Widerspruch; höchstens 5 Tests je Rätsel |

Runde 1 = die Linien durch das angenommene Feld, Runde k+1 = die Linien durch die in Runde k
gesetzten Felder (wie bei Japanese Sums). Kurze Ketten werden zuerst gesucht; die Zählung ist
gierig, also nie leichter als nötig eingestuft. Rätsel, die mehr brauchen, entstehen nicht und
werden beim Prüfen abgelehnt.

## Generator

1. Zufällige Lösung: Felder zufällig setzen, nach jedem Zug alle Folgerungen (T1–T7).
2. Minimieren: jede Vorgabe in zufälliger Reihenfolge streichen, wenn das Rätsel ohne sie noch
   auf der Zielstufe lösbar ist (ein Durchgang genügt, die Techniken sind monoton).
3. Nur behalten, wenn die Stufe **exakt** passt (mit der Stufe darunter unlösbar).
4. Eindeutigkeit beweist das unabhängige CP-SAT-Modell `pruefer.py` (kein Engine-Code).

`pruefung.verify(puzzle, solution, meta)` prüft vor Speichern und Export alles neu: Regeln,
Vorgaben, Logikweg zur gespeicherten Lösung, Stufe, Testgrenzen, CP-SAT-Eindeutigkeit.
`identity()` erkennt Doppelte bis auf Drehung, Spiegelung und Tausch von X und O.

## Punkte

Werkstatt-Formel: Punkte = 100 × Stufe + Zuschlag (0–99), Last = Σ Hürden (1 + h) − 1 +
log₂(1 + Kleinarbeit), Zuschlag = 99 × Last / (Last + H). Leicht: Lücke und Abzählen zählen
als Hürden. Halbwerte H (Median, 25 Rätsel 8 × 8 je Stufe, 13.10.2026, vorläufig):
27,5 / 8,6 / 2,5 / 0,9 / 1,75. Hürden je 8 × 8: Mittel 2–12, Schwer 1–2, Sehr schwer 1–4,
Extrem 1–5.

## Messwerte (13.10.2026, je Rätsel, mit CP-SAT-Beweis)

| Größe | Leicht | Mittel | Schwer | Sehr schwer | Extrem |
|---|---|---|---|---|---|
| 6 × 6 | < 0,1 s | < 0,1 s | < 0,1 s | 0,2–0,9 s | 0,2–0,3 s |
| 8 × 8 | < 0,1 s | 0,1 s | 0,1 s | 0,6–0,7 s | 0,6–1,3 s |
| 10 × 10 | – | – | 0,2–0,5 s | 0,8–1,1 s | 2,8–3,2 s |
| 12 × 12 | – | 0,4 s | 1,6 s | 1,2 s | 13 s |
| 14 × 14 | 0,7 s | – | 1,8 s | 2,6 s | 52 s |

Alle Rätsel eindeutig (CP-SAT unter 0,5 s), Stufe exakt, Logikweg = gespeicherte Lösung.

## Tests

```bash
python -m unittest discover -s tests -t .
```

Stufe exakt und jede Vorgabe nötig (alle Stufen), Werkstatt-Regel bei Extrem (≤ 5 Tests à
≤ 3 Runden), keine Technik verliert die Lösung (60 zufällige Teilbelegungen), Manipulationen
erkannt (Lösung, Stufe, fehlende Vorgabe), CP-SAT erkennt Mehrdeutigkeit, Identität. Braucht
`ortools` (steht ohnehin in der `requirements.txt` der Werkstatt).
