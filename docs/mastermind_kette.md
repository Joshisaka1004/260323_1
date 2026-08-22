# Mastermind-Kette — Rätselgenerator

Generator für verkettete Mastermind-Rätsel ("Superhirn"): Der Lösungscode von
Teil k wird als verdeckte **Kettenzeile** in Teil k+1 übernommen, deren
Schwarz/Weiß-Wertung bereits angegeben ist. Ohne die Lösung des Vorgängers ist
der Folgeteil **beweisbar mehrdeutig** — die Kette ist also zwingend.

Skript: [`scripts/mastermind_kette.py`](../scripts/mastermind_kette.py) —
reines Python 3 (ab 3.8). Konsole, HTML, PDF und JSON laufen ohne jede
Zusatzbibliothek; nur der PNG-Export nutzt Pillow, wenn es vorhanden ist.

## Schnellstart

```bash
python3 scripts/mastermind_kette.py            # interaktive Abfrage
python3 scripts/mastermind_kette.py --auto     # Standardwerte ohne Rückfragen
python3 scripts/mastermind_kette.py --auto --teile 2 --luegner --seed 42

# 4 Teile als PDF und PNG, Aufgabe und Lösung jeweils getrennt
python3 scripts/mastermind_kette.py --auto --formate pdf,png --basis buch_seite_12

# Gabel-Kette: zwei Stränge, Teil 5 braucht die Lösungen beider
python3 scripts/mastermind_kette.py --auto --teile 5 --gabel

# Wort-Mastermind: alle Zeilen und die Lösung sind echte deutsche Wörter
python3 scripts/mastermind_kette.py --auto --zeichen wort-de --teile 3
```

Die interaktive Abfrage fragt alles Wesentliche ab (Enter übernimmt den
Vorschlag): Anzahl Teile (1–8), Zeichensatz (farbige Kugeln, Ziffern,
deutsche oder englische Wörter), Codelänge bzw. Wortlänge, Symbolzahl,
Wiederholung ja/nein, Zeilen pro Teil, Treffer-Obergrenzen, Wertungsmodus,
Kettenrichtung, Gabel- und Lügner-Variante, Seed, Signatur und zum Schluss
die Ausgabeformate.

## Garantien — geprüft, nicht geraten

Nach der Generierung läuft eine unabhängige Endprüfung per **vollständiger
Enumeration** aller möglichen Codes (bis 2 Mio. Codes, d. h. z. B. 8 Farben ×
7 Stellen). Bestätigt werden:

1. **Eindeutigkeit** — jeder Teil hat genau eine Lösung.
2. **Minimalität** — jede normale Hinweiszeile ist nötig; lässt man irgendeine
   weg, wird der Teil mehrdeutig.
3. **Kettenzwang** — jeder Folgeteil ist ohne jede einzelne seiner
   Kettenzeilen mehrdeutig; Teil 2 ist also ohne die Lösung von Teil 1
   nachweislich nicht knackbar, und ein Gabelpunkt nicht ohne beide Stränge.
4. **Schwache Hinweise** — pro Zeile höchstens `--max-schwarz` schwarze Stifte
   (Standard 1) und `--max-treffer` Stifte gesamt (Standard 2). Es gibt also
   nie eine Zeile mit 3 oder 4 Schwarzen, die das Rätsel fast verraten würde.

Reicht die gewünschte Zeilenzahl für Eindeutigkeit nicht aus (z. B. im
Nur-Schwarz-Modus), erhöht der Generator sie selbstständig und meldet das.

## Zeichensätze

Der Code kann aus vier Zeichensätzen bestehen (`--zeichen`, interaktiv als
erste Frage nach der Teilezahl):

| Zeichensatz | Schalter | Beschreibung |
| --- | --- | --- |
| Farbige Kugeln | `--zeichen farben` | Klassisch: 3–10 Farben mit Buchstabenkürzel (Standard 7). |
| Ziffern | `--zeichen ziffern` | Codes aus Ziffern 0–9 (Standard: 10 Ziffern), farbig dargestellt. Die Lösung eignet sich z. B. als Zahlenschloss-Code. |
| Deutsche Wörter | `--zeichen wort-de` | Lösungscode und **alle Tipp-Zeilen sind echte deutsche Wörter** (Wort-Mastermind wie bei Rätselmeisterschaften). Eingebauter Wortschatz: über 1160 gebräuchliche Wörter (4/5/6 Buchstaben, ohne Umlaute und Eigennamen). |
| Englische Wörter | `--zeichen wort-en` | Wie oben mit fast 1700 englischen Wörtern. |

Im Wort-Modus ist der Kandidatenraum die Wortliste — Eindeutigkeit,
Minimalität und Kettenzwang werden über den gesamten Wortschatz bewiesen.
Weil Wörter viel Struktur tragen, kommen die Teile oft mit 3–4 Hinweiszeilen
aus (der Generator meldet das). Die Rückwärts-Kette ist im Wort-Modus
abgeschaltet, weil das gespiegelte Wort kein echtes Wort wäre.

**Wortschatz erweitern:** Die Listen stehen am Ende des Skripts als
Klartext-Blöcke `WOERTER_DE` und `WOERTER_EN` — einfach eigene Wörter
(Großbuchstaben, ohne Umlaute/ß) anhängen; Duplikate und Fremdzeichen werden
beim Laden automatisch aussortiert. Ein ehrlicher Hinweis für den
Buch-Einsatz: Die Eindeutigkeit gilt bezogen auf den eingebauten Wortschatz.
Je größer die Liste, desto sicherer ist ausgeschlossen, dass ein findiger
Löser ein weiteres passendes Wort außerhalb des Vorrats entdeckt — die
strengen Wertungen mehrerer Zeilen machen das aber ohnehin sehr
unwahrscheinlich.

## Eingebaute Varianten

| Variante | Schalter | Wirkung |
| --- | --- | --- |
| Schlampige Wertung | `--modus schlampig` | Bei rund einem Drittel der Zeilen ist nur die **Gesamtzahl** der Treffer bekannt (Feld „n Treffer“), nicht die Aufteilung schwarz/weiß. |
| Nur Schwarz | `--modus schwarz` | Es werden nur schwarze Stifte gewertet; braucht deutlich mehr Zeilen (der Generator stockt automatisch auf). |
| Rückwärts-Kette | `--kette rueckwaerts` | Der Lösungscode wird rückwärts in den nächsten Teil übertragen. |
| Gabel-Kette | `--gabel` | Ab 3 Teilen: zwei unabhängige Stränge (z. B. bei 5 Teilen 1→2 und 3→4), die im letzten Teil münden. Der Gabelpunkt hat **zwei** Kettenzeilen (K1, K2) und ist beweisbar ohne jede einzelne davon mehrdeutig — er braucht also wirklich beide Stranglösungen. Weil zwei Kettenzeilen viel Information tragen, kommt der Gabelpunkt oft mit weniger normalen Zeilen aus (der Generator meldet das). Kombinierbar mit rückwärts und Lügner. |
| Lügner | `--luegner` | Genau eine Hinweiszeile pro Teil lügt; die Kettenzeile sagt immer die Wahrheit. Der Löser muss die Lügenzeile selbst entlarven. Achtung: Generierung dauert hier spürbar länger (Größenordnung 30 s pro Teil). |
| Ohne Wiederholung | `--ohne-wiederholung` | Jede Farbe kommt im Code höchstens einmal vor. |

Warum es keinen „alles nur Summe“-Modus gibt: Die Treffersumme ist
positionsblind — Umstellungen desselben Farb-Multisets sind für sie
ununterscheidbar, ein eindeutiges Rätsel ist damit prinzipiell unmöglich.
Deshalb mischt der schlampig-Modus Summen-Zeilen mit normalen Zeilen.

## Ausgaben

Aufgabe und Lösung werden **immer als getrennte Dateien** geschrieben — die
Aufgabenseiten kommen ins Buch, die Lösungsseiten in den Anhang. Gesteuert
wird das über zwei Schalter:

```bash
--formate html,pdf,png,json     # oder 'alle'
--basis mein_raetsel            # Basisname der Dateien
--ordner ~/Buch/Kapitel3        # Ausgabeordner (wird angelegt)
--dpi 150                       # Auflösung der PNG-Ausgabe
```

Daraus entstehen z. B. `mein_raetsel_aufgabe.pdf` und
`mein_raetsel_loesung.pdf`. Im interaktiven Modus fragt das Skript am Ende
Formate, Basisname und Ordner ab.

**Ausgabeordner:** Voreingestellt ist der Ordner in der Konstanten
`STANDARD_ORDNER` am Anfang des Skripts (derzeit der iCloud-Ordner
`…/Claude_2/Puzzles/Mastermind_1/Current_Puzzles`) — dort einfach anpassen,
wenn die Rätsel woanders hin sollen. Läuft das Skript auf einem anderen
Rechner, auf dem es diesen Benutzerordner nicht gibt, weicht es automatisch
auf den Unterordner `raetsel` **neben der Skriptdatei** aus (also z. B.
`scripts/raetsel/`). Bewusst nicht das aktuelle Arbeitsverzeichnis: In
PyCharm und ähnlichen Umgebungen ist das oft ein anderer Ordner als der, in
dem das Skript liegt, und die Dateien wären schwer wiederzufinden.

Jeder Ordner (auch mehrstufig, `~` erlaubt) wird bei Bedarf automatisch
angelegt; am Ende nennt das Skript den vollen Pfad.

| Format | Inhalt |
| --- | --- |
| `pdf` | Druckfertiges A4-Vektor-PDF. Eigener PDF-Writer im Skript — **keine Zusatzbibliothek nötig**, funktioniert immer. Passt der Inhalt nicht auf die Seite, wird alles gleichmäßig verkleinert. |
| `png` | Bilddatei in A4-Seitenverhältnis, Standard 150 dpi (1240 × 1754 px). Nutzt **Pillow** (`pip install pillow`); fehlt Pillow, wird ersatzweise ein vorhandener Chrome/Edge/Chromium im Hintergrund verwendet. Ist beides nicht da, meldet das Skript das und schreibt die übrigen Formate trotzdem. |
| `html` | Seite für Bildschirm und Browser-Druck. |
| `json` | Maschinenlesbare Rohdaten (eine Datei, Lösungen inbegriffen). |

Die Konsolenausgabe zeigt das Rätsel immer an, mit den Lösungen am Ende.
Mit `--seed` ist jedes Rätsel exakt reproduzierbar; der verwendete Seed steht
in jeder Ausgabe — auch in der Kopfzeile von PDF und PNG, sodass sich
Aufgaben- und Lösungsblatt später eindeutig zuordnen lassen.

## Ideen für weitere Varianten

Noch nicht eingebaut, aber mit derselben Engine gut machbar:

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
