"""Parse Wikipedia's seat-by-seat alliance candidate lists (NDA, UPA, INDIA) for
the 2004-2024 Lok Sabha elections into one table.

Run: python3 alliances.py
Writes: alliance_candidates.csv (one row per alliance candidate per seat)
"""

import csv
import re
from collections import Counter

RAW = "raw/alliances/"
FILES = [
    (2004, "NDA", "nda_2004.wiki"),
    (2009, "NDA", "nda_2009.wiki"),
    (2009, "UPA", "upa_2009.wiki"),
    (2014, "NDA", "nda_2014.wiki"),
    (2014, "UPA", "upa_2014.wiki"),
    (2019, "NDA", "nda_2019.wiki"),
    (2019, "UPA", "upa_2019.wiki"),
    (2024, "NDA", "nda_2024.wiki"),
    (2024, "INDIA", "india_2024.wiki"),
]

SEAT = re.compile(r"\[\[([^\]|]*?)\s*\(?Lok Sabha constituency\)?(?:\|([^\]]*))?\]\]")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
PARTY_TEMPLATE = re.compile(r"\{\{\s*(?:full )?party (?:name with )?colou?r(?: cell)?\s*\|\s*([^}|]+)", re.I)
HEX_CELL = re.compile(r"bgcolor\s*=\s*\"?#[0-9a-fA-F]{3,6}\"?\s*\|[ \t]*(?:\n\|)?([^\n]*)")
MONTH = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b")


def cell_names(cell):
    """Every name a table cell could be giving: link targets, link labels, plain text."""
    names = [m.group(1).strip() for m in LINK.finditer(cell)]
    names += [m.group(1).strip() for m in PARTY_TEMPLATE.finditer(cell)]
    plain = LINK.sub("", cell)
    plain = re.sub(r"\{\{.*?\}\}", "", plain)
    plain = re.sub(r"^[^|]*=[^|]*\|", "", plain).strip(" |\n\t")
    if plain:
        names.append(plain)
    return names


def party_vocabulary(texts):
    """Party names used anywhere in the lists: colour-template arguments, plus
    whatever sits in the cell after a plain hex colour swatch."""
    vocab = set()
    for text in texts:
        vocab.update(m.group(1).strip() for m in PARTY_TEMPLATE.finditer(text))
        for m in HEX_CELL.finditer(text):
            for name in cell_names(m.group(1).split("||")[0]):
                if not MONTH.search(name) and not name.isdigit():
                    vocab.add(name)
    vocab -= {"", "None", "SC", "ST", "TBD"}
    return vocab


def strip_refs(text):
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref.*?</ref>", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def result_of(row):
    low = row.lower()
    if "{{won}}" in low or "{{yes2|won" in low or re.search(r"\|\s*won\b", low):
        return "won"
    if "{{lost}}" in low or "{{no2|lost" in low or re.search(r"\|\s*lost\b", low):
        return "lost"
    return ""


def parse(year, alliance, fname, vocab):
    text = strip_refs(open(RAW + fname, encoding="utf-8").read())
    rows, state = [], ""
    # Walk the page in order so each table row picks up the state heading above it.
    for chunk in re.split(r"\n(?==)", text):
        head = re.match(r"=+\s*(.*?)\s*=+\s*\n", chunk)
        if head:
            title = LINK.sub(lambda m: m.group(2) or m.group(1), head.group(1))
            state = re.sub(r"\s*\(\d+\)\s*$", "", title).strip()
        for row in re.split(r"\n\|-", chunk):
            seat = SEAT.search(row)
            if not seat:
                continue
            rest = row[seat.end() :]
            party = None
            for cell in re.split(r"\n\||\|\|", rest):
                hit = [n for n in cell_names(cell) if n in vocab]
                if hit:
                    party = hit[0]
                    break
            rows.append(
                {
                    "year": year,
                    "alliance": alliance,
                    "state": state,
                    "pc_name": (seat.group(2) or seat.group(1)).strip(),
                    "party": party or "",
                    "result": result_of(rest),
                }
            )
    return rows


def main():
    out = []
    vocab = party_vocabulary(strip_refs(open(RAW + f, encoding="utf-8").read()) for _, _, f in FILES)
    for year, alliance, fname in FILES:
        rows = parse(year, alliance, fname, vocab)
        out += rows
        res = Counter(r["result"] for r in rows)
        seats = len({(r["state"], r["pc_name"]) for r in rows})
        print(f"{year} {alliance}: {len(rows)} rows, {seats} distinct seats, {len({r['state'] for r in rows})} states, "
              f"won {res['won']}, lost {res['lost']}, no result {res['']}, no party {sum(not r['party'] for r in rows)}")
    with open("alliance_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote alliance_candidates.csv: {len(out)} rows")


if __name__ == "__main__":
    main()
