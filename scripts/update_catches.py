#!/usr/bin/env python3
"""釣りトレFX v6.8 公開青物情報 updater.

Public pages only, low-frequency best-effort collector.
Sources: ANGLERS user posts + retailer/shop pages (レジャックス/アングラーズグループ,
かめや釣具, 上州屋, 釣具のポイント). It keeps previous good data if a source fails.
Representative coordinates are NOT exact catch locations unless explicitly marked.
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
H={'User-Agent':'TsuritoreFX-DataBot/6.8 (+public-low-frequency-fishing-info-checker)'}
FISH=('ヒラマサ','ブリ','ハマチ','メジロ','ワラサ','ヤズ','ツバス','サワラ','サゴシ','カンパチ','ネリゴ','シオ','アカビラ','青物')
WEST=('しまなみ','伯方','大島','周防大島','浜田','温泉津','大社','出雲','美保関','境港','山陰','鳥取','島根','広島','呉','蒲刈','三原','福山','尾道','因島','生口','岡山','下津井','香川','高松','小豆島','愛媛','今治','佐田岬','宇和','山口','淡路','明石','姫路','徳島')
AREAS=[
 ('伯方島',34.205,133.085,'伯方島'),('しまなみ',34.22,133.10,'しまなみ海道'),
 ('周防大島',33.93,132.20,'周防大島'),('伍八波止',34.88,132.06,'浜田・伍八波止'),('浜田',34.88,132.07,'浜田周辺'),
 ('温泉津',35.09,132.35,'温泉津周辺'),('大社漁港',35.393,132.687,'大社漁港'),('大社',35.393,132.687,'大社周辺'),
 ('美保関',35.56,133.31,'美保関周辺'),('境港',35.54,133.23,'境港周辺'),('出雲',35.37,132.75,'出雲周辺'),
 ('蒲刈',34.19,132.72,'蒲刈方面'),('呉',34.25,132.55,'呉周辺'),('三原',34.40,133.08,'三原周辺'),('福山',34.45,133.36,'福山周辺'),
 ('尾道',34.41,133.20,'尾道周辺'),('下津井',34.43,133.80,'下津井周辺'),('岡山',34.58,133.93,'岡山沿岸'),
 ('高松',34.35,134.05,'高松周辺'),('小豆島',34.49,134.24,'小豆島'),('今治',34.07,132.99,'今治周辺'),
 ('佐田岬',33.39,132.12,'佐田岬'),('宇和',33.22,132.56,'宇和海'),('淡路',34.42,134.90,'淡路島'),('明石',34.64,135.00,'明石周辺'),
 ('徳島',34.05,134.58,'徳島沿岸')]

SOURCES=[
 {'name':'ANGLERS しまなみ','kind':'anglers','url':'https://anglers.jp/areas/2750/fishes/5','area':'しまなみ海道','lat':34.22,'lng':133.10},
 {'name':'ANGLERS 大社築港','kind':'anglers','url':'https://anglers.jp/areas/2029/fishes/5','area':'山陰・大社築港周辺','lat':35.39,'lng':132.68},
 {'name':'レジャックス/アングラーズグループ','kind':'shop','url':'https://www.anglers.co.jp/','src':'レジャックス/アングラーズグループ'},
 {'name':'レジャックス 店舗ブログ','kind':'shop','url':'https://www.anglers.co.jp/weblogs/','src':'レジャックス/アングラーズグループ'},
 {'name':'かめや釣具 山陽','kind':'shop','url':'https://kameya-choka.com/sanyo/','src':'かめや釣具'},
 {'name':'かめや釣具 四国','kind':'shop','url':'https://kameya-choka.com/shikoku/','src':'かめや釣具'},
 {'name':'かめや釣具 山陰','kind':'shop','url':'https://kameya-choka.com/sanin/','src':'かめや釣具'},
 {'name':'上州屋 釣り情報','kind':'shop','url':'https://www.johshuya.co.jp/information/','src':'上州屋'},
 {'name':'釣具のポイント 福山蔵王','kind':'shop','url':'https://www.point-i.jp/fishing_spot_guides?area_id=0&free_word=&from=&prefecture_id=34&shop_id=82&to=','src':'釣具のポイント'},
 {'name':'釣具のポイント 出雲','kind':'shop','url':'https://www.point-i.jp/fishing_spot_guides?free_word=&from=&prefecture_id=0&shop_id=86&to=&utf8=%E2%9C%93','src':'釣具のポイント'},
]

def read_json(p,default):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return default

def clean(s):return re.sub(r'\s+',' ',s or '').strip()
def date_of(t):
 for pat in (r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})',r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日',r'[‘\']?(\d{2})\s*(\d{1,2})月\s*(\d{1,2})日'):
  m=re.search(pat,t)
  if m:
   y=int(m.group(1));y=y+2000 if y<100 else y
   return f'{y:04d}/{int(m.group(2)):02d}/{int(m.group(3)):02d}'
 return None

def fish_of(t):
 found=[]
 for w in FISH:
  if w in t:
   m=re.search(re.escape(w)+r'[^0-9]{0,8}(\d+(?:\.\d+)?)\s*(?:cm|㎝)',t,re.I)
   found.append(w+(m.group(1)+'cm' if m else ''))
 # generic 青物 is redundant if species exists
 if len(found)>1 and '青物' in found:found.remove('青物')
 return '・'.join(dict.fromkeys(found[:3])) if found else None

def locate(t,default=None):
 for key,lat,lng,label in AREAS:
  if key in t:return lat,lng,label
 if default:return default
 return None

def infer_shore(t):
 shore_words=('陸から','ショア','波止','堤防','サーフ','磯','地磯','おかっぱり','岸から')
 boat_words=('船から','遊漁船','沖','船釣り','ティップラン','SLJ','落とし込み','ボート')
 if any(w in t for w in shore_words):return True
 if any(w in t for w in boat_words):return False
 return None

def cond_of(t):
 bits=[]
 for kw in ('陸から','ショアジギング','波止','堤防','サーフ','磯','ナブラ','ベイト','回遊','朝マズメ','夕マズメ','トップ','ポッパー','ジグ','ブレード','泳がせ'):
  if kw in t:bits.append(kw)
 return '・'.join(bits[:6]) or '公開釣果情報'

def get(url):
 r=requests.get(url,headers=H,timeout=25);r.raise_for_status();return BeautifulSoup(r.text,'html.parser')

def fetch_anglers(cfg):
 s=get(cfg['url']);rows=[];seen=set()
 for a in s.select('a[href*="/catches/"]'):
  node=a
  for _ in range(7):
   t=clean(node.get_text(' ',strip=True))
   if date_of(t) and fish_of(t):break
   node=node.parent or node
  t=clean(node.get_text(' ',strip=True));d=date_of(t);f=fish_of(t)
  if not d or not f:continue
  u=urljoin(cfg['url'],a.get('href',''));k=(d,f,u)
  if k in seen:continue
  seen.add(k);rows.append({'date':d,'fish':f,'lat':cfg['lat'],'lng':cfg['lng'],'area':cfg['area']+'（投稿地点非公開時は代表位置）','cond':cond_of(t),'src':'ANGLERS','url':u,'sourceType':'community','shore':infer_shore(t),'confidence':'confirmed-fish','location_precision':'representative'})
 if not rows:
  lines=list(s.stripped_strings)
  for i,line in enumerate(lines):
   d=date_of(line)
   if not d:continue
   w=' '.join(lines[max(0,i-12):min(len(lines),i+18)]);f=fish_of(w)
   if not f:continue
   k=(d,f,cfg['url'])
   if k in seen:continue
   seen.add(k);rows.append({'date':d,'fish':f,'lat':cfg['lat'],'lng':cfg['lng'],'area':cfg['area']+'（一覧代表位置）','cond':cond_of(w),'src':'ANGLERS','url':cfg['url'],'sourceType':'community','shore':infer_shore(w),'confidence':'confirmed-fish','location_precision':'representative'})
 return rows[:50]

def shop_scan(cfg):
 s=get(cfg['url']);lines=[clean(x) for x in s.stripped_strings if clean(x)];rows=[];seen=set()
 # windows centered on dates; requires bluefish term and a western-Japan place word
 for i,line in enumerate(lines):
  d=date_of(line)
  if not d:continue
  w=' '.join(lines[max(0,i-12):min(len(lines),i+20)])
  f=fish_of(w)
  if not f or not any(x in w for x in WEST):continue
  loc=locate(w)
  if not loc:continue
  lat,lng,area=loc;shore=infer_shore(w)
  # avoid obvious boat-only rows from default shore view; retain them marked shore=False
  src=cfg.get('src',cfg['name']);k=(d,f,area,src)
  if k in seen:continue
  seen.add(k)
  rows.append({'date':d,'fish':f,'lat':lat,'lng':lng,'area':area+'（店舗公開情報／代表位置）','cond':cond_of(w),'src':src,'url':cfg['url'],'sourceType':'shop','shore':shore,'confidence':'shop-report','location_precision':'representative'})
 return rows[:60]

def recent(items,days=75):
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
   rows=fetch_anglers(cfg) if cfg['kind']=='anglers' else shop_scan(cfg)
   scr+=rows;status.append({'name':cfg['name'],'url':cfg['url'],'ok':True,'count':len(rows)})
  except Exception as e:
   status.append({'name':cfg['name'],'url':cfg['url'],'ok':False,'count':0,'note':type(e).__name__})
  time.sleep(.8)
 # Preserve previous good rows; source outages must not erase history.
 d={}
 for x in old.get('items',[])+scr:
  x.setdefault('sourceType','community' if x.get('src')=='ANGLERS' else 'shop')
  k=(x.get('date'),x.get('fish'),x.get('area'),x.get('src'),x.get('url'));d[k]=x
 items=recent(list(d.values()));items.sort(key=lambda x:(x.get('date',''),x.get('sourceType')=='community'),reverse=True)
 now=datetime.now(JST).isoformat(timespec='seconds')
 OUT.write_text(json.dumps({'generated_at':now,'checked_at':now,'sources':status,'items':items[:350]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 v=read_json(VER,{});v.update({'schema':'tsuritorefx-data-v2','updated_at':now});v.setdefault('datasets',{})['catches']='data/latest-catches.json';VER.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('catches',len(items),'new-scan',len(scr))
if __name__=='__main__':main()
