#!/bin/sh
# Rebuild every derived file, ending with map/data.json, from the inputs in raw/.
set -e
cd "$(dirname "$0")"
python3 build.py
python3 alliances.py
python3 apply_alliances.py
python3 build_map.py
