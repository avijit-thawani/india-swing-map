"""Tag the winner and runner-up of every Lok Sabha seat, 2004-2024, with the
alliance they fought under.

Alliance membership comes from Wikipedia:
  2004 NDA, 2009-2019 NDA and UPA: seat-by-seat candidate lists, reduced to
      "which parties did the alliance field in this state".
  2004 UPA: the party table on the United Progressive Alliance page (no
      candidate list exists), applied nationally.
  2024 NDA and INDIA: the party-and-alliance table on the results page, applied
      nationally, so the totals match Wikipedia's 293 and 234.

Run: python3 alliances.py && python3 apply_alliances.py
Writes: alliance_parties.csv, seats_with_alliances.csv
"""

import csv
import difflib
import re
from collections import Counter, defaultdict

from alliances import LINK, strip_refs

# Spellings and abbreviations that mean the same party, keyed by squashed name.
ALIASES = {
    "inc": "Indian National Congress",
    "bjp": "Bharatiya Janata Party",
    "sp": "Samajwadi Party",
    "cpm": "Communist Party of India (Marxist)",
    "bsp": "Bahujan Samaj Party",
    "tdp": "Telugu Desam Party",
    "telugudesam": "Telugu Desam Party",
    "admk": "All India Anna Dravida Munnetra Kazhagam",
    "rjd": "Rashtriya Janata Dal",
    "aitc": "All India Trinamool Congress",
    "trinamoolcongress": "All India Trinamool Congress",
    "jdu": "Janata Dal (United)",
    "ncp": "Nationalist Congress Party",
    "shs": "Shiv Sena",
    "shivsena": "Shiv Sena",
    "dmk": "Dravida Munnetra Kazhagam",
    "cpi": "Communist Party of India",
    "ind": "Independent",
    "independentpolitician": "Independent",
    "bjd": "Biju Janata Dal",
    "jds": "Janata Dal (Secular)",
    "sad": "Shiromani Akali Dal",
    "ljnsp": "Lok Janshakti Party",
    "ljp": "Lok Janshakti Party",
    "lokjanshaktiparty": "Lok Janshakti Party",
    "agp": "Asom Gana Parishad",
    "jmm": "Jharkhand Mukti Morcha",
    "pmk": "Pattali Makkal Katchi",
    "rld": "Rashtriya Lok Dal",
    "trs": "Telangana Rashtra Samithi",
    "inld": "Indian National Lok Dal",
    "jkn": "Jammu & Kashmir National Conference",
    "jammuandkashmirnationalconference": "Jammu & Kashmir National Conference",
    "mdmk": "Marumalarchi Dravida Munnetra Kazhagam",
    "rsp": "Revolutionary Socialist Party",
    "revolutionarysocialistpartyindia": "Revolutionary Socialist Party",
    "jkpdp": "Jammu & Kashmir Peoples Democratic Party",
    "aifb": "All India Forward Bloc",
    "mul": "Indian Union Muslim League",
    "iuml": "Indian Union Muslim League",
    "aimim": "All India Majlis-e-Ittehadul Muslimeen",
    "cpimll": "Communist Party of India (Marxist-Leninist) Liberation",
    "communistpartyofindiamarxistleninistliberation": "Communist Party of India (Marxist-Leninist) Liberation",
    "kec": "Kerala Congress",
    "kecm": "Kerala Congress (M)",
    "ifdp": "Indian Federal Democratic Party",
    "rpia": "Republican Party of India (Athawale)",
    "republicanpartyofindiaathvale": "Republican Party of India (Athawale)",
    "rpi": "Republican Party of India",
    "mnf": "Mizo National Front",
    "npf": "Naga People's Front",
    "nagapeoplesfront": "Naga People's Front",
    "sdf": "Sikkim Democratic Front",
    "vck": "Viduthalai Chiruthaigal Katchi",
    "bopf": "Bodoland People's Front",
    "bodolandpeoplesfront": "Bodoland People's Front",
    "hjcbl": "Haryana Janhit Congress (BL)",
    "jvm": "Jharkhand Vikas Morcha (Prajatantrik)",
    "swp": "Swabhimani Paksha",
    "bva": "Bahujan Vikas Aaghadi",
    "ysrcp": "Yuvajana Sramika Rythu Congress Party",
    "aaap": "Aam Aadmi Party",
    "blsp": "Rashtriya Lok Samta Party",
    "rashtriyaloksamataparty": "Rashtriya Lok Samta Party",
    "npep": "National People's Party",
    "nationalpeoplespartyindia": "National People's Party",
    "ad": "Apna Dal",
    "apnadalkamerawadi": "Apna Dal",
    "apnadalsonelal": "Apna Dal (Soneylal)",
    "sjd": "Socialist Janata (Democratic)",
    "rsps": "Rashtriya Samaj Paksha",
    "ainrc": "All India N.R. Congress",
    "skm": "Sikkim Krantikari Morcha",
    "pt": "Puthiya Tamilagam",
    "dmdk": "Desiya Murpokku Dravida Kazhagam",
    "hindustaniawammorchasecular": "Hindustani Awam Morcha",
    "ajsuparty": "All Jharkhand Students Union",
    "janasenaparty": "Jana Sena Party",
    "lokjanshaktipartyramvilas": "Lok Janshakti Party (Ram Vilas)",
    "shivsenauddhavbalasahebthackrey": "Shiv Sena (Uddhav Balasaheb Thackeray)",
    "shivsenaubt": "Shiv Sena (Uddhav Balasaheb Thackeray)",
    "nationalistcongresspartysharadchandrapawar": "Nationalist Congress Party (Sharadchandra Pawar)",
    "unitedpeoplespartyliberal": "United People's Party Liberal",
    "ammamakkalmunnettrakazagam": "Amma Makkal Munnettra Kazhagam",
    "tamilmaanilacongress": "Tamil Maanila Congress (Moopanar)",
    "communistpartyofindiamarxist": "Communist Party of India (Marxist)",
    "communistpartyofindia": "Communist Party of India",
    "independent": "Independent",
}


def squash(name):
    name = name.lower().replace("&", "and").replace("–", " ").replace("’", "")
    return re.sub(r"[^a-z]", "", name)


def party_key(name):
    """One key per party whatever the spelling: 'Inc', 'Shivsena', 'Telugu Desam'."""
    s = squash(name)
    return squash(ALIASES.get(s, name))


def state_key(name, year):
    s = squash(name)
    s = re.sub(r"^(the|nctof)", "", s)
    s = {"orissa": "odisha", "uttaranchal": "uttarakhand", "pondicherry": "puducherry"}.get(s, s)
    if year == 2014 and s == "telangana":
        s = "andhrapradesh"  # still one state when the 2014 lists were drawn up
    if year == 2019 and s == "ladakh":
        s = "jammuandkashmir"
    return s


def seat_state_key(state, seat, year):
    """State key for a seat. The results file files the two pre-2020 union
    territories under their merged name, so split them back by seat."""
    s = state_key(state, year)
    if s == "dadraandnagarhavelianddamananddiu" and year < 2024:
        return "damananddiu" if "daman" in seat.lower() else "dadraandnagarhaveli"
    return s


def seat_key(name):
    return squash(name)


def membership():
    """(year, state or '*', party key) -> alliance, plus alliance-backed independents by seat."""
    members, independents, display = {}, {}, {}
    seat_won = defaultdict(dict)  # (year, state) -> {seat key: (alliance that won it, its party key)}

    def add(year, state, party, alliance, state_name="all states"):
        k = (year, state, party_key(party))
        display[k] = (state_name, party)
        if members.setdefault(k, alliance) != alliance:
            print(f"  conflict: {party} in {state} {year} is listed by both {members[k]} and {alliance}")

    for r in csv.DictReader(open("alliance_candidates.csv", encoding="utf-8")):
        year = int(r["year"])
        st = state_key(r["state"], year)
        if year == 2024:
            # 2024 membership comes from the national table below; the list is
            # only needed for the independents an alliance backed.
            if party_key(r["party"]) == "independent" and r["result"] == "lost":
                independents[(year, st, seat_key(r["pc_name"]))] = r["alliance"]
            continue
        if r["result"] == "won":
            seat_won[(year, st)][seat_key(r["pc_name"])] = (r["alliance"], party_key(r["party"]))
        if party_key(r["party"]) == "independent":
            if r["result"] == "lost":
                independents[(year, st, seat_key(r["pc_name"]))] = r["alliance"]
        elif r["party"]:
            add(year, st, r["party"], r["alliance"], r["state"])

    # 2004 UPA: the party table on the alliance's own page.
    text = strip_refs(open("raw/alliances/upa_main.wiki", encoding="utf-8").read())
    table = text[text.index("|+2004 Lok Sabha Election") :]
    table = table[: table.index("|}")]
    for m in re.finditer(r"\n\|\d+\.\s*\n\|\s*\[\[([^\]|]+)", table):
        add(2004, "*", m.group(1).strip(), "UPA")

    # 2024: the party-and-alliance table on the results page.
    text = strip_refs(open("raw/Results_of_the_2024_Indian_general_election.wiki", encoding="utf-8").read())
    table = text[text.index("== Results by party and alliances ==") :]
    table = table[: table.index("\n|}")]
    current = None
    for row in table.split("\n|-"):
        if "National Democratic Alliance|NDA" in row:
            current = "NDA"
        elif "Indian National Developmental Inclusive Alliance|INDIA" in row:
            current = "INDIA"
        if "''Total''" in row:
            current = None
            continue
        links = [m.group(1).strip() for m in LINK.finditer(row) if not m.group(1).startswith("File:")]
        links = [l for l in links if "Alliance" not in l]
        if current and links:
            add(2024, "*", links[-1], current)

    return members, independents, display, seat_won


def party_alliance(members, year, st, party):
    pk = party_key(party)
    return members.get((year, st, pk)) or members.get((year, "*", pk))


def seat_lookup(table, seat):
    """Find a seat in one state's {seat key: value} table, allowing spelling drift."""
    s = seat_key(seat)
    if s in table:
        return table[s]
    close = difflib.get_close_matches(s, list(table), 1, 0.8)
    return table[close[0]] if close else None


def winner_alliance(members, seat_won, year, state, seat, party):
    st = seat_state_key(state, seat, year)
    by_party = party_alliance(members, year, st, party)
    if by_party:
        return by_party
    # Party membership says nothing. Trust the list's "won" flag for the seat only
    # for independents and for one party under two names (Kerala Congress and
    # Kerala Congress (M)); the flags are wrong for a few seats other parties won.
    flagged = seat_lookup(seat_won.get((year, st), {}), seat)
    if flagged:
        alliance, listed = flagged
        pk = party_key(party)
        if pk == "independent" or (listed and (listed in pk or pk in listed)):
            return alliance
    return "Other"


def runner_up_alliance(members, independents, year, state, seat, party):
    st = seat_state_key(state, seat, year)
    if party_key(party) == "independent":
        table = {k[2]: v for k, v in independents.items() if k[:2] == (year, st)}
        return seat_lookup(table, seat) or "Other"
    return party_alliance(members, year, st, party) or "Other"


def main():
    members, independents, display, seat_won = membership()

    with open("alliance_parties.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "state", "party", "alliance"])
        for (year, st, _), alliance in sorted(members.items(), key=lambda kv: (kv[0][0], kv[1], kv[0][1], kv[0][2])):
            w.writerow([year, *display[(year, st, _)], alliance])
    print(f"wrote alliance_parties.csv: {len(members)} rows")

    seats = list(csv.DictReader(open("seats_2004_2024.csv", encoding="utf-8")))
    totals = defaultdict(Counter)
    for r in seats:
        year = int(r["year"])
        r["winner_alliance"] = winner_alliance(members, seat_won, year, r["state"], r["pc_name"], r["winner_party"])
        r["runner_up_alliance"] = runner_up_alliance(members, independents, year, r["state"], r["pc_name"], r["runner_up_party"])
        totals[year][r["winner_alliance"]] += 1
    with open("seats_with_alliances.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(seats[0]))
        w.writeheader()
        w.writerows(seats)
    print(f"wrote seats_with_alliances.csv: {len(seats)} rows")

    won = defaultdict(Counter)
    for r in csv.DictReader(open("alliance_candidates.csv", encoding="utf-8")):
        if r["result"] == "won":
            won[int(r["year"])][r["alliance"]] += 1
    print("\nseats won per alliance: this table vs 'won' flags in the candidate lists")
    for year in sorted(totals):
        print(f"  {year}: {dict(totals[year])}   lists: {dict(won[year])}")


if __name__ == "__main__":
    main()
