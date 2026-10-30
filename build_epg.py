"""Builds epg.json, the TV guide of the Bbox remote apps, from XML TV Fr (https://xmltvfr.fr).

Runs once a day (GitHub Actions, see .github/workflows/epg.yml): one download of the
compressed French guide, filtered to the Bbox channels of channels_map.json and to a
short time window, so the apps fetch a small JSON instead of hitting xmltvfr.fr.

Usage: python build_epg.py [--xml local.xml|local.xz] [--out site/epg.json]
"""
import argparse
import json
import lzma
import os
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

SOURCE_URL = "https://xmltvfr.fr/xmltv/xmltv_fr.xz"
HERE = os.path.dirname(os.path.abspath(__file__))
# Programmes kept: those still running PAST_HOURS ago up to those starting within FUTURE_HOURS.
# 4 days ahead (xmltvfr.fr publishes 5) keeps the guide usable through a few days of failed runs.
PAST_HOURS = 3
FUTURE_HOURS = 96


# Genre families shown as filters in the apps. XMLTV categories are free text (650+ values,
# "Série TV" / "Serie" / "Series"...), so they are matched by keywords on the accent-free,
# lower-case category, sub-category first. First matching rule wins.
GENRE_RULES = [
    ("jeunesse", ("animation", "anime", "jeunesse", "enfant", "dessin")),
    ("mag", ("magazine du cinema", "mag cinema")),
    ("doc", ("documentaire", "docu", "doc ")),
    ("telefilm", ("telefilm",)),
    ("serie", ("serie", "feuilleton", "sitcom", "saga", "novela")),
    ("film", ("film", "cinema", "court metrage", "western")),
    ("sport", ("sport", "football", "rugby", "tennis", "cyclisme", "automobilisme", "basket", "handball",
               "golf", "boxe", "athletisme", "equitation", "hippisme", "voile", "moto", "ski", "natation",
               "catch", "combat", "billard", "flechettes", "patinage", "hockey", "padel", "petanque",
               "base ball", "surf", "volley", "triathlon", "fitness", "aerobic", "escalade", "poker")),
    ("info", ("journal", "actualite", "info", "news", "meteo", "politique", "debat", "economie", "bourse",
              "interview")),
    ("doc", ("doc", "decouverte", "reportage", "histoire", "nature", "animalier", "science", "voyage",
             "investigation", "enquete")),
    ("musique", ("musique", "musical", "clip", "concert", "opera", "ballet", "danse", "jazz", "classique")),
    ("divert", ("divertissement", "divers", "jeu", "realite", "humour", "spectacle", "variete", "talk",
                "show", "theatre", "cirque")),
    ("mag", ("magazine", "mag ", "emission")),
    # Fiction genres without "film"/"série" are mostly films on the cinema channels.
    ("film", ("comedie", "drame", "melodrame", "fiction", "thriller")),
]


def plain(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(text.replace("-", " ").replace("'", " ").split())


def genre_family(categories):
    """Genre family code of a programme from its XMLTV categories, or None."""
    for category in reversed(categories):  # the sub-category is more precise
        text = plain(category)
        for family, keywords in GENRE_RULES:
            if any(k in text for k in keywords):
                return family
    return None


def parse_time(value):
    # XMLTV: "20261030210500 +0100"
    return int(datetime.strptime(value, "%Y%m%d%H%M%S %z").timestamp())


def open_source(path):
    if path is None:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "bbox-remote-epg/1.0 (daily build)"})
        data = urllib.request.urlopen(req, timeout=120).read()
        return lzma.decompress(data)
    with open(path, "rb") as f:
        data = f.read()
    return lzma.decompress(data) if path.endswith(".xz") else data


def build(xml_bytes, channel_map, now):
    wanted = set(channel_map.values())
    lo, hi = now - PAST_HOURS * 3600, now + FUTURE_HOURS * 3600
    programmes = {}
    root = ET.fromstring(xml_bytes)
    for p in root.iter("programme"):
        cid = p.get("channel")
        if cid not in wanted:
            continue
        try:
            start, stop = parse_time(p.get("start")), parse_time(p.get("stop"))
        except (TypeError, ValueError):
            continue
        if stop <= lo or start >= hi or stop <= start:
            continue
        title = (p.findtext("title") or "").strip()
        if not title:
            continue
        subtitle = (p.findtext("sub-title") or "").strip() or None
        categories = [c.text.strip() for c in p.findall("category") if c.text and c.text.strip()]
        category = categories[-1] if categories else None
        programmes.setdefault(cid, []).append(
            [start, stop, title, subtitle, category, genre_family(categories)])
    for items in programmes.values():
        items.sort(key=lambda it: it[0])
    return {
        "v": 1,
        "generated": now,
        "source": "XML TV Fr (xmltvfr.fr)",
        # Bbox channel number -> guide id; several numbers may share one id (TF1 and TF1 4K).
        "map": {k: v for k, v in channel_map.items() if v in programmes},
        # Guide id -> [start, stop, title, subtitle, category, genre family], epoch seconds,
        # sorted by start. Families: see GENRE_RULES (null = unclassified).
        "programmes": programmes,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", help="local XMLTV file (.xml or .xz) instead of downloading")
    ap.add_argument("--out", default=os.path.join(HERE, "site", "epg.json"))
    args = ap.parse_args()

    with open(os.path.join(HERE, "channels_map.json"), encoding="utf-8") as f:
        channel_map = json.load(f)
    epg = build(open_source(args.xml), channel_map, int(time.time()))
    if len(epg["programmes"]) < 20:
        sys.exit(f"only {len(epg['programmes'])} channels with programmes: source looks broken, epg.json kept")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(epg, f, ensure_ascii=False, separators=(",", ":"))
    count = sum(len(v) for v in epg["programmes"].values())
    print(f"{len(epg['map'])} channels, {len(epg['programmes'])} guides, {count} programmes, "
          f"{os.path.getsize(args.out) // 1024} KB -> {args.out}")


if __name__ == "__main__":
    main()
