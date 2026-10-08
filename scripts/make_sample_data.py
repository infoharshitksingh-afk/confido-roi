"""Generate synthetic, deliberately messy sales and GTM spend CSVs for the demo.
All numbers are made up. Nothing here is Confido data."""
import csv, random, datetime as dt, math, os
import sys
random.seed(int(sys.argv[1]) if len(sys.argv)>1 else 7)
OUT = os.path.join(os.path.dirname(__file__), "..", "sample_data")

PRICE = {"Deductions Management":24000,"Cash Application":14000,"Auto-Disputes":12000,"Trade Promotions":20000,
         "Sales Forecasting":12000,"Sales Analytics":9000,"Demand Planning":16000,"Supply Planning":12000}
MODS = list(PRICE)
IND = {"Food":.28,"Beverage":.25,"Health & Wellness":.15,"Beauty & Personal Care":.13,"Home Goods":.09,"Pet":.10}
# product affinity by industry (relative weights per module, same order as MODS)
AFF = {
 "Food":[5,3,3,4,2,2,3,2], "Beverage":[5,3,3,5,2,2,2,1], "Health & Wellness":[4,2,2,2,2,2,4,3],
 "Beauty & Personal Care":[2,4,1,1,4,3,2,2], "Home Goods":[4,4,3,2,1,1,2,2], "Pet":[3,2,2,4,4,2,2,1]}
CYC = {"Food":55,"Beverage":50,"Health & Wellness":60,"Beauty & Personal Care":40,"Home Goods":65,"Pet":45}
# channel: (deal share, win rate, ARR multiplier)
CH = {"Events":(.22,.32,1.35),"Paid digital":(.18,.14,.70),"Content & media":(.12,.22,.90),
      "Outbound":(.18,.16,1.00),"Partners":(.12,.38,1.15),"Referrals":(.10,.55,1.25),"Inbound organic":(.08,.30,.80)}

MESSY_IND = {
 "Food":["Food","Food & Snacks","snacks","Packaged food","FOOD","Frozen foods","Pantry / grocery"],
 "Beverage":["Beverage","Bev","beverages","Drinks","Functional soda","Spirits & RTD","Coffee/tea"],
 "Health & Wellness":["Health & Wellness","Supplements","vitamins","Wellness","Sports nutrition"],
 "Beauty & Personal Care":["Beauty","Personal care","Skincare","Beauty/PC","Hair care","Deodorant & soap"],
 "Home Goods":["Home goods","Household","Cleaning","Home & kitchen","Paper goods"],
 "Pet":["Pet","Pet food","pet care","Pet treats"]}
UNMAPPED_IND = ["Multi-category","Baby & kids","Foodservice"]
MESSY_MOD = {
 "Deductions Management":["Deductions","deductions mgmt","Deduction management","DM"],
 "Cash Application":["Cash App","cash application","Cash-app","AR cash app"],
 "Auto-Disputes":["Auto disputes","auto-dispute","Disputes automation"],
 "Trade Promotions":["TPM","Trade promo","trade promotions","Trade spend planning"],
 "Sales Forecasting":["Forecasting","sales forecast","Sales Forecasting"],
 "Sales Analytics":["Sales analytics","Analytics","POS analytics"],
 "Demand Planning":["Demand planning","demand plan","DP"],
 "Supply Planning":["Supply planning","supply plan","Production planning"]}
SEP = [" + ", "; ", ", ", " & ", " / "]
MESSY_SRC = {
 "Events":["Expo West 2026","Natural Products Expo West","Newtopia Now","BevNET Live","NOSH Live","Indie Beauty Expo","SuperZoo","Trade show"],
 "Paid digital":["LinkedIn Ads","linkedin paid","Google Ads","Paid search","Meta ads"],
 "Content & media":["NOSH webinar","Podcast sponsorship","Taste Radio podcast","Newsletter sponsor","Blog / content"],
 "Outbound":["Outbound - SDR","Cold email","SDR outbound","Apollo sequence","Cold call"],
 "Partners":["Broker partner","Accounting firm partner","NetSuite partner","Fractional CFO partner","Distributor referral"],
 "Referrals":["Customer referral","Investor intro","Referral - customer","Founder network"],
 "Inbound organic":["Organic / website","Website demo request","SEO","Inbound - direct"]}
UNMAPPED_SRC = ["Other","Board member intro","Webinar w/ partner"]
BRANDS = ["Sunny","Peak","Wildfern","Meadow","Lark","Golden","Hearth","Oak","Bright","Cedar","Field","Coast","Maple","Bold","Willow",
          "North","Fresh","Pebble","Clever","Juniper"]
NOUNS = ["Sips","Snacks","Pantry","Paws","Glow","Roots","Harvest","Kitchen","Labs","Botanics","Co.","Brands","Provisions",
         "Naturals","Goods","Tonic","Bites","Supply","Wellness","Home"]

def wpick(weights):
    keys=list(weights); tot=sum(weights.values()); r=random.random()*tot; a=0
    for k in keys:
        a+=weights[k]
        if r<=a: return k
    return keys[-1]

def date_between(a,b):
    return a+dt.timedelta(days=random.randint(0,(b-a).days))

start, end = dt.date(2026,1,1), dt.date(2026,9,30)
rows=[]; used=set(); n=0
def customer():
    while True:
        c=f"{random.choice(BRANDS)} {random.choice(NOUNS)}"
        if c not in used: used.add(c); return c

def mods_for(ind):
    k=wpick({1:35,2:30,3:20,4:10,8:5})
    if k==8: return MODS[:]
    w=dict(zip(MODS,AFF[ind])); out=[]
    while len(out)<k:
        m=wpick({x:w[x] for x in MODS if x not in out}); out.append(m)
    return out

def messy_products(ms):
    if len(ms)==8 and random.random()<.7: return random.choice(["Full platform","All modules","Full suite"])
    if random.random()<.03: return random.choice(["S&OP bundle","Retail data add-on"])
    return random.choice(SEP).join(random.choice(MESSY_MOD[m]) for m in ms)

customers_won=[]
for i in range(380):
    ind=wpick(IND); ch=wpick({k:v[0] for k,v in CH.items()})
    share,win,mult=CH[ch]
    if ind in ("Food","Beverage") and ch=="Partners": win+=.12
    if ind=="Pet" and ch=="Events": win+=.10
    ms=mods_for(ind)
    size=math.exp(random.gauss(0,.35))
    disc=.9 if len(ms)>=3 else 1.0
    arr=round(sum(PRICE[m] for m in ms)*size*mult*disc/500)*500
    created=date_between(start, end-dt.timedelta(days=20))
    cyc=int(CYC[ind]+len(ms)*8+random.gauss(0,12)); cyc=max(14,cyc)
    close=created+dt.timedelta(days=cyc)
    if close>end: continue
    won=random.random()<win
    n+=1
    cust=customer()
    ind_raw = random.choice(UNMAPPED_IND) if random.random()<.03 else random.choice(MESSY_IND[ind])
    src_raw = random.choice(UNMAPPED_SRC) if random.random()<.03 else random.choice(MESSY_SRC[ch])
    rows.append({"deal_id":f"D-{1000+n}","created_date":created.isoformat(),"close_date":close.isoformat(),
        "customer":cust,"industry":ind_raw,"products":messy_products(ms),"arr_usd":arr,
        "stage":"Closed Won" if won else "Closed Lost","deal_type":"New","lead_source":src_raw})
    if won: customers_won.append((cust,ind_raw,ms,close))

# expansions from won customers
for cust,ind_raw,ms,close in random.sample(customers_won, min(45,len(customers_won))):
    rest=[m for m in MODS if m not in ms]
    if not rest: continue
    add=random.sample(rest, k=1 if random.random()<.7 else min(2,len(rest)))
    d=close+dt.timedelta(days=random.randint(40,160))
    if d>end: continue
    n+=1
    arr=round(sum(PRICE[m] for m in add)*math.exp(random.gauss(0,.25))/500)*500
    rows.append({"deal_id":f"D-{1000+n}","created_date":(d-dt.timedelta(days=25)).isoformat(),"close_date":d.isoformat(),
        "customer":cust,"industry":ind_raw,"products":random.choice(SEP).join(random.choice(MESSY_MOD[m]) for m in add),
        "arr_usd":arr,"stage":"Closed Won","deal_type":random.choice(["Expansion","Upsell","expansion"]),
        "lead_source":random.choice(["Existing customer","CSM upsell","Account management"])})

rows.sort(key=lambda r:r["close_date"])
with open(os.path.join(OUT,"sales.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# GTM spend: monthly lines
SPEND=[]
def add(month,vendor,desc,amt,gl,ind=""):
    SPEND.append({"date":dt.date(2026,month,random.randint(3,26)).isoformat(),"vendor":vendor,"description":desc,
                  "amount_usd":round(amt,2),"gl_account":gl,"target_industry":ind})
for m in range(1,10):
    add(m,"LinkedIn","LinkedIn Campaign Manager - "+dt.date(2026,m,1).strftime("%b"),random.uniform(26000,34000),random.choice(["6100 Advertising","Paid Social","6100-ADV"]))
    add(m,"Google","Google Ads search",random.uniform(14000,20000),random.choice(["6100 Advertising","Paid search"]))
    add(m,"Apollo.io","Apollo seats + data credits",random.uniform(5500,7000),random.choice(["6400 Sales tools","Software - sales"]))
    add(m,"Payroll allocation","SDR team cost allocation (GTM)",random.uniform(48000,52000),"6500 Sales comp")
    add(m,"NOSH","NOSH newsletter / webinar sponsorship",random.uniform(6000,9000),random.choice(["6200 Content","Sponsorships"]),"Food")
    add(m,"Taste Radio","Podcast ad read",random.uniform(4500,6500),"Sponsorships","Beverage")
    add(m,"Webflow / SEO agency","Website + SEO retainer",random.uniform(10000,13000),random.choice(["6300 Web","Marketing - web"]))
    add(m,"Partner program","Accounting firm + broker co-marketing",random.uniform(15000,22000),"6600 Partnerships")
    add(m,"Referral program","Customer & investor referral payouts",random.uniform(7000,11000),"6600 Referrals")
    if m in (3,6,9): add(m,"Agency","Agency retainer - Q"+str((m-1)//3+1),random.uniform(18000,24000),"6900 Misc marketing")
add(3,"New Hope Network","Expo West booth, build & drayage",168000,"6700 Events")
add(3,"Travel","Expo West travel & hotels (team of 9)",41500,"Travel - events")
add(5,"Newtopia Now","Booth + sponsorship",72000,"6700 Events")
add(4,"BevNET Live","BevNET Live sponsor package",38000,"6700 Events","Beverage")
add(6,"NOSH Live","NOSH Live sponsorship",34000,"6700 Events","Food")
add(8,"SuperZoo","SuperZoo booth",46000,"6700 Events","Pet")
add(9,"Indie Beauty Expo","IBE booth + samples",29000,"6700 Events","Beauty & Personal Care")
add(5,"Brand agency","Brand refresh project",36000,"6900 Misc marketing")
add(7,"Swag Co","Branded cans & swag for events",12500,"6700 Events")
SPEND.sort(key=lambda r:r["date"])
with open(os.path.join(OUT,"gtm_spend.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(SPEND[0])); w.writeheader(); w.writerows(SPEND)
print(len(rows),"sales rows;",len(SPEND),"spend rows; spend total",round(sum(r['amount_usd'] for r in SPEND)))
