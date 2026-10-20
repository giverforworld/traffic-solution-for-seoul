# 원자료 파일 설명


- `data/raw/elder_all_data.json`: 서울시 고령자현황 통계, 2026년 2분기 전체인구 및 65세 이상 인구.
- `data/raw/stops_20260602.xlsx`, `stops_20260902.xlsx`: 서울시 버스정류소 위치정보 원파일.
- `data/raw/ridership_202606.csv`, `ridership_202609.csv`: 서울버스 노선별 정류장별 월간 시간대별 승하차 원자료.
- `data/raw/boundary_geometry.json`: 2026-04-01판 행정동 경계에서 서울 427개 동을 추출한 자료. 자치구 경계는 동 경계를 통합하여 작성하였다.
- `data/raw/boundary_source.json`: 경계 원본 URL, 고정 커밋, 기준일, 이용조건 및 변경 내용.
- `data/raw/boundary_LICENSE-DATA.txt`: 경계 자료 제공자의 데이터 라이선스 원문.
- `data/raw/hospitals_20261020.csv`: 서울시 병원 인허가 정보 전체 CSV, 930행. 정상영업 종합병원 2개의 주소·좌표·업태를 확인한다.
- `data/raw/subway_master_20261020.csv`: 역사마스터 전체 CSV, 784행. 5·8호선 역명·좌표를 대조한다.
- `data/raw/route_info_20261020.csv`: T-DATA 노선정보 CSV, 1,751행. 모든 셀의 U+FEFF를 제거하여 읽는다. 원파일은 보존한다.
- `data/raw/subway_transfer_20250317.csv`: 서울교통공사 환승정보, 892행. 조회일과 기준일을 구분한다.
- `data/raw/case_route_sources.json`: 지자체·병원·노선·환승의 출처와 사실 요약. 시설 안내 원문·이미지 전체를 재배포하지 않는다.
- `data/raw/carbon_parameters.json`: 공식 연료 기본계수·발열량, 분석 경계 및 관측이 아닌 연구자 가정.
- `data/raw/policy_data_sources.json`: 추가 다운로드 경로·이용조건·수집시점.

## 출처와 이용조건

1. 서울특별시 고령자현황 통계
   https://stat.eseoul.go.kr/statHtml/statHtml.do?orgId=201&tblId=DT_201004_A030002
   정의 및 공공누리 제1유형 확인: https://www.data.go.kr/data/15047003/fileData.do
2. 서울특별시 버스정류소 위치정보
   https://data.seoul.go.kr/dataList/OA-15067/A/1/datasetView.do
   공공누리 제1유형. 파일 기준일 2026-06-02 및 2026-09-02.
3. 서울특별시 버스노선별 정류장별 시간대별 승하차 인원 정보
   https://data.seoul.go.kr/dataList/OA-12913/F/1/datasetView.do
   공공누리 제1유형. 서울시내·광역·마을버스 자료이며 경기도 운영 버스 전체를 포함하지 않는다.
4. 행정동 경계 원자료: 통계청 통계지리정보서비스 SGIS
   https://sgis.kostat.go.kr
   공공누리 제1유형.
   경계 가공 및 배포: vuski/admdongkor
   https://github.com/vuski/admdongkor
   CC BY 4.0. 사용 판본 `ver20260401`, 고정 커밋 `7360288277dfd12d74e54b959c59bdd66f852e3a`.
   라이선스: https://github.com/vuski/admdongkor/blob/master/LICENSE-DATA
   본 분석의 변경 사항: 서울 427개 행정동 추출, 이름·자치구 속성 정리, 동 경계의 자치구 단위 통합.

원자료 수집일은 2026-10-20이다. 공개 스냅샷과 출처를 보존하였으며 원자료의 권리는 제공기관과 권리자에게 있다. 출처 및 이용조건을 유지하여 사용해야 한다. 참가신청서나 연락처 등 개인정보는 공개 코드에 포함하지 않는다.
