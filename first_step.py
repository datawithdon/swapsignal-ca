"""The 30-line first step: print the first date a 3-day sub-7 °C streak starts.

Usage: python first_step.py "H2X 1Y4"     (stdlib only, no installs)
"""
import json, sys, urllib.parse, urllib.request

def get(url, **params):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "SwapSignal/0.1"})
    return json.load(urllib.request.urlopen(req, timeout=20))

postal = (sys.argv[1] if len(sys.argv) > 1 else "H2X 1Y4").upper()
hit = get("https://nominatim.openstreetmap.org/search", postalcode=postal,
          country="ca", format="json", limit=1)
if not hit:
    sys.exit(f"Postal code {postal} not found (use all 6 characters).")
lat, lon = hit[0]["lat"], hit[0]["lon"]
daily = get("https://api.open-meteo.com/v1/forecast", latitude=lat, longitude=lon,
            daily="temperature_2m_mean", timezone="auto", forecast_days=10)["daily"]

run = []
for day, temp in zip(daily["time"], daily["temperature_2m_mean"]):
    run = run + [day] if temp is not None and temp < 7 else []
    if len(run) == 3:
        print(f"7 °C streak starts {run[0]}. Book your tire swap now.")
        break
else:
    print("No 3-day streak under 7 °C in the next 10 days.")
