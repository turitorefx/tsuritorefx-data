#!/usr/bin/env python3
"""Best-effort curated facility updater.
- null-camp free-camping pages: collect free camps and published coordinates.
- Enex Fleet: try to discover store pages and extract coordinates/hours when exposed.
The live app still queries OpenStreetMap/Overpass within the selected radius; this
file is a supplemental source, never the only facility source.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'facilities-curated.json';VER=ROOT/'version.json'
JST=timezone(timedelta(hours=9));H={'User-Agent':'TsuritoreFX-DataBot/6.6 (weekly public facility checker)'}
WEST_PREFS={'三重県','滋賀県','京都府','大阪府','兵庫県','奈良県','和歌山県','鳥取県','島根県','岡山県','広島県','山口県','徳島県','香川県','愛媛県','高知県','福岡県','佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県'}

def old():
    try:return json.loads(OUT.read_text(encoding='utf-8'))
    except:return {'items':[],'sources':[]}
def old_version():
    try:return json.loads(VER.read_text(encoding='utf-8'))
    except:return {}
def get(url):
    r=requests.get(url,headers=H,timeout=25);r.raise_for_status();return r

def nullcamp():
    base='https://null-camp.com/free-camping/'; soup=BeautifulSoup(get(base).text,'html.parser')
    links=[]
    for a in soup.select('a[href]'):
        u=urljoin(base,a['href'])
        if '/camp/' in urlparse(u).path and u not in links:links.append(u)
    rows=[]
    for n,u in enumerate(links[:260]):
        try:
            sp=BeautifulSoup(get(u).text,'html.parser');txt=' '.join(sp.stripped_strings);h=sp.find('h1');name=h.get_text(' ',strip=True) if h else None
            m=re.search(r'位置情報\s*[:：]\s*(-?\d{1,2}\.\d+)\s*[,，]\s*(-?\d{2,3}\.\d+)',txt)
            if not name or not m:continue
            pref=next((p for p in WEST_PREFS if p in txt),None)
            if not pref:continue
            approx=('おおよその位置' in txt or '正確な位置が未確認' in txt)
            last=(re.search(r'最終確認日\s*[:：]\s*(20\d{2}-\d{2}(?:-\d{2})?)',txt) or [None,None])[1]
            rows.append({'key':'nullcamp:'+urlparse(u).path.strip('/').replace('/','-'),'type':'camp','kind':'無料','name':name,'lat':float(m.group(1)),'lng':float(m.group(2)),'hours':'利用条件は公式確認','note':f'{pref} / ぬるキャン無料掲載'+(' / 概略位置' if approx else ''),'sourceType':'nullcamp','sourceUrl':u,'approx':approx,'lastChecked':last})
        except Exception:pass
        time.sleep(.20)
    return rows

def enexfleet():
    seeds=['https://map.enexfleet.com/','https://map.enexfleet.com/all/']
    store_links=[]
    for seed in seeds:
        try:
            sp=BeautifulSoup(get(seed).text,'html.parser')
            for a in sp.select('a[href]'):
                u=urljoin(seed,a['href']);p=urlparse(u)
                if 'enexfleet.com' in p.netloc and any(k in p.path.lower() for k in ('spot','store','shop','detail')) and u not in store_links:store_links.append(u)
        except Exception:pass
    rows=[]
    for u in store_links[:360]:
        try:
            sp=BeautifulSoup(get(u).text,'html.parser');txt=' '.join(sp.stripped_strings);name=(sp.find('h1') or sp.find('title')).get_text(' ',strip=True)
            # Common coordinate representations in map/detail HTML.
            m=(re.search(r'@(-?\d{1,2}\.\d+),(-?\d{2,3}\.\d+)',str(sp)) or re.search(r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,2}\.\d+)"?.{0,120}?"(?:lng|lon|longitude)"\s*:\s*"?(-?\d{2,3}\.\d+)',str(sp),re.I|re.S))
            if not m:continue
            hours='24/7' if '24時間' in txt else '営業時間は公式確認'
            hm=re.search(r'(\d{1,2}:\d{2})\s*[〜～\-–]\s*(\d{1,2}:\d{2})',txt)
            if hm and hours!='24/7':hours=f'{hm.group(1).zfill(5)}-{hm.group(2).zfill(5)}'
            rows.append({'key':'enex:'+re.sub(r'\W+','-',u),'type':'gas','kind':'GS','name':name[:80],'lat':float(m.group(1)),'lng':float(m.group(2)),'hours':hours,'note':'エネクスフリート公式店舗検索','sourceType':'official','sourceUrl':u,'approx':False})
        except Exception:pass
        time.sleep(.15)
    return rows

def main():
    prev=old();items=[];statuses=[]
    for name,fn,url in [('ぬるキャン',nullcamp,'https://null-camp.com/free-camping/'),('エネクスフリート',enexfleet,'https://map.enexfleet.com/')]:
        try:
            r=fn();items+=r;statuses.append({'name':name,'url':url,'ok':True,'count':len(r)})
        except Exception as e:statuses.append({'name':name,'url':url,'ok':False,'count':0,'note':type(e).__name__})
    # If an upstream site changes, preserve previous items from that source rather than emptying the map.
    if not items:items=prev.get('items',[])
    d={}
    for x in items:d[x.get('key') or (x.get('type'),x.get('name'))]=x
    payload={'generated_at':datetime.now(JST).isoformat(timespec='seconds'),'sources':statuses,'items':list(d.values())}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');v=old_version();v.update({'schema':'tsuritorefx-data-v1','updated_at':payload['generated_at']});v.setdefault('datasets',{})['facilities']='data/facilities-curated.json';VER.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('wrote',len(payload['items']),'facilities')
if __name__=='__main__':main()
