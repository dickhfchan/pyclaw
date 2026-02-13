---
name: weather
description: "Get current weather and forecasts (no API key required)."
metadata:
  requires:
    bins: ["curl"]
---

# Weather

Get current weather information for any city using the wttr.in service.

## Usage

To get a short weather summary for a city:

```bash
curl -s "wttr.in/{city}?format=3"
```

To get a detailed forecast:

```bash
curl -s "wttr.in/{city}?format=v2"
```

Replace `{city}` with the desired city name (e.g., `London`, `New+York`, `Tokyo`).

## Examples

- Quick check: `curl -s "wttr.in/London?format=3"`
- Moon phase: `curl -s "wttr.in/Moon"`
