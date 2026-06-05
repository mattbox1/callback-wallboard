import pandas as pd
from datetime import datetime, timedelta
import sys, os

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

def build():
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    except Exception as e:
        print(f"Error reading CSV: {e}"); sys.exit(1)

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
    updated_at = datetime.now().strftime('%d %b %Y %H:%M')
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
            html += f'<tr{tr_cls}><td><span class="tc{tc_cls}">{t}</span></td><td style="color:#444;font-size:11px;font-family:\'DM Mono\',monospace">{lead_id}</td><td>{co}</td><td><span class="pill {pill_class(s)}">{stage_short(s)}</span></td><td style="color:#666">{ag_short}</td><td style="font-family:\'DM Mono\',monospace;font-size:11px;color:#444">{ph}</td><td style="font-size:11px;color:#444">{lc}</td></tr>'
        return html

    agent_list = sorted(agent_map.keys())
    agent_options = ''.join(f'<option value="{a}">{a}</option>' for a in agent_list)

    with open(os.path.join(os.path.dirname(__file__),'..','_template.html'),'r',encoding='utf-8') as f:
        template = f.read()

    html = template \
        .replace('{{TODAY_LABEL}}', today_label) \
        .replace('{{UPDATED_AT}}', updated_at) \
        .replace('{{TOTAL_TODAY}}', str(total_today)) \
        .replace('{{ACTIVE_AGENTS}}', str(active_agents)) \
        .replace('{{PRIORITY_TODAY}}', str(priority_today)) \
        .replace('{{QUOTED_VERBAL}}', str(quoted_verbal)) \
        .replace('{{QUOTED_EMAIL}}', str(quoted_email)) \
        .replace('{{TOTAL_NEXT_WEEK}}', str(total_next_week)) \
        .replace('{{THIS_WEEK_STRIP}}', week_strip_html(this_week)) \
        .replace('{{NEXT_WEEK_STRIP}}', week_strip_html(next_week)) \
        .replace('{{AGENT_CARDS}}', agent_cards_html()) \
        .replace('{{AGENT_OPTIONS}}', agent_options) \
        .replace('{{QUEUE_ROWS}}', queue_rows_html())

    with open(OUTPUT_PATH,'w',encoding='utf-8') as f:
        f.write(html)

    print(f"Built OK — {total_today} callbacks today, {priority_today} priority")

if __name__=='__main__':
    build()
