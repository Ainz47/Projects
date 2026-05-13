# NYC DOB Test Task Results

Collection date: 2026-04-16

Source note: The links below point to the exact official NYC Open Data API queries used to extract each record.

| Borough | Address | Violation # | Type | Issue Date | Status | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Brooklyn | 244 Van Sicklen Street | 26-01042 | Construction | 2026-04-14 | Active | [Official Source](https://data.cityofnewyork.us/resource/3h2n-5cm9.json?$query=select%20boro%2C%20bin%2C%20house_number%2C%20street%2C%20violation_number%2C%20issue_date%2C%20violation_type%2C%20violation_category%2C%20disposition_date%2C%20disposition_comments%2C%20description%20where%20bin%3D%273191322%27%20and%20violation_number%3D%2726-01042%27%20limit%201) |
| Brooklyn | 8424 12 Avenue | 20167 | Immediate Emergency | 2026-04-14 | Active | [Official Source](https://data.cityofnewyork.us/resource/3h2n-5cm9.json?$query=select%20boro%2C%20bin%2C%20house_number%2C%20street%2C%20violation_number%2C%20issue_date%2C%20violation_type%2C%20violation_category%2C%20disposition_date%2C%20disposition_comments%2C%20description%20where%20bin%3D%273164833%27%20and%20violation_number%3D%2720167%27%20limit%201) |
| Brooklyn | 740 East 5 Street | 26-01046 | Construction | 2026-04-14 | Active | [Official Source](https://data.cityofnewyork.us/resource/3h2n-5cm9.json?$query=select%20boro%2C%20bin%2C%20house_number%2C%20street%2C%20violation_number%2C%20issue_date%2C%20violation_type%2C%20violation_category%2C%20disposition_date%2C%20disposition_comments%2C%20description%20where%20bin%3D%273127157%27%20and%20violation_number%3D%2726-01046%27%20limit%201) |
| Bronx | 912 East 219 Street | 26-01049 | Construction | 2026-04-14 | Active | [Official Source](https://data.cityofnewyork.us/resource/3h2n-5cm9.json?$query=select%20boro%2C%20bin%2C%20house_number%2C%20street%2C%20violation_number%2C%20issue_date%2C%20violation_type%2C%20violation_category%2C%20disposition_date%2C%20disposition_comments%2C%20description%20where%20bin%3D%272059020%27%20and%20violation_number%3D%2726-01049%27%20limit%201) |
| Bronx | 3359 Baychester Avenue | 26-01039 | Construction | 2026-04-13 | Active | [Official Source](https://data.cityofnewyork.us/resource/3h2n-5cm9.json?$query=select%20boro%2C%20bin%2C%20house_number%2C%20street%2C%20violation_number%2C%20issue_date%2C%20violation_type%2C%20violation_category%2C%20disposition_date%2C%20disposition_comments%2C%20description%20where%20bin%3D%272065432%27%20and%20violation_number%3D%2726-01039%27%20limit%201) |

## Short Automation Explanation

I would automate this with Python and the official NYC Open Data API:

1. Use the official DOB violations dataset as the primary extraction feed because it returns structured fields and is more reliable than scraping blocked HTML pages.
2. Store the direct official source URL for each record so the extraction remains auditable.
3. Normalize dates, standardize violation types, and dedupe with a composite key of `bin + violation_number`.
4. Push clean rows into Google Sheets or Airtable through their APIs.
5. Flag records with missing dates, malformed addresses, or unclear statuses for manual review.
