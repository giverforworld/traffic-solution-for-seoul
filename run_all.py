"""전체 분석을 처음부터 다시 실행하고, 보고서 수치를 자동 대조한다. 실행: python run_all.py (약 1분)

동봉한 원자료 스냅샷(data/raw)만 사용하므로 분석 중 인터넷 접속이 필요 없다.
마지막 단계(check_report.py)에서 보고서에 적힌 수치가 다시 계산한 결과와 모두 같은지 확인한다.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ('analyze.py', '공급량 지표, 정류장-행정동 배정'),
    ('verify.py', '공급량 지표 민감도'),
    ('evaluate_policy.py', '사례 경로 검증, 탄소 손익분기'),
    ('hospital_access.py', '100m 격자 환승 없는 종합병원 접근(16개 기준 + 9월 자료)'),
    ('hospital_access_boundary.py', '경계 민감도(경기·인천 종합병원 94곳 추가)'),
    ('figures.py', '그림 01~04'),
    ('policy_figures.py', '그림 05~06'),
    ('access_figures.py', '보고서 그림 07~10'),
    ('make_map.py', 'GitHub 인터랙티브 지도(GeoJSON)'),
    ('check_report.py', '보고서 수치 자동 대조'),
]


def main():
    t_all = time.time()
    for i, (script, desc) in enumerate(STEPS, 1):
        t = time.time()
        print(f'[{i:>2}/{len(STEPS)}] {script:<30} {desc}', flush=True)
        r = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:], sep='\n')
            sys.exit(f'중단: {script} 실패')
        if script == 'check_report.py':
            print('      ' + r.stdout.strip().splitlines()[-1])
        print(f'      완료 {time.time() - t:.1f}초', flush=True)
    print(f'\n전체 재현 완료: {time.time() - t_all:.0f}초. 대조표: results/report_number_check.md')


if __name__ == '__main__':
    main()
