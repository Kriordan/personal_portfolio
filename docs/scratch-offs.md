# Scratch-off comparison

`/scratch-offs` requires the existing Flask login. It reads only SQLAlchemy snapshots. Forms, search, sorting and expandable prize tables make no lottery-site requests. State, target, comparison basis and each state's selected prices are remembered in local storage. No ticket purchases, alerts or mobile-native changes are included.

## Operations

```sh
flask --app project db upgrade
flask --app project import-ny-lottery-metadata --dry-run
flask --app project import-ny-lottery-metadata
flask --app project refresh-lottery --state all --dry-run
flask --app project refresh-lottery --state all
```

Heroku Scheduler command: `flask --app project refresh-lottery --state all --scheduled`

Run daily at **13:00 UTC** (09:00 Eastern during daylight saving time, 08:00 otherwise). This is a collection time, not a source publication guarantee. The existing Scheduler add-on is reused. The command runs outside the web process; there is no refresh endpoint or APScheduler registration. `--state ny` refreshes NY only; `--state ct` refreshes CT and the draw panel. `--dry-run` fetches and validates but writes no metadata, snapshots, run receipts or retention cleanup.

PostgreSQL session advisory lock namespace 741938210, key 0 serializes imports and refreshes across dynos. The existing lock helper checks ownership before publication; SQLite locking is only suitable for single-process tests. State and draw publications commit independently. Complete immutable JSON snapshots have unique source/content hashes; a duplicate source version reuses its snapshot. Draw summaries deduplicate unchanged summaries within a UTC day. Last successful check comes from run receipts, separate from source date. Failure receipts never replace a last-good snapshot.

CT requests are sequential and separated by at least two seconds, including retries and the draw panel. Current catalog: 1 listing + 22 eligible details + 2 draw pages. NY uses four requests: metadata version, rows, row count, metadata version. A version change or incomplete result fails the NY publication. HTTP connect/read timeouts are 10/30 seconds, with at most three attempts for connection errors and selected 5xx responses. 403, 429 and challenges stop that host immediately. Retry-After is honored, including a persisted cooldown across subsequent runs. Long delays stop the command instead of sleeping indefinitely. Redirects fail closed.

Source dates or last-success times older than 48 hours remove “Today's picks” and show dated comparisons. The UI separately shows failures, interrupted runs and the most recent Scheduler receipt. Snapshots and receipts are pruned after 90 days, with the latest successful snapshot/receipt kept through prolonged outages.

## Sources and verified NY seed

* NY daily counts: https://data.ny.gov/d/nzqa-7unk (official Socrata resource `nzqa-7unk`). `rowsUpdatedAt` is the source version time. All tier labels, paid/unpaid counts and original totals are checked.
* NY metadata: `project/lottery/data/ny_metadata.json`, schema version 1. Forty $10/$20/$30 games were captured from official browser-rendered game tables on 2026-10-26. Each tier's original count equals its official paid + unpaid count and matches the daily dataset. Published tier odds are retained, not reverse-engineered from rounded overall odds. Provenance links and verification times accompany every game.
* NY end dates: official **Scratch-Off Game Reports as of 10.26.2026.pdf**, linked in every seed record. Eight of the forty still-listed games had announced end dates and are excluded: 1489, 1603, 1609, 1612, 1629, 1646, 1667, 1674. Launch dates absent from the verified sources remain null.
* NY verification holds: 1639 and 1686 have lifetime awards without a verified total award in the captured pages. Game 1688 advertises $3m and a $250K annual installment, while the prize feed says $150K/year for 20 years. These three games are unranked pending verification; no payment term is invented.
* Unknown NY feed entries (including zero-count unreleased placeholders and lower-priced/ended games) remain visible in a separate “awaiting details” list. A feed entry alone does not establish an eligible ticket price or active status.
* CT catalog: https://ctlottery.com/games/scratch-games. Details: `/games/scratch-games/{gameNo}`. Only public HTML is requested, never `/api/` or `/_next/` URLs. The parser decodes embedded Flight JSON and referenced text records without executing scripts. CT `asOf` is a calendar date interpreted at midnight Eastern, conservatively measuring source age.
* CT annuity tables can expose cash-option values in embedded prize data while advertising a larger gross award. Use the advertised award only when both amounts and annuity/cash-option terms occur in the official payment text. The displayed label preserves the payment terms. Unresolved values are unrankable. CT 2099 dates are open-ended sentinels, not actual end dates.
* Powerball and Mega Millions: official CT draw pages. Published odds, base prices, next drawing, annuity and cash estimates are parsed separately. Naive draw times are Eastern; display times use the timezone database.

NY website requests were blocked outside the interactive browser during source research. Daily jobs therefore use Open Data only. **NY status, price, odds and payment terms require occasional browser verification**, including status changes to existing games. Their verification date is displayed with each game; prize data freshness does not imply fresh manual metadata. Automatic imports never guess missing facts.

## Updating metadata

Copy the bundled JSON format, verify facts against the official game page and current end-of-game report, and retain provenance. An import can contain just the changed/new games; other records are preserved. Required fields: numeric-string `game_number`, `name`, eligible integer `price`, `status` (`active`/`ended`), ISO `verified_at`, official HTTPS `url` and `provenance`, optional ISO start/end dates, and nonempty `tiers`. Each tier needs a unique exact daily-feed `source_label`, human-readable `label`, gross integer `amount`, positive `original` count and published `odds_denominator`. An unresolved amount must be null with an explicit game `issue` and remains unranked.

```sh
flask --app project import-ny-lottery-metadata /path/to/reviewed.json --dry-run
flask --app project import-ny-lottery-metadata /path/to/reviewed.json
flask --app project refresh-lottery --state ny
```

All records validate before any write. Refresh joins on game number and exact tier label, and requires the original structure/counts to match. Changed CT original structures are held across runs until reviewed; a maintainer must verify the new official table and clear `structure_hold` in a deliberate reviewed data repair before publication. Do not clear holds merely to restore recommendations.

## Probability model

For tier i, launch probability `p_i` is CT original prize count / original ticket count, or NY 1 / published tier odds. Let `r_i` be unclaimed/original prizes. Let `q` be total unclaimed prizes below $1,000 / total original prizes below $1,000.

`P_est(target) = sum(p_i * r_i for awards >= target) / q`

Original chance is `sum(p_i)` for qualifying tiers. Chance per dollar is `P_est / ticket price`. Ties use lower price, then numerical game number. Amounts are gross advertised awards; annual payments are never used as the full prize. Missing inputs, nonpositive denominators, impossible probabilities, ended games and no qualifying unclaimed prizes do not produce recommendations. Two significant digits are used for odds display; ordering uses unrounded values. This estimates a target-prize chance, not expected profit.

Neither source verifies unsold-ticket counts. Unclaimed prizes may be in already-purchased tickets; claim delays and claim-rate differences can bias the proxy, particularly in older games. The tool has no retailer inventory information.

## Validation

`PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true python -m unittest tests.test_lottery -v`

Saved official fixtures test catalog extraction across split Flight chunks, annuity gross/cash distinctions, referenced payment text, missing fields, ended games, NY exact joins, metadata validation, draw odds and Eastern dates. Hand-worked examples cover $1k/$100k targets, per-ticket/per-dollar ordering, ties, exhausted prizes and invalid inputs. Integration tests cover dry runs, idempotence, locking, source-version changes, truncation, structure changes, partial failure, persistent Retry-After, authentication, stale presentation and page/filter requests with all HTTP disabled.

Implementation validation used the full saved 2026-10-26 NY feed (1,253 tiers / 115 games) and all 22 eligible CT pages. Representative CT #1850: 2,067,660 original tickets, 5 original top prizes, 1 unclaimed, $1m 20-year annuity / $750k cash option. NY #1713: 4 original/unclaimed top prizes, $3m advertised award, published top-tier odds 1 in 3,645,937.50. Calculations use the daily feed's unclaimed counts, not the browser seed's claim counts.
