# Add the USDA cow report (LM_XB461) to the scraper — handoff

Written 2026-09-04. Research behind this is in
`docs/2026-09-04-cow-report-findings.md` (structure, every priced IMPS line,
parsing gotchas) and `docs/2026-09-04-cow-report-sample.txt` (this week's
full text extraction, use it as the parser fixture).

## Why

Whetstone sells cow beef: four of its 58 fresh SKUs carry a "(U)" marker
(Utility grade, confirmed with the buyer), three ribeye rolls and a flank
steak, plus one rough flank that is almost certainly cow too. No report we
scrape today quotes cow product, so in the Demo global catalog those SKUs
price off the steer/heifer ungraded line, which is roughly double the cow
price. This report quotes every one of them exactly, on cut and weight bracket.

## The report

| | |
|---|---|
| Name | National Weekly Cutter Cow Cutout And Boxed Cow Beef Cuts |
| USDA id | LM_XB461 |
| PDF | `https://www.ams.usda.gov/mnreports/ams_2463.pdf` (**2463, not 2461** — 2461 is the steer/heifer weekly LM_XB459) |
| Cadence | Weekly, published Friday afternoon |
| Unit | $/cwt, same as the other beef reports; nothing downstream changes |
| Grade | One only: Cutter 90%. Sections split by carcass class (Boner/Breaker, Cutter/Canner), not by USDA quality grade |

## Work, in order

### 1. `config.py` — one entry

```python
"cow_beef": {
    "name": "National Weekly Cutter Cow Cutout And Boxed Cow Beef Cuts",
    "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_2463.pdf",
    "schedule": "weekly",  # Fridays
    "report_type": "cow_beef",
},
```

### 2. `pdf_parser.py` — a new branch, `_parse_cow_report`

Route it from `parse_pricing_data` on `report_type == 'cow_beef'`.
The existing `_parse_data_line` matches **zero** cow lines: the cow shape is
`IMPS DESC TRADES POUNDS WAVG [CHANGE]` with no fat-limitation digit, no
`low - high` range, and an optional trailing prior-week change that prints
negatives in parentheses. Tested regex against this week's text:

```python
COW_LINE = re.compile(
    r'^(?:(\d{3}[A-Z]?)\s+)?(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)(?:\s+\(?-?[\d,.]+\)?)?\s*$'
)
# groups: imps (optional), description, trades, pounds, weighted_avg
```

Section markers are bare ALL-CAPS lines. Order matters; match the longer
names first:

```python
COW_SECTIONS = [
    ('FROZEN BONER/BREAKER & CUTTER/CANNER', skip),
    ('FROZEN CUTTER/CANNER',                 skip),
    ('FROZEN BONER/BREAKER',                 skip),
    ('BONER/BREAKER & CUTTER/CANNER',        keep),
    ('100% LEAN',                            keep),   # no IMPS codes; loader will skip them
    ('CUTTER/CANNER',                        keep),
    ('BONER/BREAKER',                        keep),
]
```

Rules:

- Do not start parsing until the first `BONER/BREAKER` marker. Page 1 is a
  cutout-value table (`90% lean 449.29 250.88 (1.68)`) with the same numeric
  shape and will false-positive otherwise.
- Skip the three FROZEN sections. They repeat the fresh IMPS codes and
  descriptions and were all zero this week; without gating they collide.
- Drop rows with trades = 0 and rows with no numbers at all (blank brackets
  print as just `169A Round, top inside c-off, 14-up lbs.`).
- Store `category` = section name (`BONER/BREAKER`, `CUTTER/CANNER`,
  `100% LEAN`, `BONER/BREAKER & CUTTER/CANNER`). `low_price` and
  `high_price` = `None`. The `change` column is ignored.
- IMPS codes repeat by weight bracket (112 x3, 190 x4, 169A x3 ...). Keep
  the bracket in the description; the description is what makes the product
  row unique (`usda_products` is unique on `product_name, report_type`).
- Date comes from the same header line format as the other reports
  (`Agricultural Marketing Service September 04, 2026`).

Fixture: `docs/2026-09-04-cow-report-sample.txt`. Expected result on it:
27 priced rows (see the IMPS table in the findings file), of which 21 carry
an IMPS code and 6 are the codeless 100% LEAN items.

### 3. `database.py` — nothing

`category = 'beef'` is already the fallback for every non-pork type.

### 4. `demo_sync.py` — add the type

`BEEF_REPORT_TYPES = ("daily_afternoon", "branded_beef", "ungraded_beef", "cow_beef")`.
Same for `scripts/load_demo_usda_beef.py` in the Lora_Agents repo, which is
the manual/backfill twin of this file.

### 5. Demo loader — migration 087 in `Lora_Agents-demo-port` (085 supplier hook, 086 stale-key refresh are taken)

File: `companies/demo/catalog_mapping/migrations/087_usda_cow_beef_load.sql`.
Show it to Eshan before applying; project `oyyukfumyeumwgyodmkb`.
Three edits to `public.usda_boxed_beef_load` (current body is in 084):

1. The report_type guard (`need report_type in (daily_afternoon,
   branded_beef, ungraded_beef)`) must accept `cow_beef`.
2. The grade switch: when `v_type = 'cow_beef'`, `v_attrs :=
   '{"grade":"utility"}'` regardless of section. Cow cutting classes are not
   quality grades; the catalog's grade axis is the USDA scale and `utility`
   is the value already used for Whetstone's cow lines (ruling in the beef
   plan, 2026-09-04).
3. Nothing else. `mint_part_cell` mints `{grade: utility}` parts on first
   sight, the 100% LEAN lines fall out as `no IMPS code`, and the
   `catalog_line_map` source becomes `usda:cow_beef` automatically.

Add the row to the schema decisions log in
`docs/plans/2026-09-02-demo-beef-vertical-plan.md` (plain English, dated).

### 6. Demo data fix — Whetstone's three utility ribeyes are in the wrong family

The cow report quotes IMPS **112**, ribeye roll, which the catalog maps to
`protein/beef/rib/ribeye_lip_off`. Whetstone's three "(U)" lines are
"Ribeye Roll ..." — the same thing — but on 2026-09-04 (migration 082) they
were pointed at `ribeye_lip_on {utility}` (part `b95e0780`). Until they move,
the cow quotes land on a different product and the SKUs never see them.

Fix, in the same migration or a follow-up, after Eshan says go:

- mint or find `ribeye_lip_off {grade: utility}`;
- repoint `global.catalog_line_map` (source `whetstone`, codes 68405, 67747,
  69399), `ops.entity_sku` (same codes, tenant
  `fbff3a25-2952-4edb-aa2a-e827bbc27632`) to it;
- delete `b95e0780` once nothing references it.

Also decide the fifth line, 16143 "Flank Steak, Rough C/C COV, Long Prairie":
Long Prairie is a cow packer and "C/C" reads as cutter/canner. If Eshan or
Scott confirms, set its grade to utility; the cow report quotes "Flank, rough"
(no IMPS code, so it needs a category alias on `flank_steak` or its own family
before the loader will place it).

### 7. Deploy

The dev job runs nightly and carries the Demo secrets:

| | |
|---|---|
| Cloud Run job | `usda-scraper-dev`, project `whetstone-477916`, region `us-central1` |
| Image | `us-central1-docker.pkg.dev/whetstone-477916/ai-agents/usda-scraper:dev` |
| Schedule | Cloud Scheduler `usda-scraper-daily-dev`, `0 3 * * *` America/New_York |
| Report list | Hard-coded in the `Dockerfile` ENTRYPOINT — add `cow_beef` there |

Build and push the image the same way the current one was built (`gcloud
builds submit` or a docker build/push to that tag), then
`gcloud run jobs update usda-scraper-dev --image <tag> --region us-central1
--project whetstone-477916`. The nightly run dedupes on `(report_type,
report_date)`, so running a weekly report daily is harmless: it fetches the
PDF and skips six nights out of seven.

Prod (the GitHub Actions workflows under `.github/workflows/`) has no Demo
secrets and is unaffected. Do not add a prod cow workflow unless Whetstone's
own page needs it; their `subprimal_mapping` does not know the cow product
names, so it would only add unused rows to `usda_products`.

### 8. Verify

```bash
# local, scratch tables untouched
python main.py --reports cow_beef --verbose            # writes to the dev branch project
python demo_sync.py --type cow_beef --dry-run
python demo_sync.py --type cow_beef                      # needs DEMO_SUPABASE_URL/KEY
```

Then in Demo:

```sql
select count(*) from global.event_price_observation o
join global.source_document d on d.id = o.source_document_id
where d.source = 'usda:cow_beef';                       -- expect ~21

select s.item_code, p.attrs, count(o.*) quotes
from ops.entity_sku s join global.part p on p.id = s.part_id
left join global.event_price_observation o on o.part_id = p.id
where s.item_code in ('68405','67747','69399','60817')
group by 1,2;                                           -- every row should have quotes
```

And open the ontology-view Price Updates page for Whetstone: the three
ribeye rolls should show a cow price near $7/lb instead of the ~$15/lb
steer stand-in, and the flank near $5.90.

## Out of scope, noted

- The daily cow companion, ams_2455 (5-day rolling cutter cow cutout,
  afternoon). Weekly is enough for now.
- Cow trim and boneless processing beef (ams_2456, ams_2462). Demo has no
  trim families for cow.
- Frozen sections. Zero volume this week; revisit if that changes.
