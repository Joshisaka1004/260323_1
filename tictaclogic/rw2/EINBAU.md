# Auftrag: TicTacLogic in die Rätselwerkstatt 2 einbauen

Baue **TicTacLogic** als neue Rätselart (Plugin) in die **Rätselwerkstatt 2** ein. Arbeite im Projektordner der Werkstatt
(iCloud Drive → `Claude_Opus_55/Raetselwerkstatt2`). Lies zuerst `README.md` (Abschnitt „Eine neue Rätselart
hinzufügen“) und `ENTSTEHUNG.md` (Leitprinzipien, Human Logic, Werkstatt-Regel, Punkte, Ausgabe). Lies außerdem
`raetselwerk/core/plugin.py`, `options.py`, `scene.py`, `grids.py` und `score.py`. Als Vorlage dient ein bestehendes Plugin mit eigener Engine
(z. B. `plugins/zahlenpyramide/`), dazu `plugins/battle/` für Leiter und CP-SAT.

## Die Engine liegt fertig und getestet auf GitHub

```bash
git clone --depth 1 -b claude/tictaclogic https://github.com/Joshisaka1004/260323_1 /tmp/ttl
ls /tmp/ttl/tictaclogic/rw2   # README.md, tictaclogic/{engine.py,pruefer.py,pruefung.py}, tests/test_tictaclogic.py
```

Zuerst `/tmp/ttl/tictaclogic/rw2/README.md` lesen. Kurz:

- `engine.py`: Leiter `TECHNIQUES` T1–T9 in fünf Stufen (easy/medium/hard/veryhard/extreme). Kein Probieren. Extrem
  erlaubt nur Wenn-dann-Schlüsse nach der Werkstatt-Regel (`LIMITS`: höchstens 5 Tests, höchstens 3 Runden). Dazu
  `generate(w, h, level, rnd, deadline, progress)` (Stufe exakt, Vorgaben minimal), `solve_path`, `level_of_path`,
  `points`/`load`/`HALF` (Werkstatt-Formel), `identity` (Drehung/Spiegelung/X↔O), `to_rows`/`from_rows`.
- `pruefer.py`: unabhängiges CP-SAT-Modell nur aus den Regeln, ohne Engine-Code.
- `pruefung.verify(puzzle, solution, meta)`: Regeln, Vorgaben, Logikweg, Stufe, Testgrenzen, Eindeutigkeit; Fehler sind
  `ValueError`.
- Datenformat: `puzzle = {"rows": h, "cols": w, "givens": ["X..O..", …]}`, `solution = {"grid": [...]}`; Zeichen `.`/`X`/`O`.
- Gemessen: 6×6 bis 10×10 in höchstens 3 s, 14×14 Extrem rund 50 s. Alle Rätsel trafen die Stufe exakt und waren per
  CP-SAT eindeutig. Die 6 Tests laufen durch.

## Aufgabe

1. Ordner `raetselwerk/plugins/tictaclogic/` anlegen. Die Engine-Dateien kommen nach `engine/` (oder direkt in den
   Plugin-Ordner; nach Werkstatt-Konvention, relative Importe anpassen). Dazu `__init__.py` mit `PLUGIN`:
   - `key = "tictaclogic"` (nie mehr ändern), `name = "TicTacLogic"`, passendes `glyph`.
   - `levels` = die fünf Stufen der Engine (`engine.LEVELS`).
   - Optionen: Breite und Höhe (gerade, 4–14, Rechtecke erlaubt), Stufe, Suchzeit.
   - `generate(options, ctx)` mit `ctx.rng`, `ctx.progress`, Zeitgrenze. Die Punkte müssen schon in `generate`
     entstehen, weil der Worker frisch erzeugte Rätsel nicht noch einmal prüft (ENTSTEHUNG §10b).
   - `verify` über `pruefung.verify`.
   - `scene`: Gitter mit dunklen Zellkanten wie die anderen Arten; X als zwei Linien, O als Kreis (beides Formen,
     keine Schriftzeichen); Vorgaben dunkel und kräftig, Lösungszeichen in der Lösungsfarbe der Werkstatt.
   - `texts` DE/EN: Titel „TicTacLogic“, Stufe, drei Regeln.
     DE: „Nie mehr als zwei gleiche Zeichen direkt neben- oder untereinander.“ / „Jede Zeile und jede Spalte enthält
     gleich viele X wie O.“ / „Keine zwei Zeilen und keine zwei Spalten sind gleich.“
     EN: „Never more than two equal symbols side by side or one above the other.“ / „Every row and every column has
     as many X as O.“ / „No two rows and no two columns are identical.“ Nur WinAnsi-Zeichen.
   - `identity` über `engine.identity`, `score` über `core/score.py` mit eigenem `wertung.py` (Halbwerte aus
     `engine.HALF`).
   - Optional `import_data` für eigene Dateien.
2. Tests nach `tests/test_tictaclogic.py` übernehmen und an die Werkstatt anpassen. Dazu Plugin-Tests wie bei den
   anderen Arten: erzeugen und prüfen je Stufe, Manipulation erkannt, Rundreise, Identität, Zeichnung, Punkte im Band
   der Stufe. Danach die **ganze** Testsuite laufen lassen (`.venv/bin/python -m unittest discover -s tests -t .`);
   alle Tests müssen durchlaufen.
3. Je ein Rätsel pro Stufe (8 × 8) erzeugen und als Karte DE und EN exportieren (PNG 750 px, mit Lösung). Jede Karte in
   voller Größe ansehen und mit der Skill `raetselgrafik-pruefung` prüfen, bevor du sie zeigst.
4. Doku: In `README.md` TicTacLogic in die Liste der Arten aufnehmen (dann zwölf) und einen Abschnitt mit Regeln und
   Leiter-Tabelle anlegen. In `ENTSTEHUNG.md` einen Abschnitt „TicTacLogic“ plus einen Eintrag in der Chronik. Messwerte
   nur aus eigenen Läufen.

## Wichtig

- Die **Einordnung der Techniken in die Stufen ist ein Vorschlag von Claude**, noch nicht von Jochen bestätigt. So im
  README vermerken, wie bei den Käfigtechniken.
- Andere Plugins, den Kern und das alte Projekt „Rätselwerkstatt Komfort“ nicht verändern. Falls am Kern etwas nötig
  scheint, erst fragen.
- `ortools` steht schon in `requirements.txt`.
- Am Ende kurz berichten: was eingebaut ist, Testergebnis, Messzeiten, offene Punkte.
