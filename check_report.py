"""보고서에 적힌 수치를 결과 파일에서 다시 계산해 자동으로 대조한다.
실행: python check_report.py   (run_all.py가 마지막에 자동 실행)

각 항목은 '보고서 표기'와 '결과 파일에서 계산한 값을 보고서와 같은 자릿수로 표기한 값'을 비교한다.
결과는 화면과 results/report_number_check.md 에 저장되며, 하나라도 어긋나면 종료 코드 1을 반환한다.
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RES = ROOT / 'results'


def load():
    j = lambda f: json.loads((RES / f).read_text(encoding='utf8'))
    return {
        'base': j('summary.json'),
        'acc': j('hospital_access_summary.json'),
        'bnd': j('hospital_access_boundary_summary.json'),
        'ev': j('carbon_ev_summary.json'),
        'grid': pd.read_csv(RES / 'hospital_access_grid.csv', encoding='utf-8-sig'),
        'dong': pd.read_csv(RES / 'hospital_access_dong.csv', encoding='utf-8-sig'),
    }


def pct(x, nd=1):
    return f'{x * 100:.{nd}f}%'


def man(x):  # 만 명 단위 반올림
    return f'{x / 10000:.0f}만'


def checks(r):
    b, a, bd, ev, g, d = r['base'], r['acc'], r['bnd'], r['ev'], r['grid'], r['dong']
    qa = b['qa']['202606']
    core = d[d.gap_robust.eq(1)].sort_values('est_elderly_in_gap', ascending=False)
    top10 = core.head(10)
    amsa = a['case_amsa']
    C = [
        # (쪽, 항목, 보고서 표기, 결과 파일 값)
        ('1', '서울 65세 이상 인구', '약 196만 명', f"약 {b['elderly'] / 10000:.0f}만 명"),
        ('1', '고령인구 비율', '20.5%', pct(b['elderly'] / b['population'])),
        ('2', '분석 행정동 수', '427', str(b['dong_count'])),
        ('2', '6월 정류장 원자료 → 분석 정류장', '11,253 → 11,236',
         f"{qa['source_rows']:,} → {qa['analysis_stops']:,}"),
        ('2', '제외: 한강 선착장 / 경계 밖 30m 초과', '8 / 9',
         f"{qa['river_piers_excluded']} / {qa['assignment_methods']['outside']}"),
        ('2', '공급량 기준(E 이상·S 이하·R 이하)', '5,703명 / 3.63 / 11.49',  # E는 정수 인원이므로 올림
         f"{math.ceil(b['elderly_q75']):,}명 / {b['stops_per_1000_q25']:.2f} / {b['contacts_per_1000_q25']:.2f}"),
        ('2', '공급량 기준 후보 동 수', '15', str(b['candidates_june'])),
        ('2', '100m 격자 / 판정 대상 격자', '60,614 / 43,766', f"{a['cells_total']:,} / {a['cells_served']:,}"),
        ('2', '서울 종합병원 수', '59', str(a['general_hospitals'])),
        ('2', '정류장 간격 중앙값 → N=10 거리', '약 320m → 약 3.2km',
         f"약 {round(a['stop_spacing_median_m'], -1):.0f}m → 약 {a['base_n_km_equivalent']:.1f}km"),
        ('3', '직행 공백 격자 비율(기본)', '19.5%', pct(a['served_cells_gap_share_base'])),
        ('3', '16개 기준 범위', '13.0~25.3%',
         f"{g.served_cells_without_near_onestep_share.min() * 100:.1f}~{pct(g.served_cells_without_near_onestep_share.max())}"),
        ('3', '공백 지역 추정 고령인구', '약 33만 명', f"약 {man(a['est_elderly_in_gap_base'])} 명"),
        ('3', '서울 고령인구 대비', '16.8%', pct(a['est_elderly_in_gap_base'] / b['elderly'])),
        ('3', '추정 고령인구 범위', '22만~45만 명',
         f"{man(a['est_elderly_in_gap_range'][0])}~{man(a['est_elderly_in_gap_range'][1])} 명"),
        ('3', '직행 공백 50% 이상 동', '45', str(a['gap_dongs_base'])),
        ('3', '핵심 지역(구 / 동 / 고령인구)', '12 / 20 / 79,595',
         f"{core.gu.nunique()} / {a['core_dongs']} / {a['core_elderly']:,}"),
        ('3', '핵심 지역 9월 자료도 50% 이상', '20', str(int((core.gap_share_sept >= 0.5).sum()))),
        ('3', '경기·인천 종합병원(추가 도착지)', '94', str(bd['outside_general_hospitals'])),
        ('3', '경계 검증 후 유지되는 핵심 동', '18', str(bd['core_kept_with_outside'])),
        ('3', '경계 검증에서 제외된 동', '송파구 문정2동, 송파구 위례동', ', '.join(bd['core_dropped'])),
        ('4', '핵심 지역과 공급량 후보 중복', '0', str(int((core.core_candidate == True).sum()))),
        ('4', '45개 동과 공급량 후보 중복', '2', str(a['gap_overlap_with_supply_candidates_base'])),
        ('4', '정류장 수 하위 25%만 적용 시 핵심 동', '강동구 암사2동', ', '.join(a['core_in_supply_S_q25_only'])),
        ('4', '45개 동 정류장 수 중앙값 / 서울 중앙값', '6.92 / 5.20',
         f"{a['gap_median_stops_per_1000']:.2f} / {a['city_median_stops_per_1000']:.2f}"),
        ('4', '45개 동 300m 권역 비율 중앙값', '81%', pct(a['gap_median_coverage300'], 0)),
        ('4', '공급량 후보 / 서울 직행 공백 중앙값', '24% / 8%',
         f"{pct(a['supply_candidates_median_gap_share'], 0)} / {pct(a['city_median_gap_share'], 0)}"),
        ('4', '스피어만 순위상관계수', '0.16', f"{a['spearman_stops_per_1000_vs_gap_share']:.2f}"),
        ('4', '암사1·2·3동 직행 공백 비율', '34% / 63% / 55%',
         ' / '.join(pct(amsa[k]['gap_share'], 0) for k in ['암사1동', '암사2동', '암사3동'])),
        ('4', '암사1·2·3동 정류장 수(개/고령 천 명)', '1.68 / 2.38 / 4.50',
         ' / '.join(f"{amsa[k]['stops_per_1000']:.2f}" for k in ['암사1동', '암사2동', '암사3동'])),
        ('4', '핵심 지역 공백 지역 추정 고령인구', '약 5.2만 명', f"약 {a['core_est_elderly_in_gap'] / 10000:.1f}만 명"),
        ('5', '전기 마을버스 20km/일 손익분기', '약 44km', f"약 {ev['break_even_ev20_km_day']:.0f}km"),
        ('5', 'CNG 버스 20km/일 손익분기', '약 104km', f"약 {ev['break_even_cng20_km_day']:.0f}km"),
        ('5', '전기 마을버스 손익분기 범위(전비 가정)', '25~99km',
         f"{ev['ev_threshold_range_km_day'][0]:.0f}~{ev['ev_threshold_range_km_day'][1]:.0f}km"),
    ]
    rows = [
        ('종로구 평창동', '4,164', '94%', '3,931', '13.21'),
        ('구로구 수궁동', '5,732', '68%', '3,871', '7.15'),
        ('마포구 망원1동', '3,854', '100%', '3,854', '5.97'),
        ('강서구 화곡본동', '6,325', '53%', '3,353', '3.95'),
        ('서초구 내곡동', '3,937', '81%', '3,188', '14.99'),
        ('관악구 인헌동', '4,774', '65%', '3,089', '5.03'),
        ('송파구 문정2동', '4,772', '64%', '3,066', '6.92'),
        ('송파구 위례동', '4,707', '63%', '2,975', '12.75'),
        ('구로구 개봉3동', '5,293', '55%', '2,894', '3.97'),
        ('금천구 시흥4동', '5,363', '53%', '2,849', '4.10'),
    ]
    for (name, *vals), (_, rr) in zip(rows, top10.iterrows()):
        got = (f'{rr.gu} {rr.dong}', f'{rr.elderly:,.0f}', pct(rr.gap_share, 0), f'{rr.est_elderly_in_gap:,.0f}', f'{rr.stops_per_1000:.2f}')
        C.append(('3', f'핵심 지역 표: {name}', ' / '.join([name, *vals]), ' / '.join(got)))
    return C


def main():
    C = checks(load())
    ok = [c[2] == c[3] for c in C]
    lines = ['| 결과 | 쪽 | 항목 | 보고서 표기 | 결과 파일 값 |', '|---|---|---|---|---|']
    lines += [f"| {'PASS' if o else '**FAIL**'} | {p} | {k} | {e} | {v} |" for (p, k, e, v), o in zip(C, ok)]
    head = f'# 보고서 수치 자동 대조\n\n{sum(ok)}/{len(ok)}개 항목 일치\n\n'
    (RES / 'report_number_check.md').write_text(head + '\n'.join(lines) + '\n', encoding='utf8')
    for (p, k, e, v), o in zip(C, ok):
        print(f"{'PASS' if o else 'FAIL'}  [{p}쪽] {k}: {e}" + ('' if o else f'  ← 결과 파일: {v}'))
    print(f'\n보고서 수치 {sum(ok)}/{len(ok)}개 항목이 결과 파일과 일치')
    sys.exit(0 if all(ok) else 1)


if __name__ == '__main__':
    main()
