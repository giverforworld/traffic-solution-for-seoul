"""병원 직행 접근 분석 및 탄소 손익분기 그림. 실행: python access_figures.py"""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
from figures import setup, save, RES
from analyze import boundaries

GAP, OK, SUP, LINE, INK = '#c0392b', '#bcd3dc', '#e39b2d', '#8a9aa6', '#22313c'


def outline(ax, geom, **kw):
    for g in ([geom] if geom.geom_type == 'Polygon' else geom.geoms):
        if g.geom_type == 'Polygon':
            x, y = g.exterior.xy
            ax.plot(np.asarray(x) / 1000, np.asarray(y) / 1000, **kw)


def seoul_map(d, cells, parsed, polys):
    fig, ax = plt.subplots(figsize=(7.4, 5.9))
    sv = cells[cells.served]
    ok, gap = sv[sv.near_onestep_base], sv[~sv.near_onestep_base]
    ax.scatter(ok.x_m / 1000, ok.y_m / 1000, s=.55, c=OK, marker='s', linewidths=0)
    ax.scatter(gap.x_m / 1000, gap.y_m / 1000, s=.55, c=GAP, marker='s', linewidths=0)
    for i, p in enumerate(polys):
        if d.gap_core.iloc[i]:
            outline(ax, p, c='#5a1209', lw=1.1)
        elif d.core_candidate.iloc[i]:
            outline(ax, p, c=SUP, lw=1.3)
    tr = Transformer.from_crs(4326, 5179, always_xy=True).transform
    for f in parsed['SIGUNGU']['features']:
        outline(ax, transform(tr, shape(f['geometry'])), c=LINE, lw=.45)
    top = d[d.gap_core].sort_values('est_elderly_in_gap', ascending=False).head(6)
    off = {'평창동': (-3, 3), '수궁동': (-4, -2.5), '망원1동': (0.5, 5.5), '화곡본동': (-3.5, -6), '내곡동': (3, -3), '인헌동': (2, -3.5)}
    for _, r in top.iterrows():
        c = polys[int(r.name)].representative_point(); dx, dy = off.get(r.dong, (3, 2))
        ax.annotate(f'{r.gu} {r.dong}', (c.x / 1000, c.y / 1000), xytext=(c.x / 1000 + dx, c.y / 1000 + dy), fontsize=8, color='#7d1f15',
                    ha='center', arrowprops={'arrowstyle': '-', 'color': '#a8584e', 'lw': .6})
    ax.autoscale(); ax.set_aspect('equal'); ax.axis('off')
    ax.legend(handles=[Patch(facecolor=GAP, label='가까운 종합병원으로 가는 직행 수단이 없는 지역'),
                       Patch(facecolor=OK, label='직행 수단이 있는 지역'),
                       Line2D([], [], color='#5a1209', lw=1.2, label=f'의료 직행 사각지대 핵심 {int(d.gap_core.sum())}개 동'),
                       Line2D([], [], color=SUP, lw=1.4, label=f'정류장 공급량 기준 후보 {int(d.core_candidate.sum())}개 동')],
              loc='upper left', frameon=False, fontsize=8.6)
    fig.tight_layout(); save(fig, '07_access_gap_map.png')


def supply_vs_access(d):
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    o = ~(d.gap_core | d.core_candidate)
    ax.scatter(d.stops_per_1000[o], d.gap_share[o] * 100, s=12, c='#aab6c0', alpha=.6, linewidths=0, label='그 외 행정동')
    ax.scatter(d.stops_per_1000[d.core_candidate], d.gap_share[d.core_candidate] * 100, s=40, c=SUP, edgecolors='white', linewidths=.6,
               label=f'정류장 공급량 기준 후보({int(d.core_candidate.sum())})', zorder=3)
    ax.scatter(d.stops_per_1000[d.gap_core], d.gap_share[d.gap_core] * 100, s=44, c=GAP, edgecolors='white', linewidths=.6,
               label=f'의료 직행 사각지대 핵심({int(d.gap_core.sum())})', zorder=4)
    ax.axhline(50, c='#5d6d7a', ls='--', lw=.9)
    ax.set_xscale('log'); ax.set_xticks([1, 2, 4, 8, 16, 32, 64], labels=['1', '2', '4', '8', '16', '32', '64'])
    ax.set(xlabel='고령인구 1천 명당 버스정류장 수 (개, 로그 눈금)', ylabel='직행 공백 비율 (%)', ylim=(-3, 103))
    ax.grid(alpha=.13); ax.legend(loc='upper right', frameon=False, fontsize=8.5)
    fig.tight_layout(); save(fig, '08_supply_vs_access.png')


def amsa_case(d, cells, polys):
    names = ['암사1동', '암사2동', '암사3동']
    idx = [int(d[(d.gu == '강동구') & (d.dong == n)].index[0]) for n in names]
    from shapely.ops import unary_union
    area = unary_union([polys[i] for i in idx])
    x0, y0, x1, y1 = area.buffer(400).bounds
    c = cells[(cells.x_m.between(x0, x1)) & (cells.y_m.between(y0, y1)) & cells.served]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.6, 3.3), gridspec_kw={'width_ratios': [1.15, 1]})
    for sub, col in [(c[c.near_onestep_base], OK), (c[~c.near_onestep_base], GAP)]:
        for x, y in zip(sub.x_m, sub.y_m):
            ax.add_patch(Rectangle(((x - 50) / 1000, (y - 50) / 1000), .1, .1, color=col, lw=0))
    for i, n in zip(idx, names):
        outline(ax, polys[i], c=INK, lw=1)
        p = polys[i].representative_point(); ax.text(p.x / 1000, p.y / 1000, n, ha='center', fontsize=9.5, weight='bold', color=INK)
    ax.set_xlim(x0 / 1000, x1 / 1000); ax.set_ylim(y0 / 1000, y1 / 1000); ax.set_aspect('equal'); ax.axis('off')
    ax.legend(handles=[Patch(facecolor=GAP, label='직행 수단 없음'), Patch(facecolor=OK, label='직행 수단 있음'),
                       Patch(facecolor='white', edgecolor='#bbbbbb', label='정류장 300m 밖')], loc='lower left',
              bbox_to_anchor=(0, -0.2), ncol=3, frameon=False, fontsize=8, handlelength=1)
    vals = [d.gap_share.iloc[i] * 100 for i in idx]; sup = [d.stops_per_1000.iloc[i] for i in idx]
    bars = bx.barh(names[::-1], vals[::-1], color=[SUP, GAP, GAP][::-1], height=.5)
    for b, v, s in zip(bars, vals[::-1], sup[::-1]):
        bx.text(b.get_width() + 2, b.get_y() + b.get_height() / 2, f'{v:.0f}%  (정류장 {s:.2f}개/고령 천 명)', va='center', fontsize=8.6)
    bx.set_xlim(0, 120); bx.set_xticks([]); bx.spines['left'].set_visible(False); bx.spines['bottom'].set_visible(False)
    bx.set_title('직행 공백 비율', fontsize=10, loc='left'); bx.tick_params(labelsize=10)
    fig.tight_layout(); save(fig, '09_amsa_case.png')


def carbon(ev):
    fig, ax = plt.subplots(figsize=(7.6, 3.1))
    x = np.linspace(0, 200, 201)
    for lab, add, col in [('기존 노선 조정(추가 운행 0km)', 0.0, '#2f6f7e'), ('전기 마을버스 20km/일 추가', ev['ev_bus_kg_per_km'] * 20, '#4b8f4b'),
                          ('CNG 버스 20km/일 추가', ev['cng_bus_kg_per_km'] * 20, '#b5533d')]:
        ax.plot(x, (x * ev['car_kg_per_km'] - add) * 250 / 1000, c=col, lw=2, label=lab)
    for be, col in [(ev['break_even_ev20_km_day'], '#4b8f4b'), (ev['break_even_cng20_km_day'], '#b5533d')]:
        ax.scatter([be], [0], c=col, s=26, zorder=4); ax.annotate(f'{be:.0f}km', (be, 0), xytext=(be + 3, -2.6), fontsize=9, color=col)
    ax.axhline(0, c='#67717a', lw=.8)
    ax.set(xlabel='줄어든 승용차 주행거리 (km/일, 가정)', ylabel='연간 순감축 CO2 (t, 가정)', xlim=(0, 200), ylim=(-6.5, 11))
    ax.grid(alpha=.13); ax.legend(loc='upper left', frameon=False, fontsize=8.8); ax.tick_params(labelsize=9.5)
    fig.tight_layout(); save(fig, '10_carbon_break_even.png')


def main():
    setup()
    d = pd.read_csv(RES / 'hospital_access_dong.csv', encoding='utf-8-sig')
    d['core_candidate'] = d.core_candidate.astype(bool)
    d['gap_core'] = d.gap_robust.eq(1)
    cells = pd.read_csv(RES / 'hospital_access_cells.csv.gz')
    ev = json.loads((RES / 'carbon_ev_summary.json').read_text(encoding='utf8'))
    _, polys, _, parsed = boundaries()
    assert len(polys) == len(d)
    seoul_map(d, cells, parsed, polys); supply_vs_access(d); amsa_case(d, cells, polys); carbon(ev)
    print('saved 07~10')


if __name__ == '__main__':
    main()
