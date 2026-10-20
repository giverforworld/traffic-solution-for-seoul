"""GitHub에서 바로 열리는 인터랙티브 지도(GeoJSON)를 만든다. 실행: python make_map.py
- maps/medical_gap_dongs.geojson : 직행 공백 비율 50% 이상 45개 동(핵심 20개 동·경계 검증 결과 구분)
- maps/general_hospitals.geojson : 도착지 종합병원(서울 59곳 + 경기·인천 94곳)
GitHub 화면에서 파일을 열면 지도가 표시되고, 동·병원을 누르면 속성이 보인다.
"""
import json
from pathlib import Path

import pandas as pd
from pyproj import Transformer

import hospital_access as ha
import hospital_access_boundary as hb
from analyze import boundaries

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'maps'


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]


def main():
    OUT.mkdir(exist_ok=True)
    recs, polys, _, parsed = boundaries()
    d = pd.read_csv(ha.RES / 'hospital_access_dong.csv', encoding='utf-8-sig')
    b = pd.read_csv(ha.RES / 'hospital_access_boundary_dong.csv', encoding='utf-8-sig')
    feats = []
    for i, f in enumerate(parsed['DONG']['features']):
        r = d.iloc[i]
        if not r.gap_share >= ha.GAP_SHARE:
            continue
        core, kept = bool(r.gap_robust == 1), bool(b.robust_with_outside.iloc[i])
        tier = ('핵심 사각지대(경계 검증 유지)' if core and kept else
                '핵심 사각지대(경기·인천 병원 포함 시 제외)' if core else '기본 기준에서만 50% 이상')
        color = {'핵심 사각지대(경계 검증 유지)': '#b3261e', '핵심 사각지대(경기·인천 병원 포함 시 제외)': '#e08a2c'}.get(tier, '#f2b8b5')
        g = f['geometry']
        feats.append({'type': 'Feature', 'geometry': {'type': g['type'], 'coordinates': rnd(g['coordinates'])},
                      'properties': {'구': r.gu, '동': r.dong, '구분': tier, '고령인구': int(r.elderly),
                                     '직행 공백 비율': f'{r.gap_share * 100:.0f}%',
                                     '16개 기준 범위': f'{r.gap_share_min * 100:.0f}~{r.gap_share_max * 100:.0f}%',
                                     '9월 자료': f'{r.gap_share_sept * 100:.0f}%',
                                     '공백 지역 추정 고령인구': int(round(r.est_elderly_in_gap)),
                                     '고령 천 명당 정류장 수': round(float(r.stops_per_1000), 2),
                                     'fill': color, 'fill-opacity': 0.55, 'stroke': '#5a1209', 'stroke-width': 1}})
    (OUT / 'medical_gap_dongs.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': feats}, ensure_ascii=False), encoding='utf8')

    to_ll = Transformer.from_crs(5179, 4326, always_xy=True).transform
    hs = pd.concat([ha.load_hospitals()[['사업장명', 'x_m', 'y_m']].assign(지역='서울'),
                    hb.load_outside().rename(columns={'시도코드명': '지역'})[['사업장명', 'x_m', 'y_m', '지역']]], ignore_index=True)
    pts = []
    for _, h in hs.iterrows():
        lon, lat = to_ll(h.x_m, h.y_m)
        pts.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]},
                    'properties': {'병원': h.사업장명, '지역': h.지역, 'marker-symbol': 'hospital', 'marker-size': 'small',
                                   'marker-color': '#1f5fa8' if h.지역 == '서울' else '#7a8a99'}})
    (OUT / 'general_hospitals.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': pts}, ensure_ascii=False), encoding='utf8')
    print(f'saved maps: {len(feats)} dongs, {len(pts)} hospitals')


if __name__ == '__main__':
    main()
