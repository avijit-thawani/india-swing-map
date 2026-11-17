"""Build the data file behind the swing map: one shape per Lok Sabha seat with
its 2019 and 2024 results and the NDA's lead in each.

NDA lead = the NDA candidate's share of valid votes minus the best other
candidate's share. Positive where the NDA won, negative where it lost.
Swing = the 2024 lead minus the 2019 lead.

Run: python3 build_map.py
Writes: map/data.json
"""

import csv
import difflib
import json
import math
import os
import re
from collections import defaultdict

from apply_alliances import membership, party_alliance, party_key, seat_state_key

YEARS = (2019, 2024)

# Shape-file seat names that differ too much from the results file to match on spelling.
SEAT_RENAMES = {
    ("assam", "tezpur"): "sonitpur",
    ("assam", "nowgong"): "nagaon",
    ("assam", "kaliabor"): "kaziranga",
    ("chhattisgarh", "janjgir"): "janjgirchampa",
    ("telangana", "bhuvanagiri"): "bhongir",
    ("karnataka", "bijapur"): "vijayapura",
    ("karnataka", "gulbarga"): "kalaburagi",
    ("karnataka", "bellary"): "ballari",
    ("karnataka", "mysore"): "mysuru",
}
# The shape file names two seats "Mumbai South"; the northern one (seat 30) is South Central.
SHAPE_NAME_FIXES = {2730: "Mumbai South Central"}
# NDA candidates the party tables miss because the results file names the party differently.
NDA_CANDIDATES = {(2019, "Kottayam"): "pcthomas"}
STATE_RENAMES = {"orissa": "odisha", "andamanandnicobar": "andamanandnicobarislands"}
# Seats redrawn between the two elections, where 2019 and 2024 are not like for like.
REDRAWN_STATES = {"Assam", "Jammu And Kashmir", "Ladakh"}

# Short party names for the info box, keyed by squashed full name as the results file spells it.
ABBREVIATIONS = {
    "Bharatiya Janata Party": "BJP", "Indian National Congress": "INC", "All India Trinamool Congress": "AITC",
    "Bahujan Samaj Party": "BSP", "Samajwadi Party": "SP", "Yuvajana Sramika Rythu Congress Party": "YSRCP",
    "Telugu Desam": "TDP", "Dravida Munnetra Kazhagam": "DMK", "Shivsena": "SHS", "Shiv Sena": "SHS",
    "All India Anna Dravida Munnetra Kazhagam": "AIADMK", "Biju Janata Dal": "BJD", "Nationalist Congress Party": "NCP",
    "Rashtriya Janata Dal": "RJD", "Janata Dal (United)": "JD(U)", "Communist Party Of India (Marxist)": "CPI(M)",
    "Telangana Rashtra Samithi": "TRS", "Independent": "IND", "Shiromani Akali Dal": "SAD", "Janata Dal (Secular)": "JD(S)",
    "Pattali Makkal Katchi": "PMK", "Communist Party Of India": "CPI", "Lok Jan Shakti Party": "LJP",
    "Rashtriya Lok Samta Party": "RLSP", "Jharkhand Mukti Morcha": "JMM", "Desiya Murpokku Dravida Kazhagam": "DMDK",
    "Hindustani Awam Morcha (Secular)": "HAM(S)", "Vikassheel Insaan Party": "VIP", "Aam Aadmi Party": "AAP",
    "Jammu & Kashmir National Conference": "JKNC", "Indian Union Muslim League": "IUML", "Rashtriya Lok Dal": "RLD",
    "Asom Gana Parishad": "AGP", "All India United Democratic Front": "AIUDF", "Jharkhand Vikas Morcha (Prajatantrik)": "JVM(P)",
    "All India Majlis-E- Ittehadul Muslimeen": "AIMIM", "Swabhimani Paksha": "SWP", "Apna Dal (Soneylal)": "AD(S)",
    "Bodoland Peoples Front": "BPF", "Communist Party Of India (Marxist-Leninist) (Liberation)": "CPI(ML)L",
    "Jannayak Janta Party": "JJP", "Jammu & Kashmir People Conference": "JKPC", "Peoples Democratic Party": "PDP",
    "Jammu & Kashmir Peoples Democratic Party": "PDP", "Ajsu Party": "AJSU", "Revolutionary Socialist Party": "RSP",
    "Kerala Congress (M)": "KC(M)", "Kerala Congress": "KEC", "Vanchit Bahujan Aaghadi": "VBA", "Bahujan Vikas Aaghadi": "BVA",
    "Maharashtra Swabhimaan Paksh": "MSP", "Naga Peoples Front": "NPF", "United Democratic Party": "UDP",
    "National People'S Party": "NPP", "Mizo National Front": "MNF", "Nationalist Democratic Progressive Party": "NDPP",
    "All India N.R. Congress": "AINRC", "Lok Insaaf Party": "LIP", "Rashtriya Loktantrik Party": "RLP",
    "Sikkim Krantikari Morcha": "SKM", "Sikkim Democratic Front": "SDF", "Viduthalai Chiruthaigal Katchi": "VCK",
    "Tamil Maanila Congress (Moopanar)": "TMC(M)", "Shiv Sena (Uddhav Balasaheb Thackrey)": "SHS(UBT)",
    "Nationalist Congress Party – Sharadchandra Pawar": "NCP(SP)", "Lok Janshakti Party(Ram Vilas)": "LJP(RV)",
    "Janasena Party": "JSP", "Bharat Rashtra Samithi": "BRS", "Assam Jatiya Parishad": "AJP",
    "United People’S Party, Liberal": "UPPL", "Voice Of The People Party": "VPP", "Zoram People’S Movement": "ZPM",
    "Bharat Adivasi Party": "BAP", "Citizen Action Party-Sikkim": "CAP(S)", "Amma Makkal Munnettra Kazagam": "AMMK",
    "Marumalarchi Dravida Munnetra Kazhagam": "MDMK", "Suheldev Bharatiya Samaj Party": "SBSP",
    "Aazad Samaj Party (Kanshi Ram)": "ASP(KR)", "Rashtriya Samaj Paksha": "RSPS", "Naam Tamilar Katchi": "NTK",
}
ABBREVIATIONS = {re.sub(r"[^a-z]", "", k.lower()): v for k, v in ABBREVIATIONS.items()}
unabbreviated = set()


def short(party):
    """BJP for Bharatiya Janata Party; initials for anything not in the table."""
    key = re.sub(r"[^a-z]", "", party.lower())
    if key in ABBREVIATIONS:
        return ABBREVIATIONS[key]
    unabbreviated.add(party)
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", party) if w.lower() not in ("of", "the", "and")).upper()


def squash(s):
    return re.sub(r"[^a-z]", "", (s or "").lower().replace("&", "and"))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def nda_leads(members, seats):
    """(year, pc_code) -> the NDA's and the best other candidate's vote share."""
    # Alliance-backed independents can only be told apart by name, so carry the
    # tags already worked out for each seat's winner and runner-up.
    backed = set()
    for r in seats:
        for who in ("winner", "runner_up"):
            if r[f"{who}_alliance"] == "NDA" and party_key(r[f"{who}_party"]) == "independent":
                backed.add((int(r["year"]), r["pc_code"], squash(r[who])))

    by_seat = defaultdict(list)
    for r in csv.DictReader(open("raw/idp_detailed_2019_2024.csv", encoding="utf-8")):
        by_seat[(int(r["year"]), r["pc_code"])].append(r)

    out = {}
    for (year, code), rows in by_seat.items():
        valid = num(rows[0]["valid_votes"])
        nda, other = None, None
        for r in rows:
            if "none of the above" in r["party_name"].lower():
                continue
            votes = num(r["votes_secured_general"]) + num(r["votes_secured_postal"])
            st = seat_state_key(r["state_name"], r["pc_name"], year)
            who = squash(r["candidate_name"])
            is_nda = (
                party_alliance(members, year, st, r["party_name"]) == "NDA"
                or (year, code, who) in backed
                or NDA_CANDIDATES.get((year, r["pc_name"]), "~") in who
            )
            entry = {"name": r["candidate_name"], "party": r["party_name"], "pct": round(100 * votes / valid, 3)}
            if is_nda:
                if nda is None or entry["pct"] > nda["pct"]:
                    nda = entry
            elif other is None or entry["pct"] > other["pct"]:
                other = entry
        out[(year, code)] = {"nda": nda, "other": other}
    return out


def mercator(lon, lat):
    return [round(lon, 3), round(math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))), 3)]


def project(geometry):
    """Mercator-project up front so the page can draw the shapes as flat x/y."""
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    out = []
    for poly in polys:
        rings = []
        for ring in poly:
            pts = []
            for lon, lat in ring:
                p = mercator(lon, lat)
                if not pts or p != pts[-1]:
                    pts.append(p)
            if len(pts) >= 4:
                rings.append(pts)
        if rings:
            out.append(rings)
    return out


def main():
    members, _, _, _ = membership()
    seats = [r for r in csv.DictReader(open("seats_with_alliances.csv", encoding="utf-8")) if int(r["year"]) in YEARS]
    leads = nda_leads(members, seats)

    by_code = defaultdict(dict)
    for r in seats:
        by_code[r["pc_code"]][int(r["year"])] = r

    # Index the results by state and squashed seat name to join them to the shapes.
    index = defaultdict(dict)
    for code, years in by_code.items():
        for r in years.values():
            st = re.sub(r"^the", "", squash(r["state"]))
            index[st][squash(r["pc_name"])] = code
            # Ladakh sits under Jammu and Kashmir in the shapes; the two merged
            # union territories are separate there.
            if st == "ladakh":
                index["jammuandkashmir"][squash(r["pc_name"])] = code
            if st == "dadraandnagarhavelianddamananddiu":
                index["damananddiu" if "daman" in r["pc_name"].lower() else "dadraandnagarhaveli"][squash(r["pc_name"])] = code

    geo = json.load(open("raw/datameet_india_pc_2019_simplified.geojson", encoding="utf-8"))
    features, used, unmatched = [], {}, []
    for f in geo["features"]:
        p = f["properties"]
        st = squash(p["st_name"])
        st = STATE_RENAMES.get(st, st)
        shape_name = SHAPE_NAME_FIXES.get(p["pc_id"], p["pc_name"])
        name = SEAT_RENAMES.get((st, squash(shape_name)), squash(shape_name))
        table = index.get(st, {})
        if name not in table:
            close = difflib.get_close_matches(name, list(table), 1, 0.72)
            name = close[0] if close else None
        code = table.get(name)
        if code is None or code in used:
            unmatched.append((p["st_name"], p["pc_name"], used.get(code)))
            continue
        used[code] = p["pc_name"]

        years = by_code[code]
        latest = years.get(2024) or years[2019]
        props = {
            "code": code,
            "seat": latest["pc_name"],
            "state": re.sub(r"^The ", "", latest["state"]).replace(" And ", " and "),
            "redrawn": latest["state"] in REDRAWN_STATES,
        }
        for year in YEARS:
            r = years.get(year)
            if not r:
                continue
            lead = leads.get((year, code), {})
            nda, other = lead.get("nda"), lead.get("other")
            props[f"y{year}"] = {
                "winner": r["winner"],
                "winnerParty": short(r["winner_party"]),
                "winnerAlliance": r["winner_alliance"],
                "winnerPct": num(r["winner_pct"]),
                "runnerUp": r["runner_up"],
                "runnerUpParty": short(r["runner_up_party"]),
                "runnerUpAlliance": r["runner_up_alliance"],
                "runnerUpPct": num(r["runner_up_pct"]),
                "marginVotes": int(num(r["margin_votes"])),
                "marginPct": num(r["margin_pct"]),
                "turnout": num(r["turnout_pct"]),
                "nda": nda,
                "other": other,
                # No NDA candidate at all counts as a lead of minus the winner's share.
                "ndaLead": round((nda["pct"] if nda else 0) - (other["pct"] if other else 0), 3),
            }
        if "y2019" in props and "y2024" in props:
            props["swing"] = round(props["y2024"]["ndaLead"] - props["y2019"]["ndaLead"], 2)
        features.append({"p": props, "g": project(f["geometry"])})

    missing = sorted(set(by_code) - set(used))
    print(f"{len(features)} of {len(geo['features'])} shapes joined to results")
    print("shapes with no result:", unmatched)
    print("results with no shape:", [(by_code[c].get(2024) or by_code[c][2019])["pc_name"] for c in missing])

    # Checks against numbers already established for these files.
    won24 = sum(1 for f in features if f["p"].get("y2024", {}).get("winnerAlliance") == "NDA")
    won19 = sum(1 for f in features if f["p"].get("y2019", {}).get("winnerAlliance") == "NDA")
    print(f"NDA seats on the map: 2019 {won19} (expect 352), 2024 {won24} (expect 292, Surat unopposed)")
    for year in YEARS:
        bad = [
            (f["p"]["seat"], f["p"][f"y{year}"]["ndaLead"], f["p"][f"y{year}"]["winnerAlliance"])
            for f in features
            if f"y{year}" in f["p"] and (f["p"][f"y{year}"]["ndaLead"] > 0) != (f["p"][f"y{year}"]["winnerAlliance"] == "NDA")
        ]
        print(f"{year}: seats where the sign of the NDA lead disagrees with the winner's alliance: {bad}")
        none = [f["p"]["seat"] for f in features if f"y{year}" in f["p"] and not f["p"][f"y{year}"]["nda"]]
        print(f"{year}: {len(none)} seats with no NDA candidate found: {none}")

    print("parties abbreviated by initials (not in the table):", sorted(unabbreviated))

    os.makedirs("map", exist_ok=True)
    with open("map/data.json", "w", encoding="utf-8") as f:
        json.dump({"years": YEARS, "seats": features}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote map/data.json: {os.path.getsize('map/data.json') // 1024} KB")


if __name__ == "__main__":
    main()
