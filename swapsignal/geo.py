"""Turn a postal code, place name or "lat,lon" into coordinates."""
from __future__ import annotations

import re
from typing import Tuple

import requests

UA = {"User-Agent": "SwapSignal/0.1 (personal winter-tire alert)"}
POSTAL_RE = re.compile(r"^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$")
LATLON_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_latlon(text: str):
    m = LATLON_RE.match(text)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"coordinates out of range: {text}")
    return lat, lon


def normalize_postal(text: str) -> str:
    t = re.sub(r"\s+", "", text).upper()
    return f"{t[:3]} {t[3:]}"


def geocode(location: str, timeout: float = 15) -> Tuple[float, float, str]:
    """Returns (lat, lon, label)."""
    location = location.strip()
    if not location:
        raise ValueError("no location set: use SWAP_LOCATION (postal code, city, or 'lat,lon')")
    ll = parse_latlon(location)
    if ll:
        return ll[0], ll[1], location
    if POSTAL_RE.match(location):
        # Open-Meteo's geocoder has no Canadian postal codes; OSM Nominatim does (full 6 chars).
        pc = normalize_postal(location)
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"postalcode": pc, "country": "ca", "format": "json", "limit": 1},
            headers=UA, timeout=timeout,
        )
        r.raise_for_status()
        hits = r.json()
        if hits:
            return float(hits[0]["lat"]), float(hits[0]["lon"]), pc
        raise ValueError(f"postal code {pc} not found; try a city name or 'lat,lon'")
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "countryCode": "CA"},
        headers=UA, timeout=timeout,
    )
    r.raise_for_status()
    hits = r.json().get("results") or []
    if not hits:
        raise ValueError(f"place '{location}' not found in Canada")
    h = hits[0]
    return h["latitude"], h["longitude"], f"{h['name']}, {h.get('admin1', '')}".rstrip(", ")
