"""Build one row per Lok Sabha seat per election (2004-2024) from the India Data
Portal copies of the Election Commission's statistical reports, and check the
2019 and 2024 rows against Wikipedia's results tables.

Run: python3 build.py
Writes: seats_2004_2024.csv
"""

import csv
import re
from collections import defaultdict

RAW = "raw/"


def load(name):
    with open(RAW + name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def key(name):
    """Loose seat-name key for joining sources that spell names differently."""
    return re.sub(r"[^a-z]", "", name.lower().replace("&", "and"))


def seat_rows():
    rows = []
    for fname in ("idp_summary_2004_2009_2014.csv", "idp_summary_2019_2024.csv"):
        for r in load(fname):
            win, run = num(r["winner_votes"]), num(r["runner_up_votes"])
            valid = num(r["total_valid_votes_polled"])
            nota = num(r.get("nota_votes_including_postal")) or 0
            margin = num(r["margin_votes"])
            # The valid-vote total excludes NOTA. Shares here are of valid votes,
            # which is what the Election Commission and Wikipedia report.
            pct = lambda v: round(100 * v / valid, 2) if v is not None and valid else None
            rows.append(
                {
                    "year": int(r["year"]),
                    "state": r["state_name"],
                    "pc_name": r["pc_name"],
                    "pc_code": r.get("pc_code", ""),
                    "electors": num(r["total_electors_total"]),
                    "turnout_pct": r["polling_per_total"],
                    "valid_votes": valid,
                    "nota_votes": nota,
                    "winner": r["winner_candidate"],
                    "winner_party": r["winner_party"],
                    "winner_votes": win,
                    "winner_pct": pct(win),
                    "runner_up": r["runner_up_candidate"],
                    "runner_up_party": r["runner_up_party"],
                    "runner_up_votes": run,
                    "runner_up_pct": pct(run),
                    "margin_votes": margin,
                    "margin_pct": pct(margin),
                }
            )
    return rows


def wikipedia_rows(year):
    """Parse winner and runner-up votes out of the Wikipedia results wikitext."""
    text = open(f"{RAW}Results_of_the_{year}_Indian_general_election.wiki", encoding="utf-8").read()
    out = defaultdict(list)
    for block in text.split("\n|-"):
        cells = [c.strip() for c in re.split(r"\n[|!]", block)]
        m = None
        for i, c in enumerate(cells):
            m = re.search(r"\[\[([^\]|]*Lok Sabha constituency\)?)\|([^\]]+)\]\]", c)
            if m:
                break
        if not m:
            continue
        nums = []
        for c in cells[i + 1 :]:
            c = c.split("|")[-1].strip() if "style=" in c else c
            c = re.sub(r"<ref.*", "", c, flags=re.S).strip()
            if re.fullmatch(r"[\d,]+", c):
                nums.append(int(c.replace(",", "")))
        if len(nums) >= 3:
            out[key(m.group(2))].append({"name": m.group(2), "winner_votes": nums[0], "runner_up_votes": nums[1], "margin": nums[-1]})
    return out


def check_against_wikipedia(rows):
    for year in (2019, 2024):
        wiki = wikipedia_rows(year)
        ours = [r for r in rows if r["year"] == year]
        matched = same = 0
        diffs, unmatched = [], []
        for r in ours:
            cands = wiki.get(key(r["pc_name"]))
            if not cands:
                unmatched.append(r["pc_name"])
                continue
            # Several states share seat names (Aurangabad, Hamirpur, Maharajganj):
            # take the same-named Wikipedia row closest on winner votes.
            w = min(cands, key=lambda c: abs(c["winner_votes"] - (r["winner_votes"] or 0)))
            matched += 1
            if w["margin"] == r["margin_votes"] and w["winner_votes"] == r["winner_votes"]:
                same += 1
            else:
                diffs.append((r["pc_name"], r["winner_votes"], r["margin_votes"], w["winner_votes"], w["margin"]))
        print(f"{year}: {len(ours)} seats, {sum(map(len, wiki.values()))} parsed from Wikipedia, {matched} matched by name, {same} identical")
        print("  differ (seat, our winner votes, our margin, wiki winner votes, wiki margin):")
        for d in diffs:
            print("   ", d)
        print("  not matched by name:", unmatched)


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}: {len(rows)} rows")


def main():
    rows = seat_rows()
    rows.sort(key=lambda r: (r["year"], r["state"], r["pc_name"]))
    write("seats_2004_2024.csv", rows)

    check_against_wikipedia(rows)


if __name__ == "__main__":
    main()
