"""Fetch the daily forecast and find the first cold streak."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import requests

API = "https://api.open-meteo.com/v1/forecast"


@dataclass
class Day:
    date: str
    temp: Optional[float]


@dataclass
class Streak:
    start: str
    end: str
    days: List[Day]
    open_ended: bool  # streak runs to the end of the forecast window


def fetch(lat: float, lon: float, metric: str = "mean", days: int = 10, timeout: float = 20) -> List[Day]:
    var = f"temperature_2m_{metric}"
    r = requests.get(API, params={
        "latitude": lat, "longitude": lon, "daily": var,
        "timezone": "auto", "forecast_days": days,
    }, timeout=timeout)
    r.raise_for_status()
    daily = r.json()["daily"]
    return [Day(d, t) for d, t in zip(daily["time"], daily[var])]


def find_streak(days: Sequence[Day], threshold: float = 7.0, length: int = 3) -> Optional[Streak]:
    """First run of >= `length` consecutive days strictly below `threshold`.

    Missing values (None) break a streak.
    """
    if length < 1:
        raise ValueError("length must be >= 1")
    run: List[Day] = []
    for i, d in enumerate(days):
        if d.temp is not None and d.temp < threshold:
            run.append(d)
            continue
        if len(run) >= length:
            return Streak(run[0].date, run[-1].date, run, open_ended=False)
        run = []
    if len(run) >= length:
        return Streak(run[0].date, run[-1].date, run, open_ended=True)
    return None
