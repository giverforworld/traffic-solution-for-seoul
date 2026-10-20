"""서울 고령인구와 버스 공급 격차 분석. 실행: python analyze.py

공식 원자료만 읽으며 인구를 생성·추정하지 않습니다. 거리·면적은 EPSG:5179.
2026-04-01 경계와 2026년 2분기 인구를 427개 행정동으로 결합합니다.
"""
from pathlib import Path
from io import StringIO
import json, re, hashlib, platform
import numpy as np
import pandas as pd
from shapely.geometry import shape, Point
from shapely.ops import transform, unary_union
from shapely import STRtree, make_valid
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parent
RAW, RES = ROOT/'data/raw', ROOT/'results'
RES.mkdir(exist_ok=True)
def norm(s):
    s=re.sub(r'^\d+\)\s*', '', str(s)).strip().replace('·', '.').replace('ㆍ', '.')
    return re.sub(r'제(?=\d+(?:\.\d+)*동$)', '', s)

def load_population():
    j = json.loads((RAW/'elder_all_data.json').read_text(encoding='utf8'))
    p = pd.read_html(StringIO(j['result'][0]))[0]
    p.columns = ['city', 'gu', 'dong', 'population', 'elderly']
    p = p.dropna(subset=['population']).copy()
    p[['city','gu']] = p[['city','gu']].ffill()
    p['dong'] = p.dong.map(norm)
    totals = p[p.dong=='소계'].set_index('gu')
    p = p[p.dong!='소계'].copy()
    p = p.groupby(['gu','dong'],as_index=False)[['population','elderly']].sum()
    p[['population','elderly']] = p[['population','elderly']].astype(int)
    for gu,g in p.groupby('gu'):
        assert g.population.sum()==totals.loc[gu,'population'], ('population',gu)
        assert g.elderly.sum()==totals.loc[gu,'elderly'], ('elderly',gu)
    assert p.elderly.sum()==totals.loc['소계','elderly']
    assert p.population.sum()==totals.loc['소계','population']
    return p

def boundaries():
    parsed=json.loads((RAW/'boundary_geometry.json').read_text(encoding='utf8'))
    to_m=Transformer.from_crs(4326,5179,always_xy=True).transform
    gus=[make_valid(transform(to_m,shape(f['geometry']))) for f in parsed['SIGUNGU']['features']]
    names=[f['properties']['name'] for f in parsed['SIGUNGU']['features']]
    records=[];polys=[]
    for f in parsed['DONG']['features']:
        poly=make_valid(transform(to_m,shape(f['geometry'])))
        gi=int(np.argmax([poly.intersection(g).area for g in gus]))
        records.append({'gu':names[gi],'dong':norm(f['properties']['name']),'area_km2':poly.area/1e6,'boundary_id':f['id']})
        polys.append(poly)
    return pd.DataFrame(records),polys,to_m,parsed

def load_stops(month,to_m,polys):
    stamp={'202606':'20260602','202609':'20260902'}[month]
    s=pd.read_excel(RAW/f'stops_{stamp}.xlsx',dtype={'NODE_ID':str,'ARS_ID':str})
    qa={'source_rows':len(s),'river_piers_excluded':int((s['정류소타입']=='한강선착장').sum())}
    s=s[s['정류소타입']!='한강선착장'].copy()
    qa['duplicate_node_ids']=int(s.NODE_ID.duplicated().sum())
    assert qa['duplicate_node_ids']==0
    assert s['X좌표'].between(125,129).all() and s['Y좌표'].between(36,39).all()
    xy=np.array(to_m(s['X좌표'].to_numpy(),s['Y좌표'].to_numpy())).T
    tree=STRtree(polys);assigned=[];methods=[];distances=[]
    for x,y in xy:
        pt=Point(x,y);ii=tree.query(pt,predicate='intersects')
        if len(ii):
            assigned.append(int(min(ii)));methods.append('inside' if len(ii)==1 else 'boundary_tie');distances.append(0.)
        else:
            k=int(tree.nearest(pt));d=pt.distance(polys[k]);distances.append(d)
            assigned.append(k if d<=30 else -1);methods.append('nearest_30m' if d<=30 else 'outside')
    s['poly_id']=assigned;s['assign_method']=methods;s['boundary_distance_m']=distances
    s['x_m']=xy[:,0];s['y_m']=xy[:,1]
    qa['assignment_methods']=s.assign_method.value_counts().to_dict()
    # 월간 승하차 자료에서 이용실적이 1건 이상인 노선-정류장 조합을 센다.
    r=pd.read_csv(RAW/f'ridership_{month}.csv',encoding='cp949',dtype={'표준버스정류장ID':str,'버스정류장ARS번호':str,'노선번호':str})
    assert r['사용년월'].astype(str).eq(month).all()
    nums=[c for c in r if '총승객수' in c]
    assert len(nums)==48
    r['board_alight']=r[nums].sum(axis=1)
    qa['ridership_rows']=len(r)
    active=r[r.board_alight>0].copy()
    stopgroup=active.groupby('표준버스정류장ID').agg(route_contacts=('노선번호','nunique'),board_alight=('board_alight','sum'))
    s=s.join(stopgroup,on='NODE_ID')
    s[['route_contacts','board_alight']]=s[['route_contacts','board_alight']].fillna(0)
    qa['active_nodes_in_ridership']=len(stopgroup)
    qa['active_nodes_matched_location']=int(stopgroup.index.isin(s.NODE_ID).sum())
    qa['located_nodes_with_active_routes']=int((s.route_contacts>0).sum())
    qa['ridership_total_board_alight']=int(r.board_alight.sum())
    qa['matched_board_alight_share']=float(s.board_alight.sum()/r.board_alight.sum())
    # 서울 외곽 정류장도 원파일에 포함되어 있다. 서울 내부 및 경계 30m 보정만 집계.
    qa['analysis_stops']=int((s.poly_id>=0).sum())
    assigned_s=s[s.poly_id>=0]
    agg=assigned_s.groupby('poly_id').agg(stops=('NODE_ID','size'),route_contacts=('route_contacts','sum'),board_alight=('board_alight','sum'),active_stops=('route_contacts',lambda a:int((a>0).sum())))
    points=[Point(x,y) for x,y in xy];ptree=STRtree(points)
    coverage={300:[],500:[]};neighbor=[];clusters=[]
    for k,p in enumerate(polys):
        near=ptree.query(p.buffer(500),predicate='intersects')
        for radius in [300,500]:
            use=[points[i].buffer(radius,quad_segs=8) for i in near if points[i].distance(p)<=radius]
            ratio=unary_union(use).intersection(p).area/p.area if use else 0.
            coverage[radius].append(min(1.,ratio))
        neighbor.append(len(ptree.query(p.buffer(50),predicate='intersects')))
        coords=xy[np.asarray(assigned)==k]
        if len(coords):
            pairs=cKDTree(coords).query_pairs(50,output_type='ndarray')
            if len(pairs):
                graph=coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(coords),len(coords)))
                count,_=connected_components(graph,directed=False)
            else:count=len(coords)
        else:count=0
        clusters.append(count)
    agg=agg.reindex(range(len(polys)),fill_value=0)
    agg['clusters50']=clusters;agg['neighbor50']=neighbor
    for radius,values in coverage.items():agg[f'coverage{radius}']=values
    s.to_csv(RES/f'stops_audit_{month}.csv',index=False,encoding='utf-8-sig')
    return agg,qa

def select(df,supply,contact='contacts_per_1000'):
    # 분위수 기준은 점검 후보 선별용이며, 실제 부족이나 정류장 신설 기준이 아니다.
    return (df.elderly>=df.elderly.quantile(.75)) & (df[supply]<=df[supply].quantile(.25)) & (df[contact]<=df[contact].quantile(.25))

def main():
    p=load_population();b,polys,to_m,parsed=boundaries()
    assert len(p)==427 and len(b)==427
    d=b.merge(p,on=['gu','dong'],how='left',validate='one_to_one')
    assert d.elderly.notna().all(),d[d.elderly.isna()]
    qa={};data={}
    for month in ['202606','202609']:
        a,q=load_stops(month,to_m,polys);data[month]=a;qa[month]=q
    d=d.join(data['202606'])
    d['elderly_share']=d.elderly/d.population
    for col in ['stops','route_contacts','clusters50','neighbor50']:
        d[col+'_per_1000']=1000*d[col]/d.elderly
    d['contacts_per_1000']=d.route_contacts_per_1000
    d['candidate_june']=select(d,'stops_per_1000')
    d['candidate_cluster50']=select(d,'clusters50_per_1000')
    d['candidate_neighbor50']=select(d,'neighbor50_per_1000')
    sep=d[['elderly']].join(data['202609'])
    sep['stops_per_1000']=sep.stops/sep.elderly*1000
    sep['contacts_per_1000']=sep.route_contacts/sep.elderly*1000
    d['candidate_september']=select(sep,'stops_per_1000')
    d['robustness_count']=d[['candidate_june','candidate_cluster50','candidate_neighbor50','candidate_september']].sum(axis=1)
    d['core_candidate']=d.candidate_june & (d.robustness_count>=3)
    d['stops_september']=data['202609'].stops
    d['contacts_september']=data['202609'].route_contacts
    d['review_type']=np.where(d.coverage300<.90,'보행 접근 현장점검','운행 여건 현장점검')
    d=d.sort_values(['core_candidate','robustness_count','elderly'],ascending=[False,False,False])
    d.to_csv(RES/'dong_metrics.csv',index=False,encoding='utf-8-sig')
    cand=d[d.candidate_june].copy();cand.to_csv(RES/'priority_candidates.csv',index=False,encoding='utf-8-sig')
    core=d[d.core_candidate]
    gus=d.groupby('gu').agg(population=('population','sum'),elderly=('elderly','sum'),stops=('stops','sum'),route_contacts=('route_contacts','sum'),core_candidates=('core_candidate','sum'))
    gus['stops_per_1000']=1000*gus.stops/gus.elderly
    gus.to_csv(RES/'gu_metrics.csv',encoding='utf-8-sig')
    summary={'population':int(d.population.sum()),'elderly':int(d.elderly.sum()),'dong_count':len(d),'elderly_q75':float(d.elderly.quantile(.75)),'stops_per_1000_q25':float(d.stops_per_1000.quantile(.25)),'contacts_per_1000_q25':float(d.contacts_per_1000.quantile(.25)),'stops_per_1000_median':float(d.stops_per_1000.median()),'stops_per_1000_min':float(d.stops_per_1000.min()),'stops_per_1000_max':float(d.stops_per_1000.max()),'candidates_june':len(cand),'core_candidates':len(core),'core_elderly':int(core.elderly.sum()),'core_elderly_share_city':float(core.elderly.sum()/d.elderly.sum()),'scenario_counts':{c:int(d[c].sum()) for c in ['candidate_june','candidate_cluster50','candidate_neighbor50','candidate_september']},'qa':qa,'correlation_stop_contact':float(d.stops_per_1000.corr(d.contacts_per_1000)),'stops_total':int(d.stops.sum()),'route_contacts_total':int(d.route_contacts.sum()),'core':core[['gu','dong','elderly','stops','route_contacts','stops_per_1000','contacts_per_1000','coverage300','coverage500','robustness_count','review_type']].to_dict('records')}
    (RES/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob('*'))}
    (RES/'source_sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Validation passed: 25 district totals, city totals, 427 one-to-one joins, coordinate range, unique stop IDs, month checks.')

if __name__=='__main__':main()
