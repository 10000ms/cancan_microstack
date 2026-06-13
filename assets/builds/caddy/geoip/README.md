# GeoIP database placeholder

This folder must contain a GeoLite2 `.mmdb` file so both Caddy and the ops BFF IP locator can enrich requests during
local development. Cancan cannot redistribute those databases—create a free MaxMind account, download GeoLite2-City,
and place `GeoLite2-City.mmdb` here before starting the stack.
