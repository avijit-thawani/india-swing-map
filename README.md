# NDA vs others: Lok Sabha swing map, 2019 to 2024

An interactive map of India's 543 Lok Sabha seats showing the NDA's lead over
its nearest rival in 2019 and 2024, and how far each seat moved between them.
The map, a histogram and a scatter plot are linked: hovering or selecting in
one highlights the same seats in the others.

## Run it

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory map
```

Then open http://127.0.0.1:8765/. The page is plain HTML and JavaScript with no
dependencies; it only needs to be served over http so it can load `data.json`.

## Deploy

`netlify.toml` publishes the `map/` folder with no build step. `map/data.json`
is committed, so the site works as soon as the repository is connected.

## Rebuild the data

```sh
./build_all.sh
```

Needs only Python 3 (standard library). The steps, in order:

| Script | Reads | Writes |
| --- | --- | --- |
| `build.py` | constituency summaries in `raw/` | `seats_2004_2024.csv`: one row per seat per election, 2004 to 2024 |
| `alliances.py` | `raw/alliances/*.wiki` | `alliance_candidates.csv`: each alliance's candidate in each seat |
| `apply_alliances.py` | the two files above | `alliance_parties.csv`, `seats_with_alliances.csv`: winner and runner-up tagged by alliance |
| `build_map.py` | the tagged seats, candidate results, seat shapes | `map/data.json` |

Each script prints its own checks, such as seat totals per alliance against
Wikipedia's and seats it could not match.

## Definitions

- **NDA lead**: the NDA candidate's share of valid votes minus the best other
  candidate's share, in percentage points.
- **Change since 2019**: the 2024 lead minus the 2019 lead.
- The NDA is taken as it stood at each election, so a party changing sides
  moves a seat a long way. Andhra Pradesh moves towards the NDA largely because
  the TDP joined it in 2024.

## Known limits

- Assam and Jammu and Kashmir were redrawn after 2019. The results file lists
  their 2019 results under 2024 seat names, so their change is not like for
  like. All shapes are 2019 boundaries.
- Surat was won unopposed in 2024 and has no 2024 lead.
- Four seats have no NDA candidate in the data (Rajampet in 2019; Baramulla,
  Srinagar and Anantnag in 2024); their NDA share counts as zero.
- Alliance totals differ slightly from Wikipedia's headline figures for 2004,
  2009 and 2019, mostly over which parties count as members. 2014 and 2024
  match.
- Indore 2024: the results file names the BSP candidate as runner-up, not NOTA.

## Sources and licences

- **Results**: Election Commission of India statistical reports, as published
  by [India Data Portal](https://ckandev.indiadataportal.com/dataset/loksabha-general-election-results)
  under the Open Data Commons Attribution License.
- **Alliances**: Wikipedia's candidate lists and results pages for each
  election (wikitext copies in `raw/`), CC BY-SA 4.0.
- **Seat shapes**: [DataMeet](https://github.com/datameet/maps/tree/master/parliamentary-constituencies)
  simplified 2019 parliamentary constituencies by Arun Ganesh, CC0.
