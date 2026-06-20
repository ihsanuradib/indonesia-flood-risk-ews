#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_URL = os.getenv("BBWS_API_URL", "https://hidrologi.bbws-bsolo.net/api/last_data")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "stations.geojson")

# Network tuning (overridable via env vars)
TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "60"))
RETRIES = int(os.getenv("FETCH_RETRIES", "4"))
BACKOFF = int(os.getenv("FETCH_BACKOFF", "5"))

# If true (default), a failed fetch keeps the existing snapshot and exits 0.
# Set ALLOW_STALE=0 to make the script fail hard instead.
ALLOW_STALE = os.getenv("ALLOW_STALE", "1") != "0"

LEVELS = {0: ("Aman", "#2ecc71"), 1: ("Waspada", "#f1c40f"),
          2: ("Siaga", "#e67e22"), 3: ("Awas", "#e74c3c")}


def fetch_json(url, timeout=TIMEOUT, retries=RETRIES, backoff=BACKOFF):
    """Fetch and parse JSON with retries + exponential backoff.

    Returns the parsed JSON, or None if all attempts fail.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "flood-ews-bot/1.0"})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < retries:
                wait = backoff * (2 ** (attempt - 1))
                print(f"[attempt {attempt}/{retries}] fetch failed: {e}. "
                      f"Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"[attempt {attempt}/{retries}] fetch failed: {e}. "
                      f"Giving up.", file=sys.stderr)
    print(f"WARNING: could not reach {url} after {retries} attempts: {last_err}",
          file=sys.stderr)
    return None


def to_float(v):
    try:
        s = str(v).strip()
        if s in ("", "null", "-", "None"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_latlng(s):
    try:
        a, b = str(s).split(",")
        lat, lon = float(a.strip()), float(b.strip())
        if -12 < lat < 7 and 94 < lon < 142:
            return lat, lon
    except Exception:
        return None
    return None


def classify_tma(wse, h, k, m):
    if wse is None:
        return 0
    if m is not None and wse >= m:
        return 3
    if k is not None and wse >= k:
        return 2
    if h is not None and wse >= h:
        return 1
    return 0


def classify_rain(mm):
    if mm is None:
        return 0
    return 3 if mm >= 20 else 2 if mm >= 10 else 1 if mm >= 5 else 0


def main():
    raw = fetch_json(API_URL)

    # --- Graceful degradation: keep the last good snapshot if fetch failed ---
    if raw is None:
        if ALLOW_STALE and os.path.exists(OUT):
            print("Fetch failed but a previous snapshot exists -> keeping it "
                  "and exiting 0 (no change).")
            return
        if ALLOW_STALE:
            print("Fetch failed and no previous snapshot exists -> exiting 0 "
                  "without writing.")
            return
        raise SystemExit(f"ERROR: could not reach {API_URL} (ALLOW_STALE=0)")

    features = []
    for d in raw:
        coords = parse_latlng(d.get("latlng"))
        if not coords:
            continue
        lat, lon = coords
        tipe = (d.get("tipe") or "").strip()
        h = to_float(d.get("level_siaga_hijau_meter"))
        k = to_float(d.get("level_siaga_kuning_meter"))
        m = to_float(d.get("level_siaga_merah_meter"))
        wse = None
        if tipe == "TMA":
            ec = to_float(d.get("elevasi_cm"))
            wse = ec / 100.0 if ec is not None else None
            level = classify_tma(wse, h, k, m)
        else:
            level = classify_rain(to_float(d.get("curah_hujan_mm")))
        label, color = LEVELS[level]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "pos_id": str(d.get("pos_id")), "name": d.get("nama_pos") or "Tanpa Nama",
                "code": d.get("kode_pos"), "instansi": d.get("instansi"),
                "tipe": tipe or "Lainnya", "wilayah": d.get("wilayah"),
                "das": None if str(d.get("das")).lower() == "null" else d.get("das"),
                "tma_lokal_cm": to_float(d.get("tma_lokal_cm")), "water_surface_elev_m": wse,
                "debit_m3s": to_float(d.get("debit_m3perdetik")),
                "siaga_hijau_m": h, "siaga_kuning_m": k, "siaga_merah_m": m,
                "curah_hujan_mm": to_float(d.get("curah_hujan_mm")),
                "temperature": to_float(d.get("temperature")), "humidity": to_float(d.get("humidity")),
                "siaga_level": level, "siaga_label": label, "siaga_color": color,
                "last_sampling": d.get("last_sampling"), "battery": to_float(d.get("battery")),
                "signal_quality": d.get("signal_quality"),
            },
        })

    fc = {"type": "FeatureCollection",
          "generated_at": datetime.now(timezone.utc).isoformat(),
          "count": len(features), "features": features}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    print(f"Wrote {len(features)} stations -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
