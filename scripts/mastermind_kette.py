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
import random
import sys
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
    tipp: tuple          # der (transformierte) Lösungscode des Vorgängers
    schwarz: int
    weiss: int


@dataclass
class Teil:
    nummer: int
    code: tuple
    zeilen: list
    kette: Optional[Kettenzeile]
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


def generiere_teil(nummer, zeilen_n, vorgaenger, alle, cfg, rng):
    f = cfg.farben
    for _ in range(cfg.versuche):
        code = rng.choice(alle)
        kette = None
        basis = alle
        if vorgaenger is not None:
            kt = kettentipp(vorgaenger, cfg)
            if kt == code:
                continue
            ks, kw = bewertung(kt, code, f)
            if not schwach(ks, kw, cfg):
                continue
            basis = filtere(alle, kt, "sw", (ks, kw), f)
            # Die Kettenzeile darf den Suchraum nicht schon fast leeren.
            if len(basis) < 12 * zeilen_n:
                continue
            kette = Kettenzeile(kt, ks, kw)

        # Pool aller "schwachen" Tipps relativ zum Geheimcode.
        pool = [g for g in alle
                if g != code
                and (kette is None or g != kette.tipp)
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
                continue

        # Kettenzwang: ohne Kettenzeile muss der Teil mehrdeutig sein.
        if kette is not None:
            if cfg.luegner:
                ohne = luegner_kandidaten(zeilen, alle, f)
            else:
                ohne = loesungsmenge(zeilen, alle, f)
            if len(ohne) < 2:
                continue

        rng.shuffle(zeilen)
        teil = Teil(nummer, code, zeilen, kette)
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
        teile = []
        vorher = None
        for n in range(1, cfg.teile + 1):
            teil = generiere_teil(n, zeilen_n, vorher, alle, cfg, rng)
            if teil is None:
                teile = None
                break
            teile.append(teil)
            vorher = teil.code
            print(f"  Teil {n} erzeugt "
                  f"(Schwierigkeit: {teil.schwierigkeit}) ...",
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
    vorher = None
    for teil in teile:
        basis = alle
        if teil.kette is not None:
            assert teil.kette.tipp == kettentipp(vorher, cfg), \
                f"Teil {teil.nummer}: Kettenzeile passt nicht zum Vorgänger."
            assert bewertung(teil.kette.tipp, teil.code, f) == \
                (teil.kette.schwarz, teil.kette.weiss), \
                f"Teil {teil.nummer}: Kettenwertung falsch."
            basis = filtere(alle, teil.kette.tipp, "sw",
                            (teil.kette.schwarz, teil.kette.weiss), f)
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
        if teil.kette is not None:
            if cfg.luegner:
                ohne = luegner_kandidaten(teil.zeilen, alle, f)
            else:
                ohne = loesungsmenge(teil.zeilen, alle, f)
            assert len(ohne) >= 2, \
                f"Teil {teil.nummer}: auch ohne Kettenzeile lösbar!"
        vorher = teil.code


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
        if teil.kette is not None:
            richtung = ("rückwärts eingetragener "
                        if cfg.kette == "rueckwaerts" else "")
            b.append(f"  K  {'? ' * cfg.laenge} <- {richtung}Code aus "
                     f"Teil {teil.nummer - 1}   "
                     f"{wertung_text('sw', (teil.kette.schwarz, teil.kette.weiss))}")
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
        if cfg.kette == "rueckwaerts":
            regeln.append("Löse Teil 1. Übertrage danach jeden Lösungscode "
                          "RÜCKWÄRTS in die markierte Kettenzeile des "
                          "nächsten Teils.")
        else:
            regeln.append("Löse Teil 1. Übertrage danach jeden Lösungscode in "
                          "die markierte Kettenzeile des nächsten Teils.")
        regeln.append("Die Schwarz/Weiß-Wertung der Kettenzeile ist bereits "
                      "gegeben. Ohne sie ist der Teil nicht eindeutig lösbar.")
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


def schreibe_html(teile, cfg: Konfig, seed: int, pfad: str):
    modus_txt = {"standard": "Schwarz/Weiß-Wertung",
                 "schlampig": "teils nur Treffersumme",
                 "schwarz": "nur schwarze Stifte"}[cfg.modus]
    unter = (f"{cfg.laenge} Stellen · {cfg.farben} Farben · "
             f"{'Wiederholungen erlaubt' if cfg.wiederholung else 'ohne Wiederholung'}"
             f" · max. {cfg.max_schwarz} schwarz / {cfg.max_treffer} Treffer je Zeile"
             f" · {modus_txt}")
    if cfg.luegner:
        unter += " · Lügner-Variante"
    if cfg.kette == "rueckwaerts" and cfg.teile > 1:
        unter += " · Rückwärts-Kette"
    schwierig = max((t.schwierigkeit for t in teile),
                    key=lambda s: ["leicht", "mittel", "schwer"].index(s))
    wert_kopf = {"standard": "schwarz / weiß", "schlampig": "Wertung",
                 "schwarz": "schwarz"}[cfg.modus]

    karten = []
    for teil in teile:
        zeilen_html = []
        if teil.kette is not None:
            frage = "".join('<span class="peg ghost">?</span>'
                            for _ in range(cfg.laenge))
            richtung = " (rückwärts!)" if cfg.kette == "rueckwaerts" else ""
            fb = html_wertung("sw", (teil.kette.schwarz, teil.kette.weiss))
            zeilen_html.append(
                f'<div class="row chain"><span class="idx">K</span>'
                f'<span class="chainlabel">Code aus Teil {teil.nummer - 1}'
                f'{richtung}</span>{frage}<span class="fb">{fb}</span></div>')
        for i, z in enumerate(teil.zeilen, 1):
            pegs = "".join(html_kreis(x) for x in z.tipp)
            zeilen_html.append(
                f'<div class="row"><span class="idx">{i}</span>{pegs}'
                f'<span class="fb">{html_wertung(z.art, z.key)}</span></div>')
        karten.append(
            f'<section class="card"><header><h2>TEIL {teil.nummer}</h2>'
            f'<span class="fbhead">{wert_kopf}</span></header>'
            + "".join(zeilen_html) + "</section>")

    regeln = "".join(f"<li>{html_mod.escape(r)}</li>" for r in regel_zeilen(cfg))
    legende = " · ".join(f"<b>{s}</b>&nbsp;=&nbsp;{FARBEN[s][0]}"
                         for s in SYMBOLE[:cfg.farben])
    loesungen = []
    for teil in teile:
        extra = ""
        if cfg.luegner:
            li = next(i for i, z in enumerate(teil.zeilen, 1) if z.luege)
            lz = next(z for z in teil.zeilen if z.luege)
            wahr = wertung_text(lz.art, projektion(lz.art, lz.wahr_schwarz,
                                                   lz.wahr_weiss))
            extra = (f'Lügenzeile: {li} &nbsp;·&nbsp; wahre Wertung: '
                     f'{html_mod.escape(wahr)}')
        pegs = "".join(html_kreis(x) for x in teil.code)
        loesungen.append(f'<div class="row"><span class="idx">T{teil.nummer}'
                         f'</span>{pegs}<span class="fb">{extra}</span></div>')

    signatur = (f'<div class="sig">{html_mod.escape(cfg.signatur)}</div>'
                if cfg.signatur else "")

    doc = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mastermind-Kette</title>
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
  details {{ max-width:1200px; margin:22px auto 0; }}
  summary {{ cursor:pointer; font-weight:700; color:var(--chainline); }}
  .sig {{ text-align:right; max-width:1200px; margin:18px auto 0;
          color:var(--muted); }}
  @media print {{
    body {{ background:#fff; padding:10px; }}
    details {{ display:none; }}
  }}
</style></head><body>
<h1>MASTERMIND-KETTE</h1>
<div class="sub">{unter} · Level (heuristisch): {schwierig} · Seed {seed}</div>
<div class="grid">{''.join(karten)}</div>
<div class="rules"><ul>{regeln}</ul></div>
<div class="legende">Farben: {legende}</div>
<details><summary>Lösungen anzeigen</summary>
<div class="card" style="margin-top:10px">{''.join(loesungen)}</div></details>
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
            "kette": None if t.kette is None else {
                "tipp": code_str(t.kette.tipp),
                "schwarz": t.kette.schwarz, "weiss": t.kette.weiss},
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
    p.add_argument("--luegner", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--signatur", default="")
    p.add_argument("--html", default="mastermind_kette.html",
                   help="HTML-Ausgabedatei ('-' = keine)")
    p.add_argument("--json", default=None, help="JSON-Ausgabedatei")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cfg = Konfig(teile=args.teile, laenge=args.laenge, farben=args.farben,
                 zeilen=args.zeilen, max_schwarz=args.max_schwarz,
                 max_treffer=args.max_treffer,
                 wiederholung=not args.ohne_wiederholung,
                 modus=args.modus, kette=args.kette, luegner=args.luegner,
                 seed=args.seed, signatur=args.signatur)
    if not args.auto:
        cfg = interaktiv(cfg)

    if not cfg.wiederholung and cfg.farben < cfg.laenge:
        sys.exit("Ohne Wiederholung braucht es mindestens so viele Farben "
                 "wie Stellen.")
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
    if args.html and args.html != "-":
        schreibe_html(teile, cfg, seed, args.html)
        print(f"\nHTML geschrieben: {args.html} (druckfertig, Lösungen "
              f"eingeklappt)")
    if args.json:
        schreibe_json(teile, cfg, seed, args.json)
        print(f"JSON geschrieben: {args.json}")


if __name__ == "__main__":
    main()
