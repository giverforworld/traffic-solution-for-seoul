"""추가 공개 원자료 재수집. raw를 덮어쓰지 않고 data/refetched에 저장한다."""
from pathlib import Path
import json
import requests

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'data/raw';DEST=ROOT/'data/refetched'


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    meta=json.loads((RAW/'policy_data_sources.json').read_text(encoding='utf8'))
    session=requests.Session()
    d=meta['sheet_download']
    for filename,form in d['per_dataset_form'].items():
        r=session.post(d['url'],data=d['common_form']|form,timeout=60)
        r.raise_for_status();(DEST/filename).write_bytes(r.content)
    case=json.loads((RAW/'case_route_sources.json').read_text(encoding='utf8'))
    for source in case['sources']:
        if source['id'] not in ['route_info','subway_transfer']:continue
        if source.get('download_method')=='POST':
            r=session.post(source['download_url'],data=source['download_form'],timeout=60)
        else:r=session.get(source['download_url'],timeout=60)
        r.raise_for_status();(DEST/source['raw_file']).write_bytes(r.content)
    print('추가 자료를 data/refetched에 저장했습니다. 기준일과 해시를 비교한 후 사용하세요.')


if __name__=='__main__':main()
