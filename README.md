# GTM ROI Lab

A small finance agent for a CPG back-office software company. It takes two CSV exports, a CRM deal export and a GTM spend export, and sorts every row into buckets:

- **8 products:** Cash Application, Deductions Management, Auto-Disputes, Trade Promotions, Sales Forecasting, Sales Analytics, Demand Planning, Supply Planning
- **6 industries:** Beauty & Personal Care, Beverage, Food, Health & Wellness, Home Goods, Pet
- **7 GTM channels:** Events, Paid digital, Content & media, Outbound, Partners, Referrals, Inbound organic

From those buckets it shows:

- each product's contribution by industry
- ROI, CAC and payback for each channel and each industry
- the factors behind deal size and sales speed
- a short list of strategy plays

Independent work sample. Not affiliated with or endorsed by Confido. The sample data is synthetic.

## Three ways to run it

**Dashboard (no install).** Open `dist/gtm-roi-lab.html` in a browser and drop in your CSVs. The page loads with sample data.

Labels the rules can't place go to a review list instead of being guessed. You can fix them two ways:

- pick a bucket from the dropdown yourself
- press **Classify with Claude**. Inside claude.ai this uses the viewer's Claude account. On Vercel it uses a server key or the visitor's own key (see below)

**Hosted on Vercel.** The `web/` folder is a ready-to-deploy site: `index.html` plus one serverless function at `api/claude.js`.

1. Push the repo to GitHub, import it in Vercel, and set **Root Directory** to `web`. No build command is needed.
2. Pick a Claude mode:
   - **Bring your own key (default).** Leave `ANTHROPIC_API_KEY` unset. Visitors paste their own key in step 2 of the page.
   - **Server key.** Set `ANTHROPIC_API_KEY` in Vercel → Settings → Environment Variables. Also set `ACCESS_CODE` if the link will be shared, so strangers can't spend your credits.
3. Copy `web/.env.example` to `.env.local` for `vercel dev`. Never commit a real key; `.gitignore` already excludes env files.

**Python pipeline.**

```
python pipeline.py --sales sample_data/sales.csv --spend sample_data/gtm_spend.csv --out output
```

It writes these files to `output/`:

| File | What's in it |
|---|---|
| `sales_bucketed.csv` | each deal with its industry, product and channel buckets |
| `spend_bucketed.csv` | each spend line with its channel bucket |
| `product_industry_arr.csv` | won ARR by product and industry |
| `channel_roi.csv` | ROI, CAC and payback by channel |
| `industry_roi.csv` | the same by industry |
| `needs_review.csv` | labels the rules couldn't place |
| `summary.json` | headline totals |

The dashboard and the pipeline use the same `rules.json`. On the sample data they produce identical numbers.

## How the numbers work

- **ROI multiple** = new ARR × gross margin ÷ spend. This is first-year gross profit per $1 of spend. Gross margin defaults to 75%.
- **CAC** = channel spend ÷ new customers won.
- **Payback** = spend ÷ (new ARR × gross margin ÷ 12), in months.
- **Multi-product deals** are split across products in proportion to list price, so the heatmap adds up to total won ARR.
- **Industry spend:** lines with a `target_industry` count against that industry. All other spend is spread by each industry's share of new opportunities.
- **Expansion deals** count toward product and industry contribution. They are kept out of channel ROI, because no new GTM dollar sourced them.

## Key safety

**Bring-your-own-key mode:**

- The key is held in a JavaScript variable in the open tab, and nowhere else.
- It is never written to localStorage, sessionStorage, cookies, the URL, the page or the console.
- The input box clears as soon as you press **Use key**.
- The key is sent only to `api.anthropic.com`, using Anthropic's `anthropic-dangerous-direct-browser-access` header for browser calls.
- Pressing **Forget key**, or closing the tab, drops it.

**Server-key mode:**

- The key lives only in a Vercel environment variable.
- `api/claude.js` never returns or logs the key, and never logs prompts.
- It accepts only two fixed tasks, each with a fixed model and token cap.
- It rejects cross-origin calls, checks the optional access code in constant time, and rate-limits to 20 calls per minute per IP.

**Both modes:**

- `vercel.json` sets a strict Content-Security-Policy. The page can only talk to itself and `api.anthropic.com`, so even injected script couldn't send a key anywhere else.
- It also sets no-referrer, nosniff and frame-deny headers.
- Claude's output is rendered as text, never HTML.
- Classifications are checked against the allowed bucket lists before they're applied.

Use a key with a monthly spend limit for demos. Before release this was tested in a headless browser with a fake key: the only request carrying it went to `api.anthropic.com`, and nothing showed up in storage, the page or the console.

Models: `claude-haiku-5-5` classifies labels, and `claude-sonnet-5-5` writes the memo. Change them in `MODELS`, in both `dashboard/template.html` and `web/api/claude.js`.

## How the verdicts work

Verdicts are fixed rules on the **ROI multiple**: new ARR × gross margin ÷ spend. That is first-year gross profit per $1 of spend. Claude does not decide them.

| ROI multiple | Channel verdict | Industry verdict | Why |
|---|---|---|---|
| 2× or more | Scale | Grow | Each dollar returns at least two in first-year gross profit, about a 6-month payback. Room to spend more before returns fall below break-even. |
| 1× to 2× | Tune | Tune | Pays back within 12 months, but not by much. Keep it and improve conversion or deal size before adding budget. |
| Under 1× | Fix or cut | Rethink | Doesn't earn back its cost in year one. Fix the funnel or move the money. |

The metric is deliberately conservative. It counts only year one, so it ignores renewals and expansion and understates the long-run value of every channel equally. Attribution is single-touch, from the deal's lead source.

The strategy cards build on the same tables:

| Card | How it's chosen |
|---|---|
| Scale | the highest-ROI channel |
| Fix or cut | the lowest-ROI channel, with a haircut estimate of what half its budget would earn elsewhere |
| Focus aisle | the highest-ROI industry |
| Cross-sell | the product whose share of an industry's ARR is under half its share overall |
| Bundle | average deal size for 3+ products vs 1 |

## Changing the rules

`rules.json` holds the keyword lists and list prices. Rules are checked in order and the first keyword found wins. Add your own CRM's labels there.

After editing, run `python build.py` to re-embed the rules and samples. It rebuilds both `dist/gtm-roi-lab.html` and `web/index.html`.

To regenerate the sample data, run `python scripts/make_sample_data.py 7`. The number is the random seed.

## Input columns

**Sales CSV.**

- Required: `deal_id`, `close_date`, `industry`, `products`, `arr_usd`, `stage` (Closed Won / Closed Lost), `lead_source`
- Optional: `created_date`, `deal_type` (New / Expansion), `customer`

**Spend CSV.**

- Required: `date`, `amount_usd`, and at least one of `vendor`, `description` or `gl_account`
- Optional: `target_industry`

The dashboard also recognises common aliases, such as `amount`, `ACV`, `source` and `segment`.
