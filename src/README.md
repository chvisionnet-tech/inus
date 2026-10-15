# 점검용 소스 폴더

`/inus-audit` 점검이 읽는 소스를 여기에 둔다. 폴더가 비어 있으면 점검은 시작되지 않는다(사전점검에서 중단).

| 폴더 | 넣을 것 | 공개 저장소에 올려도 되나 |
|---|---|---|
| `src/vba/` | VBA 모듈 내보내기 (.bas .cls .frm) | 엑셀 파일이 이미 공개라 새로 드러나는 것은 적지만, 키가 박혀 있지 않은지 먼저 확인 |
| `src/gas-main/` | 메인 GAS 파일들 (.gs) | **아니오** (결제·로그인 서버 로직) |
| `src/gas-sales/` | 영업 GAS 파일들 (.gs) | **아니오** |
| `src/worker/` | Cloudflare 워커 inus-api 소스 | **아니오** |
| `site/` | 홈페이지 html (s, route, leader, index, _worker.js 등) | 이미 공개 배포된 파일이면 가능 |

서버 소스를 올리려면 **비공개 저장소**를 따로 만들고, 그 저장소에 `.claude/skills/inus-audit/`와 `CLAUDE.md`를 같이 복사해서 쓴다.

## VBA 내보내기 (수동)
1. 엑셀에서 `Alt+F11`
2. 왼쪽 프로젝트 탐색기에서 모듈을 우클릭 → **파일 내보내기**
3. 저장 위치를 `src/vba/`로 한다. 모듈마다 반복한다(ModFollowUp, 2, 3, 4, Module1, Sheet1, Sheet4, ThisWorkbook, ModProfile, ModInquiry, ModKakao, ModKkSend, ModSMS, ModMobileSync, ModErrorReport 등).
4. 폼을 내보내면 `.frx`(바이너리)가 같이 생긴다. 점검에는 필요 없으니 올리지 않는다.
5. 내보낸 파일은 CP949(ANSI) 인코딩이다. 그대로 올려도 된다. 점검 때 자동으로 UTF-8로 변환한다.

모듈이 많아 일괄 내보내기 매크로가 필요하면 요청한다. 배포용 `inus_solution.xlsm`에는 넣지 않고 별도 통합문서에서 실행하는 방식을 권한다(백신 오탐 때문).

## GAS 내보내기
- 수동: Apps Script 편집기에서 파일마다 내용을 복사해 같은 이름의 `.gs`로 저장한다. 프로젝트마다 `Code.gs`가 있으니 폴더(`gas-main`, `gas-sales`)로 구분한다.
- 선택: `clasp`(Node 필요, Google 로그인)로 한 번에 가져올 수 있다.

## 올리기 전 확인
- 키·토큰·비밀번호가 코드에 직접 적혀 있지 않은지: `python3 .claude/skills/inus-audit/prep.py` 의 "키 노출 의심" 항목으로 1차 확인한다(완전하지 않음).
- 고객 정보(연락처 등)가 샘플 데이터로 들어 있지 않은지.
