"""환승 없는 종합병원 근거리 접근성 분석(100m 격자). 실행: python hospital_access.py

analyze.py 실행 후 사용한다. 서울을 100m 격자로 나누고, 정류장 300m 권역 안의 각 지점에서
'걸어서 갈 수 있는 정류장·역에서 환승 없이 가까운 종합병원에 갈 수 있는가'를 판정한다.

- 도착지: 서울시 병원 인허가 정보 중 영업 중인 종합병원(59곳)
- 보행 접근: 지점에서 버스정류장 300m, 도시철도역 500m, 종합병원 500m 이내(직선거리)
- 버스 직행: 같은 노선(방향별 노선명, 심야 N노선 제외)에서 출발 정류장 순번 < 도착 정류장 순번,
  순번 차(정류장 구간 수)가 N 이하이고, 도착 정류장이 병원 반경 300m 이내
- 철도 직행: 출발 역과 병원 반경 500m 이내 역이 같은 호선이고 두 역의 직선거리가 K km 이하
- 판정 대상: 정류장 300m 권역 안의 격자(공급 지표상 버스 서비스를 받는 지역)
- 지표: 행정동별 '직행 공백 비율' = 판정 대상 격자 중 근거리 직행 종합병원이 없는 격자 비율
- 기준 N(8·10·12·15구간) × K(4·5·6·8km) 16개 조합으로 반복 계산(기본 N=10, K=5)
실측 통행시간·배차·저상버스·무장애 동선·서울 밖 병원·격자별 실제 거주인구는 반영하지 않는다.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import STRtree, contains_xy
from shapely.ops import unary_union
from scipy.spatial import cKDTree
from analyze import boundaries, load_population

ROOT = Path(__file__).resolve().parent
RAW, RES = ROOT / 'data/raw', ROOT / 'results'

CELL = 100
WALK_STOP, WALK_RAIL, WALK_HOSP = 300, 500, 500
HOSP_STOP, HOSP_RAIL = 300, 500
N_GRID, K_GRID = [8, 10, 12, 15], [4, 5, 6, 8]
BASE_N, BASE_K = 10, 5
GAP_SHARE = 0.5   # 직행 공백 비율이 50% 이상인 동을 '의료 직행 사각지대'로 본다
TRACK = 60


def load_hospitals():
    h = pd.read_csv(RAW / 'hospitals_20261020.csv', encoding='cp949', dtype=str)
    h = h[(h['영업상태코드'] == '01') & (h['업태구분명'] == '종합병원')].dropna(subset=['좌표정보(X)', '좌표정보(Y)']).copy()
    tr = Transformer.from_crs(5174, 5179, always_xy=True)
    h['x_m'], h['y_m'] = tr.transform(h['좌표정보(X)'].astype(float).to_numpy(), h['좌표정보(Y)'].astype(float).to_numpy())
    return h.reset_index(drop=True)


def load_rail(to_m):
    s = pd.read_csv(RAW / 'subway_master_20261020.csv', encoding='cp949', dtype=str)
    s['line'] = s['호선'].str.replace(r'\(연장\)', '', regex=True).str.strip()
    s['x_m'], s['y_m'] = to_m(s['경도'].astype(float).to_numpy(), s['위도'].astype(float).to_numpy())
    return s.reset_index(drop=True)


def stop_matrix(month, stops, hosp):
    """[정류장, 병원] 환승 없는 최소 정류장 구간 수(심야 N노선 제외). 불가는 inf."""
    r = pd.read_csv(RAW / f'ridership_{month}.csv', encoding='cp949', dtype=str)
    r = r[~r['노선번호'].str.startswith('N')]
    r['seq'] = pd.to_numeric(r['역명'].str.extract(r'\((\d+)\)$')[0], errors='coerce')
    r = r.dropna(subset=['seq'])[['노선명', '표준버스정류장ID', 'seq']].drop_duplicates()
    idx = pd.Series(np.arange(len(stops)), index=stops.NODE_ID.to_numpy())
    r = r[r['표준버스정류장ID'].isin(idx.index)]
    tree = cKDTree(stops[['x_m', 'y_m']].to_numpy())
    stop_h = {}
    for hi, row in hosp.iterrows():
        for si in tree.query_ball_point([row.x_m, row.y_m], HOSP_STOP):
            stop_h.setdefault(si, []).append(hi)
    M = np.full((len(stops), len(hosp)), np.inf)
    for _, g in r.groupby('노선명'):
        g = g.sort_values('seq')
        seq = g.seq.to_numpy(); si = idx[g['표준버스정류장ID']].to_numpy()
        tgt = [(seq[j], h) for j in range(len(g)) for h in stop_h.get(si[j], ())]
        for i in range(len(g)):
            for sj, h in tgt:
                d = sj - seq[i]
                if 0 < d <= TRACK and d < M[si[i], h]:
                    M[si[i], h] = d
    return M


def station_matrix(rail, hosp):
    """[역, 병원] 같은 호선 역 간 최소 직선거리(km). 불가는 inf."""
    rk = cKDTree(rail[['x_m', 'y_m']].to_numpy())
    D = np.full((len(rail), len(hosp)), np.inf)
    for hi, h in hosp.iterrows():
        for j in rk.query_ball_point([h.x_m, h.y_m], HOSP_RAIL):
            same = np.where(rail.line.to_numpy() == rail.line.iloc[j])[0]
            dist = np.hypot(rail.x_m.to_numpy()[same] - rail.x_m.iloc[j], rail.y_m.to_numpy()[same] - rail.y_m.iloc[j]) / 1000
            D[same, hi] = np.minimum(D[same, hi], dist)
    return D


def grid_points(polys):
    city = unary_union(polys)
    x0, y0, x1, y1 = city.bounds
    xs, ys = np.meshgrid(np.arange(x0 + CELL / 2, x1, CELL), np.arange(y0 + CELL / 2, y1, CELL))
    xs, ys = xs.ravel(), ys.ravel()
    owner = np.full(len(xs), -1)
    for k, p in enumerate(polys):
        m = (owner < 0) & contains_xy(p, xs, ys)
        owner[m] = k
    keep = owner >= 0
    return xs[keep], ys[keep], owner[keep]


def evaluate(xs, ys, stops, M, rail, D, hosp):
    """격자별 [버스 최소 구간 수, 철도 최소 km, 도보 병원 여부]"""
    pts = np.c_[xs, ys]
    st = cKDTree(stops[['x_m', 'y_m']].to_numpy())
    served = np.array([len(v) > 0 for v in st.query_ball_point(pts, WALK_STOP)])
    bus_min = np.full((len(xs), M.shape[1]), np.inf)
    for i, near in enumerate(st.query_ball_point(pts, WALK_STOP)):
        if near:
            bus_min[i] = M[near].min(0)
    rk = cKDTree(rail[['x_m', 'y_m']].to_numpy())
    rail_min = np.full((len(xs), D.shape[1]), np.inf)
    for i, near in enumerate(rk.query_ball_point(pts, WALK_RAIL)):
        if near:
            rail_min[i] = D[near].min(0)
    hk = cKDTree(hosp[['x_m', 'y_m']].to_numpy())
    walk = np.array([len(v) > 0 for v in hk.query_ball_point(pts, WALK_HOSP)])
    return served, bus_min, rail_min, walk


def near_any(bus_min, rail_min, walk, n, k):
    return ((bus_min <= n) | (rail_min <= k)).any(1) | walk


def dong_table(owner, served, ok, n_dong):
    s = pd.DataFrame({'k': owner, 'served': served, 'gap': served & ~ok})
    g = s.groupby('k').agg(cells=('served', 'size'), served_cells=('served', 'sum'), gap_cells=('gap', 'sum'))
    g = g.reindex(range(n_dong), fill_value=0)
    g['gap_share'] = np.where(g.served_cells > 0, g.gap_cells / g.served_cells.clip(lower=1), np.nan)
    return g


def main():
    recs, polys, to_m, _ = boundaries()
    recs = recs.merge(load_population(), on=['gu', 'dong'], how='left', validate='one_to_one')
    dm = pd.read_csv(RES / 'dong_metrics.csv', encoding='utf-8-sig')
    recs = recs.merge(dm[['gu', 'dong', 'stops_per_1000', 'coverage300', 'core_candidate']], on=['gu', 'dong'], how='left', validate='one_to_one')
    assert len(recs) == 427 and recs.elderly.notna().all()
    hosp, rail = load_hospitals(), load_rail(to_m)
    assert len(hosp) == 59
    xs, ys, owner = grid_points(polys)
    D = station_matrix(rail, hosp)

    results = {}
    for month in ['202606', '202609']:
        stops = pd.read_csv(RES / f'stops_audit_{month}.csv', encoding='utf-8-sig', dtype={'NODE_ID': str})
        stops = stops[stops.poly_id >= 0].reset_index(drop=True)  # 서울 안 정류장(경계 30m 보정 포함)
        M = stop_matrix(month, stops, hosp)
        results[month] = evaluate(xs, ys, stops, M, rail, D, hosp)

    served, bus_min, rail_min, walk = results['202606']
    base_ok = near_any(bus_min, rail_min, walk, BASE_N, BASE_K)
    base = dong_table(owner, served, base_ok, len(polys))
    d = pd.concat([recs, base], axis=1)
    d['est_elderly_in_gap'] = d.elderly * d.gap_share.fillna(0)
    d['medical_gap'] = d.gap_share >= GAP_SHARE
    d['near_hosp_cells_median'] = np.nan
    # 동별 근거리 직행 가능 병원 수(정류장 권역 격자 기준 중앙값) — 사례 설명용
    reach_n = ((bus_min <= BASE_N) | (rail_min <= BASE_K)).sum(1)
    tmp = pd.DataFrame({'k': owner, 'n': reach_n, 'served': served})
    med = tmp[tmp.served].groupby('k').n.median()
    d['near_hosp_median'] = med.reindex(range(len(polys))).to_numpy()
    bm = np.where(np.isfinite(bus_min), bus_min, np.nan)
    with np.errstate(all='ignore'):
        nearest = np.nanmin(bm, axis=1)
    tmp['nearest'] = nearest
    d['nearest_bus_stops_median'] = tmp[tmp.served].groupby('k').nearest.median().reindex(range(len(polys))).to_numpy()

    grid, shares = [], []
    for n in N_GRID:
        for k in K_GRID:
            g = dong_table(owner, served, near_any(bus_min, rail_min, walk, n, k), len(polys))
            gap = (g.gap_share >= GAP_SHARE).to_numpy()
            shares.append(g.gap_share.to_numpy())
            grid.append({'max_bus_stops': n, 'max_rail_km': k,
                         'served_cells_without_near_onestep_share': float(g.gap_cells.sum() / g.served_cells.sum()),
                         'est_elderly_in_gap_cells': float((recs.elderly * g.gap_share.fillna(0)).sum()),
                         'gap_dongs': int(gap.sum()),
                         'gap_overlap_with_supply_candidates': int((gap & recs.core_candidate.eq(True).to_numpy()).sum())})
    S = np.vstack(shares)
    d['gap_share_min'] = np.nanmin(S, 0); d['gap_share_max'] = np.nanmax(S, 0)
    d['gap_robust'] = (S >= GAP_SHARE).mean(0)
    s9, b9, r9, w9 = results['202609']
    sep = dong_table(owner, s9, near_any(b9, r9, w9, BASE_N, BASE_K), len(polys))
    d['gap_share_sept'] = sep.gap_share.to_numpy()

    d.to_csv(RES / 'hospital_access_dong.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(grid).to_csv(RES / 'hospital_access_grid.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame({'x_m': xs, 'y_m': ys, 'dong_idx': owner, 'served': served, 'near_onestep_base': base_ok}).to_csv(
        RES / 'hospital_access_cells.csv.gz', index=False, compression='gzip')

    gapd = d[d.medical_gap].sort_values('gap_share', ascending=False)
    cand = d[d.core_candidate.eq(True)]
    case = {}
    for dong in ['암사1동', '암사2동', '암사3동']:
        r = d[(d.gu == '강동구') & (d.dong == dong)].iloc[0]
        case[dong] = {k: (None if pd.isna(r[k]) else float(r[k])) for k in
                      ['elderly', 'gap_share', 'near_hosp_median', 'nearest_bus_stops_median', 'stops_per_1000', 'coverage300']}
        case[dong]['supply_candidate'] = bool(r.core_candidate)
    summary = {
        'definition': {'cell_m': CELL, 'walk_stop_m': WALK_STOP, 'walk_rail_m': WALK_RAIL, 'walk_hosp_m': WALK_HOSP,
                       'hosp_stop_m': HOSP_STOP, 'hosp_rail_m': HOSP_RAIL, 'base_n': BASE_N, 'base_k': BASE_K,
                       'grid_n': N_GRID, 'grid_k': K_GRID, 'gap_share_threshold': GAP_SHARE, 'night_routes_excluded': True},
        'general_hospitals': int(len(hosp)),
        'cells_total': int(len(xs)), 'cells_served': int(served.sum()),
        'served_cells_gap_share_base': float((served & ~base_ok).sum() / served.sum()),
        'est_elderly_in_gap_base': float(d.est_elderly_in_gap.sum()),
        'est_elderly_in_gap_range': [min(g['est_elderly_in_gap_cells'] for g in grid), max(g['est_elderly_in_gap_cells'] for g in grid)],
        'gap_dongs_base': int(len(gapd)),
        'gap_dongs_elderly': int(gapd.elderly.sum()),
        'gap_dongs_range_over_grid': [min(g['gap_dongs'] for g in grid), max(g['gap_dongs'] for g in grid)],
        'gap_overlap_with_supply_candidates_base': int((d.medical_gap & d.core_candidate.eq(True)).sum()),
        'gap_overlap_with_supply_candidates_max_over_grid': int(max(g['gap_overlap_with_supply_candidates'] for g in grid)),
        'gap_dongs_robust_all16': int((d.gap_robust == 1).sum()),
        'gap_dongs_sept_base': int((d.gap_share_sept >= GAP_SHARE).sum()),
        'gap_dongs_sept_overlap': int(((d.gap_share_sept >= GAP_SHARE) & d.medical_gap).sum()),
        'gap_median_coverage300': float(gapd.coverage300.median()),
        'gap_median_stops_per_1000': float(gapd.stops_per_1000.median()),
        'city_median_stops_per_1000': float(d.stops_per_1000.median()),
        'city_median_gap_share': float(d.gap_share.median()),
        'supply_candidates_median_gap_share': float(cand.gap_share.median()),
        'spearman_stops_per_1000_vs_gap_share': float(d.stops_per_1000.corr(d.gap_share, method='spearman')),
        'gap_list': gapd[['gu', 'dong', 'elderly', 'gap_share', 'gap_share_min', 'gap_share_max', 'gap_robust', 'gap_share_sept',
                          'est_elderly_in_gap', 'near_hosp_median', 'nearest_bus_stops_median', 'stops_per_1000', 'coverage300']].to_dict('records'),
        'case_amsa': case,
    }
    (RES / 'hospital_access_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding='utf8')
    assert summary['cells_served'] > 0
    print(json.dumps({k: v for k, v in summary.items() if k != 'gap_list'}, ensure_ascii=False, indent=1, default=float))
    print(pd.DataFrame(grid).to_string())
    print(gapd[['gu', 'dong', 'elderly', 'gap_share', 'gap_share_min', 'gap_share_max', 'gap_robust', 'gap_share_sept', 'est_elderly_in_gap',
                'nearest_bus_stops_median', 'stops_per_1000', 'coverage300']].round(2).to_string())


if __name__ == '__main__':
    main()
