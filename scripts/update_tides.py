#!/usr/bin/env python3
"""釣りトレFX 潮汐更新データ生成。
気象庁の公開「潮位表」から各基準点の満潮・干潮予測を取得し、
data/tides.json に今後5日分を保存する。
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'tides.json'
VER=ROOT/'version.json'
JST=timezone(timedelta(hours=9))
H={'User-Agent':'TsuritoreFX-DataBot/6.8.3 (JMA tide table checker)'}

STATIONS=[
 ('M0','今治市小島',34.1333,132.9833),
 ('L0','今治',34.0667,133.0000),
 ('Q9','呉',34.2333,132.5500),
 ('Q8','広島',34.3500,132.4667),
 ('UN','宇野',34.4833,133.9500),
 ('TA','高松',34.3500,134.0500),
 ('MT','松山',33.8667,132.7167),
 ('QA','徳山',34.0333,131.8000),
 ('ST','洲本',34.3500,134.9000),
 ('UW','宇和島',33.2333,132.5500),
 ('SK','境',35.5500,133.2500),
 ('HA','浜田',34.9000,132.0667),
]

def clean(s): return re.sub(r'\s+',' ',s or '').strip()

def read_json(p, default):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return default

def jma_url(code, start, end):
    q={
      'LV':'DL','S_HILO':'on',
      'ds':f'{start.day:02d}','ms':f'{start.month:02d}','ys':str(start.year),
      'de':f'{end.day:02d}','me':f'{end.month:02d}','ye':str(end.year),
      'stn':code
    }
    return 'https://www.data.jma.go.jp/kaiyou/db/tide/suisan/suisan.php?'+urlencode(q)

def pairs_from_tokens(tokens):
    out=[]
    for i in range(len(tokens)-1):
        t=tokens[i].strip()
        v=tokens[i+1].strip()
        if re.fullmatch(r'\d{1,2}:\d{2}',t) and re.fullmatch(r'-?\d+(?:\.\d+)?',v):
            out.append((t,int(float(v))))
    # remove accidental duplicates
    seen=set(); ans=[]
    for x in out:
        if x not in seen: seen.add(x); ans.append(x)
    return ans

def parse_page(html):
    soup=BeautifulSoup(html,'html.parser')
    days=[]
    for tr in soup.find_all('tr'):
        cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
        if not cells: continue
        m=re.search(r'(20\d{2})/(\d{1,2})/(\d{1,2})',cells[0])
        if not m: continue
        date=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        vals=cells[1:]
        events=[]
        # JMA table layout: after date, high-tide slots (4 pairs), then low-tide slots (4 pairs).
        # If the structure changes, fall back to classifying time/level pairs by relative level.
        if len(vals)>=16:
            hi=pairs_from_tokens(vals[:8])
            lo=pairs_from_tokens(vals[8:16])
            events += [{'type':'high','time':t,'cm':cm} for t,cm in hi]
            events += [{'type':'low','time':t,'cm':cm} for t,cm in lo]
        if not events:
            pp=pairs_from_tokens(vals)
            if pp:
                levels=sorted(cm for _,cm in pp)
                pivot=(levels[(len(levels)-1)//2]+levels[len(levels)//2])/2
                events=[{'type':'high' if cm>pivot else 'low','time':t,'cm':cm} for t,cm in pp]
        if events:
            events.sort(key=lambda x:x['time'])
            days.append({'date':date,'events':events})
    return days

def main():
    now=datetime.now(JST)
    start=now.date()
    end=start+timedelta(days=4)
    old=read_json(OUT,{'stations':{}})
    stations={}
    status=[]
    for code,name,lat,lng in STATIONS:
        url=jma_url(code,start,end)
        try:
            r=requests.get(url,headers=H,timeout=25)
            r.raise_for_status()
            r.encoding=r.apparent_encoding or r.encoding
            days=parse_page(r.text)
            if not days: raise RuntimeError('no tide rows parsed')
            stations[code]={'name':name,'lat':lat,'lng':lng,'days':days,'url':url}
            status.append({'code':code,'name':name,'ok':True,'days':len(days)})
        except Exception as e:
            prev=old.get('stations',{}).get(code)
            if prev: stations[code]=prev
            status.append({'code':code,'name':name,'ok':False,'days':0,'note':type(e).__name__})
    out={
      'generated_at':now.isoformat(timespec='seconds'),
      'source':'気象庁 潮位表',
      'status':status,
      'stations':stations
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    v=read_json(VER,{})
    v['updated_at']=now.isoformat(timespec='seconds')
    v.setdefault('datasets',{})['tides']='data/tides.json'
    VER.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('tide stations',sum(1 for x in status if x['ok']),'/',len(status))

if __name__=='__main__':
    main()
