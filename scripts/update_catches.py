#!/usr/bin/env python3
"""釣りトレFX 公開青物情報 updater (data-only repo).
Low-frequency best-effort collector. It preserves history when upstream layouts change.
Do not treat representative coordinates as exact catch locations.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'latest-catches.json'; VER=ROOT/'version.json'
JST=timezone(timedelta(hours=9))
H={'User-Agent':'TsuritoreFX-DataBot/6.6 (low-frequency public fishing info checker)'}
FISH=('ブリ','ハマチ','メジロ','ワラサ','ヤズ','ツバス','サワラ','サゴシ','カンパチ','ネリゴ','シオ')
SOURCES=[
 {'name':'ANGLERS しまなみ海道 ブリ','url':'https://anglers.jp/areas/2750/fishes/5','area':'しまなみ海道','lat':34.22,'lng':133.10,'must':['しまなみ']},
 {'name':'ANGLERS しまなみ海道 釣行','url':'https://anglers.jp/areas/2750/fishings','area':'しまなみ海道','lat':34.22,'lng':133.10,'must':['しまなみ']},
 {'name':'ANGLERS 大社築港 ブリ','url':'https://anglers.jp/areas/2029/fishes/5','area':'山陰・大社築港周辺','lat':35.39,'lng':132.68,'must':[]},
]

def read_json(p,default):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return default

def clean(s):return re.sub(r'\s+',' ',s or '').strip()
def date_of(t):
 m=re.search(r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})',t)
 return f'{int(m.group(1)):04d}/{int(m.group(2)):02d}/{int(m.group(3)):02d}' if m else None
def fish_of(t):
 for w in FISH:
  if w in t:
   m=re.search(re.escape(w)+r'\s*(\d+(?:\.\d+)?)\s*cm',t)
   return w+(m.group(1)+'cm' if m else '')
 return None

def source_fetch(cfg):
 r=requests.get(cfg['url'],headers=H,timeout=25);r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
 rows=[];seen=set()
 # Catch cards / links
 for a in s.select('a[href*="/catches/"]'):
  node=a
  for _ in range(7):
   t=clean(node.get_text(' ',strip=True));
   if date_of(t) and fish_of(t):break
   if node.parent:node=node.parent
  t=clean(node.get_text(' ',strip=True));d=date_of(t);f=fish_of(t)
  if not d or not f:continue
  if cfg['must'] and not any(x in t for x in cfg['must']):continue
  u=urljoin(cfg['url'],a.get('href',''));k=(d,f,u)
  if k in seen:continue
  seen.add(k);bits=[]
  for kw in ('ポッパー','トップ','ジグ','ブレード','ナブラ','サワラジャンプ','朝マヅメ','夕マヅメ'):
   if kw in t:bits.append(kw)
  rows.append({'date':d,'fish':f,'lat':cfg['lat'],'lng':cfg['lng'],'area':cfg['area']+'（投稿地点非公開時は代表位置）','cond':'公開投稿から自動取得'+(('／'+'・'.join(bits)) if bits else ''),'src':'ANGLERS','url':u,'confidence':'confirmed-fish'})
 # Text fallback catches pages rendered server-side/search-cache style
 if not rows:
  lines=list(s.stripped_strings)
  for i,line in enumerate(lines):
   d=date_of(line)
   if not d:continue
   w=' '.join(lines[max(0,i-10):min(len(lines),i+15)]);f=fish_of(w)
   if not f:continue
   if cfg['must'] and not any(x in w for x in cfg['must']):continue
   k=(d,f,cfg['url'])
   if k in seen:continue
   seen.add(k);rows.append({'date':d,'fish':f,'lat':cfg['lat'],'lng':cfg['lng'],'area':cfg['area']+'（一覧代表位置）','cond':'公開一覧から自動取得','src':'ANGLERS','url':cfg['url'],'confidence':'confirmed-fish'})
 return rows

def recent(items,days=60):
 cut=datetime.now(JST).date().toordinal()-days;out=[]
 for x in items:
  try:
   y,m,d=map(int,re.search(r'(20\d{2})/(\d{2})/(\d{2})',x['date']).groups())
   if datetime(y,m,d).date().toordinal()>=cut:out.append(x)
  except Exception:pass
 return out

def main():
 old=read_json(OUT,{'items':[]});scr=[];status=[]
 for cfg in SOURCES:
  try:
   rows=source_fetch(cfg);scr+=rows;status.append({'name':cfg['name'],'url':cfg['url'],'ok':True,'count':len(rows)})
  except Exception as e:status.append({'name':cfg['name'],'url':cfg['url'],'ok':False,'count':0,'note':type(e).__name__})
  time.sleep(1)
 d={}
 for x in old.get('items',[])+scr:
  k=(x.get('date'),x.get('fish'),x.get('area'),x.get('url'));d[k]=x
 items=recent(list(d.values()));items.sort(key=lambda x:x.get('date',''),reverse=True)
 now=datetime.now(JST).isoformat(timespec='seconds')
 OUT.write_text(json.dumps({'generated_at':now,'checked_at':now,'sources':status,'items':items[:200]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 v=read_json(VER,{});v.update({'schema':'tsuritorefx-data-v1','updated_at':now});v.setdefault('datasets',{})['catches']='data/latest-catches.json';VER.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('catches',len(items))
if __name__=='__main__':main()
