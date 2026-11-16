# HSR relic scoring

This directory contains the offline relic selector migrated from the in progress RelicForge work in `D:\March7thAssistant_dev`.

The package reads Reliquary JSON exports and evaluates relics against character build profiles. It does not capture game data, send input, enhance relics, lock items, discard items, or claim that a result is safe for unattended execution.

## Data

- `data/hsr/relic_database/` stores the pinned relic and character catalogs.
- `game_packs/hsr/relic_scoring/` stores the generated Fribbels profile configuration and the local override file.
- `manifest.json` records upstream revisions and hashes for the migrated dataset.

Use `relic_scoring.overrides.yaml` for local profile policy. Treat generated YAML and database files as replaceable upstream data; refreshes must preserve the override file and re-run the offline tests.

The migrated implementation is currently a library used by offline analysis. Real game observation and input remain outside this package and require a separately verified backend.
