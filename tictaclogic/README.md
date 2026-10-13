# TicTacLogic

Logikrätsel nach den Regeln von Conceptis „Tic-Tac-Logic“ (auch Takuzu/Binairo):

1. Nie mehr als zwei gleiche Zeichen direkt neben- oder untereinander.
2. Jede Zeile und jede Spalte enthält gleich viele X wie O.
3. Keine zwei Zeilen und keine zwei Spalten sind gleich.

## Dateien

- `index.html` – spielbare Web-Version (ohne Build, einfach im Browser öffnen): Größen 6×6 bis 14×14 und rechteckig,
  vier Stufen, Tipps mit Begründung, Prüfen, Rückgängig, Rätsel-Code zum Teilen (`index.html#8x8-2-271828`).
- `tictaclogic.py` – Generator für Druckkarten (PNG, Deutsch und Englisch, Rätsel + Lösung). Benötigt Pillow, läuft auch in Pythonista.

```
python3 tictaclogic.py --size 10 --level 3 --count 6 --out karten
```

## So entsteht ein Rätsel

1. Zufällige vollständige Lösung: Felder zufällig setzen und nach jedem Zug alle Folgerungen ziehen.
2. Vorgaben entfernen: in zufälliger Reihenfolge jedes Feld probeweise leeren und nur dann leer lassen,
   wenn das Rätsel mit der Logik der gewählten Stufe noch vollständig lösbar ist.
3. Da jede Folgerung zwingend ist, hat das Rätsel damit genau eine Lösung. Zur Kontrolle zählt eine
   separate Suche die Lösungen nach.

| Stufe | benötigte Logik |
|---|---|
| Leicht | Paare (XX → O), Lücken (X_X → O), Abzählen |
| Mittel | zusätzlich alle Verteilungen einer Zeile/Spalte durchprobieren |
| Schwer | zusätzlich „keine zwei Linien gleich“ |
| Experte | zusätzlich Widerspruchsbeweis an einem Feld |

Jedes Rätsel trifft die Stufe genau: Es ist mit der Logik der eigenen Stufe lösbar, mit der darunter nicht.
