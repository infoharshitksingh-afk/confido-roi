"""CPG GTM ROI pipeline.

Reads a sales CSV and a GTM spend CSV, sorts every row into product, industry and
channel buckets using rules.json, and writes bucketed files plus ROI tables.

    python pipeline.py --sales sample_data/sales.csv --spend sample_data/gtm_spend.csv --out output

Rows the rules cannot place are written to output/needs_review.csv instead of being guessed.
Fill in their bucket by hand (or with the dashboard's "Classify with Claude") and re-run.
"""
import argparse, csv, json, os, re, statistics
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
UNASSIGNED = "Unassigned"


def load_rules(path=None):
    with open(path or os.path.join(HERE, "rules.json")) as f:
        return json.load(f)


def first_match(text, rules):
    t = text.lower()
    for bucket, words in rules:
        if any(w in t for w in words):
            return bucket
    return None


def bucket_industry(raw, R):
    t = (raw or "").lower().strip()
    if not t or any(x in t for x in R["industry_exclude"]):
        return None
    return first_match(t, R["industry_rules"])


def bucket_products(raw, R):
    """Return a list of product buckets, or None if any part is unrecognised."""
    t = (raw or "").lower().strip()
    if not t or any(x in t for x in R["product_exclude"]):
        return None
    if any(x in t for x in R["product_full_platform"]):
        return list(R["products"])
    out = []
    for tok in [x.strip() for x in re.split(r"[+;,&/]", t) if x.strip()]:
        hit = None
        for bucket, words in R["product_rules"]:
            for w in words:
                if (tok == w) if w in R["product_exact_tokens"] else (w in tok):
                    hit = bucket
                    break
            if hit:
                break
        if not hit:
            return None
        if hit not in out:
            out.append(hit)
    return out or None


def bucket_lead_source(raw, R):
    t = (raw or "").lower()
    if any(x in t for x in R["expansion_sources"]):
        return "Expansion"
    return first_match(t, R["lead_source_rules"])


def bucket_spend(row, R):
    text = " ".join([row.get("vendor", ""), row.get("description", ""), row.get("gl_account", "")])
    return first_match(text, R["spend_rules"])


def allocate(arr, products, R):
    """Split a deal's ARR across its products in proportion to list price."""
    w = {p: R["list_price_usd"][p] for p in products}
    tot = sum(w.values())
    return {p: arr * w[p] / tot for p in products}


def run(sales_rows, spend_rows, R, gross_margin=0.75):
    review = []
    deals = []
    for r in sales_rows:
        ind = bucket_industry(r.get("industry"), R)
        prods = bucket_products(r.get("products"), R)
        ch = bucket_lead_source(r.get("lead_source"), R)
        for field, val in (("industry", ind), ("products", prods), ("lead_source", ch)):
            if val is None:
                review.append({"file": "sales", "source_row": r.get("source_row", ""), "id": r["deal_id"], "reference": r["deal_id"],
                               "field": field, "raw_value": r.get(field, ""), "amount_usd": r.get("arr_usd", ""), "bucket": ""})
        is_exp = (r.get("deal_type", "").strip().lower() in ("expansion", "upsell")) or ch == "Expansion"
        deals.append({**r,
                      "industry_bucket": ind or UNASSIGNED,
                      "product_buckets": "|".join(prods) if prods else UNASSIGNED,
                      "channel_bucket": ch or UNASSIGNED,
                      "is_won": r.get("stage", "").strip().lower() == "closed won",
                      "is_expansion": is_exp,
                      "arr": float(r["arr_usd"])})

    spend = []
    for i, r in enumerate(spend_rows):
        ch = bucket_spend(r, R)
        if ch is None:
            review.append({"file": "spend", "source_row": r.get("source_row", ""), "id": f"S-{i+1}", "reference": r.get("reference", ""),
                           "field": "channel", "raw_value": f'{r.get("vendor","")} | {r.get("description","")}', "amount_usd": r.get("amount_usd", ""), "bucket": ""})
        ti = (r.get("target_industry") or "").strip()
        spend.append({**r, "row_id": f"S-{i+1}", "channel_bucket": ch or UNASSIGNED,
                      "industry_bucket": bucket_industry(ti, R) if ti else "", "amount": float(r["amount_usd"])})

    won = [d for d in deals if d["is_won"]]
    new_won = [d for d in won if not d["is_expansion"]]
    new_opps = [d for d in deals if not d["is_expansion"]]

    # product x industry ARR (won, new + expansion)
    matrix = defaultdict(float)
    for d in won:
        prods = d["product_buckets"].split("|") if d["product_buckets"] != UNASSIGNED else [UNASSIGNED]
        alloc = allocate(d["arr"], prods, R) if prods != [UNASSIGNED] else {UNASSIGNED: d["arr"]}
        for p, v in alloc.items():
            matrix[(p, d["industry_bucket"])] += v

    # channel ROI
    spend_by_ch = defaultdict(float)
    for s in spend:
        spend_by_ch[s["channel_bucket"]] += s["amount"]
    ch_rows = []
    for ch in R["channels"]:
        opps = [d for d in new_opps if d["channel_bucket"] == ch]
        w = [d for d in opps if d["is_won"]]
        arr = sum(d["arr"] for d in w)
        sp = spend_by_ch.get(ch, 0.0)
        gp = arr * gross_margin
        ch_rows.append({"channel": ch, "spend": round(sp, 2), "opportunities": len(opps), "won": len(w),
                        "win_rate": round(len(w) / len(opps), 4) if opps else 0,
                        "new_arr": round(arr, 2), "avg_deal": round(arr / len(w), 2) if w else 0,
                        "cac": round(sp / len(w), 2) if w else None,
                        "roi_multiple": round(gp / sp, 3) if sp else None,
                        "payback_months": round(sp / (gp / 12), 2) if gp else None})

    # industry ROI: tagged spend to its industry, the rest spread by share of new opportunities
    opp_share = defaultdict(float)
    for d in new_opps:
        opp_share[d["industry_bucket"]] += 1
    tot_opps = sum(opp_share[i] for i in R["industries"]) or 1
    ind_spend = defaultdict(float)
    for s in spend:
        if s["industry_bucket"] in R["industries"]:
            ind_spend[s["industry_bucket"]] += s["amount"]
        else:
            for i in R["industries"]:
                ind_spend[i] += s["amount"] * opp_share[i] / tot_opps
    ind_rows = []
    for i in R["industries"]:
        w = [d for d in new_won if d["industry_bucket"] == i]
        opps = [d for d in new_opps if d["industry_bucket"] == i]
        arr = sum(d["arr"] for d in w)
        exp = sum(d["arr"] for d in won if d["is_expansion"] and d["industry_bucket"] == i)
        cyc = [(date.fromisoformat(d["close_date"]) - date.fromisoformat(d["created_date"])).days for d in w]
        sp = ind_spend[i]
        ind_rows.append({"industry": i, "allocated_spend": round(sp, 2), "opportunities": len(opps), "won": len(w),
                         "win_rate": round(len(w) / len(opps), 4) if opps else 0, "new_arr": round(arr, 2),
                         "expansion_arr": round(exp, 2), "median_cycle_days": statistics.median(cyc) if cyc else None,
                         "roi_multiple": round(arr * gross_margin / sp, 3) if sp else None})

    total_spend = sum(s["amount"] for s in spend)
    new_arr = sum(d["arr"] for d in new_won)
    summary = {"new_arr": round(new_arr, 2), "expansion_arr": round(sum(d["arr"] for d in won if d["is_expansion"]), 2),
               "gtm_spend": round(total_spend, 2), "new_customers": len(new_won),
               "blended_cac": round(total_spend / len(new_won), 2) if new_won else None,
               "blended_roi": round(new_arr * gross_margin / total_spend, 3) if total_spend else None,
               "payback_months": round(total_spend / (new_arr * gross_margin / 12), 2) if new_arr else None,
               "rows_needing_review": len(review)}
    return deals, spend, matrix, ch_rows, ind_rows, summary, review


def read_csv(path):
    """Rows as dicts. source_row is the spreadsheet row number (header = row 1), so review rows can be found in Excel."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        recs = list(csv.reader(f))
    filled = [(n, r) for n, r in enumerate(recs, start=1) if any(x.strip() for x in r)]
    if not filled:
        return []
    head = filled[0][1]
    return [{**{h: (r[i] if i < len(r) else "") for i, h in enumerate(head)}, "source_row": n} for n, r in filled[1:]]


def write_csv(path, rows, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sales", required=True)
    ap.add_argument("--spend", required=True)
    ap.add_argument("--rules", default=None)
    ap.add_argument("--gross-margin", type=float, default=0.75)
    ap.add_argument("--out", default="output")
    a = ap.parse_args()
    R = load_rules(a.rules)
    deals, spend, matrix, ch_rows, ind_rows, summary, review = run(read_csv(a.sales), read_csv(a.spend), R, a.gross_margin)
    os.makedirs(a.out, exist_ok=True)
    write_csv(os.path.join(a.out, "sales_bucketed.csv"), deals)
    write_csv(os.path.join(a.out, "spend_bucketed.csv"), spend)
    write_csv(os.path.join(a.out, "channel_roi.csv"), ch_rows)
    write_csv(os.path.join(a.out, "industry_roi.csv"), ind_rows)
    write_csv(os.path.join(a.out, "needs_review.csv"), review)
    prods = R["products"] + [UNASSIGNED]
    inds = R["industries"] + [UNASSIGNED]
    write_csv(os.path.join(a.out, "product_industry_arr.csv"),
              [{"product": p, **{i: round(matrix.get((p, i), 0), 2) for i in inds}} for p in prods], ["product"] + inds)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
