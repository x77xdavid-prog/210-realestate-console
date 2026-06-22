# BL0 — encParam 생성 역공학 (매각물건명세서 딥링크) — 2026-06-22

> 결과: **encParam은 courtauction 서버가 생성** → 클라이언트 AES 재현 불필요. 서버 호출만으로 공식 전자문서 뷰어 딥링크를 만들 수 있다. **go.** B-link/B-full 모두 언블록.

## 흐름 (라이브 캡처로 확정)

매각물건명세서 버튼(`btn_dspslGdsSpcfc1`) 클릭 시 courtauction이 `insertDspslGdsSpecArtcWdrwInf.on`을 호출하고, 그 응답으로 encParam을 받아 ecfs 뷰어를 연다. encParam 생성용 클라이언트 암호화 없음(로드된 JS·페이지 XML에 encParam/SGVO201 부재, 서버 응답에만 존재).

```
같은 세션(CookieJar 1개):
1) GET  /pgj/index.on                              (쿠키 WMONID/SID/JSESSIONID)
2) POST /pgj/pgj15B/selectAuctnCsSrchRslt.on       (sc-userid: SYSTEM)
     body {dma_srchGdsDtlSrch:{csNo,cortOfcCd,dspslGdsSeq,pgmId:PGJ151F01}}
   → data.dma_result.dspslGdsDxdyInfo.{orvParam, dspslGdsSpcfcEcdocId}
3) POST /pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on
     headers: sc-userid: NONUSER, sc-pgmid: PGJ15BM01,
              submissionid: mf_wfm_mainFrame_sbm_insertDspslGdsSpecLogInfo,
              Referer: /pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml
     body {dma_dspslGdsSpecLog:{cortOfcCd, csNo, dspslGdsSeq(int), orvParam,
           dspslGdsSpcfcEcdocId, cortAuctnMbrsId:"NONUSER", docFlag:"1",
           dspslDxdyPbancEcdocId:""}}
   → data.dma_dspslSpcfcInfo.{url, encParam}
4) 딥링크 = url + "?paramData=" + base64({encParam, pspTkn:"NA", pspSid:"NA"})
```

## 핵심 사실
- **orvParam은 상세를 조회한 세션에 바인딩**된다. fresh 세션에서 다른 세션의 orvParam을 쓰면 500. → 상세조회+로그호출을 **같은 세션**에서 해야 함.
- **헤더가 결정적**: `sc-userid: NONUSER`(상세는 SYSTEM), `sc-pgmid: PGJ15BM01`, `submissionid`가 없으면 500.
- `dspslGdsSpcfcEcdocId`는 상세 응답에 있고 우리의 `doc_ecid`(parse_detail)와 동일.
- encParam은 단기 토큰 추정 → **클릭 시점에 생성**(프런트는 클릭 시 /api/listing/doc-link 호출).

## 검증 (라이브, 결정적)
- Python `court_documents.sale_spec_viewer_url('20080130025092','B000210','1')` → 실제 encParam(len 144) 딥링크.
- 그 딥링크를 새 브라우저 탭에서 열면 ecfs `selectDocVwrInf.on`→`getPdf.on`(새 streamdocsId)→StreamDocs renderings 0~2 = **매각물건명세서 PDF 3페이지 렌더**.
- 프런트: 상세 우측 레일 '매각물건명세서' 클릭 → 단일 새 탭으로 문서뷰어 열림(noopener 빈탭 버그 수정).

## 구현
- `realestate_alert/court_documents.py`: 순수(`extract_doc_params`/`build_sale_spec_log_body`/`build_viewer_url`) + `_LiveSession`(같은 세션 2-POST) + `sale_spec_viewer_url`(주입 가능, 실패 흡수→None).
- `GET /api/listing/doc-link?cs=&court=&seq=&kind=sale_spec` → `{url}`.
- `web/detail.js#initDocLinks`: 클릭 시 빈 탭 동기 open → /api/listing/doc-link → 리다이렉트. cs/court 없으면 courtauction 안내 유지.

## 남은 것 (B-link 완성용)
- **현황조사서·감정평가서**: 각자 별도 버튼/서비스(예: 현황조사 `btn_curstExmndcTop`). 해당 버튼이 있는 물건(아파트 등)에서 같은 방식으로 서비스명·body 캡처하면 동일 패턴으로 추가 가능. (2008타경25092엔 두 버튼 없음.)
- **B-full**: 같은 흐름의 `getPdf.on`→streamdocs `texts/N`(EUC-KR, per-glyph 좌표) 또는 PDF 다운로드 파싱으로 임차인 표·권리 구조화.
