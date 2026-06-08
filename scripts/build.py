import pandas as pd
from datetime import datetime, timedelta
import sys, os, base64, io

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'callbacks.csv')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'index.html')

PRIORITY = ['AWAITING PAC', 'AWAITING DD', 'AWAITING SIGN']
HIGH = ['QUOTED VERBAL', 'QUOTED EMAIL', 'QUOTED']

def stage_short(s):
    m = {'CUSTOMER REQUESTED':'Cust. req.','NOT ELIGIBLE - PIPELINED':'Not eligible',
         'QUOTED VERBAL':'Qtd verbal','QUOTED EMAIL':'Qtd email',
         'AWAITING PAC':'Awaiting PAC','AWAITING DD':'Awaiting DD',
         'AWAITING SIGN':'Awaiting Sign','QUOTED':'Quoted'}
    return m.get(s, s.title())

def dot_color(s):
    if s in PRIORITY: return '#f87171'
    if s in HIGH: return '#EF9F27'
    return '#333'

def pill_class(s):
    if s in PRIORITY: return 'p-pri'
    if s in HIGH: return 'p-hi'
    return 'p-nm'

def initials(name):
    return ''.join(w[0] for w in str(name).split())[:2].upper()

def read_csv_smart(path):
    """Read CSV handling base64 encoded content from Power Automate"""
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        raw = f.read().strip()
    # Try base64 decode first
    try:
        decoded = base64.b64decode(raw).decode('utf-8-sig')
        # Check if decoded looks like a CSV (has commas and newlines)
        if ',' in decoded and '\n' in decoded:
            print("Decoded base64 content successfully")
            return pd.read_csv(io.StringIO(decoded))
    except Exception:
        pass
    # Fall back to reading as plain CSV
    print("Reading as plain CSV")
    return pd.read_csv(path, encoding='utf-8-sig')

def build():
    try:
        df = read_csv_smart(CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}"); sys.exit(1)

    print(f"Columns found: {df.columns.tolist()}")
    df.columns = df.columns.str.strip()
    df['callback_date'] = pd.to_datetime(df['callback_date'], dayfirst=True, errors='coerce')
    df['last_call_date'] = pd.to_datetime(df['last_call_date'], dayfirst=True, errors='coerce')
    df['Call Back Stage'] = df['Call Back Stage'].str.strip().str.upper()

    today = pd.Timestamp(datetime.now().date())
    week_start = today - timedelta(days=today.weekday())
    this_week_days = [week_start + timedelta(days=i) for i in range(5)]
    next_week_days = [week_start + timedelta(days=i+7) for i in range(5)]

    def day_data(d):
        day_df = df[df['callback_date'].dt.date == d.date()]
        stages = day_df['Call Back Stage'].value_counts().to_dict()
        sorted_stages = sorted(stages.items(), key=lambda x:(0 if x[0] in PRIORITY else 1 if x[0] in HIGH else 2,-x[1]))
        return {'label':d.strftime('%a %d %b'),'date_obj':d,'total':len(day_df),'stages':sorted_stages,'is_today':d.date()==today.date()}

    this_week = [day_data(d) for d in this_week_days]
    next_week = [day_data(d) for d in next_week_days]

    today_df = df[df['callback_date'].dt.date == today.date()].copy()
    today_df['_pri'] = today_df['Call Back Stage'].apply(lambda s: 0 if s in PRIORITY else 1)
    today_df = today_df.sort_values(['_pri','callback_date'])

    agent_map = {}
    for _, row in today_df.iterrows():
        ag = str(row.get('Agent Name','')).strip()
        if not ag or ag=='nan': continue
        if ag not in agent_map: agent_map[ag]=[]
        agent_map[ag].append(row)

    total_today = len(today_df)
    active_agents = len(agent_map)
    priority_today = int((today_df['Call Back Stage'].isin(PRIORITY)).sum())
    quoted_verbal = int((today_df['Call Back Stage']=='QUOTED VERBAL').sum())
    quoted_email = int((today_df['Call Back Stage']=='QUOTED EMAIL').sum())
    total_next_week = sum(d['total'] for d in next_week)
    updated_at = (datetime.now() + timedelta(hours=1)).strftime('%d %b %Y %H:%M')
    today_label = today.strftime('%A %d %B %Y')

    def week_strip_html(days):
        html = ''
        for d in days:
            past = d['date_obj'].date() < today.date()
            cls = 'dc tod' if d['is_today'] else ('dc dim' if past else 'dc')
            lbl_cls = 'dc-lbl tl' if d['is_today'] else 'dc-lbl'
            lbl_text = f"{d['label']} — today" if d['is_today'] else d['label']
            n_col = ' style="color:#2a2a2a"' if past else ''
            html += f'<div class="{cls}"><div class="{lbl_cls}">{lbl_text}</div>'
            html += f'<div class="dc-n"{n_col}>{d["total"] if d["total"]>0 else "—"}</div>'
            for stage,count in d['stages']:
                pri_cls = ' pri' if stage in PRIORITY else ''
                html += f'<div class="sl{pri_cls}"><span class="dot" style="background:{dot_color(stage)}"></span><span class="sn">{stage_short(stage)}</span><span class="sc">{count}</span></div>'
            html += '</div>'
        return html

    def agent_cards_html():
        sorted_agents = sorted(agent_map.items(),key=lambda x:(0 if any(r['Call Back Stage'] in PRIORITY for r in x[1]) else 1,-len(x[1])))
        html = ''
        for name,rows in sorted_agents:
            has_pri = any(r['Call Back Stage'] in PRIORITY for r in rows)
            by_st = {}
            for r in rows:
                s=r['Call Back Stage']; by_st[s]=by_st.get(s,0)+1
            sorted_st = sorted(by_st.items(),key=lambda x:(0 if x[0] in PRIORITY else 1 if x[0] in HIGH else 2))
            pri_badge = '<span class="pb">priority</span>' if has_pri else ''
            html += f'<div class="ag{"  has-pri" if has_pri else ""}"><div class="ag-hd"><div class="av">{initials(name)}</div><div><div class="ag-nm">{name}{pri_badge}</div><div class="ag-ct">{len(rows)} callback{"s" if len(rows)!=1 else ""} today</div></div></div><div>'
            for s,c in sorted_st:
                pri_cls = ' pri' if s in PRIORITY else ''
                html += f'<div class="ag-row"><span class="ag-sn{pri_cls}"><span style="width:5px;height:5px;border-radius:50%;flex-shrink:0;display:inline-block;background:{dot_color(s)}"></span>{stage_short(s)}</span><span class="ag-sc{pri_cls}">{c}</span></div>'
            html += '</div></div>'
        return html

    def queue_rows_html():
        html = ''
        for _,row in today_df.iterrows():
            s = row['Call Back Stage']
            is_pri = s in PRIORITY
            t = row['callback_date'].strftime('%H:%M') if pd.notna(row['callback_date']) else '—'
            lc = row['last_call_date'].strftime('%d %b') if pd.notna(row['last_call_date']) else '—'
            ag = str(row.get('Agent Name','')).strip()
            ag_short = ' '.join(w[0]+'.' if i==0 else w for i,w in enumerate(ag.split()))
            co = str(row.get('CompanyName','')).strip()[:40]
            ph = str(row.get('Callback Number','')).strip()
            lead_id = str(row.get('lead_id','')).strip()
            tr_cls = ' class="pr"' if is_pri else ''
            tc_cls = ' pr' if is_pri else ''
            callback_time = row['callback_date'].strftime('%H:%M') if pd.notna(row['callback_date']) else ''
            html += f'<tr{tr_cls} data-time="{callback_time}" data-pri="{"1" if is_pri else "0"}"><td><span class="tc{tc_cls}">{t}</span></td><td style="color:#444;font-size:11px;font-family:\'DM Mono\',monospace">{lead_id}</td><td>{co}</td><td><span class="pill {pill_class(s)}">{stage_short(s)}</span></td><td style="color:#666">{ag_short}</td><td style="font-family:\'DM Mono\',monospace;font-size:11px;color:#444">{ph}</td><td style="font-size:11px;color:#444">{lc}</td></tr>'
        return html

    agent_list = sorted(agent_map.keys())
    agent_options = ''.join(f'<option value="{a}">{a}</option>' for a in agent_list)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="3600">
<title>Callback Wallboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#060608;min-height:100vh;font-family:'Barlow',sans-serif;color:#e0e0e0}}
body::before{{content:'';position:absolute;top:-300px;left:50%;transform:translateX(-50%);width:1000px;height:1000px;border-radius:50%;border:1px solid rgba(0,200,255,.12);box-shadow:0 0 0 80px rgba(0,200,255,.05),0 0 0 160px rgba(0,200,255,.04),0 0 0 260px rgba(0,200,255,.025),0 0 0 380px rgba(0,200,255,.015);background:radial-gradient(ellipse at center,rgba(0,200,255,.05) 0%,transparent 60%);pointer-events:none;z-index:0}}
html{{position:relative}}
.wrap{{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:1.5rem 2rem 4rem}}
nav{{display:flex;align-items:center;justify-content:space-between;padding-bottom:1.5rem;border-bottom:1px solid rgba(255,255,255,.06);margin-bottom:3rem}}
.nav-brand{{font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:800;letter-spacing:-.01em;color:#fff}}
.nav-brand span{{color:#00c8ff}}
.nav-right{{display:flex;align-items:center;gap:8px}}
.live-pill{{display:flex;align-items:center;gap:7px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:30px;padding:5px 14px;font-size:11px;color:#888;font-family:'DM Mono',monospace}}
.live-dot{{width:7px;height:7px;border-radius:50%;background:#00e5a0;animation:blink 2s infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.date-pill{{background:rgba(0,200,255,.1);border:1px solid rgba(0,200,255,.25);border-radius:30px;padding:5px 14px;font-size:11px;color:#00c8ff;font-family:'DM Mono',monospace}}
.updated{{font-size:10px;color:#444;font-family:'DM Mono',monospace}}
.hero{{margin-bottom:2.5rem}}
.hero-sub{{font-size:11px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:#444;margin-bottom:.5rem}}
.hero h1{{font-family:'Barlow Condensed',sans-serif;font-size:56px;font-weight:800;line-height:.95;letter-spacing:-.02em;text-transform:uppercase}}
.hero h1 .w{{color:#fff}}.hero h1 .c{{color:#00c8ff}}
.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:2.5rem}}
.mc{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:18px 20px;position:relative;overflow:hidden;transition:border-color .2s,background .2s}}
.mc:hover{{background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.12)}}
.mc::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:var(--c)}}
.mc.c1{{--c:#EF9F27}}.mc.c2{{--c:#00c8ff}}
#overdue-card{{--c:#fb923c}}
#overdue-card .mc-val{{color:#fb923c}}.mc.c3{{--c:#f87171}}.mc.c4{{--c:#a78bfa}}.mc.c5{{--c:#00e5a0}}.mc.c6{{--c:#60a5fa}}
.mc-lbl{{font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#555;margin-bottom:10px}}
.mc-val{{font-family:'Barlow Condensed',sans-serif;font-size:44px;font-weight:800;line-height:1;letter-spacing:-.01em}}
.mc.c1 .mc-val{{color:#EF9F27}}.mc.c2 .mc-val{{color:#00c8ff}}.mc.c3 .mc-val{{color:#f87171}}
.mc.c4 .mc-val{{color:#a78bfa}}.mc.c5 .mc-val{{color:#00e5a0}}.mc.c6 .mc-val{{color:#60a5fa}}
.sec-head{{display:flex;align-items:center;gap:12px;margin:2.5rem 0 .75rem}}
.sec-head-lbl{{font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#444}}
.sec-head::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,.06)}}
.week-strip{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:.5rem}}
.dc{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:10px 12px;transition:border-color .2s}}
.dc:hover{{border-color:rgba(255,255,255,.12)}}
.dc.tod{{border-color:rgba(0,200,255,.4);background:rgba(0,200,255,.04)}}
.dc.dim{{opacity:.3;pointer-events:none}}
.dc-lbl{{font-size:9px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#444;margin-bottom:4px}}
.dc-lbl.tl{{color:#00c8ff}}
.dc-n{{font-family:'Barlow Condensed',sans-serif;font-size:36px;font-weight:800;color:#fff;line-height:1;margin-bottom:6px}}
.sl{{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#444;padding:1.5px 0;gap:4px}}
.sl .dot{{width:5px;height:5px;border-radius:50%;flex-shrink:0}}
.sl .sn{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sl .sc{{font-weight:500;color:#666;font-family:'DM Mono',monospace;font-size:10px}}
.sl.pri .sn,.sl.pri .sc{{color:#f87171;font-weight:600}}
.tabs{{display:flex;gap:6px;margin-bottom:1rem}}
.tb{{padding:7px 18px;border-radius:6px;border:1px solid rgba(255,255,255,.1);background:transparent;cursor:pointer;font-size:12px;font-weight:600;letter-spacing:.06em;color:#555;font-family:'Barlow',sans-serif;text-transform:uppercase;transition:all .15s}}
.tb.on{{background:rgba(255,255,255,.06);color:#fff;border-color:rgba(255,255,255,.2)}}
.ag-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:8px;margin-bottom:.5rem}}
.ag{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 14px;transition:border-color .2s}}
.ag:hover{{border-color:rgba(255,255,255,.1)}}
.ag.has-pri{{border-color:rgba(248,113,113,.25)}}
.ag-hd{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
.av{{width:32px;height:32px;border-radius:50%;background:rgba(0,200,255,.1);border:1px solid rgba(0,200,255,.2);display:flex;align-items:center;justify-content:center;font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:700;color:#00c8ff;flex-shrink:0;letter-spacing:.04em}}
.ag-nm{{font-size:13px;font-weight:600;color:#ddd;line-height:1.2}}
.ag-ct{{font-size:11px;color:#444;font-family:'DM Mono',monospace}}
.pb{{display:inline-block;background:rgba(248,113,113,.15);color:#f87171;font-size:9px;padding:1px 7px;border-radius:10px;font-weight:700;margin-left:4px;border:1px solid rgba(248,113,113,.25);letter-spacing:.04em;text-transform:uppercase}}
.ag-row{{display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-top:1px solid rgba(255,255,255,.04)}}
.ag-sn{{font-size:11px;color:#444;display:flex;align-items:center;gap:6px}}
.ag-sn.pri{{color:#f87171}}
.ag-sc{{font-size:11px;font-weight:600;background:rgba(255,255,255,.05);color:#777;padding:1px 8px;border-radius:4px;font-family:'DM Mono',monospace}}
.ag-sc.pri{{background:rgba(248,113,113,.15);color:#f87171}}
.flt{{display:flex;gap:8px;align-items:center;margin-bottom:.75rem;flex-wrap:wrap}}
.flt select{{font-size:12px;padding:7px 12px;border-radius:7px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:#aaa;font-family:'Barlow',sans-serif;cursor:pointer}}
.flt select:focus{{outline:none;border-color:rgba(0,200,255,.4)}}
.flt option{{background:#111}}
.shw{{font-size:11px;color:#444;margin-left:auto;font-family:'DM Mono',monospace}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.75rem}}
.leg{{display:flex;align-items:center;gap:6px;font-size:11px;color:#444;font-weight:500;letter-spacing:.04em;text-transform:uppercase}}
.leg-dot{{width:6px;height:6px;border-radius:50%}}
.qw{{overflow-x:auto}}
table.qt{{width:100%;border-collapse:collapse;font-size:13px}}
table.qt th{{font-size:10px;font-weight:700;color:#444;text-transform:uppercase;letter-spacing:.1em;padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.07);text-align:left;white-space:nowrap;font-family:'Barlow Condensed',sans-serif}}
table.qt td{{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle;white-space:nowrap;color:#bbb;max-width:200px;overflow:hidden;text-overflow:ellipsis}}
table.qt tr.pr td{{background:rgba(248,113,113,.05);color:#f87171}}
table.qt tr:hover td{{background:rgba(255,255,255,.03)}}
.pill{{display:inline-block;font-size:10px;padding:3px 10px;border-radius:20px;font-weight:700;white-space:nowrap;font-family:'DM Mono',monospace;letter-spacing:.03em}}
.p-pri{{background:rgba(248,113,113,.15);color:#f87171;border:1px solid rgba(248,113,113,.3)}}
.p-hi{{background:rgba(239,159,39,.12);color:#EF9F27;border:1px solid rgba(239,159,39,.3)}}
.p-nm{{background:rgba(255,255,255,.05);color:#555;border:1px solid rgba(255,255,255,.08)}}
.tc{{font-family:'DM Mono',monospace;font-size:12px;font-weight:500;color:#ccc}}
.tc.pr{{color:#f87171}}
.overdue td{{background:rgba(249,115,22,.06)!important;color:#fb923c!important}}
.overdue .tc{{color:#fb923c!important}}
.overdue .pill{{background:rgba(249,115,22,.15)!important;color:#fb923c!important;border-color:rgba(249,115,22,.3)!important}}
.overdue-tag{{display:inline-block;background:rgba(249,115,22,.15);color:#fb923c;font-size:9px;padding:1px 6px;border-radius:8px;font-weight:700;margin-left:4px;border:1px solid rgba(249,115,22,.25);text-transform:uppercase;letter-spacing:.04em;vertical-align:middle}}
.tv-mode .hero{{margin-bottom:1.5rem}}
.tv-mode .hero h1{{font-size:80px}}
.tv-mode .metrics{{gap:12px;margin-bottom:1.5rem}}
.tv-mode .mc-val{{font-size:60px}}
.tv-mode .dc-n{{font-size:48px}}
.tv-mode .flt,.tv-mode .legend,.tv-mode .qw,.tv-mode table.qt{{display:none!important}}
.tv-mode .sec-head{{display:none!important}}
.tv-mode #next-week-strip,.tv-mode #next-week-head{{display:none!important}}
.tv-mode #this-week-strip,.tv-mode #this-week-head{{display:none!important}}
.tv-mode .hero{{display:none!important}}
.tv-mode .tabs{{display:none!important}}
.tv-mode .ag-grid{{grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.tv-mode .ag-nm{{font-size:15px}}
.tv-mode .ag-ct{{font-size:13px}}
.tv-mode .ag-sc{{font-size:13px;padding:2px 10px}}
.tv-mode .week-strip .dc{{padding:12px 14px}}
.tv-mode #tv-btn{{color:#00c8ff;border-color:rgba(0,200,255,.4)}}
</style>
</head>
<body>
<div class="wrap">
  <nav>
    <div class="nav-brand">plan<span>.</span>com <span style="color:#333;font-weight:400;font-size:14px;margin-left:4px">· callback pipeline</span></div>
    <div class="nav-right" id="nav-right">
      <span class="updated">Updated {updated_at}</span>
      <span class="live-pill"><span class="live-dot"></span>Live</span>
      <span class="date-pill">{today_label}</span>
      <span class="live-pill" style="font-family:'DM Mono',monospace;font-size:13px;color:#00c8ff;min-width:70px;justify-content:center" id="live-clock">--:--</span>
      <button onclick="toggleTV()" id="tv-btn" style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:5px 14px;font-size:11px;color:#666;cursor:pointer;font-family:'Barlow',sans-serif;font-weight:600;letter-spacing:.06em;text-transform:uppercase">TV</button>
    </div>
  </nav>
  <div class="hero">
    <div class="hero-sub">Account managers · callbacks</div>
    <h1><span class="w">Callback<br></span><span class="c">Wallboard</span></h1>
  </div>
  <div class="metrics">
    <div class="mc c1"><div class="mc-lbl">Due today</div><div class="mc-val">{total_today}</div></div>
    <div class="mc c2" id="overdue-card"><div class="mc-lbl">Overdue now</div><div class="mc-val" id="overdue-count">0</div></div>
    <div class="mc c3"><div class="mc-lbl">Priority today</div><div class="mc-val">{priority_today}</div></div>
    <div class="mc c4"><div class="mc-lbl">Quoted verbal</div><div class="mc-val">{quoted_verbal}</div></div>
    <div class="mc c5"><div class="mc-lbl">Quoted email</div><div class="mc-val">{quoted_email}</div></div>
    <div class="mc c6"><div class="mc-lbl">Due next week</div><div class="mc-val">{total_next_week}</div></div>
  </div>
  <div class="sec-head" id="this-week-head"><span class="sec-head-lbl">This week</span></div>
  <div class="week-strip" id="this-week-strip" style="margin-bottom:1.5rem">{week_strip_html(this_week)}</div>
  <div class="sec-head" id="next-week-head"><span class="sec-head-lbl">Next week</span></div>
  <div class="week-strip" id="next-week-strip" style="margin-bottom:1.5rem">{week_strip_html(next_week)}</div>
  <div class="sec-head"><span class="sec-head-lbl">By account manager</span></div>
  <div class="tabs"><button class="tb on">Today</button></div>
  <div class="ag-grid">{agent_cards_html()}</div>
  <div class="sec-head"><span class="sec-head-lbl">Today\'s callback queue</span></div>
  <div class="legend">
    <span class="leg"><span class="leg-dot" style="background:#f87171"></span>Priority</span>
    <span class="leg"><span class="leg-dot" style="background:#EF9F27"></span>Quoted</span>
    <span class="leg"><span class="leg-dot" style="background:#444"></span>Standard</span>
  </div>
  <div class="flt">
    <select id="qa" onchange="filterQ()">
      <option value="">All agents</option>
      {agent_options}
    </select>
    <select id="qs" onchange="filterQ()">
      <option value="">All stages</option>
      <option value="awaiting pac">Awaiting PAC</option>
      <option value="awaiting sign">Awaiting Sign</option>
      <option value="awaiting dd">Awaiting DD</option>
      <option value="qtd verbal">Quoted verbal</option>
      <option value="qtd email">Quoted email</option>
      <option value="quoted">Quoted</option>
      <option value="cust. req.">Customer requested</option>
      <option value="not eligible">Not eligible</option>
      <option value="call back complete">Call back complete</option>
    </select>
    <span class="shw" id="shw"></span>
  </div>
  <div class="qw">
    <table class="qt">
      <thead><tr><th>Due</th><th>Lead ID</th><th>Company</th><th>Stage</th><th>Agent</th><th>Phone</th><th>Last call</th></tr></thead>
      <tbody id="qb">{queue_rows_html()}</tbody>
    </table>
  </div>
</div>
<script>
const allRows = Array.from(document.querySelectorAll('#qb tr'));

// Live clock
function updateClock() {{
  const now = new Date();
  const h = String(now.getHours()).padStart(2,'0');
  const m = String(now.getMinutes()).padStart(2,'0');
  const s = String(now.getSeconds()).padStart(2,'0');
  document.getElementById('live-clock').textContent = h+':'+m+':'+s;
}}
setInterval(updateClock, 1000);
updateClock();

// TV mode
let tvMode = false;
function toggleTV() {{
  tvMode = !tvMode;
  document.body.classList.toggle('tv-mode', tvMode);
  document.getElementById('tv-btn').textContent = tvMode ? 'Exit TV' : 'TV';
  if (tvMode) {{
    document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
  }} else {{
    document.exitFullscreen && document.exitFullscreen();
  }}
}}
document.addEventListener('keydown', e => {{ if(e.key === 'Escape' && tvMode) toggleTV(); }});

// Overdue logic - runs every 30 seconds
function checkOverdue() {{
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();
  let overdueCount = 0;
  const tbody = document.getElementById('qb');
  const rows = Array.from(tbody.querySelectorAll('tr'));

  rows.forEach(tr => {{
    const t = tr.getAttribute('data-time');
    if (!t) return;
    const parts = t.split(':');
    const rowMins = parseInt(parts[0]) * 60 + parseInt(parts[1]);
    const isOverdue = rowMins < nowMins;
    if (isOverdue) {{
      overdueCount++;
      tr.classList.add('overdue');
    }} else {{
      tr.classList.remove('overdue');
    }}
  }});

  // Sort: overdue first, then priority, then by time
  rows.sort((a, b) => {{
    const aOver = a.classList.contains('overdue') ? 0 : 1;
    const bOver = b.classList.contains('overdue') ? 0 : 1;
    if (aOver !== bOver) return aOver - bOver;
    const aPri = a.getAttribute('data-pri') === '1' ? 0 : 1;
    const bPri = b.getAttribute('data-pri') === '1' ? 0 : 1;
    if (aPri !== bPri) return aPri - bPri;
    return (a.getAttribute('data-time') || '').localeCompare(b.getAttribute('data-time') || '');
  }});
  rows.forEach(r => tbody.appendChild(r));

  // Update overdue metric card
  const card = document.getElementById('overdue-card');
  document.getElementById('overdue-count').textContent = overdueCount;
  card.style.display = '';
}}

setInterval(checkOverdue, 30000);
checkOverdue();

// Auto-refresh every 3 minutes with cache busting
console.log('Auto-refresh active — reloads every 3 minutes');
setInterval(() => {{
  window.location.href = window.location.href.split('?')[0] + '?t=' + Date.now();
}}, 3 * 60 * 1000);

function filterQ() {{
  const ag = document.getElementById('qa').value.toLowerCase();
  const st = document.getElementById('qs').value.toLowerCase();
  let shown = 0;
  allRows.forEach(tr => {{
    const cells = tr.querySelectorAll('td');
    const rowAg = cells[4] ? cells[4].textContent.toLowerCase() : '';
    const rowSt = cells[3] ? cells[3].textContent.toLowerCase().trim() : '';
    const agMatch = !ag || rowAg.replace(/[.]/g,'').replace(/ /g,'').includes(ag.replace(/ /g,'').toLowerCase());
    const stMatch = !st || rowSt === st.toLowerCase();
    const show = agMatch && stMatch;
    tr.style.display = show ? '' : 'none';
    if(show) shown++;
  }});
  document.getElementById('shw').textContent = 'Showing ' + shown + ' of ' + allRows.length;
}}
filterQ();
</script>
</body>
</html>'''

    with open(OUTPUT_PATH,'w',encoding='utf-8') as f:
        f.write(html)
    print(f"Built OK — {total_today} callbacks today, {priority_today} priority")

if __name__=='__main__':
    build()
