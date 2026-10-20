"""공식 원자료 재다운로드. 기본 분석은 동봉 스냅샷을 사용한다.

온라인 원본이 바뀔 수 있으므로 기존 raw 폴더를 덮어쓰지 않는다.
재수집 파일은 data/refetched 아래에 저장한다.
"""
from pathlib import Path
from html.parser import HTMLParser
import json,re,time
import requests
BASE=Path(__file__).resolve().parent/'data/refetched'
BASE.mkdir(parents=True,exist_ok=True)
S=requests.Session()
def save_get(name,url):
 r=S.get(url,timeout=60);r.raise_for_status();(BASE/name).write_bytes(r.content);return r.text
def download(name,inf,seq,infseq):
 r=S.post('https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false',data={'infId':inf,'seq':seq,'infSeq':infseq},timeout=120)
 r.raise_for_status();(BASE/name).write_bytes(r.content)
def main():
 for args in [('stops_20260602.xlsx','OA-15067','55','1'),('stops_20260902.xlsx','OA-15067','58','1'),('ridership_202606.csv','OA-12913','111','3'),('ridership_202609.csv','OA-12913','114','3')]:download(*args)
 # 이용조건이 명시된 SGIS 기반 가공자료의 고정 커밋을 사용한다.
 source_url='https://raw.githubusercontent.com/vuski/admdongkor/7360288277dfd12d74e54b959c59bdd66f852e3a/ver20260401/HangJeongDong_ver20260401.geojson'
 national=json.loads(save_get('national_boundary_source.geojson',source_url))
 from shapely.geometry import shape,mapping
 from shapely.ops import unary_union
 from collections import defaultdict
 seoul=[f for f in national['features'] if str(f['properties'].get('adm_cd2','')).startswith('11')]
 dong=[];groups=defaultdict(list)
 for i,f in enumerate(seoul):
  a=f['properties'];name=a['adm_nm'].split(' ',2)[2];gu=a['sggnm']
  dong.append({'type':'Feature','id':str(i),'properties':{'name':name,'gu':gu,'adm_cd2':a['adm_cd2']},'geometry':f['geometry']});groups[gu].append(shape(f['geometry']))
 gus=[{'type':'Feature','id':str(i),'properties':{'name':gu},'geometry':mapping(unary_union(polys))} for i,(gu,polys) in enumerate(groups.items())]
 boundary={'DONG':{'type':'FeatureCollection','features':dong},'SIGUNGU':{'type':'FeatureCollection','features':gus}}
 (BASE/'boundary_geometry.json').write_text(json.dumps(boundary,ensure_ascii=False),encoding='utf8')
 text=save_get('elder_stat.html','https://stat.eseoul.go.kr/statHtml/statHtml.do?orgId=201&tblId=DT_201004_A030002&conn_path=I2&mode=tab')
 params={}
 class Hidden(HTMLParser):
  def handle_starttag(self,t,attrs):
   a=dict(attrs)
   if t=='input' and a.get('type')=='hidden' and a.get('name'):params[a['name']]=a.get('value','')
 Hidden().feed(text)
 meta={'objVarId':'A','searchCondition':'J','orgId':'201','tblId':'DT_201004_A030002','dataOpt':'ko','language':'ko','dbUser':'NSI_IN_201.'}
 def classes(itm,lvl):
  r=S.post('https://stat.eseoul.go.kr/statHtml/classDivSelect.do',data=meta|{'itmId':itm,'lvl':lvl},timeout=45);r.raise_for_status();return r.json()['result']
 gu=classes('001',1);all_ids=['001']+[g['itmId'] for g in gu]
 for g in gu:
  all_ids +=[a['itmId'] for a in classes(g['itmId'],2)];time.sleep(.1)
 fields=[{'targetId':'PRD','targetValue':'','prdValue':'Q,202602,@'},{'targetId':'ITM_ID','targetValue':'T001','prdValue':''}]
 fields +=[{'targetId':'OV_L1_ID','targetValue':a,'prdValue':''} for a in all_ids]
 fields +=[{'targetId':'OV_L2_ID','targetValue':a,'prdValue':''} for a in ['001','002']]
 params.update({'fieldList':json.dumps(fields),'rowAxis':'A','colAxis':'TIME,B','itemMultiply':'1','dimCo':'12876','reqCellCnt':str(len(all_ids)*2),'tableType':'default','viewKind':'1','view':'table','headCheck':'Q','isFirst':'Y','selectAllFlag':'N','enableLevelExpr':'Y','prdSort':'desc','classAllArr':json.dumps([{'objVarId':'A','ovlSn':'1'},{'objVarId':'B','ovlSn':'2'}]),'classSet':json.dumps([{'objVarId':'A','ovlSn':'1','visible':'true'},{'objVarId':'B','ovlSn':'2','visible':'true'}])})
 r=S.post('https://stat.eseoul.go.kr/statHtml/html.do',data=params,timeout=90);r.raise_for_status();j=r.json();assert 'result' in j,j
 (BASE/'elder_all_data.json').write_text(r.text,encoding='utf8')
 print('Downloaded to data/refetched. Compare checksums and dates before replacing the supplied snapshots.')
if __name__=='__main__':main()
