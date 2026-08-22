# Mastermind-Kette — Rätselgenerator

Generator für verkettete Mastermind-Rätsel ("Superhirn"): Der Lösungscode von
Teil k wird als verdeckte **Kettenzeile** in Teil k+1 übernommen, deren
Schwarz/Weiß-Wertung bereits angegeben ist. Ohne die Lösung des Vorgängers ist
der Folgeteil **beweisbar mehrdeutig** — die Kette ist also zwingend.

Skript: [`scripts/mastermind_kette.py`](../scripts/mastermind_kette.py)
(reines Python 3, keine Abhängigkeiten).

## Schnellstart

```bash
python3 scripts/mastermind_kette.py            # interaktive Abfrage
python3 scripts/mastermind_kette.py --auto     # Standardwerte ohne Rückfragen
python3 scripts/mastermind_kette.py --auto --teile 2 --luegner --seed 42
```

Die interaktive Abfrage fragt alles Wesentliche ab (Enter übernimmt den
Vorschlag): Anzahl Teile (1–8), Codelänge, Farbenzahl, Wiederholung ja/nein,
Zeilen pro Teil, Treffer-Obergrenzen, Wertungsmodus, Kettenrichtung,
Lügner-Variante, Seed und Signatur.

## Garantien — geprüft, nicht geraten

Nach der Generierung läuft eine unabhängige Endprüfung per **vollständiger
Enumeration** aller möglichen Codes (bis 2 Mio. Codes, d. h. z. B. 8 Farben ×
7 Stellen). Bestätigt werden:

1. **Eindeutigkeit** — jeder Teil hat genau eine Lösung.
2. **Minimalität** — jede normale Hinweiszeile ist nötig; lässt man irgendeine
   weg, wird der Teil mehrdeutig.
3. **Kettenzwang** — jeder Folgeteil ist ohne die Kettenzeile mehrdeutig,
   Teil 2 ist also ohne die Lösung von Teil 1 nachweislich nicht knackbar.
4. **Schwache Hinweise** — pro Zeile höchstens `--max-schwarz` schwarze Stifte
   (Standard 1) und `--max-treffer` Stifte gesamt (Standard 2). Es gibt also
   nie eine Zeile mit 3 oder 4 Schwarzen, die das Rätsel fast verraten würde.

Reicht die gewünschte Zeilenzahl für Eindeutigkeit nicht aus (z. B. im
Nur-Schwarz-Modus), erhöht der Generator sie selbstständig und meldet das.

## Eingebaute Varianten

| Variante | Schalter | Wirkung |
| --- | --- | --- |
| Schlampige Wertung | `--modus schlampig` | Bei rund einem Drittel der Zeilen ist nur die **Gesamtzahl** der Treffer bekannt (Feld „n Treffer“), nicht die Aufteilung schwarz/weiß. |
| Nur Schwarz | `--modus schwarz` | Es werden nur schwarze Stifte gewertet; braucht deutlich mehr Zeilen (der Generator stockt automatisch auf). |
| Rückwärts-Kette | `--kette rueckwaerts` | Der Lösungscode wird rückwärts in den nächsten Teil übertragen. |
| Lügner | `--luegner` | Genau eine Hinweiszeile pro Teil lügt; die Kettenzeile sagt immer die Wahrheit. Der Löser muss die Lügenzeile selbst entlarven. Achtung: Generierung dauert hier spürbar länger (Größenordnung 30 s pro Teil). |
| Ohne Wiederholung | `--ohne-wiederholung` | Jede Farbe kommt im Code höchstens einmal vor. |

Warum es keinen „alles nur Summe“-Modus gibt: Die Treffersumme ist
positionsblind — Umstellungen desselben Farb-Multisets sind für sie
ununterscheidbar, ein eindeutiges Rätsel ist damit prinzipiell unmöglich.
Deshalb mischt der schlampig-Modus Summen-Zeilen mit normalen Zeilen.

## Ausgaben

* **Konsole** — Rätsel, Regeln und (mit Abstand) die Lösungen.
* **HTML** (`--html datei.html`, Standard `mastermind_kette.html`) —
  druckfertige Seite in der Buch-Optik (farbige Kreise, Schwarz/Weiß-Punkte,
  gestrichelte Kettenzeile); Lösungen eingeklappt und vom Druck ausgenommen.
* **JSON** (`--json datei.json`) — maschinenlesbar für Weiterverarbeitung.

Mit `--seed` ist jedes Rätsel exakt reproduzierbar; der verwendete Seed steht
in jeder Ausgabe.

## Ideen für weitere Varianten

Noch nicht eingebaut, aber mit derselben Engine gut machbar:

* **Gabel-Kette** — Teil 3 braucht die Lösungen von Teil 1 *und* Teil 2
  (zwei Kettenzeilen); aus der Kette wird ein Baum.
* **Geheime Transformation** — die Kettenzeile ist der Vorgängercode nach
  einer Regel, die der Löser erst aus den Wertungen erschließen muss
  (z. B. „jede Farbe eine Stufe weitergedreht“ oder zyklisch verschoben).
* **Meta-Finale** — die N Teillösungen ergeben spaltenweise gelesen einen
  Meta-Code, der ein letztes Mini-Mastermind löst (Buch-Endgegner).
* **Fehlende Wertung** — bei einer Zeile fehlt die Wertung komplett; gefragt
  ist zusätzlich, wie sie gelautet haben muss.
* **Duell-Modus** — zwei Löser bekommen dieselben Zeilen, aber
  komplementäre Wertungshälften (einer nur schwarz, einer nur weiß) und
  müssen kooperieren.
* **Zahlen-Ausgabe** — Ziffern statt Farben (nur Anzeigeschicht tauschen),
  dann eignet sich die Lösung z. B. als Zahlenschloss-Code einer Schnitzeljagd.
