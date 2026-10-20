"""판정 기준을 바꿔 즉시 다시 계산한다(결과 파일은 덮어쓰지 않음). 약 10초.

예시
  python scenario.py                      # 기본 기준(버스 10구간, 철도 5km)
  python scenario.py --n 12 --k 6         # 버스 12구간, 철도 6km
  python scenario.py --walk-stop 200      # 고령자 보행거리를 200m로 줄였을 때
  python scenario.py --outside            # 경기·인천 종합병원까지 도착지에 포함
"""
import argparse

import numpy as np
import pandas as pd

import hospital_access as ha
from analyze import boundaries, load_population


def main():
    p = argparse.ArgumentParser(description='환승 없는 종합병원 접근 — 기준 변경 시나리오')
    p.add_argument('--n', type=int, default=ha.BASE_N, help='버스 최대 정류장 구간 수 (기본 10)')
    p.add_argument('--k', type=float, default=ha.BASE_K, help='철도 최대 직선거리 km (기본 5)')
    p.add_argument('--walk-stop', type=int, default=ha.WALK_STOP, help='정류장까지 보행 거리 m (기본 300)')
    p.add_argument('--month', default='202606', choices=['202606', '202609'])
    p.add_argument('--outside', action='store_true', help='경기·인천 종합병원 94곳 추가')
    p.add_argument('--top', type=int, default=10)
    a = p.parse_args()

    ha.WALK_STOP = a.walk_stop
    recs, polys, to_m, _ = boundaries()
    recs = recs.merge(load_population(), on=['gu', 'dong'], how='left', validate='one_to_one')
    hosp = ha.load_hospitals()[['사업장명', 'x_m', 'y_m']]
    if a.outside:
        import hospital_access_boundary as hb
        hosp = pd.concat([hosp, hb.load_outside()[['사업장명', 'x_m', 'y_m']]], ignore_index=True)
    rail = ha.load_rail(to_m)
    xs, ys, owner = ha.grid_points(polys)
    stops = pd.read_csv(ha.RES / f'stops_audit_{a.month}.csv', encoding='utf-8-sig', dtype={'NODE_ID': str})
    stops = stops[stops.poly_id >= 0].reset_index(drop=True)
    served, bus_min, rail_min, walk = ha.evaluate(xs, ys, stops, ha.stop_matrix(a.month, stops, hosp), rail,
                                                  ha.station_matrix(rail, hosp), hosp)
    g = ha.dong_table(owner, served, ha.near_any(bus_min, rail_min, walk, a.n, a.k), len(polys))
    d = pd.concat([recs[['gu', 'dong', 'elderly']], g], axis=1)
    d['est_elderly_in_gap'] = d.elderly * d.gap_share.fillna(0)
    gap = d[d.gap_share >= ha.GAP_SHARE].sort_values('est_elderly_in_gap', ascending=False)

    print(f'\n[기준] 버스 {a.n}구간 · 철도 {a.k:g}km · 정류장 보행 {a.walk_stop}m · {a.month[:4]}년 {int(a.month[4:])}월'
          f" · 도착지 종합병원 {len(hosp)}곳{' (경기·인천 포함)' if a.outside else ''}")
    print(f'판정 대상 격자 {int(served.sum()):,}개 중 직행 공백 {g.gap_cells.sum() / g.served_cells.sum() * 100:.1f}%')
    print(f'직행 공백 지역 추정 고령인구 약 {d.est_elderly_in_gap.sum() / 10000:.1f}만 명')
    print(f'직행 공백 비율 50% 이상 행정동 {len(gap)}곳 (고령인구 {int(gap.elderly.sum()):,}명)\n')
    print(gap.head(a.top).assign(직행공백=lambda x: (x.gap_share * 100).round(0).astype(int).astype(str) + '%',
                                 추정고령인구=lambda x: x.est_elderly_in_gap.round(0).astype(int))
          [['gu', 'dong', 'elderly', '직행공백', '추정고령인구']]
          .rename(columns={'gu': '구', 'dong': '동', 'elderly': '고령인구'}).to_string(index=False))


if __name__ == '__main__':
    main()
