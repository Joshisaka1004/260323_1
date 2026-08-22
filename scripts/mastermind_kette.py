#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mastermind-Kette — Generator für verkettete Mastermind-Rätsel ("Superhirn").

Erzeugt 1 bis N verkettete Mastermind-Teile: Der Lösungscode von Teil k wird
als (verdeckte) Kettenzeile in Teil k+1 übernommen, deren Schwarz/Weiß-Wertung
bereits angegeben ist. Ohne die Lösung des Vorgängers ist der Folgeteil
nachweislich mehrdeutig — die Kette ist also zwingend.

Garantien (per vollständiger Enumeration geprüft, nicht nur "wahrscheinlich"):
  * Jeder Teil hat GENAU EINE Lösung.
  * Jede normale Hinweiszeile ist NÖTIG (ohne sie: mehrdeutig).
  * Jeder Folgeteil ist OHNE die Kettenzeile mehrdeutig.
  * Schwache Hinweise: pro Zeile höchstens `max_schwarz` schwarze Stifte und
    höchstens `max_treffer` Stifte insgesamt (Standard: 1 schwarz, 2 gesamt).
    Nie 3 oder 4 Schwarze, die das Rätsel fast verraten würden.

Varianten (wählbar):
  * Modus "standard"   — klassische Schwarz/Weiß-Wertung.
  * Modus "schlampig"  — bei einigen Zeilen war der Wertende schlampig: dort
                         steht nur die GESAMTZAHL der Treffer, nicht die
                         Aufteilung in schwarz/weiß (schwerer).
                         (Hinweis: ALLE Zeilen nur mit Summe zu werten wäre
                         unlösbar — die Summe ist positionsblind und kann
                         Umstellungen desselben Codes nie unterscheiden.)
  * Modus "schwarz"    — es werden NUR schwarze Stifte gewertet; weiße gibt
                         es nicht. Braucht deutlich mehr Zeilen.
  * Kette "rueckwaerts" — der Lösungscode wird RÜCKWÄRTS in den nächsten
                         Teil eingetragen.
  * Gabel-Kette        — zwei unabhängige Stränge; der letzte Teil ist der
                         Gabelpunkt mit ZWEI Kettenzeilen und braucht die
                         Lösungen beider Stränge (ab 3 Teilen).
  * Lügner-Variante    — genau eine Hinweiszeile pro Teil lügt; der Löser
                         muss sie selbst entlarven.
  * Mit/ohne Farbwiederholung im Code.

Reicht die gewünschte Zeilenzahl für Eindeutigkeit nicht aus, erhöht der
Generator sie selbstständig (mit Meldung).

Aufruf:
    python3 mastermind_kette.py            # interaktive Abfrage
    python3 mastermind_kette.py --auto     # ohne Rückfragen, Werte per Flags

Ausgabe: Konsole (Text), druckfertiges HTML (Optik wie die Buchvorlage) und
optional JSON. Lösungen stehen am Ende bzw. im HTML eingeklappt.
"""

from __future__ import annotations

import argparse
import html as html_mod
import itertools
import json
import math
import os
import random
import sys
import zlib
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Symbole und Farben
# ---------------------------------------------------------------------------

SYMBOLE = "RGBYOVTPWN"  # bis zu 10 Farben

FARBEN = {
    "R": ("Rot", "#e05252", "#1d2733"),
    "G": ("Grün", "#5aab4c", "#1d2733"),
    "B": ("Blau", "#4a72ab", "#ffffff"),
    "Y": ("Gelb", "#e8c743", "#1d2733"),
    "O": ("Orange", "#f08c1e", "#1d2733"),
    "V": ("Violett", "#8465ab", "#ffffff"),
    "T": ("Türkis", "#2f9e8f", "#ffffff"),
    "P": ("Pink", "#e06ba8", "#1d2733"),
    "W": ("Weiß", "#e9edf2", "#1d2733"),
    "N": ("Braun", "#9c6b3f", "#ffffff"),
}

MAX_RAUM = 2_000_000   # Obergrenze farben**laenge für die Enumeration
MAX_EXTRA_ZEILEN = 9   # so weit darf der Generator die Zeilenzahl anheben


# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------

@dataclass
class Zeile:
    """Eine Hinweiszeile. `art` bestimmt, WAS der Löser sieht:
    "sw" = (schwarz, weiss), "summe" = nur schwarz+weiss, "schwarz" = nur
    schwarz. `key` ist die ANGEZEIGTE Wertung in dieser Projektion; sie
    weicht nur in der Lügner-Variante von der wahren Wertung ab."""
    tipp: tuple
    wahr_schwarz: int
    wahr_weiss: int
    art: str
    key: object
    luege: bool = False


@dataclass
class Kettenzeile:
    tipp: tuple          # der (transformierte) Lösungscode des Quell-Teils
    schwarz: int
    weiss: int
    quelle: int          # Nummer des Teils, dessen Lösung hier eingetragen wird


@dataclass
class Teil:
    nummer: int
    code: tuple
    zeilen: list
    ketten: list         # 0 (Startteil), 1 (Kette) oder 2 (Gabelpunkt) Einträge
    schwierigkeit: str = "?"


@dataclass
class Konfig:
    teile: int = 4
    laenge: int = 5
    farben: int = 7
    zeilen: int = 5
    max_schwarz: int = 1
    max_treffer: int = 2
    wiederholung: bool = True
    modus: str = "standard"          # standard | schlampig | schwarz
    kette: str = "direkt"            # direkt | rueckwaerts
    gabel: bool = False              # zwei Stränge, die im letzten Teil münden
    luegner: bool = False
    seed: Optional[int] = None
    signatur: str = ""
    # interne Suchparameter
    versuche: int = 90               # Neustarts pro Teil und Zeilenstufe
    stichprobe: int = 140            # getestete Tipps pro Zeilenschritt
    endsuche: int = 6000             # getestete Tipps für die letzte Zeile


# ---------------------------------------------------------------------------
# Kernlogik: Wertung, Projektion, Filterung
# ---------------------------------------------------------------------------

def bewertung(tipp: tuple, code: tuple, farben: int) -> tuple:
    """Klassische Mastermind-Wertung: (schwarz, weiss)."""
    schwarz = 0
    zt = [0] * farben
    zc = [0] * farben
    for a, b in zip(tipp, code):
        if a == b:
            schwarz += 1
        else:
            zt[a] += 1
            zc[b] += 1
    weiss = 0
    for x, y in zip(zt, zc):
        weiss += x if x < y else y
    return schwarz, weiss


def projektion(art: str, s: int, w: int):
    """Was der Löser von der wahren Wertung (s, w) zu sehen bekommt."""
    if art == "sw":
        return (s, w)
    if art == "summe":
        return s + w
    if art == "schwarz":
        return s
    raise ValueError(f"Unbekannte Wertungsart: {art}")


def filtere(kandidaten, tipp, art, key, farben):
    bew = bewertung
    proj = projektion
    return [c for c in kandidaten if proj(art, *bew(tipp, c, farben)) == key]


def loesungsmenge(zeilen, basis, farben):
    cur = basis
    for z in zeilen:
        cur = filtere(cur, z.tipp, z.art, z.key, farben)
        if not cur:
            return cur
    return cur


def schwach(s: int, w: int, cfg: Konfig) -> bool:
    return s <= cfg.max_schwarz and s + w <= cfg.max_treffer


def alle_codes(cfg: Konfig):
    symbole = range(cfg.farben)
    if cfg.wiederholung:
        return list(itertools.product(symbole, repeat=cfg.laenge))
    return list(itertools.permutations(symbole, cfg.laenge))


def kettentipp(code: tuple, cfg: Konfig) -> tuple:
    if cfg.kette == "rueckwaerts":
        return tuple(reversed(code))
    return code


def topologie(cfg: Konfig):
    """Vorgänger-Teile je Teilnummer (1-basiert). Linear: 1 -> 2 -> ... -> N.
    Gabel: zwei unabhängige Stränge, die beide im letzten Teil münden,
    z. B. bei 5 Teilen  1 -> 2  und  3 -> 4,  Teil 5 braucht 2 und 4."""
    n = cfg.teile
    if not cfg.gabel or n < 3:
        return {i: ([i - 1] if i > 1 else []) for i in range(1, n + 1)}
    a = (n - 1 + 1) // 2  # Länge des ersten Strangs: Teile 1..a
    plan = {}
    for i in range(1, a + 1):
        plan[i] = [i - 1] if i > 1 else []
    for i in range(a + 1, n):
        plan[i] = [i - 1] if i > a + 1 else []
    plan[n] = [a, n - 1]
    return plan


def zeilen_arten(anzahl: int, cfg: Konfig, rng: random.Random):
    """Wertungsart je (Bau-)Zeile. Die zuletzt gebaute Zeile bekommt immer
    volle Information, damit die Reduktion auf genau eine Lösung gelingt;
    die Anzeige-Reihenfolge wird später ohnehin gemischt."""
    if cfg.modus == "standard":
        return ["sw"] * anzahl
    if cfg.modus == "schwarz":
        return ["schwarz"] * anzahl
    # schlampig: gut ein Drittel der Zeilen zeigt nur die Summe
    arten = ["sw"] * anzahl
    kandidaten = list(range(anzahl - 1))
    rng.shuffle(kandidaten)
    for i in kandidaten[:max(1, anzahl // 3)]:
        arten[i] = "summe"
    return arten


# ---------------------------------------------------------------------------
# Generierung eines Teils
# ---------------------------------------------------------------------------

def baue_zeilen(code, basis, pool, arten, cfg, rng):
    """Wählt schwache Hinweiszeilen (eine je Eintrag in `arten`), die die
    Kandidatenmenge `basis` schrittweise auf genau {code} reduzieren. Die
    Zielgröße pro Schritt wird so gesteuert, dass die Menge erst mit der
    letzten Zeile kollabiert."""
    f = cfg.farben
    anzahl = len(arten)
    kandidaten = basis
    zeilen = []
    benutzt = set()
    for t in range(anzahl):
        art = arten[t]
        rest = anzahl - t
        if rest == 1:
            # Letzte Zeile: muss auf genau eine Lösung reduzieren.
            for g in rng.sample(pool, min(len(pool), cfg.endsuche)):
                if g in benutzt:
                    continue
                s, w = bewertung(g, code, f)
                key = projektion(art, s, w)
                neu = filtere(kandidaten, g, art, key, f)
                if len(neu) == 1:
                    zeilen.append(Zeile(g, s, w, art, key))
                    return zeilen
            return None
        # Zwischenzeile: gleichmäßig Richtung 1 schrumpfen, aber >= 2 lassen.
        ziel = max(2.0, len(kandidaten) ** ((rest - 1.0) / rest))
        n_probe = max(8, min(cfg.stichprobe, 300_000 // max(1, len(kandidaten))))
        beste = None
        for g in rng.sample(pool, min(len(pool), n_probe)):
            if g in benutzt:
                continue
            s, w = bewertung(g, code, f)
            key = projektion(art, s, w)
            neu = filtere(kandidaten, g, art, key, f)
            n = len(neu)
            if n < 2 or n >= len(kandidaten):
                continue
            d = abs(n - ziel)
            if beste is None or d < beste[0]:
                beste = (d, g, s, w, key, neu)
        if beste is None:
            return None
        _, g, s, w, key, neu = beste
        zeilen.append(Zeile(g, s, w, arten[t], key))
        benutzt.add(g)
        kandidaten = neu
    return zeilen


def entferne_redundante(zeilen, basis, farben):
    """Streicht so lange Zeilen, deren Weglassen die Lösung eindeutig lässt,
    bis jede verbleibende Zeile nötig ist. Wird am Gabelpunkt gebraucht:
    Dort schrumpfen zwei Kettenzeilen den Suchraum so stark, dass die volle
    Zeilenzahl kaum je komplett nötig ist."""
    zeilen = list(zeilen)
    geaendert = True
    while geaendert and len(zeilen) > 1:
        geaendert = False
        for i in range(len(zeilen)):
            rest = zeilen[:i] + zeilen[i + 1:]
            if len(loesungsmenge(rest, basis, farben)) == 1:
                del zeilen[i]
                geaendert = True
                break
    return zeilen


def jede_zeile_noetig(zeilen, basis, farben) -> bool:
    for i in range(len(zeilen)):
        rest = zeilen[:i] + zeilen[i + 1:]
        if len(loesungsmenge(rest, basis, farben)) < 2:
            return False
    return True


def moegliche_keys(art: str, cfg: Konfig):
    """Alle im Rahmen der Schwach-Grenzen anzeigbaren Wertungen einer Art."""
    if art == "sw":
        return [(s, w) for s in range(cfg.max_schwarz + 1)
                for w in range(cfg.laenge + 1)
                if s + w <= cfg.max_treffer]
    if art == "summe":
        return list(range(cfg.max_treffer + 1))
    return list(range(cfg.max_schwarz + 1))


def luegner_kandidaten(zeilen, basis, farben):
    """Codes, die mit höchstens EINER angezeigten Zeile im Widerspruch
    stehen. Bricht ab, sobald ein zweiter gefunden ist."""
    treffer = []
    for c in basis:
        fehl = 0
        for z in zeilen:
            if projektion(z.art, *bewertung(z.tipp, c, farben)) != z.key:
                fehl += 1
                if fehl > 1:
                    break
        if fehl <= 1:
            treffer.append(c)
            if len(treffer) > 1:
                return treffer
    return treffer


def finde_luege(code, zeilen, basis, cfg, rng):
    """Wählt Zeile + gefälschte Wertung, sodass unter der Regel 'genau eine
    Zeile lügt' weiterhin nur `code` als Lösung bleibt."""
    idxs = list(range(len(zeilen)))
    rng.shuffle(idxs)
    for idx in idxs[:3]:
        z = zeilen[idx]
        fakes = [k for k in moegliche_keys(z.art, cfg) if k != z.key]
        rng.shuffle(fakes)
        for fake in fakes[:6]:
            probe = list(zeilen)
            probe[idx] = Zeile(z.tipp, z.wahr_schwarz, z.wahr_weiss,
                               z.art, fake, luege=True)
            if luegner_kandidaten(probe, basis, cfg.farben) == [code]:
                return probe
    return None


def kettenzwang_ok(zeilen, ketten, alle, cfg) -> bool:
    """Wahr, wenn der Teil ohne jede einzelne Kettenzeile (bei sonst
    vollständiger Information) mehrdeutig bleibt."""
    f = cfg.farben
    for weg in range(len(ketten)):
        basis = alle
        for i, k in enumerate(ketten):
            if i != weg:
                basis = filtere(basis, k.tipp, "sw", (k.schwarz, k.weiss), f)
        if cfg.luegner:
            ohne = luegner_kandidaten(zeilen, basis, f)
        else:
            ohne = loesungsmenge(zeilen, basis, f)
        if len(ohne) < 2:
            return False
    return True


def generiere_teil(nummer, zeilen_n, vorgaenger, alle, cfg, rng):
    """Erzeugt einen Teil. `vorgaenger` ist eine Liste von Paaren
    (quell_nummer, quell_code) — leer für Startteile, ein Eintrag in der
    normalen Kette, zwei am Gabelpunkt."""
    f = cfg.farben
    for _ in range(cfg.versuche):
        code = rng.choice(alle)
        ketten = []
        basis = alle
        for quelle, qcode in vorgaenger:
            kt = kettentipp(qcode, cfg)
            if kt == code or any(kt == k.tipp for k in ketten):
                ketten = None
                break
            ks, kw = bewertung(kt, code, f)
            if not schwach(ks, kw, cfg):
                ketten = None
                break
            basis = filtere(basis, kt, "sw", (ks, kw), f)
            ketten.append(Kettenzeile(kt, ks, kw, quelle))
        # Die Kettenzeilen dürfen den Suchraum nicht schon fast leeren.
        if ketten is None or len(basis) < 12 * zeilen_n:
            continue

        # Pool aller "schwachen" Tipps relativ zum Geheimcode.
        ketten_tipps = {k.tipp for k in ketten}
        pool = [g for g in alle
                if g != code
                and g not in ketten_tipps
                and schwach(*bewertung(g, code, f), cfg)]
        if len(pool) < zeilen_n * 3:
            continue

        if cfg.luegner:
            # R-1 Zeilen reichen zur Eindeutigkeit, eine Redundanzzeile
            # kommt dazu, damit jede (R-1)-Teilmenge eindeutig bleibt —
            # nötig, damit eine lügende Zeile verkraftbar ist.
            arten = zeilen_arten(zeilen_n - 1, cfg, rng)
            kern = baue_zeilen(code, basis, pool, arten, cfg, rng)
            if kern is None:
                continue
            # Lösungsmengen der (R-2)-Teilmengen einmal vorberechnen: die
            # Redundanzzeile g macht jede (R-1)-Teilmenge eindeutig genau
            # dann, wenn g jede dieser Mengen auf {code} reduziert.
            teilmengen = [loesungsmenge(kern[:i] + kern[i + 1:], basis, f)
                          for i in range(len(kern))]
            benutzt = {z.tipp for z in kern}
            zeilen = None
            for g in rng.sample(pool, min(len(pool), 250)):
                if g in benutzt:
                    continue
                s, w = bewertung(g, code, f)
                if all(filtere(m, g, "sw", (s, w), f) == [code]
                       for m in teilmengen):
                    zeilen = kern + [Zeile(g, s, w, "sw", (s, w))]
                    break
            if zeilen is None:
                continue
            zeilen = finde_luege(code, zeilen, basis, cfg, rng)
            if zeilen is None:
                continue
        else:
            arten = zeilen_arten(zeilen_n, cfg, rng)
            zeilen = baue_zeilen(code, basis, pool, arten, cfg, rng)
            if zeilen is None:
                continue
            if not jede_zeile_noetig(zeilen, basis, f):
                if len(vorgaenger) < 2:
                    continue
                # Gabelpunkt: überzählige Zeilen streichen statt verwerfen.
                zeilen = entferne_redundante(zeilen, basis, f)
                if len(zeilen) < 3:
                    continue

        # Kettenzwang: ohne JEDE einzelne Kettenzeile muss der Teil
        # mehrdeutig sein — am Gabelpunkt sind also beide Zuträger nötig.
        if not kettenzwang_ok(zeilen, ketten, alle, cfg):
            continue

        rng.shuffle(zeilen)
        teil = Teil(nummer, code, zeilen, ketten)
        teil.schwierigkeit = schaetze_schwierigkeit(teil, basis, cfg)
        return teil
    return None


def schaetze_schwierigkeit(teil, basis, cfg) -> str:
    """Heuristik: Wie lange bleibt die Kandidatenmenge groß, wenn man die
    Zeilen der Reihe nach anwendet, und wie mager sind die Hinweise?"""
    punkte = math.log2(max(2, len(basis))) / 2.0
    if cfg.luegner:
        punkte += 4.0  # die Lügner-Suche ist per se deutlich schwerer
    else:
        cur = basis
        verlauf = []
        for z in teil.zeilen:
            cur = filtere(cur, z.tipp, z.art, z.key, cfg.farben)
            verlauf.append(len(cur))
        mitte = verlauf[len(verlauf) // 2] if verlauf else 2
        punkte += math.log2(max(2, mitte))
    mager = sum(1 for z in teil.zeilen
                if z.wahr_schwarz + z.wahr_weiss <= 2) / len(teil.zeilen)
    punkte += 3.0 * mager
    if cfg.modus != "standard":
        punkte += 1.5
    if punkte < 9:
        return "leicht"
    if punkte < 12.5:
        return "mittel"
    return "schwer"


def generiere_puzzle(cfg: Konfig, rng: random.Random):
    alle = alle_codes(cfg)
    for extra in range(MAX_EXTRA_ZEILEN + 1):
        zeilen_n = cfg.zeilen + extra
        if extra:
            print(f"  {cfg.zeilen + extra - 1} Zeilen reichen bei diesen "
                  f"Einstellungen nicht für Eindeutigkeit — versuche es mit "
                  f"{zeilen_n} Zeilen pro Teil ...", file=sys.stderr)
        plan = topologie(cfg)
        teile = []
        codes = {}
        for n in range(1, cfg.teile + 1):
            vorgaenger = [(q, codes[q]) for q in plan[n]]
            teil = generiere_teil(n, zeilen_n, vorgaenger, alle, cfg, rng)
            if teil is None:
                teile = None
                break
            teile.append(teil)
            codes[n] = teil.code
            zusatz = ""
            if len(teil.zeilen) != zeilen_n:
                zusatz = (f", Gabelpunkt kommt mit {len(teil.zeilen)} "
                          f"normalen Zeilen aus")
            print(f"  Teil {n} erzeugt "
                  f"(Schwierigkeit: {teil.schwierigkeit}{zusatz}) ...",
                  file=sys.stderr)
        if teile is not None:
            cfg.zeilen = zeilen_n  # damit Kopf- und Regeltexte stimmen
            return teile
    raise RuntimeError(
        f"Auch mit {cfg.zeilen + MAX_EXTRA_ZEILEN} Zeilen pro Teil wurde "
        f"kein gültiges Rätsel gefunden. Tipp: mehr Farben, kürzeren Code "
        f"oder lockerere Treffer-Grenzen (--max-treffer) wählen.")


# ---------------------------------------------------------------------------
# Unabhängige Endprüfung (Beweis der Garantien per Enumeration)
# ---------------------------------------------------------------------------

def pruefe_puzzle(teile, cfg: Konfig):
    alle = alle_codes(cfg)
    f = cfg.farben
    plan = topologie(cfg)
    codes = {t.nummer: t.code for t in teile}
    for teil in teile:
        basis = alle
        assert [k.quelle for k in teil.ketten] == plan[teil.nummer], \
            f"Teil {teil.nummer}: Kettenzeilen passen nicht zur Topologie."
        for k in teil.ketten:
            assert k.tipp == kettentipp(codes[k.quelle], cfg), \
                f"Teil {teil.nummer}: Kettenzeile passt nicht zu Teil {k.quelle}."
            assert bewertung(k.tipp, teil.code, f) == (k.schwarz, k.weiss), \
                f"Teil {teil.nummer}: Kettenwertung falsch."
            assert schwach(k.schwarz, k.weiss, cfg), \
                f"Teil {teil.nummer}: Kettenwertung verletzt die Grenzen."
            basis = filtere(basis, k.tipp, "sw", (k.schwarz, k.weiss), f)
        for z in teil.zeilen:
            s, w = bewertung(z.tipp, teil.code, f)
            assert (s, w) == (z.wahr_schwarz, z.wahr_weiss), \
                f"Teil {teil.nummer}: gespeicherte Wertung falsch."
            assert schwach(s, w, cfg), \
                f"Teil {teil.nummer}: Zeile verletzt die Schwach-Grenzen."
            assert z.luege == (projektion(z.art, s, w) != z.key), \
                f"Teil {teil.nummer}: Lügen-Markierung inkonsistent."
        if cfg.luegner:
            rest = luegner_kandidaten(teil.zeilen, basis, f)
            assert rest == [teil.code], \
                f"Teil {teil.nummer}: Lügner-Lösung nicht eindeutig!"
            assert sum(1 for z in teil.zeilen if z.luege) == 1
        else:
            rest = loesungsmenge(teil.zeilen, basis, f)
            assert rest == [teil.code], \
                f"Teil {teil.nummer}: Lösung nicht eindeutig!"
            assert jede_zeile_noetig(teil.zeilen, basis, f), \
                f"Teil {teil.nummer}: Eine Zeile ist überflüssig."
        assert kettenzwang_ok(teil.zeilen, teil.ketten, alle, cfg), \
            f"Teil {teil.nummer}: auch ohne eine der Kettenzeilen lösbar!"


# ---------------------------------------------------------------------------
# Ausgabe: Konsole
# ---------------------------------------------------------------------------

def code_text(code) -> str:
    return " ".join(SYMBOLE[i] for i in code)


def wertung_text(art, key) -> str:
    if art == "sw":
        s, w = key
        return "●" * s + "○" * w if (s or w) else "—"
    if art == "summe":
        return f"[{key} Treffer]"
    return "●" * key if key else "—"


def drucke_konsole(teile, cfg: Konfig, seed: int):
    b = []
    b.append("=" * 62)
    b.append("MASTERMIND-KETTE".center(62))
    b.append((f"{cfg.laenge} Stellen · {cfg.farben} Farben · "
              f"{cfg.zeilen} Zeilen/Teil · Seed {seed}").center(62))
    b.append("=" * 62)
    farbleiste = "  ".join(f"{s}={FARBEN[s][0]}" for s in SYMBOLE[:cfg.farben])
    b.append(f"Farben: {farbleiste}")
    b.append("")
    for teil in teile:
        b.append(f"TEIL {teil.nummer}   (Schwierigkeit: {teil.schwierigkeit})")
        for ki, k in enumerate(teil.ketten, 1):
            label = f"K{ki}" if len(teil.ketten) > 1 else "K "
            richtung = ("rückwärts eingetragener "
                        if cfg.kette == "rueckwaerts" else "")
            b.append(f"  {label} {'? ' * cfg.laenge}<- {richtung}Code aus "
                     f"Teil {k.quelle}   "
                     f"{wertung_text('sw', (k.schwarz, k.weiss))}")
        for i, z in enumerate(teil.zeilen, 1):
            b.append(f"  {i}  {code_text(z.tipp)}   {wertung_text(z.art, z.key)}")
        b.append("")
    b.append("-" * 62)
    b.append("Regeln:")
    for r in regel_zeilen(cfg):
        b.append(f"  * {r}")
    b.append("")
    b.append("LÖSUNGEN (nicht weiterscrollen, wer selbst rätseln will!)")
    for teil in teile:
        extra = ""
        if cfg.luegner:
            li = next(i for i, z in enumerate(teil.zeilen, 1) if z.luege)
            lz = next(z for z in teil.zeilen if z.luege)
            wahr = wertung_text(lz.art,
                                projektion(lz.art, lz.wahr_schwarz,
                                           lz.wahr_weiss))
            extra = f"   (Lügenzeile: {li}, wahre Wertung: {wahr})"
        b.append(f"  Teil {teil.nummer}: {code_text(teil.code)}{extra}")
    print("\n".join(b))


def regel_zeilen(cfg: Konfig):
    regeln = []
    regeln.append("Schwarz ● = richtiges Symbol am richtigen Platz; "
                  "Weiß ○ = richtiges Symbol am falschen Platz.")
    if cfg.modus == "schlampig":
        regeln.append("Bei Zeilen mit Treffer-Feld [n Treffer] war der "
                      "Wertende schlampig: Es ist nur die GESAMTZAHL der "
                      "Treffer bekannt, nicht die Aufteilung schwarz/weiß.")
    elif cfg.modus == "schwarz":
        regeln.append("In diesem Rätsel werden NUR schwarze Stifte gewertet; "
                      "weiße Hinweise gibt es nicht.")
    if cfg.wiederholung:
        regeln.append("Farben dürfen sich im Code wiederholen.")
    else:
        regeln.append("Im Code kommt jede Farbe höchstens einmal vor.")
    regeln.append(f"Jede normale Zeile hat höchstens {cfg.max_schwarz} Treffer "
                  f"in richtiger Position und {cfg.max_treffer} Treffer "
                  f"insgesamt.")
    if cfg.luegner:
        regeln.append("ACHTUNG: In jedem Teil lügt GENAU EINE normale "
                      "Hinweiszeile (ihre Wertung ist falsch). Die "
                      "Kettenzeile sagt immer die Wahrheit.")
    else:
        regeln.append("Trotzdem sind alle normalen Zeilen nötig.")
    if cfg.teile > 1:
        rueck = " RÜCKWÄRTS" if cfg.kette == "rueckwaerts" else ""
        if cfg.gabel and cfg.teile >= 3:
            regeln.append("Das Rätsel gabelt sich: Teile ohne K-Zeile sind "
                          "eigenständige Startpunkte zweier Stränge. Übertrage "
                          f"jeden Lösungscode{rueck} in die markierten "
                          "K-Zeilen der Teile, die ihn verlangen.")
            regeln.append(f"Der letzte Teil ist der Gabelpunkt: Er hat ZWEI "
                          f"Kettenzeilen (K1 und K2) und braucht die Lösungen "
                          f"beider Stränge.")
        else:
            regeln.append(f"Löse Teil 1. Übertrage danach jeden Lösungscode"
                          f"{rueck} in die markierte Kettenzeile des "
                          f"nächsten Teils.")
        regeln.append("Die Schwarz/Weiß-Wertung jeder Kettenzeile ist bereits "
                      "gegeben. Ohne jede einzelne von ihnen ist der Teil "
                      "nicht eindeutig lösbar.")
    return regeln


# ---------------------------------------------------------------------------
# Ausgabe: HTML (druckfertig, Optik wie die Buchvorlage)
# ---------------------------------------------------------------------------

def html_wertung(art, key) -> str:
    if art == "sw":
        s, w = key
        dots = "".join('<span class="dot black"></span>' for _ in range(s))
        dots += "".join('<span class="dot white"></span>' for _ in range(w))
        return dots or '<span class="none">–</span>'
    if art == "summe":
        return f'<span class="badge">{key}&nbsp;Treffer</span>'
    dots = "".join('<span class="dot black"></span>' for _ in range(key))
    return dots or '<span class="none">–</span>'


def html_kreis(sym_index: int) -> str:
    s = SYMBOLE[sym_index]
    _, bg, fg = FARBEN[s]
    return f'<span class="peg" style="background:{bg};color:{fg}">{s}</span>'


def schreibe_html(teile, cfg: Konfig, seed: int, pfad: str,
                  art: str = "aufgabe"):
    unter = _untertitel(cfg, teile, seed)
    wert_kopf = {"standard": "schwarz / weiß", "schlampig": "Wertung",
                 "schwarz": "schwarz"}[cfg.modus]
    titel = ("MASTERMIND-KETTE" if art == "aufgabe"
             else "MASTERMIND-KETTE — LÖSUNGEN")

    karten = []
    for teil in teile:
        zeilen_html = []
        if art == "loesung":
            pegs = "".join(html_kreis(x) for x in teil.code)
            zeilen_html.append(
                f'<div class="row"><span class="idx">L</span>{pegs}</div>')
            zusatz = [f"Code: {code_text(teil.code)}"]
            if cfg.luegner:
                li = next(i for i, z in enumerate(teil.zeilen, 1) if z.luege)
                lz = next(z for z in teil.zeilen if z.luege)
                wahr = wertung_text(lz.art, projektion(
                    lz.art, lz.wahr_schwarz, lz.wahr_weiss))
                zusatz.append(f"Lügenzeile: {li} (wahre Wertung: {wahr})")
            for ki, k in enumerate(teil.ketten, 1):
                label = f"K{ki}" if len(teil.ketten) > 1 else "K"
                zusatz.append(f"Zeile {label} aus Teil {k.quelle}: "
                              f"{code_text(k.tipp)}")
            for txt in zusatz:
                zeilen_html.append(
                    f'<div class="note">{html_mod.escape(txt)}</div>')
            kopf = f"Level: {teil.schwierigkeit}"
        else:
            for ki, k in enumerate(teil.ketten, 1):
                label = f"K{ki}" if len(teil.ketten) > 1 else "K"
                frage = "".join('<span class="peg ghost">?</span>'
                                for _ in range(cfg.laenge))
                richtung = " (rückwärts!)" if cfg.kette == "rueckwaerts" else ""
                fb = html_wertung("sw", (k.schwarz, k.weiss))
                zeilen_html.append(
                    f'<div class="row chain"><span class="idx">{label}</span>'
                    f'<span class="chainlabel">Code aus Teil '
                    f'{k.quelle}{richtung}</span>{frage}'
                    f'<span class="fb">{fb}</span></div>')
            for i, z in enumerate(teil.zeilen, 1):
                pegs = "".join(html_kreis(x) for x in z.tipp)
                zeilen_html.append(
                    f'<div class="row"><span class="idx">{i}</span>{pegs}'
                    f'<span class="fb">{html_wertung(z.art, z.key)}</span>'
                    f'</div>')
            kopf = wert_kopf
        karten.append(
            f'<section class="card"><header><h2>TEIL {teil.nummer}</h2>'
            f'<span class="fbhead">{kopf}</span></header>'
            + "".join(zeilen_html) + "</section>")

    if art == "aufgabe":
        regeln = "".join(f"<li>{html_mod.escape(r)}</li>"
                         for r in regel_zeilen(cfg))
        legende = ('<div class="legende">Farben: ' + " · ".join(
            f"<b>{s}</b>&nbsp;=&nbsp;{FARBEN[s][0]}"
            for s in SYMBOLE[:cfg.farben]) + "</div>")
        fuss = f'<div class="rules"><ul>{regeln}</ul></div>{legende}'
    else:
        fuss = ('<div class="rules">Zu jeder Aufgabe gibt es genau eine '
                'Lösung — per vollständiger Enumeration geprüft.</div>')

    signatur = (f'<div class="sig">{html_mod.escape(cfg.signatur)}</div>'
                if cfg.signatur else "")

    doc = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titel}</title>
<style>
  :root {{
    --bg:#eef1f5; --card:#ffffff; --ink:#1b3a55; --muted:#8a97a5;
    --line:#e3e8ee; --chain:#e8f4fa; --chainline:#2f7f9e;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--ink);
         font-family:"Segoe UI",system-ui,Arial,sans-serif; padding:28px; }}
  h1 {{ text-align:center; font-size:2.1rem; letter-spacing:.03em; }}
  .sub {{ text-align:center; color:#5b6b7a; margin:.4rem 0 1.6rem; }}
  .grid {{ display:grid; gap:26px;
           grid-template-columns:repeat(auto-fit,minmax(420px,1fr));
           max-width:1200px; margin:0 auto; }}
  .card {{ background:var(--card); border:1px solid var(--line);
           border-radius:14px; padding:18px 20px;
           box-shadow:0 2px 8px rgba(27,58,85,.07); }}
  .card header {{ display:flex; justify-content:space-between;
                  align-items:baseline; margin-bottom:10px; }}
  .card h2 {{ font-size:1.25rem; }}
  .fbhead {{ color:var(--muted); font-size:.85rem; }}
  .row {{ display:flex; align-items:center; gap:9px; padding:8px 6px;
          border-radius:9px; }}
  .row:nth-child(odd) {{ background:#f7f9fb; }}
  .idx {{ width:1.6em; text-align:right; color:#5b6b7a; font-weight:600;
          flex:none; }}
  .peg {{ width:44px; height:44px; border-radius:50%; flex:none;
          display:inline-flex; align-items:center; justify-content:center;
          font-weight:700; font-size:1.05rem;
          border:2.5px solid #24303c; }}
  .peg.ghost {{ background:#f4fafd; color:var(--chainline);
                border:2.5px dashed var(--chainline); }}
  .row.chain {{ background:var(--chain);
                border:2px dashed var(--chainline); margin-bottom:6px; }}
  .chainlabel {{ font-size:.72rem; font-weight:700; color:var(--chainline);
                 width:64px; line-height:1.15; flex:none; }}
  .fb {{ margin-left:auto; display:flex; gap:5px; align-items:center;
         min-width:56px; justify-content:flex-end; font-size:.85rem; }}
  .dot {{ width:15px; height:15px; border-radius:50%; display:inline-block;
          border:2px solid #24303c; }}
  .dot.black {{ background:#24303c; }}
  .dot.white {{ background:#fff; }}
  .none {{ color:var(--muted); }}
  .badge {{ background:#24303c; color:#fff; border-radius:999px;
            padding:3px 10px; font-size:.8rem; font-weight:600; }}
  .rules {{ max-width:1200px; margin:26px auto 0; color:#3d4f60;
            font-size:.95rem; }}
  .rules ul {{ list-style:"• "; padding-left:1.1em; }}
  .rules li {{ margin:.25em 0; }}
  .legende {{ max-width:1200px; margin:14px auto 0; color:#5b6b7a;
              font-size:.9rem; }}
  .note {{ color:#5b6b7a; font-size:.85rem; padding:2px 6px; }}
  .sig {{ text-align:right; max-width:1200px; margin:18px auto 0;
          color:var(--muted); }}
  @media print {{
    body {{ background:#fff; padding:10px; }}
    details {{ display:none; }}
  }}
</style></head><body>
<h1>{titel}</h1>
<div class="sub">{unter}</div>
<div class="grid">{''.join(karten)}</div>
{fuss}
{signatur}
</body></html>"""
    with open(pfad, "w", encoding="utf-8") as fh:
        fh.write(doc)


def schreibe_json(teile, cfg: Konfig, seed: int, pfad: str):
    def code_str(c):
        return "".join(SYMBOLE[i] for i in c)
    daten = {
        "konfig": {k: v for k, v in vars(cfg).items()
                   if k not in ("versuche", "stichprobe", "endsuche")},
        "seed": seed,
        "teile": [{
            "nummer": t.nummer,
            "loesung": code_str(t.code),
            "schwierigkeit": t.schwierigkeit,
            "ketten": [{
                "quelle": k.quelle,
                "tipp": code_str(k.tipp),
                "schwarz": k.schwarz, "weiss": k.weiss} for k in t.ketten],
            "zeilen": [{
                "tipp": code_str(z.tipp),
                "art": z.art,
                "angezeigt": ({"schwarz": z.key[0], "weiss": z.key[1]}
                              if z.art == "sw" else z.key),
                "luege": z.luege,
                **({"wahr": {"schwarz": z.wahr_schwarz,
                             "weiss": z.wahr_weiss}} if z.luege else {}),
            } for z in t.zeilen],
        } for t in teile],
    }
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Zeichenmodell (gemeinsame Grundlage für PDF- und PNG-Ausgabe)
# ---------------------------------------------------------------------------
#
# Eine Seite ist eine Liste einfacher Grundelemente in einem Koordinatensystem
# mit Ursprung oben links (y wächst nach unten, Einheit = Punkt wie im PDF).
# Beide Ausgabewege rendern daraus dasselbe Bild.

A4 = (595.28, 841.89)


@dataclass
class Seite:
    breite: float
    hoehe: float
    elemente: list


def el_rect(x, y, w, h, radius=0, fuell=None, rand=None, breite=1,
            gestrichelt=False):
    return ("rect", x, y, w, h, radius, fuell, rand, breite, gestrichelt)


def el_kreis(cx, cy, r, fuell=None, rand=None, breite=1, gestrichelt=False):
    return ("kreis", cx, cy, r, fuell, rand, breite, gestrichelt)


def el_text(x, basislinie, s, groesse, farbe=(0, 0, 0), anker="start",
            fett=False):
    return ("text", x, basislinie, s, groesse, farbe, anker, fett)


def rgb(hexfarbe: str):
    h = hexfarbe.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


# Zeichenbreiten der PDF-Standardschrift Helvetica (Einheiten pro 1000).
# Damit werden Textbreiten für Zentrierung und Zeilenumbruch berechnet.
_W_NORMAL = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667,
    "'": 191, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584,
    "?": 556, "@": 1015, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556,
    "`": 333, "{": 334, "|": 260, "}": 334, "~": 584,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722,
    "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722,
    "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556,
    "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556,
    "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
}
_W_FETT = dict(_W_NORMAL, **{
    "A": 722, "B": 722, "J": 556, "K": 722, "L": 611, "?": 611,
    "a": 556, "b": 611, "c": 556, "d": 611, "e": 556, "f": 333, "g": 611,
    "h": 611, "i": 278, "j": 278, "k": 556, "l": 278, "m": 889, "n": 611,
    "o": 611, "p": 611, "q": 611, "r": 389, "s": 556, "t": 333, "u": 611,
    "v": 556, "w": 778, "x": 556, "y": 556, "z": 500,
    ":": 333, ";": 333, "!": 333, "-": 333,
})
# Umlaute und Sonderzeichen auf die Breite ihres Grundzeichens abbilden.
for _tab in (_W_NORMAL, _W_FETT):
    for _z, _basis in (("ä", "a"), ("ö", "o"), ("ü", "u"),
                       ("Ä", "A"), ("Ö", "O"), ("Ü", "U"), ("é", "e")):
        _tab[_z] = _tab[_basis]
    _tab["ß"] = 556
    _tab["·"] = 278
    _tab["•"] = 350
    _tab["●"] = 640
    _tab["○"] = 640
    _tab["–"] = 556
    _tab["—"] = 1000
    _tab["„"] = 333
    _tab["“"] = 333
    _tab["€"] = 556


def text_breite(s: str, groesse: float, fett=False) -> float:
    tab = _W_FETT if fett else _W_NORMAL
    ziffer = 556
    return sum(tab.get(z, ziffer if z.isdigit() else 556)
               for z in s) * groesse / 1000.0


def umbruch(s: str, breite: float, groesse: float, fett=False):
    """Bricht einen Text auf die gegebene Breite um."""
    zeilen, akt = [], ""
    for wort in s.split(" "):
        probe = f"{akt} {wort}".strip()
        if akt and text_breite(probe, groesse, fett) > breite:
            zeilen.append(akt)
            akt = wort
        else:
            akt = probe
    if akt:
        zeilen.append(akt)
    return zeilen


def el_text_stifte(el, x, basislinie, s, groesse, farbe=(0, 0, 0),
                  fett=False):
    """Wie el_text, zeichnet aber ● und ○ als echte Kreise. Die
    PDF-Standardkodierung kennt diese Zeichen nicht, und so sehen sie
    ohnehin genauso aus wie die Stifte in den Hinweiszeilen."""
    if "●" not in s and "○" not in s:
        el.append(el_text(x, basislinie, s, groesse, farbe))
        return
    r = groesse * 0.25
    puffer = ""
    for zeichen in s:
        if zeichen in "●○":
            if puffer:
                el.append(el_text(x, basislinie, puffer, groesse, farbe,
                                  "start", fett))
                x += text_breite(puffer, groesse, fett)
                puffer = ""
            el.append(el_kreis(x + groesse * 0.275, basislinie - r, r,
                               fuell=C_DUNKEL if zeichen == "●" else C_WEISS,
                               rand=C_DUNKEL, breite=groesse * 0.09))
            x += text_breite(zeichen, groesse, fett)
        else:
            puffer += zeichen
    if puffer:
        el.append(el_text(x, basislinie, puffer, groesse, farbe, "start", fett))


# ---------------------------------------------------------------------------
# Seitenaufbau (Aufgabe und Lösung)
# ---------------------------------------------------------------------------

C_INK = rgb("#1b3a55")
C_GRAU = rgb("#5b6b7a")
C_MUTED = rgb("#8a97a5")
C_LINIE = rgb("#e3e8ee")
C_ZEILE = rgb("#f7f9fb")
C_KETTE = rgb("#e8f4fa")
C_KETTELINIE = rgb("#2f7f9e")
C_DUNKEL = rgb("#24303c")
C_WEISS = (1, 1, 1)


def _untertitel(cfg: Konfig, teile, seed: int) -> str:
    modus_txt = {"standard": "Schwarz/Weiß-Wertung",
                 "schlampig": "teils nur Treffersumme",
                 "schwarz": "nur schwarze Stifte"}[cfg.modus]
    unter = (f"{cfg.laenge} Stellen · {cfg.farben} Farben · "
             f"{'Wiederholungen erlaubt' if cfg.wiederholung else 'ohne Wiederholung'}"
             f" · max. {cfg.max_schwarz} schwarz / {cfg.max_treffer} Treffer "
             f"je Zeile · {modus_txt}")
    if cfg.luegner:
        unter += " · Lügner-Variante"
    if cfg.kette == "rueckwaerts" and cfg.teile > 1:
        unter += " · Rückwärts-Kette"
    if cfg.gabel and cfg.teile >= 3:
        unter += " · Gabel-Kette"
    schwierig = max((t.schwierigkeit for t in teile),
                    key=lambda s: ["leicht", "mittel", "schwer"].index(s))
    return f"{unter} · Level: {schwierig} · Seed {seed}"


def _wertung_elemente(el, x_rechts, mitte, art, key, punkt_r=3.4):
    """Zeichnet die Schwarz/Weiß-Stifte rechtsbündig; gibt die Breite zurück."""
    if art == "summe":
        txt = f"{key} Treffer"
        w = text_breite(txt, 7.5, True) + 12
        el.append(el_rect(x_rechts - w, mitte - 6, w, 12, 6, fuell=C_DUNKEL))
        el.append(el_text(x_rechts - w / 2, mitte + 2.7, txt, 7.5,
                          C_WEISS, "middle", True))
        return w
    if art == "sw":
        s, weiss = key
    else:
        s, weiss = key, 0
    n = s + weiss
    if n == 0:
        el.append(el_text(x_rechts, mitte + 3, "–", 9, C_MUTED, "end"))
        return text_breite("–", 9)
    schritt = 2 * punkt_r + 2.6
    x = x_rechts - n * schritt + punkt_r
    for i in range(n):
        el.append(el_kreis(x + i * schritt, mitte, punkt_r,
                           fuell=C_DUNKEL if i < s else C_WEISS,
                           rand=C_DUNKEL, breite=1.1))
    return n * schritt


def _karte(el, x, y, breite, titel, kopf_rechts, zeilen, cfg, peg_d, zeilen_h,
           hinweise=()):
    """Zeichnet eine Teil-Karte; `zeilen` sind Tupel
    (label, pegs|None, art, key, stil) mit stil in {'normal','kette','loesung'}.
    Gibt die Höhe der Karte zurück."""
    pad = 9.0
    kopf_h = 15.0
    hinweis_h = 10.0 * len(hinweise)
    hoehe = pad + kopf_h + hinweis_h + len(zeilen) * zeilen_h + pad
    el.append(el_rect(x, y, breite, hoehe, 8, fuell=C_WEISS,
                      rand=C_LINIE, breite=1))
    el.append(el_text(x + pad, y + pad + 10, titel, 11.5, C_INK, "start", True))
    if kopf_rechts:
        el.append(el_text(x + breite - pad, y + pad + 9, kopf_rechts, 7.5,
                          C_MUTED, "end"))

    idx_b = 11.0
    fb_b = max(34.0, cfg.laenge * (2 * 3.4 + 2.6) + 4)
    peg_x0 = x + pad + idx_b + 4
    peg_gap = 3.6
    for hi, hinweis in enumerate(hinweise):
        el.append(el_text(x + pad, y + pad + kopf_h + 7 + 10.0 * hi, hinweis,
                          7.2, C_KETTELINIE, "start", True))
    yy = y + pad + kopf_h + hinweis_h
    for i, (label, pegs, art, key, stil) in enumerate(zeilen):
        mitte = yy + zeilen_h / 2
        if stil == "kette":
            el.append(el_rect(x + pad - 3, yy + 1.5, breite - 2 * pad + 6,
                              zeilen_h - 3, 6, fuell=C_KETTE,
                              rand=C_KETTELINIE, breite=1.2,
                              gestrichelt=True))
        elif i % 2 == 1:
            el.append(el_rect(x + pad - 3, yy + 1.5, breite - 2 * pad + 6,
                              zeilen_h - 3, 6, fuell=C_ZEILE))
        el.append(el_text(x + pad + idx_b, mitte + 3, label, 8.5,
                          C_GRAU, "end", True))
        if pegs is None:  # verdeckte Kettenzeile: Fragezeichen
            for j in range(cfg.laenge):
                cx = peg_x0 + j * (peg_d + peg_gap) + peg_d / 2
                el.append(el_kreis(cx, mitte, peg_d / 2, fuell=rgb("#f4fafd"),
                                   rand=C_KETTELINIE, breite=1.6,
                                   gestrichelt=True))
                el.append(el_text(cx, mitte + peg_d * 0.17, "?", peg_d * 0.5,
                                  C_KETTELINIE, "middle", True))
        else:
            for j, sym in enumerate(pegs):
                cx = peg_x0 + j * (peg_d + peg_gap) + peg_d / 2
                buchstabe = SYMBOLE[sym]
                _, bg, fg = FARBEN[buchstabe]
                el.append(el_kreis(cx, mitte, peg_d / 2, fuell=rgb(bg),
                                   rand=C_DUNKEL, breite=1.6))
                el.append(el_text(cx, mitte + peg_d * 0.17, buchstabe,
                                  peg_d * 0.46, rgb(fg), "middle", True))
        if art is not None:
            _wertung_elemente(el, x + breite - pad - 2, mitte, art, key)
        yy += zeilen_h
    return hoehe


def _peg_masse(cfg: Konfig, karten_b: float):
    """Passende Kreisgröße für die Kartenbreite."""
    pad, idx_b = 9.0, 11.0
    fb_b = max(34.0, cfg.laenge * (2 * 3.4 + 2.6) + 4)
    frei = karten_b - 2 * pad - idx_b - 4 - fb_b - 6
    peg_d = min(30.0, (frei - (cfg.laenge - 1) * 3.6) / cfg.laenge)
    return max(12.0, peg_d)


def baue_seite(teile, cfg: Konfig, seed: int, art: str) -> Seite:
    """Baut die Aufgaben- oder die Lösungsseite als Zeichnung auf."""
    rand = 34.0
    breite, hoehe = A4
    inhalt_b = breite - 2 * rand
    el = []
    y = rand

    titel = ("MASTERMIND-KETTE" if art == "aufgabe"
             else "MASTERMIND-KETTE — LÖSUNGEN")
    el.append(el_text(breite / 2, y + 16, titel, 19, C_INK, "middle", True))
    y += 24
    for zeile in umbruch(_untertitel(cfg, teile, seed), inhalt_b, 8.2):
        el.append(el_text(breite / 2, y + 8, zeile, 8.2, C_GRAU, "middle"))
        y += 11
    y += 10

    spalten = 2 if len(teile) > 1 else 1
    luecke = 16.0
    karten_b = (inhalt_b - luecke * (spalten - 1)) / spalten
    peg_d = _peg_masse(cfg, karten_b)
    zeilen_h = peg_d + 6
    wert_kopf = {"standard": "schwarz / weiß", "schlampig": "Wertung",
                 "schwarz": "schwarz"}[cfg.modus]

    zeilen_y = y
    max_h = 0.0
    for n, teil in enumerate(teile):
        spalte = n % spalten
        if spalte == 0 and n > 0:
            zeilen_y += max_h + luecke
            max_h = 0.0
        x = rand + spalte * (karten_b + luecke)

        mehrere = len(teil.ketten) > 1
        if art == "aufgabe":
            zeilen = []
            for ki, k in enumerate(teil.ketten, 1):
                label = f"K{ki}" if mehrere else "K"
                zeilen.append((label, None, "sw", (k.schwarz, k.weiss),
                               "kette"))
            for i, z in enumerate(teil.zeilen, 1):
                zeilen.append((str(i), z.tipp, z.art, z.key, "normal"))
            kopf = wert_kopf
        else:
            zeilen = [("L", teil.code, None, None, "loesung")]
            kopf = f"Level: {teil.schwierigkeit}"

        hinweise = []
        if art == "aufgabe":
            richtung = (" rückwärts" if cfg.kette == "rueckwaerts" else "")
            for ki, k in enumerate(teil.ketten, 1):
                label = f"K{ki}" if mehrere else "K"
                hinweise.append(f"Zeile {label}: Lösungscode aus Teil "
                                f"{k.quelle}{richtung} eintragen")
        h = _karte(el, x, zeilen_y, karten_b, f"TEIL {teil.nummer}", kopf,
                   zeilen, cfg, peg_d, zeilen_h, hinweise)

        if art == "loesung":
            # Klartext und ggf. Lügenzeile unter die Lösung schreiben.
            zusatz = [f"Code: {code_text(teil.code)}"]
            if cfg.luegner:
                li = next(i for i, z in enumerate(teil.zeilen, 1) if z.luege)
                lz = next(z for z in teil.zeilen if z.luege)
                wahr = wertung_text(lz.art, projektion(lz.art, lz.wahr_schwarz,
                                                       lz.wahr_weiss))
                zusatz.append(f"Lügenzeile: {li} (wahr: {wahr})")
            for ki, k in enumerate(teil.ketten, 1):
                label = f"K{ki}" if mehrere else "K"
                zusatz.append(f"Zeile {label} aus Teil {k.quelle}: "
                              f"{code_text(k.tipp)}")
            ty = zeilen_y + h + 3
            for txt in zusatz:
                el_text_stifte(el, x + 9, ty + 7, txt, 7.6, C_GRAU)
                ty += 9.5
            h = ty - zeilen_y
        max_h = max(max_h, h)
    y = zeilen_y + max_h + 16

    if art == "aufgabe":
        for regel in regel_zeilen(cfg):
            for i, zeile in enumerate(umbruch(regel, inhalt_b - 10, 8.0)):
                if i == 0:
                    el.append(el_text(rand, y + 7, "•", 8.0, C_GRAU))
                el_text_stifte(el, rand + 10, y + 7, zeile, 8.0, C_GRAU)
                y += 10
        y += 4
        legende = "Farben: " + " · ".join(
            f"{s} = {FARBEN[s][0]}" for s in SYMBOLE[:cfg.farben])
        for zeile in umbruch(legende, inhalt_b, 8.0):
            el.append(el_text(rand, y + 7, zeile, 8.0, C_MUTED))
            y += 10
    else:
        el.append(el_text(rand, y + 7,
                          "Zu jeder Aufgabe gibt es genau eine Lösung — "
                          "per vollständiger Enumeration geprüft.",
                          8.0, C_MUTED))
        y += 10

    if cfg.signatur:
        el.append(el_text(breite - rand, hoehe - rand + 6, cfg.signatur, 8.0,
                          C_MUTED, "end"))

    # Passt der Inhalt nicht auf die Seite, alles gleichmäßig verkleinern.
    verbraucht = y + rand
    if verbraucht > hoehe:
        f = (hoehe - 2 * rand) / (verbraucht - 2 * rand)
        el = [_skaliere(e, f, rand) for e in el]
    return Seite(breite, hoehe, el)


def _skaliere(e, f, rand):
    def s(v):
        return rand + (v - rand) * f
    if e[0] == "rect":
        _, x, y, w, h, r, fu, ra, b, g = e
        return ("rect", s(x), s(y), w * f, h * f, r * f, fu, ra, b * f, g)
    if e[0] == "kreis":
        _, cx, cy, r, fu, ra, b, g = e
        return ("kreis", s(cx), s(cy), r * f, fu, ra, b * f, g)
    _, x, y, txt, gr, farbe, anker, fett = e
    return ("text", s(x), s(y), txt, gr * f, farbe, anker, fett)


# ---------------------------------------------------------------------------
# Ausgabe: PDF (eigener Vektor-Writer, ohne Fremdbibliotheken)
# ---------------------------------------------------------------------------

_K = 0.5523  # Bézier-Faktor für Kreise


_ERSATZ = {"★": "*", "→": "->", "←": "<-", "✓": "v", "✗": "x", "≤": "<=",
           "≥": ">=", "≠": "!=", "…": "...", "●": "*", "○": "o"}


def _pdf_str(s: str) -> bytes:
    """Text nach WinAnsi (cp1252) kodieren und PDF-gerecht maskieren.
    Zeichen außerhalb von WinAnsi (etwa in einer eigenen Signatur) werden
    durch lesbare Entsprechungen ersetzt statt durch Fragezeichen."""
    for _alt, _neu in _ERSATZ.items():
        s = s.replace(_alt, _neu)
    roh = s.encode("cp1252", "replace")
    out = bytearray()
    for b in roh:
        if b in (0x28, 0x29, 0x5C):
            out += b"\\" + bytes([b])
        elif b < 32 or b > 126:
            out += ("\\%03o" % b).encode("ascii")
        else:
            out.append(b)
    return bytes(out)


def _pdf_kreis(cx, cy, r):
    k = _K * r
    return (f"{cx + r:.2f} {cy:.2f} m "
            f"{cx + r:.2f} {cy + k:.2f} {cx + k:.2f} {cy + r:.2f} "
            f"{cx:.2f} {cy + r:.2f} c "
            f"{cx - k:.2f} {cy + r:.2f} {cx - r:.2f} {cy + k:.2f} "
            f"{cx - r:.2f} {cy:.2f} c "
            f"{cx - r:.2f} {cy - k:.2f} {cx - k:.2f} {cy - r:.2f} "
            f"{cx:.2f} {cy - r:.2f} c "
            f"{cx + k:.2f} {cy - r:.2f} {cx + r:.2f} {cy - k:.2f} "
            f"{cx + r:.2f} {cy:.2f} c h ")


def _pdf_rundrect(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    k = _K * r
    x2, y2 = x + w, y + h
    return (f"{x + r:.2f} {y:.2f} m {x2 - r:.2f} {y:.2f} l "
            f"{x2 - r + k:.2f} {y:.2f} {x2:.2f} {y + r - k:.2f} "
            f"{x2:.2f} {y + r:.2f} c "
            f"{x2:.2f} {y2 - r:.2f} l "
            f"{x2:.2f} {y2 - r + k:.2f} {x2 - r + k:.2f} {y2:.2f} "
            f"{x2 - r:.2f} {y2:.2f} c "
            f"{x + r:.2f} {y2:.2f} l "
            f"{x + r - k:.2f} {y2:.2f} {x:.2f} {y2 - r + k:.2f} "
            f"{x:.2f} {y2 - r:.2f} c "
            f"{x:.2f} {y + r:.2f} l "
            f"{x:.2f} {y + r - k:.2f} {x + r - k:.2f} {y:.2f} "
            f"{x + r:.2f} {y:.2f} c h ")


def _mal_befehl(fuell, rand) -> str:
    if fuell is not None and rand is not None:
        return "B\n"
    return "f\n" if fuell is not None else "S\n"


def seite_als_pdf(seite: Seite) -> bytes:
    H = seite.hoehe
    c = [f"1 J 1 j\n"]
    for e in seite.elemente:
        if e[0] in ("rect", "kreis"):
            if e[0] == "rect":
                _, x, y, w, h, r, fuell, rnd, bre, gestr = e
                pfad = (_pdf_rundrect(x, H - y - h, w, h, r) if r > 0
                        else f"{x:.2f} {H - y - h:.2f} {w:.2f} {h:.2f} re ")
            else:
                _, cx, cy, r, fuell, rnd, bre, gestr = e
                pfad = _pdf_kreis(cx, H - cy, r)
            if fuell is None and rnd is None:
                continue
            if fuell is not None:
                c.append(f"{fuell[0]:.3f} {fuell[1]:.3f} {fuell[2]:.3f} rg\n")
            if rnd is not None:
                c.append(f"{rnd[0]:.3f} {rnd[1]:.3f} {rnd[2]:.3f} RG\n"
                         f"{bre:.2f} w\n")
                c.append("[2.6 2.2] 0 d\n" if gestr else "[] 0 d\n")
            c.append(pfad + _mal_befehl(fuell, rnd))
        else:
            _, x, basis, txt, gr, farbe, anker, fett = e
            if not txt:
                continue
            b = text_breite(txt, gr, fett)
            if anker == "middle":
                x -= b / 2
            elif anker == "end":
                x -= b
            c.append(f"{farbe[0]:.3f} {farbe[1]:.3f} {farbe[2]:.3f} rg\n"
                     f"BT /{'F2' if fett else 'F1'} {gr:.2f} Tf "
                     f"{x:.2f} {H - basis:.2f} Td ")
            c.append(b"(".decode() + _pdf_str(txt).decode("latin-1")
                     + ") Tj ET\n")
    strom = "".join(c).encode("latin-1")
    komprimiert = zlib.compress(strom)

    objekte = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (f"<< /Type /Pages /Kids [3 0 R] /Count 1 >>").encode(),
        (f"<< /Type /Page /Parent 2 0 R /MediaBox "
         f"[0 0 {seite.breite:.2f} {seite.hoehe:.2f}] /Resources "
         f"<< /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>").encode(),
        (b"<< /Length " + str(len(komprimiert)).encode()
         + b" /Filter /FlateDecode >>\nstream\n" + komprimiert
         + b"\nendstream"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    aus = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    pos = []
    for i, obj in enumerate(objekte, 1):
        pos.append(len(aus))
        aus += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(aus)
    aus += f"xref\n0 {len(objekte) + 1}\n".encode()
    aus += b"0000000000 65535 f \n"
    for p in pos:
        aus += f"{p:010d} 00000 n \n".encode()
    aus += (f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(aus)


def schreibe_pdf(teile, cfg: Konfig, seed: int, pfad: str, art: str):
    with open(pfad, "wb") as fh:
        fh.write(seite_als_pdf(baue_seite(teile, cfg, seed, art)))


# ---------------------------------------------------------------------------
# Ausgabe: PNG
# ---------------------------------------------------------------------------

def _finde_schrift(fett: bool):
    """Sucht eine TrueType-Schrift auf dem System (Windows/macOS/Linux)."""
    kandidaten = [
        "DejaVuSans-Bold.ttf" if fett else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf"
        % ("-Bold" if fett else ""),
        "/usr/share/fonts/dejavu/DejaVuSans%s.ttf"
        % ("-Bold" if fett else ""),
        r"C:\Windows\Fonts\%s" % ("arialbd.ttf" if fett else "arial.ttf"),
        r"C:\Windows\Fonts\%s" % ("segoeuib.ttf" if fett else "segoeui.ttf"),
        "/System/Library/Fonts/Supplemental/Arial%s.ttf"
        % (" Bold" if fett else ""),
        "/Library/Fonts/Arial%s.ttf" % (" Bold" if fett else ""),
    ]
    from PIL import ImageFont
    for name in kandidaten:
        try:
            return ImageFont.truetype(name, 40)
        except (OSError, IOError):
            continue
    return None


def _png_mit_pillow(seite: Seite, pfad: str, skala: float) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    ss = 2  # Überabtastung für weiche Kanten
    s = skala * ss
    bild = Image.new("RGB", (round(seite.breite * s), round(seite.hoehe * s)),
                     rgb255(rgb("#eef1f5")))
    d = ImageDraw.Draw(bild)
    basis = {False: _finde_schrift(False), True: _finde_schrift(True)}

    def schrift(gr, fett):
        f = basis[fett]
        if f is None:
            return ImageFont.load_default(), False
        return f.font_variant(size=max(1, round(gr * s))), True

    for e in seite.elemente:
        if e[0] == "rect":
            _, x, y, w, h, r, fuell, rnd, bre, gestr = e
            kasten = [x * s, y * s, (x + w) * s, (y + h) * s]
            if r > 0:
                d.rounded_rectangle(kasten, radius=r * s,
                                    fill=rgb255(fuell) if fuell else None,
                                    outline=rgb255(rnd) if rnd else None,
                                    width=max(1, round(bre * s)))
            else:
                d.rectangle(kasten, fill=rgb255(fuell) if fuell else None,
                            outline=rgb255(rnd) if rnd else None,
                            width=max(1, round(bre * s)))
        elif e[0] == "kreis":
            _, cx, cy, r, fuell, rnd, bre, gestr = e
            d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s],
                      fill=rgb255(fuell) if fuell else None,
                      outline=rgb255(rnd) if rnd else None,
                      width=max(1, round(bre * s)))
        else:
            _, x, y, txt, gr, farbe, anker, fett = e
            if not txt:
                continue
            f, echt = schrift(gr, fett)
            if echt:
                d.text((x * s, y * s), txt, font=f, fill=rgb255(farbe),
                       anchor={"start": "ls", "middle": "ms",
                               "end": "rs"}[anker])
            else:  # Notnagel: Standard-Bitmapschrift ohne Anker-Unterstützung
                b = text_breite(txt, gr, fett) * s
                dx = {"start": 0, "middle": -b / 2, "end": -b}[anker]
                d.text((x * s + dx, y * s - gr * s * 0.78), txt,
                       font=f, fill=rgb255(farbe))

    if ss > 1:
        bild = bild.resize((round(seite.breite * skala),
                            round(seite.hoehe * skala)), Image.LANCZOS)
    bild.save(pfad)
    return True


def rgb255(farbe):
    return tuple(round(k * 255) for k in farbe)


def _finde_browser():
    namen = ["chromium", "chromium-browser", "google-chrome", "chrome",
             "msedge", "microsoft-edge"]
    pfade = [
        "/opt/pw-browsers/chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    import shutil
    for n in namen:
        p = shutil.which(n)
        if p:
            return p
    for p in pfade:
        if os.path.exists(p):
            return p
    return None


def _png_mit_browser(teile, cfg, seed, pfad, art, breite_px) -> bool:
    """Notlösung ohne Pillow: HTML im Browser aufnehmen."""
    browser = _finde_browser()
    if browser is None:
        return False
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "seite.html")
        schreibe_html(teile, cfg, seed, html, art)
        hoehe_px = round(breite_px * 1.45)
        try:
            subprocess.run(
                [browser, "--headless", "--disable-gpu", "--no-sandbox",
                 "--hide-scrollbars", f"--screenshot={os.path.abspath(pfad)}",
                 f"--window-size={breite_px},{hoehe_px}",
                 "file://" + os.path.abspath(html)],
                check=True, timeout=90,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.SubprocessError, OSError):
            return False
    return os.path.exists(pfad)


def schreibe_png(teile, cfg: Konfig, seed: int, pfad: str, art: str,
                 dpi: int = 150) -> str:
    """Schreibt eine PNG-Datei. Rückgabe: der benutzte Weg."""
    seite = baue_seite(teile, cfg, seed, art)
    if _png_mit_pillow(seite, pfad, dpi / 72.0):
        return "Pillow"
    if _png_mit_browser(teile, cfg, seed, pfad, art,
                        round(seite.breite * dpi / 72.0)):
        return "Browser"
    raise RuntimeError(
        "PNG-Ausgabe nicht möglich: weder Pillow noch ein Chrome/Edge-Browser "
        "gefunden. Abhilfe: 'pip install pillow' (in PyCharm: rechts unten im "
        "Python-Interpreter-Menü) — die PDF-Ausgabe funktioniert immer.")


# ---------------------------------------------------------------------------
# Interaktive Abfrage
# ---------------------------------------------------------------------------

def frage(text, default, cast=str, pruefung=None, hinweis=None):
    while True:
        try:
            roh = input(f"{text} [{default}]: ").strip()
        except EOFError:
            roh = ""
        if not roh:
            wert = default
        else:
            try:
                wert = cast(roh)
            except (ValueError, TypeError):
                print("  Bitte eine gültige Eingabe machen.")
                continue
        if pruefung is not None and not pruefung(wert):
            print(f"  {hinweis or 'Wert außerhalb des erlaubten Bereichs.'}")
            continue
        return wert


def frage_janein(text, default: bool) -> bool:
    d = "j" if default else "n"
    while True:
        try:
            roh = input(f"{text} (j/n) [{d}]: ").strip().lower()
        except EOFError:
            roh = ""
        if not roh:
            return default
        if roh in ("j", "ja", "y", "yes"):
            return True
        if roh in ("n", "nein", "no"):
            return False
        print("  Bitte j oder n eingeben.")


def frage_formate(formate, basis):
    """Fragt die gewünschten Ausgabeformate ab. Aufgabe und Lösung werden
    immer als getrennte Dateien geschrieben."""
    print("\nAusgabeformate (Aufgabe und Lösung jeweils als eigene Datei):")
    gewaehlt = set()
    if frage_janein("  HTML (Bildschirm und Browser-Druck)?",
                    "html" in formate):
        gewaehlt.add("html")
    if frage_janein("  PDF (druckfertig, Vektor)?", "pdf" in formate):
        gewaehlt.add("pdf")
    if frage_janein("  PNG (Bilddatei)?", "png" in formate):
        gewaehlt.add("png")
    if frage_janein("  JSON (Rohdaten)?", "json" in formate):
        gewaehlt.add("json")
    if gewaehlt:
        basis = frage("Basisname der Dateien", basis, str,
                      lambda v: bool(str(v).strip()), "Bitte einen Namen "
                      "angeben.")
    return gewaehlt, str(basis).strip()


def interaktiv(cfg: Konfig) -> Konfig:
    print("\nMASTERMIND-KETTE — Generator")
    print("Einfach Enter drücken übernimmt jeweils den Vorschlag in [].\n")
    cfg.teile = frage("Wie viele verkettete Teile?", cfg.teile, int,
                      lambda v: 1 <= v <= 8, "1 bis 8 Teile.")
    cfg.laenge = frage("Codelänge (Stellen)", cfg.laenge, int,
                       lambda v: 3 <= v <= 8, "3 bis 8 Stellen.")
    cfg.farben = frage("Anzahl Farben/Symbole", cfg.farben, int,
                       lambda v: 3 <= v <= len(SYMBOLE),
                       f"3 bis {len(SYMBOLE)} Farben.")
    cfg.wiederholung = frage_janein("Dürfen sich Farben im Code wiederholen?",
                                    cfg.wiederholung)
    if not cfg.wiederholung and cfg.farben < cfg.laenge:
        print(f"  Ohne Wiederholung braucht es mindestens {cfg.laenge} "
              f"Farben — setze Farben auf {cfg.laenge}.")
        cfg.farben = cfg.laenge
    raum = (cfg.farben ** cfg.laenge if cfg.wiederholung
            else math.perm(cfg.farben, cfg.laenge))
    if raum > MAX_RAUM:
        print(f"  Achtung: {raum:,} mögliche Codes sind zu viele für die "
              f"Eindeutigkeitsprüfung (max. {MAX_RAUM:,}). Bitte Länge oder "
              f"Farbenzahl verringern.")
        return interaktiv(cfg)
    cfg.zeilen = frage("Hinweiszeilen pro Teil (wird bei Bedarf automatisch "
                       "erhöht)", cfg.zeilen, int,
                       lambda v: 3 <= v <= 20, "3 bis 20 Zeilen.")
    cfg.max_schwarz = frage("Max. SCHWARZE Stifte pro Zeile", cfg.max_schwarz,
                            int, lambda v: 0 <= v < cfg.laenge,
                            "Muss kleiner als die Codelänge sein.")
    cfg.max_treffer = frage("Max. Treffer (schwarz+weiß) pro Zeile",
                            cfg.max_treffer, int,
                            lambda v: cfg.max_schwarz <= v <= cfg.laenge,
                            "Mindestens so groß wie max. Schwarz.")
    print("\nWertungsmodus:  1 = klassisch schwarz/weiß")
    print("                2 = schlampig: einige Zeilen zeigen nur die "
          "Treffersumme (schwerer)")
    print("                3 = nur schwarze Stifte (braucht viele Zeilen)")
    m = frage("Modus", {"standard": 1, "schlampig": 2, "schwarz": 3}[cfg.modus],
              int, lambda v: v in (1, 2, 3), "1, 2 oder 3.")
    cfg.modus = {1: "standard", 2: "schlampig", 3: "schwarz"}[m]
    if cfg.teile > 1:
        cfg.kette = ("rueckwaerts" if frage_janein(
            "Kette rückwärts übertragen (Zusatz-Dreh)?",
            cfg.kette == "rueckwaerts") else "direkt")
    if cfg.teile >= 3:
        cfg.gabel = frage_janein(
            "Gabel-Kette (zwei Stränge, der letzte Teil braucht beide "
            "Lösungen)?", cfg.gabel)
    else:
        cfg.gabel = False
    cfg.luegner = frage_janein(
        "Lügner-Variante (genau eine Zeile pro Teil lügt)?", cfg.luegner)
    seed = frage("Zufalls-Seed (leer = zufällig)", cfg.seed or "", str)
    cfg.seed = int(seed) if str(seed).strip().isdigit() else None
    cfg.signatur = frage("Signatur unten rechts (leer = keine)",
                         cfg.signatur or "", str)
    return cfg


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Generator für verkettete Mastermind-Rätsel.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--auto", action="store_true",
                   help="keine interaktive Abfrage, nur Flag-Werte verwenden")
    p.add_argument("--teile", type=int, default=4)
    p.add_argument("--laenge", type=int, default=5)
    p.add_argument("--farben", type=int, default=7)
    p.add_argument("--zeilen", type=int, default=5)
    p.add_argument("--max-schwarz", type=int, default=1)
    p.add_argument("--max-treffer", type=int, default=2)
    p.add_argument("--ohne-wiederholung", action="store_true")
    p.add_argument("--modus", choices=("standard", "schlampig", "schwarz"),
                   default="standard")
    p.add_argument("--kette", choices=("direkt", "rueckwaerts"),
                   default="direkt")
    p.add_argument("--gabel", action="store_true",
                   help="Gabel-Kette: zwei unabhängige Stränge, der letzte "
                        "Teil braucht die Lösungen beider (ab 3 Teilen)")
    p.add_argument("--luegner", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--signatur", default="")
    p.add_argument("--formate", default="html",
                   help="Ausgabeformate, mit Komma getrennt: "
                        "html, pdf, png, json (oder 'alle')")
    p.add_argument("--basis", default="mastermind_kette",
                   help="Basisname der Ausgabedateien; Aufgabe und Lösung "
                        "werden getrennt geschrieben")
    p.add_argument("--dpi", type=int, default=150,
                   help="Auflösung der PNG-Ausgabe")
    return p.parse_args(argv)


def schreibe_dateien(teile, cfg: Konfig, seed: int, formate, basis: str,
                     dpi: int):
    """Schreibt alle gewünschten Formate; Aufgabe und Lösung getrennt."""
    erzeugt = []
    for kuerzel in ("html", "pdf", "png"):
        if kuerzel not in formate:
            continue
        for art, endung in (("aufgabe", "aufgabe"), ("loesung", "loesung")):
            pfad = f"{basis}_{endung}.{kuerzel}"
            if kuerzel == "html":
                schreibe_html(teile, cfg, seed, pfad, art)
                erzeugt.append(pfad)
            elif kuerzel == "pdf":
                schreibe_pdf(teile, cfg, seed, pfad, art)
                erzeugt.append(pfad)
            else:
                try:
                    weg = schreibe_png(teile, cfg, seed, pfad, art, dpi)
                    erzeugt.append(f"{pfad}  (über {weg})")
                except RuntimeError as fehler:
                    print(f"\n{fehler}", file=sys.stderr)
                    break
    if "json" in formate:
        pfad = f"{basis}.json"
        schreibe_json(teile, cfg, seed, pfad)
        erzeugt.append(pfad)
    return erzeugt


def main(argv=None):
    args = parse_args(argv)
    cfg = Konfig(teile=args.teile, laenge=args.laenge, farben=args.farben,
                 zeilen=args.zeilen, max_schwarz=args.max_schwarz,
                 max_treffer=args.max_treffer,
                 wiederholung=not args.ohne_wiederholung,
                 modus=args.modus, kette=args.kette, gabel=args.gabel,
                 luegner=args.luegner, seed=args.seed, signatur=args.signatur)
    formate = {f.strip().lower() for f in args.formate.split(",") if f.strip()}
    if "alle" in formate:
        formate = {"html", "pdf", "png", "json"}
    basis = args.basis
    if not args.auto:
        cfg = interaktiv(cfg)
        formate, basis = frage_formate(formate, basis)
    unbekannt = formate - {"html", "pdf", "png", "json"}
    if unbekannt:
        sys.exit(f"Unbekanntes Format: {', '.join(sorted(unbekannt))}")

    if not cfg.wiederholung and cfg.farben < cfg.laenge:
        sys.exit("Ohne Wiederholung braucht es mindestens so viele Farben "
                 "wie Stellen.")
    if cfg.gabel and cfg.teile < 3:
        sys.exit("Die Gabel-Kette braucht mindestens 3 Teile "
                 "(zwei Stränge plus Gabelpunkt).")
    raum = (cfg.farben ** cfg.laenge if cfg.wiederholung
            else math.perm(cfg.farben, cfg.laenge))
    if raum > MAX_RAUM:
        sys.exit(f"{raum:,} mögliche Codes sind zu viele für die "
                 f"Eindeutigkeitsprüfung (max. {MAX_RAUM:,}). Bitte Länge "
                 f"oder Farbenzahl verringern.")

    seed = cfg.seed if cfg.seed is not None else random.randrange(2 ** 32)
    rng = random.Random(seed)
    print(f"\nErzeuge {cfg.teile} Teil(e) — Suchraum {raum:,} Codes, "
          f"Seed {seed} ...", file=sys.stderr)
    teile = generiere_puzzle(cfg, rng)

    print("Prüfe Garantien per vollständiger Enumeration ...", file=sys.stderr)
    pruefe_puzzle(teile, cfg)
    print("  ✓ Eindeutigkeit, Minimalität und Kettenzwang bestätigt.\n",
          file=sys.stderr)

    drucke_konsole(teile, cfg, seed)
    erzeugt = schreibe_dateien(teile, cfg, seed, formate, basis, args.dpi)
    if erzeugt:
        print("\nGeschriebene Dateien:")
        for name in erzeugt:
            print(f"  {name}")


if __name__ == "__main__":
    main()
