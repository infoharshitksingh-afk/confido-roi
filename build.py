"""Embed rules.json and the sample CSVs into the dashboard so it ships as one HTML file."""
import os
H = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(H, "dashboard/template.html")).read()
t = t.replace("/*RULES*/", open(os.path.join(H, "rules.json")).read())
t = t.replace("/*SALES*/", open(os.path.join(H, "sample_data/sales.csv")).read())
t = t.replace("/*SPEND*/", open(os.path.join(H, "sample_data/gtm_spend.csv")).read())
os.makedirs(os.path.join(H, "dist"), exist_ok=True)
open(os.path.join(H, "dist/gtm-roi-lab.html"), "w").write(t)
# Vercel deploy copy: a full document so it works as a standalone page
page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
        "<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style></head><body>" + t + "</body></html>")
open(os.path.join(H, "web/index.html"), "w").write(page)
print("built dist/gtm-roi-lab.html and web/index.html", len(t)//1024, "KB")
