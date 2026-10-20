"""보고서용 시각화. 실행: python figures.py"""
from pathlib import Path
import json,os,tempfile
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'seoul_transport_mpl'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,ticker
from matplotlib.patches import Polygon as MPolygon,Patch
from matplotlib.collections import PatchCollection
from analyze import boundaries,ROOT
RES,FIG=ROOT/'results',ROOT/'figures'
FIG.mkdir(exist_ok=True)
def setup():
 candidates=[Path('C:/Windows/Fonts/malgun.ttf'),Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'),Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]
 custom=os.environ.get('KOREAN_FONT')
 if custom:candidates.insert(0,Path(custom))
 found=next((p for p in candidates if p.exists()),None)
 if found:
  font_manager.fontManager.addfont(str(found));plt.rcParams['font.family']=font_manager.FontProperties(fname=found).get_name()
 else:  # 설치된 한글 글꼴을 이름으로 탐색(맑은 고딕·나눔고딕·애플고딕·Noto CJK KR)
  names={f.name for f in font_manager.fontManager.ttflist}
  fam=next((n for n in ['Malgun Gothic','NanumGothic','AppleGothic','Apple SD Gothic Neo','Noto Sans CJK KR','Noto Sans KR'] if n in names),None)
  if fam:plt.rcParams['font.family']=fam
  else:print('경고: 한글 글꼴을 찾지 못했습니다. KOREAN_FONT 환경변수에 한글 TTF 경로를 지정하세요.')
 plt.rcParams.update({'axes.unicode_minus':False,'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','savefig.facecolor':'white'})
def save(fig,name):
 fig.savefig(FIG/name,dpi=240,bbox_inches='tight',pad_inches=.16);plt.close(fig)
def main():
 setup();d=pd.read_csv(RES/'dong_metrics.csv');s=json.loads((RES/'summary.json').read_text(encoding='utf8'));v=json.loads((RES/'verification.json').read_text(encoding='utf8'))
 cand=d[d.candidate_june]
 fig,ax=plt.subplots(figsize=(7.1,3.45));ax.scatter(d.elderly/1000,d.stops_per_1000,s=14,c='#a9b5c0',alpha=.65,linewidths=0,label='전체 행정동')
 ax.scatter(cand.elderly/1000,cand.stops_per_1000,s=39,c='#c54b39',edgecolors='white',linewidths=.6,label=f'3개 선별 조건을 모두 충족한 {len(cand)}개 동',zorder=3)
 ax.axvline(s['elderly_q75']/1000,c='#627483',ls='--',lw=.9);ax.axhline(s['stops_per_1000_q25'],c='#627483',ls='--',lw=.9)
 ax.set_yscale('log');ax.set_ylim(.75,160);ax.set_yticks([1,2,4,8,16,32,64,128],labels=['1','2','4','8','16','32','64','128'])
 ax.set(xlabel='65세 이상 인구  (천 명)',ylabel='고령인구 1천 명당 정류장 수  (개, 로그 눈금)')
 ax.grid(axis='y',alpha=.14);ax.legend(loc='upper right',frameon=False,fontsize=8)
 for gu,dong,dx,dy in [('강동구','암사1동',-1.8,-.5),('성북구','석관동',.55,-.55),('강동구','길동',.6,.8)]:
  r=d[(d.gu==gu)&(d.dong==dong)].iloc[0];ax.annotate(dong,(r.elderly/1000,r.stops_per_1000),xytext=(r.elderly/1000+dx,r.stops_per_1000+dy),fontsize=8,color='#923a2d',arrowprops={'arrowstyle':'-','color':'#a96b61','lw':.6})
 fig.tight_layout();save(fig,'01_demand_supply.png')
 b,polys,_,parsed=boundaries();dd=b.merge(d[['gu','dong','candidate_june']],on=['gu','dong'],validate='one_to_one')
 fig,ax=plt.subplots(figsize=(7.1,4.05));patches=[];colors=[]
 for i,p in enumerate(polys):
  geoms=[p] if p.geom_type=='Polygon' else p.geoms
  for g in geoms:
   if g.geom_type!='Polygon':continue
   patches.append(MPolygon(np.array(g.exterior.coords)/1000,closed=True));colors.append('#c54b39' if dd.iloc[i].candidate_june else '#e5ebef')
 ax.add_collection(PatchCollection(patches,facecolors=colors,edgecolors='white',linewidths=.28))
 from shapely.geometry import shape
 from shapely.ops import transform
 from pyproj import Transformer
 tr=Transformer.from_crs(4326,5179,always_xy=True).transform
 for f in parsed['SIGUNGU']['features']:
  p=transform(tr,shape(f['geometry']));gs=[p] if p.geom_type=='Polygon' else p.geoms
  for g in gs:
   x,y=g.exterior.xy;ax.plot(np.asarray(x)/1000,np.asarray(y)/1000,c='#81919d',lw=.55)
  if f['properties']['name'] in set(cand.gu):
   c=p.representative_point();ax.text(c.x/1000,c.y/1000,f['properties']['name'],fontsize=7.3,ha='center',color='#223441')
 ax.autoscale();ax.set_aspect('equal');ax.axis('off');ax.legend(handles=[Patch(facecolor='#c54b39',label=f'우선점검 후보 {len(cand)}개 동'),Patch(facecolor='#e5ebef',label='그 외 행정동')],loc='upper left',frameon=False,fontsize=8)
 fig.tight_layout();save(fig,'02_seoul_candidates.png')
 stops=pd.read_csv(RES/'stops_audit_202606.csv');gidx=b.index[b.gu=='강동구'].tolist();gstop=stops[stops.poly_id.isin(gidx)]
 fig,ax=plt.subplots(figsize=(4.3,4.2));patches=[];colors=[]
 for i in gidx:
  p=polys[i];gs=[p] if p.geom_type=='Polygon' else p.geoms
  for g in gs:
   patches.append(MPolygon(np.array(g.exterior.coords)/1000,closed=True));colors.append('#f0b9aa' if dd.iloc[i].candidate_june else '#e9eef1')
 ax.add_collection(PatchCollection(patches,facecolors=colors,edgecolors='white',linewidths=1))
 ax.scatter(gstop.x_m/1000,gstop.y_m/1000,s=3.2,c='#304c5a',alpha=.75,linewidths=0)
 for i in gidx:
  if not dd.iloc[i].candidate_june:continue
  c=polys[i].representative_point();ax.text(c.x/1000,c.y/1000,b.iloc[i].dong,fontsize=8,ha='center',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none','pad':1.5})
 ax.autoscale();ax.set_aspect('equal');ax.axis('off');ax.text(.97,.95,'N ↑',transform=ax.transAxes,ha='right',fontsize=8)
 x0,y0=ax.get_xlim()[0]+.3,ax.get_ylim()[0]+.3;ax.plot([x0,x0+1],[y0,y0],c='#1e3443',lw=2);ax.text(x0+.5,y0+.13,'1 km',ha='center',fontsize=7)
 ax.legend(handles=[Patch(facecolor='#f0b9aa',label='우선점검 후보'),plt.Line2D([0],[0],marker='o',color='w',markerfacecolor='#304c5a',markersize=4,label='버스정류장')],frameon=False,loc='lower right',fontsize=7)
 fig.tight_layout();save(fig,'03_gangdong_detail.png')
 focus=d[(d.gu=='강동구')&d.candidate_june].sort_values('stops_per_1000')
 fig,ax=plt.subplots(figsize=(3.3,3.6));ax.barh(focus.dong,focus.stops_per_1000,color='#48768a',height=.55);ax.axvline(s['stops_per_1000_median'],c='#c54b39',ls='--',lw=1.1)
 for i,r in enumerate(focus.itertuples()):ax.text(r.stops_per_1000+.08,i,f'{r.stops_per_1000:.2f}',va='center',fontsize=8)
 ax.set_xlim(0,6.4);ax.set_xlabel('고령인구 1천 명당 정류장 수 (개)',fontsize=8);ax.text(s['stops_per_1000_median']+.1,.98,f'서울 동별 중앙값\n{s["stops_per_1000_median"]:.2f}',transform=ax.get_xaxis_transform(),va='top',color='#a44839',fontsize=7);ax.grid(axis='x',alpha=.12);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
 fig.tight_layout();save(fig,'04_gangdong_comparison.png')
 print('Saved four report figures.')
if __name__=='__main__':main()
