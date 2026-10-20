"""경계 민감도: 서울 밖(경기·인천) 종합병원을 도착지에 추가하여 핵심 지역이 유지되는지 확인한다.
실행: python hospital_access_boundary.py  (hospital_access.py 실행 후)

- 추가 도착지: 건강보험심사평가원 '전국 병의원 및 약국 현황'의 병원정보서비스 중 종별 '종합병원', 시도 경기·인천
- 판정 방식은 hospital_access.py와 동일(버스 N구간·철도 K km·도보 500m, 16개 기준 + 9월 자료)
- 한계: 버스 정류장 좌표는 서울시 정류소 자료만 있어, 경기 구간 정류장에서 내리는 버스 직행은
  병원 300m 이내에 서울 정류장이 있는 경우만 반영된다(보수적 판정). 철도는 수도권 전체 역을 사용한다.
"""
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

import hospital_access as ha
from analyze import boundaries, load_population

ROOT = Path(__file__).resolve().parent
RAW, RES = ROOT / 'data/raw', ROOT / 'results'
HIRA = RAW / 'hira_hospitals_gyeonggi_incheon.csv'


def extract_from_zip(zpath):
    """심평원 zip에서 병원정보서비스 시트를 읽어 경기·인천 종합병원만 저장한다."""
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if '병원정보' in n.encode('cp437').decode('cp949', 'ignore') or '병원정보' in n]
        name = names[0] if names else [n for n in z.namelist() if n.lower().endswith(('.xlsx', '.csv'))][0]
        with z.open(name) as f:
            df = pd.read_excel(f, dtype=str) if name.lower().endswith('.xlsx') else pd.read_csv(f, dtype=str, encoding='cp949')
    df.columns = [c.strip() for c in df.columns]
    keep = df[(df['종별코드명'] == '종합병원') & (df['시도코드명'].isin(['경기', '인천']))]
    keep.to_csv(HIRA, index=False, encoding='utf-8-sig')
    return keep


def load_outside():
    h = pd.read_csv(HIRA, encoding='utf-8-sig', dtype=str).dropna(subset=['좌표(x)', '좌표(y)'])
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    h['x_m'], h['y_m'] = tr.transform(h['좌표(x)'].astype(float).to_numpy(), h['좌표(y)'].astype(float).to_numpy())
    h['사업장명'] = h['요양기관명']
    return h[['사업장명', '시도코드명', 'x_m', 'y_m']].reset_index(drop=True)


def main():
    if len(sys.argv) > 1:
        extract_from_zip(sys.argv[1])
    recs, polys, to_m, _ = boundaries()
    recs = recs.merge(load_population(), on=['gu', 'dong'], how='left', validate='one_to_one')
    seoul = ha.load_hospitals()
    outside = load_outside()
    hosp = pd.concat([seoul[['사업장명', 'x_m', 'y_m']].assign(시도코드명='서울'), outside], ignore_index=True)
    rail = ha.load_rail(to_m)
    xs, ys, owner = ha.grid_points(polys)
    D = ha.station_matrix(rail, hosp)

    res = {}
    for month in ['202606', '202609']:
        stops = pd.read_csv(RES / f'stops_audit_{month}.csv', encoding='utf-8-sig', dtype={'NODE_ID': str})
        stops = stops[stops.poly_id >= 0].reset_index(drop=True)
        M = ha.stop_matrix(month, stops, hosp)
        res[month] = ha.evaluate(xs, ys, stops, M, rail, D, hosp)

    served, bus_min, rail_min, walk = res['202606']
    shares = []
    for n in ha.N_GRID:
        for k in ha.K_GRID:
            shares.append(ha.dong_table(owner, served, ha.near_any(bus_min, rail_min, walk, n, k), len(polys)).gap_share.to_numpy())
    S = np.vstack(shares)
    base = ha.dong_table(owner, served, ha.near_any(bus_min, rail_min, walk, ha.BASE_N, ha.BASE_K), len(polys))
    s9, b9, r9, w9 = res['202609']
    sep = ha.dong_table(owner, s9, ha.near_any(b9, r9, w9, ha.BASE_N, ha.BASE_K), len(polys))

    d = recs[['gu', 'dong', 'elderly']].copy()
    d['gap_share_with_outside'] = base.gap_share.to_numpy()
    d['robust_with_outside'] = ((S >= ha.GAP_SHARE).all(0)) & (sep.gap_share.to_numpy() >= ha.GAP_SHARE)
    orig = pd.read_csv(RES / 'hospital_access_dong.csv', encoding='utf-8-sig')
    d['gap_share_seoul_only'] = orig.gap_share.to_numpy()
    d['core_seoul_only'] = orig.gap_robust.eq(1).to_numpy()
    d.to_csv(RES / 'hospital_access_boundary_dong.csv', index=False, encoding='utf-8-sig')

    core = d[d.core_seoul_only]
    kept = core[core.robust_with_outside]
    dropped = core[~core.robust_with_outside]
    summary = {
        'outside_general_hospitals': int(len(outside)),
        'outside_by_sido': outside['시도코드명'].value_counts().to_dict(),
        'served_gap_share_seoul_only': float(orig.gap_cells.sum() / orig.served_cells.sum()) if 'gap_cells' in orig else None,
        'served_gap_share_with_outside': float(base.gap_cells.sum() / base.served_cells.sum()),
        'core_seoul_only': int(len(core)),
        'core_kept_with_outside': int(len(kept)),
        'core_kept_elderly': int(kept.elderly.sum()),
        'core_dropped': (dropped.gu + ' ' + dropped.dong).tolist(),
        'core_dropped_gap_share_with_outside': dict(zip(dropped.gu + ' ' + dropped.dong, dropped.gap_share_with_outside.round(3))),
        'new_core_with_outside_not_in_seoul_only': (d[d.robust_with_outside & ~d.core_seoul_only].gu + ' ' + d[d.robust_with_outside & ~d.core_seoul_only].dong).tolist(),
    }
    (RES / 'hospital_access_boundary_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
