"""수치 무결성과 후보 선별 기준의 민감도를 점검한다."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
RES=ROOT/'results'
def main():
 d=pd.read_csv(RES/'dong_metrics.csv')
 s=pd.read_csv(RES/'stops_audit_202606.csv',dtype={'NODE_ID':str})
 assert len(d)==427 and not d[['gu','dong']].duplicated().any()
 assert d.population.sum()==9560471 and d.elderly.sum()==1962133
 assert (d.elderly<=d.population).all()
 assert d.stops.sum()==(s.poly_id>=0).sum()
 assert np.allclose(d.coverage500>=d.coverage300,True)
 assert d.coverage300.between(0,1).all() and d.coverage500.between(0,1).all()
 assert d.route_contacts.ge(d.active_stops).all()
 base=set(d.loc[d.candidate_june,'boundary_id'])
 def pick(supply,contacts,q=.25):
  return set(d.loc[(d.elderly>=d.elderly.quantile(1-q)) & (supply<=supply.quantile(q)) & (contacts<=contacts.quantile(q)),'boundary_id'])
 scenarios=[]
 def add(name,selected):
  scenarios.append({'scenario':name,'candidate_count':len(selected),'base_overlap':len(base&selected),'jaccard':len(base&selected)/len(base|selected)})
 add('6월 기본 기준',base)
 for name,col in [('50m 정류장 군집','candidate_cluster50'),('동 경계 밖 50m 포함','candidate_neighbor50'),('9월 공급 자료 대체','candidate_september')]:
  add(name,set(d.loc[d[col],'boundary_id']))
 add('운행실적 있는 정류장만',pick(d.active_stops/d.elderly*1000,d.contacts_per_1000))
 inside=s[(s.poly_id>=0) & (s.assign_method=='inside')].groupby('poly_id').agg(stops=('NODE_ID','size'),contacts=('route_contacts','sum'))
 rawid=d.boundary_id.astype(int)
 # 원자료의 feature 순서와 boundary_id가 일치하는지 확인 후 엄격 경계 기준 재집계.
 assert sorted(rawid.tolist())==list(range(427))
 strict_stops=rawid.map(inside.stops).fillna(0)/d.elderly*1000
 strict_contacts=rawid.map(inside.contacts).fillna(0)/d.elderly*1000
 add('경계보정 및 중복경계 제외',pick(strict_stops,strict_contacts))
 for q in [.20,.30]:add(f'상하위 {q*100:.0f}% 기준',pick(d.stops_per_1000,d.contacts_per_1000,q))
 pd.DataFrame(scenarios).to_csv(RES/'sensitivity.csv',index=False,encoding='utf-8-sig')
 # 후보 분포와 공간 지표는 실제 주민의 접근률이 아님을 명시한다.
 extra={'candidate_districts':d[d.candidate_june].groupby('gu').size().to_dict(),'contacts_per_1000_median':float(d.contacts_per_1000.median()),'core_coverage300_median':float(d.loc[d.core_candidate,'coverage300'].median()),'core_stop_ratio_median':float(d.loc[d.core_candidate,'stops_per_1000'].median()),'core_contacts_ratio_median':float(d.loc[d.core_candidate,'contacts_per_1000'].median()),'core_geometric_below90':int(((d.coverage300<.90)&d.core_candidate).sum()),'sensitivity':scenarios,'checks':'PASS'}
 (RES/'verification.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(extra,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
