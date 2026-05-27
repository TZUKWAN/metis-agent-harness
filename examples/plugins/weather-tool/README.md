# Weather Tool Plugin

A Metis plugin that provides a `get_weather` tool for fetching current weather conditions.

## Usage

Install the plugin into your Metis plugins directory, then the agent can use:

```
get_weather(city="Beijing")
```

## Data Source

Uses [wttr.in](https://wttr.in) — a free, no-API-key weather service.

## Permissions

Requires `network` permission level.
