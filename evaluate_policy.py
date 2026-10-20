"""공개자료의 의료 접근 경로 교차검증 및 조건부 연료 연소 CO2 계산.

실측 통행시간·수단전환량·정책 효과를 생성하지 않는다.
실행: python evaluate_policy.py (고정 스냅샷만 사용)
"""
from pathlib import Path
import json, hashlib, math
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent
RAW, RES = ROOT / 'data/raw', ROOT / 'results'


def save_json(name, value):
    (RES / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def evaluate_routes():
    hospitals = pd.read_csv(RAW / 'hospitals_20261020.csv', encoding='cp949', dtype=str)
    subway = pd.read_csv(RAW / 'subway_master_20261020.csv', encoding='cp949', dtype=str)
    routes = pd.read_csv(RAW / 'route_info_20261020.csv', encoding='utf-8-sig', dtype=str)
    routes.columns = routes.columns.str.replace('\ufeff', '', regex=False).str.strip()
    routes = routes.map(lambda x: x.replace('\ufeff', '').strip() if isinstance(x, str) else x)
    month = pd.read_csv(RAW / 'ridership_202609.csv', encoding='cp949', dtype=str)
    month['sequence'] = month['역명'].str.extract(r'\((\d+)\)$')[0].astype(int)
    month['stop_name'] = month['역명'].str.replace(r'\(\d+\)$', '', regex=True)
    assert month['사용년월'].eq('202609').all()
    sequence = month[(month['노선번호'] == '3411') & month.sequence.between(70, 82)].sort_values('sequence')
    assert sequence.sequence.tolist() == list(range(70, 83)), '출발~도착 정류장 순서 결측'
    assert sequence.iloc[0]['버스정류장ARS번호'] == '25156'
    assert sequence.iloc[-1]['버스정류장ARS번호'] == '25177'
    assert sequence.iloc[0]['stop_name'] == '암사역2번출구.암사종합시장'
    assert sequence.iloc[-1]['stop_name'] == '강동경희대병원.명일동이마트'
    sequence[['노선번호', '표준버스정류장ID', '버스정류장ARS번호', 'stop_name', 'sequence']].to_csv(RES / 'case_bus_stops.csv', index=False, encoding='utf-8-sig')

    # 공식 CSV의 한글 항목명. 데이터의 배차값은 관측 대기시간과 다르다.
    rr = routes[routes['노선명'].eq('3411')]
    assert len(rr) == 1, ('3411 unique', len(rr))
    rr.to_csv(RES / 'case_route_schedule.csv', index=False, encoding='utf-8-sig')
    assert rr.iloc[0]['운행여부'] == '1' and rr.iloc[0]['사용여부'] == '1'
    headway = float(rr.iloc[0]['배차'])
    minimum = float(rr.iloc[0]['최소배차'])
    maximum = float(rr.iloc[0]['최대배차'])
    assert 0 < minimum <= headway <= maximum < 120

    selected = hospitals[hospitals['사업장명'].isin(['성심의료재단강동성심병원', '강동경희대학교병원'])].copy()
    assert len(selected) == 2 and selected['영업상태코드'].eq('01').all()
    assert selected['업태구분명'].eq('종합병원').all()
    tr = Transformer.from_crs(5174, 4326, always_xy=True)
    selected['longitude'], selected['latitude'] = tr.transform(selected['좌표정보(X)'].astype(float), selected['좌표정보(Y)'].astype(float))
    assert selected.longitude.between(127.10, 127.20).all()
    assert selected.latitude.between(37.50, 37.60).all()
    selected[['사업장명', '도로명주소', '영업상태명', '업태구분명', 'longitude', 'latitude']].to_csv(RES / 'case_hospitals.csv', index=False, encoding='utf-8-sig')
    rail = subway[subway['역사_ID'].isin(['2811', '2812', '2548', '2549'])]
    assert len(rail) == 4
    assert set(rail['호선']) == {'5호선', '8호선'}
    assert set(rail[rail['역사명'].str.startswith('천호')]['호선']) == {'5호선', '8호선'}
    rail.to_csv(RES / 'case_rail_stations.csv', index=False, encoding='utf-8-sig')
    transfers = pd.read_csv(RAW / 'subway_transfer_20250317.csv', encoding='cp949', dtype=str)
    transfer = transfers[(transfers['환승시작 코드'] == '2812') & (transfers['환승종료역 코드'] == '2548') & (transfers['하차 열차 방면'] == '강동구청 방면') & (transfers['환승 열차 방면'] == '강동 방면')]
    assert len(transfer) == 1 and transfer.iloc[0]['소요시간'] == '01:59'
    transfer.to_csv(RES / 'case_rail_transfer.csv', index=False, encoding='utf-8-sig')
    facts = json.loads((RAW / 'case_route_sources.json').read_text(encoding='utf8'))
    case = {
        'case_selection': '후보 암사1동의 공개 거점과 의료기관을 예시로 검토. 모든 주민 또는 모든 의료목적지의 대표 표본 아님.',
        'hospital_records_checked': len(selected),
        'rail_path': ['암사역 8호선', '천호역 8→5호선 환승', '강동역 5호선', '강동성심병원'],
        'rail_transfers': 1,
        'rail_transfer_guide_time_mm_ss': transfer.iloc[0]['소요시간'],
        'rail_transfer_scope': '2025-03-17 서울교통공사 안내 참고값. 고령자 실측 또는 무장애 경로 소요시간 아님.',
        'official_guide_walk_minutes': {'amsa_station_exit1_to_community_centre': 10, 'gangdong_station_exit2_or_2_1_to_hospital': 5},
        'sum_of_two_official_guide_walk_minutes': 15,
        'walk_time_scope': '두 기관 안내시간의 합계. 주민센터 출발 경로의 양단 참고값이며 역내 이동·열차 대기·차내·환승시간을 제외. 고령자 실측이나 총 소요시간 아님.',
        'bus_path': ['암사역2번출구.암사종합시장(25156)', '3411', '강동경희대병원.명일동이마트(25177)'],
        'bus_sequence_start': int(sequence.sequence.min()),
        'bus_sequence_end': int(sequence.sequence.max()),
        'bus_stop_intervals': int(sequence.sequence.max() - sequence.sequence.min()),
        'bus_transfers_from_boarding_stop': 0,
        'bus_headway_minutes_in_source': headway,
        'bus_min_headway_minutes_in_source': minimum,
        'bus_max_headway_minutes_in_source': maximum,
        'bus_headway_scope': '노선정보의 배차 필드. 특정 시간대 실제 도착간격·대기시간·주행시간 아님. 정류장까지의 보행시간 미측정.',
        'interpretation': '버스 공급비율이 낮아도 지하철 대체 및 목적지별 직통버스가 존재. 실제 접근 취약성은 목적지별 보행·대기·환승 및 무장애 동선을 추가 조사해야 함.',
        'official_source_count': len(facts['sources'])
    }
    save_json('case_summary.json', case)
    return case


def evaluate_carbon():
    p = json.loads((RAW / 'carbon_parameters.json').read_text(encoding='utf8'))
    a = p['analyst_assumptions_not_observations']
    fuel = {k: v['kg_co2_per_tj'] * v['ncv_mj_per_unit'] * 1e-6 for k, v in p['fuel_factors'].items()}
    e_car = fuel['petrol'] / a['car_km_per_litre']
    e_bus = fuel['cng'] / a['bus_km_per_nm3']
    rows = []
    for bus in a['extra_bus_vehicle_km_per_day']:
        for car in a['avoided_car_vehicle_km_per_day']:
            saved, added = car * e_car, bus * e_bus
            rows.append({'extra_bus_vehicle_km_day_assumption': bus, 'avoided_car_vehicle_km_day_assumption': car, 'avoided_co2_kg_day': saved, 'extra_bus_co2_kg_day': added, 'net_co2_reduction_kg_day': saved-added, 'net_co2_reduction_t_year_assumption': (saved-added)*a['operating_days_per_year']/1000})
    scenarios = pd.DataFrame(rows)
    assert math.isclose(fuel['petrol'], 2.08593) and math.isclose(fuel['cng'], 2.15985)
    assert (scenarios.groupby('extra_bus_vehicle_km_day_assumption')['net_co2_reduction_kg_day'].diff().dropna() > 0).all()
    scenarios.to_csv(RES / 'carbon_scenarios.csv', index=False, encoding='utf-8-sig')
    sens = []
    for ce in a['car_efficiency_sensitivity_km_per_litre']:
        for be in a['bus_efficiency_sensitivity_km_per_nm3']:
            threshold = 20 * fuel['cng']/be / (fuel['petrol']/ce)
            sens.append({'car_km_litre_assumption': ce, 'bus_km_nm3_assumption': be, 'extra_bus_vehicle_km_day_assumption': 20, 'break_even_avoided_car_vehicle_km_day': threshold})
    ss = pd.DataFrame(sens)
    ss.to_csv(RES / 'carbon_sensitivity.csv', index=False, encoding='utf-8-sig')
    threshold = 20*e_bus/e_car
    assert math.isclose(threshold*e_car-20*e_bus, 0, abs_tol=1e-10)
    assert (80*e_car-20*e_bus) < 0 < (200*e_car-20*e_bus)
    result = {'boundary': p['boundary'], 'all_demand_distance_efficiency_and_days_are_assumptions': True, 'fuel_co2_kg_per_litre_petrol': fuel['petrol'], 'fuel_co2_kg_per_nm3_cng': fuel['cng'], 'car_co2_kg_vehicle_km_assumption': e_car, 'bus_co2_kg_vehicle_km_assumption': e_bus, 'break_even_avoided_car_vehicle_km_day_for_extra_bus20': threshold, 'threshold_sensitivity_min_car_vehicle_km_day': float(ss.break_even_avoided_car_vehicle_km_day.min()), 'threshold_sensitivity_max_car_vehicle_km_day': float(ss.break_even_avoided_car_vehicle_km_day.max()), 'scenarios_extra_bus20': scenarios[scenarios.extra_bus_vehicle_km_day_assumption.eq(20)].to_dict('records')}
    save_json('carbon_summary.json', result)
    return result


def main():
    RES.mkdir(exist_ok=True)
    case, carbon = evaluate_routes(), evaluate_carbon()
    files = ['hospitals_20261020.csv', 'subway_master_20261020.csv', 'subway_transfer_20250317.csv', 'route_info_20261020.csv', 'ridership_202609.csv', 'case_route_sources.json', 'carbon_parameters.json']
    save_json('policy_source_sha256.json', {name: hashlib.sha256((RAW / name).read_bytes()).hexdigest() for name in files})
    save_json('policy_verification.json', {'hospital_status_and_type': True, 'rail_station_ids_and_transfer_lines': True, 'official_transfer_direction_record': True, 'bus_direction_sequence_complete': True, 'headway_bounds': True, 'carbon_unit_conversion': True, 'carbon_break_even_zero': True, 'carbon_positive_and_negative_scenarios': True, 'no_measured_total_travel_time_or_mode_shift_claimed': True})
    print('의료 접근 경로와 조건부 CO2 계산 검증 완료.')


if __name__ == '__main__':
    main()
