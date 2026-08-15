#!/usr/bin/env python3
"""Performance-blind SEC 8-K Item 2.02 coverage audit for a liquid IBKR universe."""
from __future__ import annotations
import argparse,hashlib,json,os,time,urllib.error,urllib.request
from datetime import datetime
from pathlib import Path

UNIVERSE={'AAPL':'0000320193','MSFT':'0000789019','JPM':'0000019617','CAT':'0000018230','NVDA':'0001045810','GOOGL':'0001652044','AMZN':'0001018724','META':'0001326801','TSLA':'0001318605','KO':'0000021344'}
AGENT=os.environ.get('SEC_USER_AGENT','TradingAgent research contact@github.com/romros')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fetch(url,retries=4):
 request=urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'application/json','Accept-Encoding':'identity'})
 for attempt in range(retries):
  try:
   with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
  except urllib.error.HTTPError as error:
   if error.code not in (403,429,500,502,503,504) or attempt+1==retries:raise
  except (TimeoutError,urllib.error.URLError):
   if attempt+1==retries:raise
  time.sleep(1.5*(attempt+1))
def events(recent,start_year,end_year):
 out=[]
 for i,form in enumerate(recent['form']):
  accepted=recent['acceptanceDateTime'][i];year=int(accepted[:4]);items={x.strip() for x in recent['items'][i].split(',')}
  if form=='8-K' and '2.02' in items and start_year<=year<=end_year:
   out.append({'accepted_utc':accepted,'filing_date':recent['filingDate'][i],'report_date':recent['reportDate'][i],'accession':recent['accessionNumber'][i],'primary_document':recent['primaryDocument'][i],'description':recent['primaryDocDescription'][i],'items':recent['items'][i]})
 return sorted(out,key=lambda x:x['accepted_utc'])
def audit(output_dir,start_year,end_year):
 output_dir.mkdir(parents=True,exist_ok=True);assets={}
 for ticker,cik in UNIVERSE.items():
  raw=output_dir/f'{ticker.lower()}_submissions.json';payload=fetch(f'https://data.sec.gov/submissions/CIK{cik}.json');raw.write_text(json.dumps(payload,sort_keys=True)+'\n');parts=[payload['filings']['recent']]
  for historical in payload['filings'].get('files',[]):
   name=historical['name'];part=fetch(f'https://data.sec.gov/submissions/{name}');part_path=output_dir/f'{ticker.lower()}_{name}';part_path.write_text(json.dumps(part,sort_keys=True)+'\n');parts.append(part);time.sleep(.12)
  by_accession={row['accession']:row for part in parts for row in events(part,start_year,end_year)};rows=sorted(by_accession.values(),key=lambda x:x['accepted_utc']);years={str(y):sum(x['accepted_utc'].startswith(str(y)) for x in rows) for y in range(start_year,end_year+1)};gaps=[]
  for left,right in zip(rows,rows[1:]):gaps.append((datetime.fromisoformat(right['accepted_utc'].replace('Z','+00:00'))-datetime.fromisoformat(left['accepted_utc'].replace('Z','+00:00'))).days)
  assets[ticker]={'cik':cik,'raw_path':str(raw),'raw_sha256':sha(raw),'events':rows,'events_count':len(rows),'events_by_year':years,'non_quarterly_gap_count':sum(g<55 or g>125 for g in gaps),'after_20utc_count':sum(x['accepted_utc'][11:16]>='20:00' for x in rows)};time.sleep(.12)
 coverage=all(a['events_count']>=4*(end_year-start_year+1)-2 for a in assets.values());clean=all(a['non_quarterly_gap_count']==0 for a in assets.values())
 result={'schema_version':1,'decision':'PASS_EVENT_CALENDAR_ONLY' if coverage and clean else 'BLOCK_EVENT_CLASSIFICATION_REQUIRED','source':'SEC EDGAR submissions JSON','user_agent':AGENT,'period':[start_year,end_year],'assets':assets,'checks':{'coverage_near_quarterly':coverage,'quarterly_cadence_unambiguous':clean},'performance_accessed':False,'price_data_accessed':False,'research_authorized':False,'paper_authorized':False,'live_authorized':False};report=output_dir/'preflight.json';report.write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--start-year',type=int,default=2017);p.add_argument('--end-year',type=int,default=2024);a=p.parse_args();x=audit(a.output_dir,a.start_year,a.end_year);print(json.dumps({'decision':x['decision'],'assets':{k:{'events':v['events_count'],'non_quarterly_gaps':v['non_quarterly_gap_count']} for k,v in x['assets'].items()}},indent=2))
if __name__=='__main__':main()
