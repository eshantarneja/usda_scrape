# USDA LM_XB461 — National Weekly Cutter Cow Cutout And Boxed Cow Beef Cuts

Research only. Report dated 2026-09-04 (Friday). Files in this directory:

- `ams_2463_LM_XB461.pdf` — the cow report (4 pages)
- `cow_report.txt` — full pdfplumber text extraction of it
- `steer_heifer_XB459_ams_2461.pdf` / `steer_heifer_XB459_from_ams_2461.txt` — what `ams_2461.pdf` actually returns (see first note below)

**URL correction.** `https://www.ams.usda.gov/mnreports/ams_2461.pdf` is NOT the cow report. It returns
**LM_XB459, "National Weekly Boxed Beef Cutout And Boxed Beef Cuts - Negotiated Sales"** (steer/heifer, 5 pages).
The `ams_NNNN` number is the MyMarketNews report id, not the `LM_XB` number. Probing 2455-2467 found:

| ams id | Report |
|---|---|
| 2453 | LM_XB403 Daily Boxed Beef Afternoon (already scraped as `daily_afternoon`) |
| 2455 | National 5-Day Rolling Cutter Cow Cutout — Afternoon (daily cow companion) |
| 2456 | National Weekly Formulated Boneless Cow Beef & Beef Trimmings |
| 2457 | LM_XB452 Branded Product weekly (already scraped as `branded_beef`) |
| 2461 | LM_XB459 Weekly Boxed Beef Cutout (steer/heifer) |
| 2462 | National/Regional Weekly Boneless Processing Beef and Beef Trimmings |
| **2463** | **LM_XB461 National Weekly Cutter Cow Cutout And Boxed Cow Beef Cuts — THIS REPORT** |
| 2464 | LM_XB462 Ungraded Product weekly (already scraped as `ungraded_beef`) |

So the config entry would be `pdf_url: f"{USDA_BASE_URL}/mnreports/ams_2463.pdf"`.

---

## (a) Structure summary

Every page carries the same 5-line header (title, subtitle "USDA Estimate Cutter Cow Carcass Cut-Out Value - Negotiated Sales",
date, `LM_XB461`, accessibility note) and the same 4-line footer (Source/Page N of 4, phone/email, XML/JSON links, viewreport/2463).
`_is_header_row` already eats most of those (`usda`, `page`, `report`).

Sections, in order:

### Page 1 — Cutter Cow Cutout Value (NOT a cuts table)

```
Based on negotiated prices and volume of cow cuts delivered within 0-21 days and on average industry cutting yields. Values reflect U.S.
dollars per 100 pounds.
Cutter 90%
350#/up
Current Cutout Value: 346.58
Change from prior week: -3.58
Item Price Value Change
90% lean 449.29 250.88 (1.68)
100% lean inside round 478.74 11.11 (0.15)
...
Tenderloin 3-4 lbs. 872.42 6.46 (0.13)
Ribeye Roll 8up lbs. 697.58 5.09 0.09
Flank Steak 587.55 2.47 (0.02)
Kidney, Edible 55.00 0.25 0.02
Fat, Inedible 54.77 1.27 0.12
Bone 8.83 2.12 0.00
```

One grade only ("Cutter 90%, 350#/up") — there is no Choice/Select split and no per-grade cutout table like XB459's.
Columns: `Item | Price ($/cwt) | Value (contribution to cutout) | Change (from prior week; negatives in parentheses)`.
15 items, no IMPS codes, no trades/pounds. The Price column here duplicates the weighted average from the cuts tables on pages 2-3
(e.g. Flank Steak 587.55, Knuckle 434.84, Chuck Tender 434.16), so this table is derivable and could be skipped.

### Page 2 — "USDA National Boxed Cow Beef Cuts - Negotiated Sales", volume block, then cuts tables

Volume block (5 lines, `X loads -- Y pounds`): Boner/Breaker Cuts, Cutter/Canner Cuts, Boner/Breaker/Cutter/Canner Cuts,
100% Lean Items, Frozen Cuts.

Then ONE column header that applies to all the cut tables that follow:

```
# of Total Weighted Change from
IMPS Sub-Primal Trades Pounds Average Prior Week
```

Columns: `IMPS | Sub-Primal | # of Trades | Total Pounds | Weighted Average | Change from Prior Week`.
**There is no Fat-Limitation column and no Price Range (low - high) column.** Only the weighted average is given.

Sub-sections are single-word-ish ALL-CAPS lines (these are the section markers):

1. `BONER/BREAKER` (p2) — 22 lines. IMPS 112, 112A, (no code) Chuck boneless 85%, (no code) Semi-Bnls Short Loin x2, 120, 168, 169A, 171B, 171C, 180, 182, 184, 185A, 191A.
2. `CUTTER/CANNER` (p3) — 3 lines, all IMPS 112 ribeye roll by weight bracket.
3. `100% LEAN` (p3) — 9 lines, **no IMPS codes**: Inside round Combo/Boxed, Outside round, Eye of round, Flats and eyes Combo/Boxed, Striploin, S.P.B. Combo/Boxed.
4. `BONER/BREAKER & CUTTER/CANNER` (p3) — 8 lines: 116B, 167A, 190 x4 weight brackets, 193, (no code) Flank rough.
5. `FROZEN BONER/BREAKER` (p3) — 10 lines, all zero this week.
6. `FROZEN CUTTER/CANNER` (p4) — 3 lines, all zero.
7. `FROZEN BONER/BREAKER & CUTTER/CANNER` (p4) — 5 lines, all zero.

There is no trimmings section in this report (cow trim lives in ams_2456 / ams_2462), and no ground beef section.

### Raw data lines from the cow cuts sections (verbatim from `cow_report.txt`)

```
112A Rib, ribeye roll-lip-on, 8-dn lbs. 16 28,763 758.11 (27.46)
120 Chuck, brisket 22 44,646 415.09 (20.22)
168 Round, top inside, 10-dn lbs. 5 32,904 376.16
169A Round, top inside c-off, 14-up lbs.
167A Round, knuckle, peeled 23 177,987 434.84 (57.46)
193 Flank, flank steak 48 56,329 587.55 (5.12)
Inside round - Combo 32 210,572 485.41 (3.59)
112 Rib, ribeye roll, 6-8 lbs. 0 0 0.00
```

### Does the existing `_parse_data_line` handle these? **No — 0 of 138 lines match.**

The existing regex (`pdf_parser.py:266`) is

```
^(\S+)\s+(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)\s*-\s*([\d,.]+)\s+([\d,.]+)\s*$
 IMPS   FL     description  trades pounds   low         -   high         wavg
```

and expects the existing line shape (identical in `daily_afternoon` / LM_XB403, `ungraded_beef` / LM_XB462, and XB459):

```
109E 1 Rib, ribeye, lip-on, bn-in 106 543,149 1,185.00 - 1,429.00 1,244.67
116A 3 Chuck, roll, lxl, neck/off 152 1,033,087 464.88 - 584.00 531.68
```

The cow line shape is `IMPS DESC TRADES POUNDS WAVG [CHANGE]`:

- no Fat-Limitation digit after the IMPS code (the existing regex's mandatory `(\d+)` group 2),
- no `low - high` range (mandatory groups 6-7),
- a trailing optional "Change from Prior Week" column, written `(27.46)` for negatives, `4.62` for positives, absent when there was no prior-week trade (see the `168 ... 376.16` line above — 5 tokens, not 6),
- `_parse_ground_beef_line` also fails for the same range reason (0 matches).

A new dedicated regex is straightforward. Tested against the extracted text:

```
^(?:(\d{3}[A-Z]?)\s+)?(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)(?:\s+\(?-?[\d,.]+\)?)?\s*$
```

matches 53 lines including all 41 IMPS-coded cut lines (zero-volume ones included), the 100% Lean lines, and the "Chuck, boneless 85%" /
"Flank, rough" / "Semi-Bnls Short Loin" lines, once the page-1 cutout table and the `loads -- pounds` volume lines are excluded by section gating.

---

## (b) IMPS codes with a price this week (weighted average, $/cwt)

Only rows with trades > 0 are listed. Zero-volume rows (`0 0 0.00`) and blank rows are omitted.
All 24 "Frozen" rows were zero this week; every priced row is fresh.

| IMPS | Section | Product (as printed) | Trades | Pounds | Wtd Avg $/cwt | $/lb | Chg vs prior wk |
|---|---|---|---|---|---|---|---|
| 112 | Boner/Breaker | Rib, ribeye roll, 8-10 lbs. | 26 | 56,119 | 710.18 | 7.10 | (3.86) |
| 112 | Boner/Breaker | Rib, ribeye roll, 10-up lbs. | 30 | 50,600 | 698.26 | 6.98 | (23.82) |
| 112A | Boner/Breaker | Rib, ribeye roll-lip-on, 8-dn lbs. | 16 | 28,763 | 758.11 | 7.58 | (27.46) |
| — | Boner/Breaker | Chuck, boneless 85% | 8 | 118,648 | 442.31 | 4.42 | (15.71) |
| 120 | Boner/Breaker | Chuck, brisket | 22 | 44,646 | 415.09 | 4.15 | (20.22) |
| 168 | Boner/Breaker | Round, top inside, 10-dn lbs. | 5 | 32,904 | 376.16 | 3.76 | (none printed) |
| 169A | Boner/Breaker | Round, top inside c-off, 10-14 lbs. | 21 | 179,272 | 496.78 | 4.97 | 4.62 |
| 171C | Boner/Breaker | Round, eye of round | 41 | 55,571 | 486.28 | 4.86 | 49.28 |
| 180 | Boner/Breaker | Loin, strip, bnls, 9-up lbs. | 10 | 8,482 | 614.54 | 6.15 | (1.90) |
| 184 | Boner/Breaker | Loin, top sirloin butt | 11 | 11,619 | 400.68 | 4.01 | (4.75) |
| 185A | Boner/Breaker | Loin, bottom sirloin butt flap, bnls. | 6 | 7,247 | 611.80 | 6.12 | 76.32 |
| 112 | Cutter/Canner | Rib, ribeye roll, 6-8 lbs. | 56 | 91,003 | 704.73 | 7.05 | 9.89 |
| 112 | Cutter/Canner | Rib, ribeye roll, 8-up lbs. | 21 | 52,248 | 697.58 | 6.98 | 12.19 |
| — | 100% Lean | Inside round - Combo | 32 | 210,572 | 485.41 | 4.85 | (3.59) |
| — | 100% Lean | Inside round - Boxed | 39 | 175,969 | 470.76 | 4.71 | (7.59) |
| — | 100% Lean | Eye of round | 20 | 62,722 | 480.65 | 4.81 | (4.60) |
| — | 100% Lean | Flats and eyes - Combo | 7 | 93,670 | 484.08 | 4.84 | (17.26) |
| — | 100% Lean | Striploin | 57 | 113,507 | 643.88 | 6.44 | 4.71 |
| — | 100% Lean | S.P.B. - Combo | 9 | 148,935 | 485.42 | 4.85 | (11.44) |
| 116B | B/B & C/C | Chuck, chuck tender | 17 | 31,197 | 434.16 | 4.34 | (21.10) |
| 167A | B/B & C/C | Round, knuckle, peeled | 23 | 177,987 | 434.84 | 4.35 | (57.46) |
| 190 | B/B & C/C | Loin, tenderloin, 2-3 lbs. | 9 | 7,613 | 839.24 | 8.39 | (none printed) |
| 190 | B/B & C/C | Loin, tenderloin, 3-4 lbs. | 30 | 41,815 | 875.68 | 8.76 | (14.20) |
| 190 | B/B & C/C | Loin, tenderloin, 4-5 lbs. | 28 | 37,166 | 926.61 | 9.27 | 17.60 |
| 190 | B/B & C/C | Loin, tenderloin, 5-up lbs. | 42 | 73,811 | 967.90 | 9.68 | (23.01) |
| 193 | B/B & C/C | Flank, flank steak | 48 | 56,329 | 587.55 | 5.88 | (5.12) |
| — | B/B & C/C | Flank, rough | 81 | 86,352 | 508.79 | 5.09 | (0.76) |

IMPS codes that appear in the report but had **no price this week** (blank or 0/0/0.00): 171B outside round, 182 sirloin butt, 191A butt tender,
169A 8-10 and 14-up brackets, 112A 8-up, 168 10-up, 180 7-9, 112 6-8 (B/B) and 4-6 (C/C), plus every Frozen row.

Distinct IMPS codes present in the report (priced or not): **112, 112A, 116B, 120, 167A, 168, 169A, 171B, 171C, 180, 182, 184, 185A, 190, 191A, 193** (16).
Codes from the task's checklist that do NOT appear anywhere in the cow report: **114 (shoulder clod), 116A (chuck roll), 170 (gooseneck), 174 (short loin), 189A (tenderloin, steer code — the cow report uses 190)**.
"Chuck, boneless 85%" is the cow-side chuck item and carries no IMPS code.

---

## (c) Whetstone utility-line match

Of the 58 fresh-beef lines in `whetstone_lines.json`, **4** carry a `(U)` marker. **0** contain "Cow" and **0** contain "Utl".

| item_code | Whetstone description | Cow report match | IMPS | Cow wtd avg $/cwt ($/lb) | Exact? |
|---|---|---|---|---|---|
| 68405 | Ribeye Roll 10/Up, AFG/LP (U) | Rib, ribeye roll, 10-up lbs. (Boner/Breaker) | 112 | 698.26 (6.98) | Yes — cut + weight bracket |
| 67747 | Ribeye Roll 8/10, Small AFG/LP (U) | Rib, ribeye roll, 8-10 lbs. (Boner/Breaker) | 112 | 710.18 (7.10) | Yes — cut + weight bracket |
| 69399 | Ribeye Roll 10/Up, Four Star (U) | Rib, ribeye roll, 10-up lbs. (Boner/Breaker) | 112 | 698.26 (6.98) | Yes — cut + weight bracket |
| 60817 | Flank Steak, Long Prairie (U) | Flank, flank steak (B/B & C/C) | 193 | 587.55 (5.88) | Yes |

**Count: 4 of 4 utility lines get an exact cow quote (100%).** Note the cow report quotes ribeye roll (112, boneless roll) rather than
lip-on (112A) in the 8-10 / 10-up brackets, which is exactly what Whetstone's utility lines are ("Ribeye Roll", not "Ribeye Lip On"),
so the match is tighter than it would be against the steer/heifer 112A line.

One near-match worth flagging, not counted: **16143 "Flank Steak, Rough C/C COV, Long Prairie"** has no `(U)` marker, but Long Prairie is
a cow packer and "C/C" reads as Cutter/Canner; the cow report prints `Flank, rough 81 86,352 508.79` — the only USDA report that quotes a
rough flank. If that line is in fact cow product, the count becomes 5 of 5.

The other 54 lines are Choice/Select/Prime/Angus/N-R steer-heifer product and belong to the existing XB403/XB459 quotes, not this report.
Nothing in the cow report would be an appropriate reference for them.

---

## (d) Parsing complications

1. **Wrong URL in the brief.** `ams_2461.pdf` is XB459 (steer/heifer weekly). The cow report is `ams_2463.pdf`. Verify the id
   again at implementation time; AMS has renumbered before.
2. **Different line shape.** `IMPS DESC TRADES POUNDS WAVG [CHANGE]` — no Fat-Limitation digit, no `low - high` price range.
   `_parse_data_line` matches 0 lines; a new `_parse_cow_line` regex is needed (candidate above, verified against this week's text).
   `low_price` / `high_price` will have to be stored as NULL (or = weighted avg) for this report type.
3. **Trailing "Change from Prior Week" column** is optional per line and prints negatives in accounting parentheses `(27.46)`.
   The regex must treat it as optional and either ignore it or parse `\((.+)\)` as negative. Lines with no prior-week trade
   (`168 ... 376.16`, `190 ... 839.24`) have 5 tokens instead of 6.
4. **Missing IMPS codes.** 12 of 53 data lines have no code: "Chuck, boneless 85%", both "Loin, Semi-Bnls Short Loin" brackets,
   "Flank, rough", and all 9 "100% LEAN" items. Same situation as the daily report's Ground Beef / "Cap and Wedge Meat" lines —
   `product_code=None`, name-keyed. The `imps` group must be optional.
5. **IMPS codes repeat within a section** by weight bracket: 112 x3, 112A x2, 168 x2, 169A x3, 180 x2, 190 x4. `product_code`
   alone is not a unique key; the bracket lives only in the description text (`8-10 lbs.`, `10-up lbs.`, `8-dn lbs.`). Any join
   to Whetstone SKUs has to match on code + bracket, not code alone.
6. **Blank rows.** Rows with no trade at all print just `IMPS DESC` with no numbers at all (`169A Round, top inside c-off, 14-up lbs.`,
   `171B Round, outside round`, `191A Loin, butt tender, peeled`, `112 Rib, ribeye roll, 4-6 lbs.`). Other rows print `0 0 0.00`.
   Both should be dropped (or stored as zero volume); the daily parser currently drops non-matching lines silently, which works here.
7. **Fresh vs Frozen is by section, not by column.** Sections 5-7 are `FROZEN ...` duplicates of sections 1, 2, 4 with the same IMPS
   codes and descriptions. Without section gating, a frozen `112 Rib, ribeye roll, 8-up lbs. 0 0 0.00` would collide with the fresh
   one. Section markers are bare ALL-CAPS lines (`BONER/BREAKER`, `CUTTER/CANNER`, `100% LEAN`, `BONER/BREAKER & CUTTER/CANNER`,
   `FROZEN BONER/BREAKER`, ...) — like the daily parser's `section_markers` list, order matters (match `FROZEN ...` and the `&`
   variants before the shorter names). Recommend storing `category` = section name and skipping the three FROZEN sections
   (they were 100% zero this week; 4,020 lb total frozen volume).
8. **Page-1 cutout table** has the same `NAME PRICE VALUE CHANGE` numeric shape and would false-positive against a loose regex
   (`90% lean 449.29 250.88 (1.68)`). Gate on the first `BONER/BREAKER` marker before parsing. The `Item Price Value Change`
   header is caught by `_is_header_row` (`price`) but the data rows below it are not.
9. **Volume block** (`Boner/Breaker Cuts 15.05 loads -- 602,011 pounds`) sits between the page-2 title and the first section —
   `_is_header_row` drops it via `pounds`, fine.
10. **Multi-line product names: none.** Every product is a single line. Descriptions contain hyphens and periods
    (`roll-lip-on`, `8-dn lbs.`, `bnls.`) — make sure the description group stays non-greedy and the numeric tail is anchored.
11. **Unit: $/cwt (dollars per 100 lb).** The report states "Values reflect U.S. dollars per 100 pounds" — the same convention as
    XB403/XB459/XB462, so the existing handling applies unchanged (698.26 -> $6.98/lb). Pounds are plain lbs. For reference, the
    Demo loader stores USDA prices as published with `uom='cwt'` (`companies/demo/catalog_mapping/migrations/065_usda_boxed_beef_load.sql`,
    `084_...sql`, `010_beef_latest_usda_prices.sql` in the demo-port repo) and consumers divide by 100 at read time
    (`decision_layer/migrations/035_pork_decision_features_view.sql`) — a cow row would flow through the same path.
12. **Frequency: weekly, published Friday afternoon** (this issue is dated Fri 2026-09-04; the daily companion is ams_2455,
    "5-Day Rolling ... Afternoon"). The two existing weekly reports in `config.py` are commented `# Mondays` (they're dated
    Aug 31) — a cow entry needs `schedule: weekly # Fridays`, or the existing Monday cron will pull a week-old file.
    Date extraction from the header line (`Agricultural Marketing Service September 04, 2026`) is the same format as the others.
13. **Single grade.** No Choice/Select axis; "Cutter 90% 350#/up" is the only cutout. The grade axis this report exposes is
    Boner/Breaker vs Cutter/Canner (cow carcass class), which is a different concept from USDA quality grade. If the Demo
    catalog's `grade` scale is USDA quality grade (Prime/Choice/Select/...), cow product needs its own value (e.g. Utility/Cow),
    and Boner/Breaker vs Cutter/Canner should be carried as `category`, not `grade`.

---

## (e) Recommendation

**Effort: SMALL** (roughly half a day) — one `config.py` entry (`ams_2463`, weekly/Friday), one new `_parse_cow_report` branch in
`pdf_parser.py` with a 7-entry section-marker list and one new regex (no FL digit, no range, optional parenthesized change), and
NULL low/high in the record; nothing in the loader changes because the unit is the same $/cwt.

**Value: high for exactly the lines nothing else covers** — all 4 Whetstone `(U)` lines (3 ribeye-roll brackets + flank) get an exact
IMPS+weight-bracket cow quote, likely 5 with the rough flank, and today those lines have no correct USDA reference at all
(a steer/heifer 112A quote at ~$15/lb vs the cow 112 at ~$7/lb would be wildly wrong).

**Do it, with two guardrails:** gate parsing on the `BONER/BREAKER` marker and skip the FROZEN sections; and key the SKU mapping on
IMPS + weight bracket text, because 112/168/169A/180/190 each appear several times per section.
