"use strict";

/* ============================================================
   detail.js — 경매 전용 상세 페이지 컨트롤러
   Reads: ?id=&cs=&court=&seq=
   Fetches: GET /api/listing/detail?id=...&cs=...&court=...&seq=...
   ============================================================ */

// ── Helpers ──────────────────────────────────────────────────────────────────

/** HTML 이스케이프 (모든 동적 텍스트에 적용) */
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * 금액을 억/만 단위 한국어 문자열로 변환
 * e.g. 1_050_000_000 → "10억 5,000만"
 * @param {number|null|undefined} n
 * @returns {string}
 */
function won(n) {
  if (n === null || n === undefined || isNaN(Number(n))) return "—";
  const v = Math.round(Number(n));
  if (v === 0) return "0원";
  const eok = Math.floor(v / 100_000_000);
  const man = Math.floor((v % 100_000_000) / 10_000);
  let parts = [];
  if (eok > 0) parts.push(eok.toLocaleString("ko-KR") + "억");
  if (man > 0) parts.push(man.toLocaleString("ko-KR") + "만");
  if (parts.length === 0) return v.toLocaleString("ko-KR") + "원";
  return parts.join(" ");
}

/**
 * m² → 평 변환 (1평 = 3.3058 m²), 소수점 1자리
 * @param {number|null|undefined} m2
 * @returns {string}  e.g. "123.4m² (37.3평)"
 */
function pyeong(m2) {
  if (m2 === null || m2 === undefined || isNaN(Number(m2))) return "—";
  const v = Number(m2);
  const p = (v / 3.3058).toFixed(1);
  return `${v.toFixed(1)}m² (${p}평)`;
}

/**
 * "YYYYMMDD" → "YYYY.MM.DD"
 * @param {string|null|undefined} s
 * @returns {string}
 */
function fmtY(s) {
  if (!s || s.length < 8) return s || "—";
  return `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}`;
}

/**
 * 하락률 계산: round((1 - min_bid / appraisal) * 100)
 * @param {number} minBid
 * @param {number} appraisal
 * @returns {string}  e.g. "-30%"
 */
function dropRate(minBid, appraisal) {
  if (!appraisal || !minBid) return "";
  const rate = Math.round((1 - minBid / appraisal) * 100);
  if (rate === 0) return "";
  return `−${rate}%`;
}

/**
 * 평당 가격 계산 (원/평)
 * @param {number|null} amount
 * @param {number|null} m2
 * @returns {string}
 */
function perPyeong(amount, m2) {
  if (!amount || !m2) return "—";
  const pyeongVal = Number(m2) / 3.3058;
  if (pyeongVal <= 0) return "—";
  return won(Math.round(Number(amount) / pyeongVal)) + "/평";
}

/**
 * 외부(API) URL을 http(s)로만 허용한다. javascript:/data: 등 위험 스킴 차단.
 * @param {*} url
 * @returns {string|null} 안전한 절대 URL 또는 null
 */
function safeHref(url) {
  try {
    const u = new URL(String(url), window.location.origin);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch (_) {
    return null;
  }
}

/**
 * 시군구·동이 포함된 완전한 지번주소를 고른다.
 * court 응답의 addr_jibun(rprsLtnoAddr)은 "508-123"처럼 지번만일 때가 많아
 * 시세·주변통계·주변입주·병원분석의 지역 파싱이 실패한다. jibun_list[0].addr
 * (시도 시군구 읍면동 지번)을 우선 쓰고, 없으면 addr_road, 마지막으로 addr_jibun.
 * @param {object} d
 * @returns {string}
 */
function fullAddress(d) {
  if (Array.isArray(d.jibun_list) && d.jibun_list.length && d.jibun_list[0] && d.jibun_list[0].addr) {
    return d.jibun_list[0].addr;
  }
  return d.addr_road || d.addr_jibun || "";
}

// ── URL params ────────────────────────────────────────────────────────────────

function getParams() {
  const sp = new URLSearchParams(window.location.search);
  return {
    id: sp.get("id") || "",
    cs: sp.get("cs") || "",
    court: sp.get("court") || "",
    seq: sp.get("seq") || "",
  };
}

// ── DOM refs ──────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const elLoading     = $("dp-loading");
const elError       = $("dp-error");
const elErrorMsg    = $("dp-error-msg");
const elErrorSub    = $("dp-error-sub");
const elBody        = $("dp-body");
const elCaseHeader  = $("dp-case-header");

// ── State ────────────────────────────────────────────────────────────────────

/** @type {Array<{file:string,dvs:string,seq:string}>} */
let _photos = [];
let _mainPhotoIdx = 0;

// ── Fetch detail ─────────────────────────────────────────────────────────────

async function fetchDetail(params) {
  const qs = new URLSearchParams({
    id: params.id,
    cs: params.cs,
    court: params.court,
    seq: params.seq,
  }).toString();
  const resp = await fetch(`/api/listing/detail?${qs}`);
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status}: ${body || resp.statusText}`);
  }
  return resp.json();
}

// ── Render functions ─────────────────────────────────────────────────────────

/** Fills the sticky case header strip */
function renderCaseHeader(d) {
  $("dp-court-badge").textContent = d.court || "";
  $("dp-case-no").textContent     = d.case_no || "";
  $("dp-case-type").textContent   = d.auction_type || "";
  $("dp-addr-road").textContent   = d.addr_road || "";
  $("dp-addr-jibun").textContent  = d.addr_jibun || "";
  elCaseHeader.hidden = false;
  document.title = `${d.case_no || "상세"} — 병원매물 자동검색`;
}

/** Gallery: main image + thumbs */
function renderGallery(photos) {
  _photos = Array.isArray(photos) ? photos : [];
  const wrap = $("dp-gallery");
  wrap.innerHTML = "";

  if (_photos.length === 0) {
    const empty = document.createElement("div");
    empty.className = "dp-gallery-empty";
    empty.textContent = "사진 없음";
    wrap.appendChild(empty);
    return;
  }

  // Main image
  const mainImg = document.createElement("img");
  mainImg.className = "dp-gallery-main";
  mainImg.alt = "물건 사진";
  mainImg.loading = "eager";
  mainImg.src = photoSrc(_photos[0]);
  mainImg.addEventListener("click", () => openLightbox(0));
  wrap.appendChild(mainImg);

  // Thumbs
  if (_photos.length > 1) {
    const thumbRow = document.createElement("div");
    thumbRow.className = "dp-gallery-thumbs";

    _photos.forEach((ph, idx) => {
      const img = document.createElement("img");
      img.className = "dp-gallery-thumb" + (idx === 0 ? " dp-thumb-active" : "");
      img.src = photoSrc(ph);
      img.alt = `사진 ${idx + 1}`;
      img.loading = "lazy";
      img.addEventListener("click", () => selectPhoto(idx));
      thumbRow.appendChild(img);
    });

    wrap.appendChild(thumbRow);
  }
}

function photoSrc(ph) {
  return `/api/photo?path=${encodeURIComponent(ph.file || "")}`;
}

function selectPhoto(idx) {
  _mainPhotoIdx = idx;
  const mainImg = $("dp-gallery").querySelector(".dp-gallery-main");
  if (mainImg) {
    mainImg.src = photoSrc(_photos[idx]);
  }
  const thumbs = $("dp-gallery").querySelectorAll(".dp-gallery-thumb");
  thumbs.forEach((t, i) => t.classList.toggle("dp-thumb-active", i === idx));
}

function openLightbox(idx) {
  const lb = $("dp-lightbox");
  const lbImg = $("dp-lightbox-img");
  lbImg.src = photoSrc(_photos[idx]);
  lbImg.alt = `물건 사진 ${idx + 1}`;
  lb.hidden = false;
}

function closeLightbox() {
  const lb = $("dp-lightbox");
  lb.hidden = true;
  $("dp-lightbox-img").src = "";
}

/**
 * WGS84 한국 bbox 유효성 검사
 * 위도 33~39, 경도 124~132 범위만 유효한 좌표로 간주
 * @param {*} lat
 * @param {*} lng
 * @returns {boolean}
 */
function isValidKoreaCoord(lat, lng) {
  const la = Number(lat);
  const lo = Number(lng);
  return (
    !isNaN(la) && !isNaN(lo) &&
    la >= 33 && la <= 39 &&
    lo >= 124 && lo <= 132
  );
}

/** Map: OpenStreetMap iframe (좌표 유효 시) 또는 외부 지도 링크 버튼 */
function renderMap(lat, lng, addr) {
  const wrap = $("dp-map-wrap");
  wrap.innerHTML = "";

  if (isValidKoreaCoord(lat, lng)) {
    const la = Number(lat);
    const lo = Number(lng);
    const src =
      `https://www.openstreetmap.org/export/embed.html` +
      `?bbox=${lo - 0.004}%2C${la - 0.003}%2C${lo + 0.004}%2C${la + 0.003}` +
      `&layer=mapnik` +
      `&marker=${la}%2C${lo}`;
    const iframe = document.createElement("iframe");
    iframe.className = "dp-map-iframe";
    iframe.src = src;
    iframe.title = "물건 위치 지도";
    iframe.loading = "lazy";
    iframe.setAttribute("allowfullscreen", "");
    wrap.appendChild(iframe);
  } else {
    // 유효하지 않은 좌표 — 외부 지도 검색 링크 제공
    const searchAddr = (addr || "").trim();
    const ph = document.createElement("div");
    ph.className = "dp-map-placeholder";

    if (searchAddr) {
      ph.innerHTML =
        `<div style="margin-bottom:8px;color:var(--ink-faint);font-size:.85rem;">좌표 정보를 사용할 수 없어 외부 지도로 검색합니다.</div>` +
        `<div class="dp-map-links">` +
          `<a class="dp-map-link" href="https://map.kakao.com/?q=${encodeURIComponent(searchAddr)}" target="_blank" rel="noopener noreferrer">카카오맵에서 보기</a>` +
          `<a class="dp-map-link" href="https://map.naver.com/v5/search/${encodeURIComponent(searchAddr)}" target="_blank" rel="noopener noreferrer">네이버지도에서 보기</a>` +
        `</div>`;
    } else {
      ph.textContent = "위치 정보 없음";
    }

    wrap.appendChild(ph);
  }
}

/** 기본내역 table */
function renderBasicTable(d) {
  const tbody = $("dp-basic-table").querySelector("tbody");
  tbody.innerHTML = "";

  const areaM2 = (Number(d.land_m2) || 0) + (Number(d.bldg_m2) || 0);
  const drop = dropRate(d.min_bid, d.appraisal);

  const rows = [
    ["용도",         escapeHtml(d.usage || "—")],
    ["토지면적",      `<strong>${escapeHtml(pyeong(d.land_m2))}</strong>`],
    ["건물면적",      `<strong>${escapeHtml(pyeong(d.bldg_m2))}</strong>`],
    ["감정가",        `<span class="dp-val-highlight">${escapeHtml(won(d.appraisal))}</span>`],
    ["최저입찰가",    `<span class="dp-val-highlight">${escapeHtml(won(d.min_bid))}</span>${drop ? `<span class="dp-val-drop">(${escapeHtml(drop)})</span>` : ""}`],
    ["보증금",        escapeHtml(won(d.deposit))],
    ["청구액",        escapeHtml(won(d.claim_amt))],
    ["유찰횟수",      `<strong>${escapeHtml(String(d.fail_count ?? "—"))}</strong>회`],
    ["매각기일",      escapeHtml(fmtY(d.sale_date))],
    ["배당요구종기",  escapeHtml(d.dividend_deadline ? fmtY(d.dividend_deadline) : "—")],
  ];

  rows.forEach(([label, valHtml]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${escapeHtml(label)}</th><td>${valHtml}</td>`;
    tbody.appendChild(tr);
  });
}

/** 가격·시세 cards */
function renderPriceCards(d) {
  const wrap = $("dp-price-cards");
  wrap.innerHTML = "";

  const cards = [
    { label: "감정가",      val: won(d.appraisal),         sub: perPyeong(d.appraisal, (Number(d.land_m2)||0)+(Number(d.bldg_m2)||0)) },
    { label: "최저입찰가",  val: won(d.min_bid),           sub: perPyeong(d.min_bid, (Number(d.land_m2)||0)+(Number(d.bldg_m2)||0)) },
    { label: "보증금",      val: won(d.deposit),           sub: "" },
    { label: "청구액",      val: won(d.claim_amt),         sub: "" },
  ];

  cards.forEach((c) => {
    const div = document.createElement("div");
    div.className = "dp-price-card";
    div.innerHTML =
      `<div class="dp-price-card-label">${escapeHtml(c.label)}</div>` +
      `<div class="dp-price-card-val">${escapeHtml(c.val)}</div>` +
      (c.sub ? `<div class="dp-price-card-sub">${escapeHtml(c.sub)}</div>` : "");
    wrap.appendChild(div);
  });
}

// ── 실거래 시세 (시세분석 섹션) ──────────────────────────────────────────────

/**
 * POST /api/market 로 실거래 시세만 가볍게 조회 (건축물대장/토지 호출 없음).
 * @param {string} address 지번주소
 * @returns {Promise<object>}  { address, market, error }
 */
async function fetchMarket(address) {
  const resp = await fetch("/api/market", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, months: 6 }),
  });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status}: ${txt || resp.statusText}`);
  }
  return resp.json();
}

/** 시세분석 섹션에 실거래 시세(요약 + 최근 거래표) 렌더 */
function renderMarket(result) {
  const body = $("dp-market-body");
  if (!body) return;
  body.innerHTML = "";

  const market = result && result.market;
  if (!market) {
    const msg = document.createElement("div");
    msg.className = "dp-market-empty";
    msg.textContent =
      result && result.error
        ? "실거래 시세를 불러오지 못했습니다."
        : "주변 실거래 내역이 없습니다.";
    body.appendChild(msg);
    return;
  }

  // 요약 stat 카드
  const stats = document.createElement("div");
  stats.className = "dp-market-stats";
  const months = Array.isArray(market.months) ? market.months.length : null;
  const statRows = [
    ["평균 ㎡당가", market.avg_price_per_m2 != null ? won(market.avg_price_per_m2) : "—"],
    ["최저 ㎡당가", market.min_price_per_m2 != null ? won(market.min_price_per_m2) : "—"],
    ["최고 ㎡당가", market.max_price_per_m2 != null ? won(market.max_price_per_m2) : "—"],
    ["거래 건수", (market.trade_count != null ? market.trade_count : 0) + "건"],
    ["조회 기간", months != null ? `최근 ${months}개월` : "—"],
  ];
  statRows.forEach(([label, val]) => {
    const card = document.createElement("div");
    card.className = "dp-market-stat";
    card.innerHTML =
      `<div class="dp-market-stat-val">${escapeHtml(val)}</div>` +
      `<div class="dp-market-stat-label">${escapeHtml(label)}</div>`;
    stats.appendChild(card);
  });
  body.appendChild(stats);

  // 최근 실거래 테이블
  const trades = Array.isArray(market.recent_trades) ? market.recent_trades : [];
  if (trades.length === 0) {
    const none = document.createElement("div");
    none.className = "dp-market-empty";
    none.textContent = "표시할 최근 거래가 없습니다.";
    body.appendChild(none);
    return;
  }

  const tableWrap = document.createElement("div");
  tableWrap.style.overflowX = "auto";
  const table = document.createElement("table");
  table.className = "dp-market-table";
  table.innerHTML =
    "<thead><tr><th>거래일</th><th>동</th><th>용도</th><th>거래가</th><th>전용면적</th><th>㎡당가</th></tr></thead>";
  const tbody = document.createElement("tbody");
  trades.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(t.deal_date || "—")}</td>` +
      `<td>${escapeHtml(t.dong || "—")}</td>` +
      `<td>${escapeHtml(t.building_use || "—")}</td>` +
      `<td>${escapeHtml(won(t.deal_amount_won))}</td>` +
      `<td>${escapeHtml(t.building_area_m2 != null ? pyeong(t.building_area_m2) : "—")}</td>` +
      `<td>${escapeHtml(t.price_per_building_m2 != null ? won(t.price_per_building_m2) : "—")}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  body.appendChild(tableWrap);
}

/** 시세 비동기 로드 (논블로킹: 본문 렌더를 막지 않는다) */
async function loadMarket(address) {
  const body = $("dp-market-body");
  if (!address) {
    if (body) {
      body.innerHTML =
        '<div class="dp-market-empty">주소 정보가 없어 시세를 조회할 수 없습니다.</div>';
    }
    return;
  }
  try {
    const result = await fetchMarket(address);
    renderMarket(result);
  } catch (err) {
    if (body) {
      body.innerHTML = "";
      const msg = document.createElement("div");
      msg.className = "dp-market-empty";
      msg.textContent = "실거래 시세를 불러오지 못했습니다.";
      body.appendChild(msg);
    }
  }
}

// ── 주변 경매 통계 (자체 수집 데이터 집계) ─────────────────────────────────────

/** 대한민국 17개 광역자치단체 정식 명칭 (시/도 검증용) */
const KOREAN_SIDO = new Set([
  "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
  "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도",
  "강원특별자치도", "충청북도", "충청남도", "전라북도", "전라남도",
  "전북특별자치도", "경상북도", "경상남도", "제주특별자치도", "제주도",
]);

/** 한국 주소에서 시/도·구/군·동/읍/면 토큰 추출 */
function parseRegion(addr) {
  const s = String(addr || "");
  // 시/도는 주소 맨 앞 토큰(서울특별시·부산광역시·경기도 등). 같은 이름의 구를
  // 구분하려면(서울 강서구 ≠ 부산 강서구) 시/도가 반드시 필요하다. 맨 앞에
  // 고정(^)하고 정식 명칭만 인정해 '수원시' 같은 시·군을 시/도로 오인하지 않는다.
  const sidoMatch = s.match(
    /^\s*([가-힣]+(?:특별자치시|특별자치도|특별시|광역시|자치시|자치도|도|시))(?=\s|$)/
  );
  const sido = sidoMatch && KOREAN_SIDO.has(sidoMatch[1]) ? sidoMatch[1] : "";
  const guMatch = s.match(/([가-힣]{1,6}(?:구|군))(?:\s|$)/);
  const dongMatch = s.match(/([가-힣]{1,6}(?:동|읍|면))(?:\s|\d|$)/);
  return {
    sido,
    gu: guMatch ? guMatch[1] : "",
    dong: dongMatch ? dongMatch[1] : "",
  };
}

/** GET /api/listings → 매물 풀 (matched + unmatched 합산) */
async function fetchListings() {
  const resp = await fetch("/api/listings");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  const a = Array.isArray(data.listings) ? data.listings : [];
  const b = Array.isArray(data.unmatched_listings) ? data.unmatched_listings : [];
  return a.concat(b);
}

/**
 * 현재 물건과 같은 구의 경매 물건 통계 집계
 * @returns {object|null}  null = 지역 파싱 실패
 */
function computeNearbyStats(listings, currentAddr, currentIdentity) {
  const cur = parseRegion(currentAddr);
  if (!cur.gu) return null;

  const pool = (Array.isArray(listings) ? listings : []).filter(
    (l) => l && l.identity !== currentIdentity && parseRegion(l.location).gu === cur.gu
  );
  if (pool.length === 0) return { gu: cur.gu, dong: cur.dong, count: 0 };

  const sameDong = cur.dong
    ? pool.filter((l) => parseRegion(l.location).dong === cur.dong).length
    : 0;

  const drops = [];
  pool.forEach((l) => {
    const ap = Number(l.appraisal_price);
    const mb = Number(l.min_bid_price);
    if (ap > 0 && mb > 0) drops.push((1 - mb / ap) * 100);
  });
  const avgDrop = drops.length ? drops.reduce((a, b) => a + b, 0) / drops.length : null;

  const fails = pool.map((l) => Number(l.fail_count)).filter((n) => !isNaN(n));
  const avgFail = fails.length ? fails.reduce((a, b) => a + b, 0) / fails.length : null;

  const usageMap = {};
  pool.forEach((l) => {
    const u = ((l.usage || l.property_type || "기타") + "").trim() || "기타";
    usageMap[u] = (usageMap[u] || 0) + 1;
  });
  const usageDist = Object.entries(usageMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return { gu: cur.gu, dong: cur.dong, count: pool.length, sameDong, avgDrop, avgFail, usageDist };
}

/** 주변 통계 렌더 */
function renderNearbyStats(stats) {
  const body = $("dp-nearby-body");
  if (!body) return;
  body.innerHTML = "";

  if (!stats || !stats.gu) {
    body.innerHTML =
      '<div class="dp-market-empty">지역 정보를 확인할 수 없어 통계를 낼 수 없습니다.</div>';
    return;
  }
  if (stats.count === 0) {
    body.innerHTML = `<div class="dp-market-empty">수집된 ${escapeHtml(stats.gu)} 인근 경매 물건이 없습니다.</div>`;
    return;
  }

  const stat = document.createElement("div");
  stat.className = "dp-market-stats";
  const rows = [
    [`${stats.gu} 경매물건`, stats.count + "건"],
    [`같은 동(${stats.dong || "—"})`, stats.dong ? stats.sameDong + "건" : "—"],
    ["평균 하락률", stats.avgDrop != null ? `−${Math.round(stats.avgDrop)}%` : "—"],
    ["평균 유찰횟수", stats.avgFail != null ? stats.avgFail.toFixed(1) + "회" : "—"],
  ];
  rows.forEach(([label, val]) => {
    const card = document.createElement("div");
    card.className = "dp-market-stat";
    card.innerHTML =
      `<div class="dp-market-stat-val">${escapeHtml(val)}</div>` +
      `<div class="dp-market-stat-label">${escapeHtml(label)}</div>`;
    stat.appendChild(card);
  });
  body.appendChild(stat);

  const dist = Array.isArray(stats.usageDist) ? stats.usageDist : [];
  if (dist.length) {
    const title = document.createElement("div");
    title.className = "dp-subsection-title";
    title.textContent = "용도별 분포";
    body.appendChild(title);

    const wrap = document.createElement("div");
    wrap.className = "dp-usage-dist";
    const max = dist[0][1] || 1;
    dist.forEach(([usage, n]) => {
      const row = document.createElement("div");
      row.className = "dp-usage-row";
      const pct = Math.max(6, Math.round((n / max) * 100));
      row.innerHTML =
        `<span class="dp-usage-name">${escapeHtml(usage)}</span>` +
        `<span class="dp-usage-bar"><span class="dp-usage-fill" style="width:${pct}%"></span></span>` +
        `<span class="dp-usage-count">${escapeHtml(String(n))}건</span>`;
      wrap.appendChild(row);
    });
    body.appendChild(wrap);
  }
}

/** 주변 통계 비동기 로드 (논블로킹) */
async function loadNearbyStats(currentAddr, currentIdentity) {
  const body = $("dp-nearby-body");
  try {
    const listings = await fetchListings();
    renderNearbyStats(computeNearbyStats(listings, currentAddr, currentIdentity));
  } catch (err) {
    if (body) {
      body.innerHTML = '<div class="dp-market-empty">주변 통계를 불러오지 못했습니다.</div>';
    }
  }
}

// ── 주변 입주예정 (청약홈 분양정보) ────────────────────────────────────────────

/** GET /api/nearby-supply?region=&sido= → 같은 시/도+시군구 입주예정 분양 */
async function fetchSupply(region, sido) {
  const params = new URLSearchParams({ region });
  if (sido) params.set("sido", sido);
  const resp = await fetch(`/api/nearby-supply?${params.toString()}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

/** 주변 입주예정 렌더 */
function renderSupply(data) {
  const body = $("dp-supply-body");
  if (!body) return;
  body.innerHTML = "";

  if (data && data.error) {
    body.innerHTML =
      '<div class="dp-market-empty">주변 분양정보를 불러오지 못했습니다. (청약홈 API)</div>';
    return;
  }
  const supplies = data && Array.isArray(data.supplies) ? data.supplies : [];
  const gu = (data && data.region) || "";
  const sido = (data && data.sido) || "";
  const region = sido ? `${sido} ${gu}`.trim() : gu;
  if (supplies.length === 0) {
    body.innerHTML =
      `<div class="dp-market-empty">${escapeHtml(region || "해당 지역")}에 입주예정 신규 분양이 없습니다.</div>`;
    return;
  }

  const total = supplies.reduce((sum, s) => sum + (Number(s.total_households) || 0), 0);
  const summary = document.createElement("div");
  summary.className = "dp-tenant-meta";
  summary.textContent =
    `${region} 입주예정 ${supplies.length}개 단지 · 총 ${total.toLocaleString("ko-KR")}세대 (미래 배후수요)`;
  body.appendChild(summary);

  const wrap = document.createElement("div");
  wrap.style.overflowX = "auto";
  const table = document.createElement("table");
  table.className = "dp-market-table";
  table.innerHTML =
    "<thead><tr><th>입주예정</th><th>단지명</th><th>세대수</th><th>구분</th><th>위치</th><th>공고</th></tr></thead>";
  const tbody = document.createElement("tbody");
  supplies.forEach((s) => {
    const tr = document.createElement("tr");
    const href = s.notice_url ? safeHref(s.notice_url) : null;
    const link = href
      ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">보기</a>`
      : "—";
    tr.innerHTML =
      `<td><strong>${escapeHtml(s.move_in_label || "미정")}</strong></td>` +
      `<td>${escapeHtml(s.house_name || "—")}</td>` +
      `<td>${s.total_households != null ? Number(s.total_households).toLocaleString("ko-KR") + "세대" : "—"}</td>` +
      `<td>${escapeHtml(s.house_type || "—")}</td>` +
      `<td>${escapeHtml((s.address || "").slice(0, 30))}</td>` +
      `<td>${link}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  body.appendChild(wrap);
}

/** 주변 입주예정 비동기 로드 (논블로킹). 주소에서 시군구를 뽑아 조회 */
async function loadSupply(addr) {
  const body = $("dp-supply-body");
  const { sido, gu } = parseRegion(addr);
  if (!gu) {
    if (body) body.innerHTML = '<div class="dp-market-empty">지역 정보를 확인할 수 없습니다.</div>';
    return;
  }
  try {
    renderSupply(await fetchSupply(gu, sido));
  } catch (err) {
    if (body) {
      body.innerHTML = '<div class="dp-market-empty">주변 분양정보를 불러오지 못했습니다.</div>';
    }
  }
}

// ── 임차인 · 점유관계 (현황조사서) ─────────────────────────────────────────────

/** GET /api/listing/tenants → 현황조사서 임대차/점유 데이터 */
async function fetchTenants(cs, court) {
  const qs = new URLSearchParams({ cs, court }).toString();
  const resp = await fetch(`/api/listing/tenants?${qs}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

/** 임차인 · 점유관계 렌더 */
function renderTenants(data) {
  const body = $("dp-tenants-body");
  if (!body) return;
  body.innerHTML = "";

  const tenants = data && Array.isArray(data.tenants) ? data.tenants : [];
  const survey = (data && data.survey) || {};

  if (survey.sent_date || survey.exam_dates) {
    const meta = document.createElement("div");
    meta.className = "dp-tenant-meta";
    const parts = [];
    if (survey.sent_date) parts.push("송달일 " + fmtY(survey.sent_date));
    if (survey.exam_dates) parts.push("조사일시 " + survey.exam_dates);
    meta.textContent = parts.join("   ·   ");
    body.appendChild(meta);
  }

  if (tenants.length === 0) {
    const none = document.createElement("div");
    none.className = "dp-market-empty";
    none.textContent = "현황조사서상 임차인·점유자 정보가 없습니다.";
    body.appendChild(none);
    return;
  }

  const wrap = document.createElement("div");
  wrap.style.overflowX = "auto";
  const table = document.createElement("table");
  table.className = "dp-market-table";
  table.innerHTML =
    "<thead><tr><th>점유자</th><th>호/부분</th><th>전입일</th><th>확정일자</th>" +
    "<th>보증금</th><th>차임</th><th>비고</th></tr></thead>";
  const tbody = document.createElement("tbody");
  tenants.forEach((t) => {
    const part = [t.address, t.part].filter(Boolean).join(" ");
    const note = [t.possession, t.note].filter(Boolean).join(" / ");
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(t.name || "—")}</td>` +
      `<td>${escapeHtml(part || "—")}</td>` +
      `<td>${escapeHtml(t.move_in || "—")}</td>` +
      `<td>${escapeHtml(t.confirm || "—")}</td>` +
      `<td>${escapeHtml(t.deposit || "—")}</td>` +
      `<td>${escapeHtml(t.rent || "—")}</td>` +
      `<td>${escapeHtml(note || "—")}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  body.appendChild(wrap);
}

/** 임차인 비동기 로드 (논블로킹) */
async function loadTenants(cs, court) {
  const body = $("dp-tenants-body");
  if (!cs || !court) {
    if (body) {
      body.innerHTML =
        '<div class="dp-market-empty">법원경매 물건이 아니어서 현황조사서를 조회할 수 없습니다.</div>';
    }
    return;
  }
  try {
    renderTenants(await fetchTenants(cs, court));
  } catch (err) {
    if (body) {
      body.innerHTML =
        '<div class="dp-market-empty">현황조사서를 불러오지 못했습니다.</div>';
    }
  }
}

// ── 매각물건명세서 (법원 판단: 말소기준·확정·배당·대항력) ──────────────────────

/** GET /api/listing/sale-spec → 매각물건명세서 텍스트 추출·파싱 결과 */
async function fetchSaleSpec(cs, court, seq) {
  const qs = new URLSearchParams({ cs, court, seq: seq || "1" }).toString();
  const resp = await fetch(`/api/listing/sale-spec?${qs}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

/** 매각물건명세서 분석 결과 렌더 (원문 발췌 — 우측 링크에서 원문 대조 가능) */
function renderSaleSpec(data) {
  const body = $("dp-salespec-body");
  if (!body) return;
  body.innerHTML = "";

  if (!data || !data.has_data) {
    body.innerHTML =
      '<div class="dp-market-empty">매각물건명세서 정보를 불러오지 못했습니다. 원문은 우측 “매각물건명세서” 링크에서 확인하세요.</div>';
    return;
  }

  // 핵심 사실: 말소기준권리 + 배당요구종기
  const facts = [];
  if (Array.isArray(data.priority) && data.priority.length) {
    facts.push(["말소기준권리(최선순위 설정)", data.priority.join("   ·   ")]);
  }
  if (data.dividend_deadline) facts.push(["배당요구종기", data.dividend_deadline]);
  if (facts.length) {
    const kv = document.createElement("div");
    kv.className = "dp-hosp-kv";
    facts.forEach(([k, v]) => {
      const row = document.createElement("div");
      row.className = "dp-hosp-kv-row";
      row.innerHTML =
        `<span class="dp-hosp-kv-key">${escapeHtml(k)}</span>` +
        `<span class="dp-hosp-kv-val">${escapeHtml(v)}</span>`;
      kv.appendChild(row);
    });
    body.appendChild(kv);
  }

  // 임차인 (법원 명세서 기준: 전입·확정·보증금·배당요구가 한 줄에 담김)
  const tenants = Array.isArray(data.tenants) ? data.tenants : [];
  if (tenants.length) {
    const wrap = document.createElement("div");
    wrap.style.overflowX = "auto";
    const table = document.createElement("table");
    table.className = "dp-market-table";
    table.innerHTML =
      "<thead><tr><th>성명</th><th>점유·임대차 (전입·확정·보증금·배당요구)</th></tr></thead>";
    const tbody = document.createElement("tbody");
    tenants.forEach((t) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${escapeHtml(t.name || "—")}</td>` +
        `<td>${escapeHtml(t.detail || "—")}</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    body.appendChild(wrap);
  }

  // 비고 (대항력·인수 주의 등 물건별 특이사항)
  const notes = Array.isArray(data.notes) ? data.notes : [];
  if (notes.length) {
    const title = document.createElement("div");
    title.className = "dp-subsection-title";
    title.textContent = "비고";
    body.appendChild(title);
    const list = document.createElement("div");
    list.className = "dp-rights-list";
    notes.forEach((n) => {
      const div = document.createElement("div");
      div.className = "dp-rights-item";
      div.textContent = n;
      list.appendChild(div);
    });
    body.appendChild(list);
  }
}

/** 매각물건명세서 비동기 로드 (논블로킹) */
async function loadSaleSpec(cs, court, seq) {
  const body = $("dp-salespec-body");
  if (!cs || !court) {
    if (body) body.innerHTML = "";
    const blk = $("dp-salespec-block");
    if (blk) blk.hidden = true;
    return;
  }
  try {
    renderSaleSpec(await fetchSaleSpec(cs, court, seq));
  } catch (err) {
    if (body) {
      body.innerHTML =
        '<div class="dp-market-empty">매각물건명세서를 분석하지 못했습니다. 원문은 우측 링크에서 확인하세요.</div>';
    }
  }
}

/** 권리분석 인수사항 */
function renderRights(incumbrances) {
  const wrap = $("dp-rights-content");
  wrap.innerHTML = "";

  const list = Array.isArray(incumbrances) ? incumbrances : [];
  if (list.length === 0) {
    const div = document.createElement("div");
    div.className = "dp-rights-empty";
    div.textContent = "특이 인수사항 없음";
    wrap.appendChild(div);
    return;
  }

  const container = document.createElement("div");
  container.className = "dp-rights-list";
  list.forEach((item) => {
    const div = document.createElement("div");
    div.className = "dp-rights-item";
    div.textContent = String(item);
    container.appendChild(div);
  });
  wrap.appendChild(container);
}

/** 기일내역 */
function renderBidHistory(bidHistory) {
  const tbody = $("dp-bid-table").querySelector("tbody");
  tbody.innerHTML = "";

  const rows = Array.isArray(bidHistory) ? bidHistory : [];
  if (rows.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="3" style="padding:14px;color:var(--ink-faint);text-align:center;">기일내역 없음</td>`;
    tbody.appendChild(tr);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const result = escapeHtml(row.result || "");
    const chipClass = ["유찰","진행","매각결정","변경"].includes(row.result || "")
      ? escapeHtml(row.result)
      : "";
    tr.innerHTML =
      `<td>${escapeHtml(fmtY(row.date))}</td>` +
      `<td>${row.low ? escapeHtml(won(row.low)) : "—"}</td>` +
      `<td><span class="dp-bid-chip ${chipClass}">${result || "—"}</span></td>`;
    tbody.appendChild(tr);
  });
}

/** 현황정보 */
function renderStatusItems(statusItems) {
  const list = $("dp-status-list");
  list.innerHTML = "";

  const items = Array.isArray(statusItems) ? statusItems : [];
  if (items.length === 0) {
    const div = document.createElement("div");
    div.style.cssText = "padding:14px 18px;color:var(--ink-faint);font-size:.87rem;";
    div.textContent = "현황정보 없음";
    list.appendChild(div);
    return;
  }

  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "dp-status-item";
    div.innerHTML =
      `<div class="dp-status-label">${escapeHtml(item.label || "")}</div>` +
      `<div class="dp-status-text">${escapeHtml(item.text || "")}</div>`;
    list.appendChild(div);
  });
}

/** 제시외건물 table (empty → section hidden) */
function renderPresentedOutside(items) {
  const secPresented = $("sec-presented");
  const presentedWrap = $("dp-presented-wrap");

  const rows = Array.isArray(items) ? items : [];
  if (rows.length === 0) {
    presentedWrap.hidden = true;
    return;
  }

  presentedWrap.hidden = false;
  const tbody = $("dp-presented-table").querySelector("tbody");
  tbody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(row.usage || "")}</td>` +
      `<td>${escapeHtml(row.structure || "")}</td>` +
      `<td>${escapeHtml(pyeong(row.area))}</td>` +
      `<td>${escapeHtml(won(row.appraisal))}</td>` +
      `<td>${escapeHtml(row.note || "")}</td>`;
    tbody.appendChild(tr);
  });

  secPresented.hidden = false;
}

/** 건물상세 (empty → wrap hidden) */
function renderBuildingDetail(items) {
  const secPresented = $("sec-presented");
  const bldgWrap = $("dp-bldg-wrap");

  const rows = Array.isArray(items) ? items : [];
  if (rows.length === 0) {
    bldgWrap.hidden = true;
    return;
  }

  bldgWrap.hidden = false;
  const list = $("dp-bldg-list");
  list.innerHTML = "";
  rows.forEach((row) => {
    const item = document.createElement("div");
    item.innerHTML =
      `<div class="dp-bldg-item-kind">${escapeHtml(row.kind || "")}</div>` +
      `<div class="dp-bldg-item-detail">${escapeHtml(row.detail || "")}</div>`;
    list.appendChild(item);
  });

  secPresented.hidden = false;
}

/** 지번 목록 (empty → section hidden) */
function renderJibunList(items) {
  const sec = $("sec-register");
  const rows = Array.isArray(items) ? items : [];
  if (rows.length === 0) {
    sec.hidden = true;
    return;
  }

  sec.hidden = false;
  const tbody = $("dp-jibun-table").querySelector("tbody");
  tbody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(row.jibun || "")}</td>` +
      `<td>${escapeHtml(row.addr || "")}</td>` +
      `<td>${escapeHtml(row.road || "")}</td>`;
    tbody.appendChild(tr);
  });
}

/** 물건비고 (null → section hidden) */
function renderSaleNotice(notice) {
  const sec = $("sec-misc");
  if (!notice) {
    sec.hidden = true;
    return;
  }
  sec.hidden = false;
  $("dp-notice-text").textContent = notice;
}

// ── 병원 분석 (심평원·공공데이터 검증) ─────────────────────────────────────────

/**
 * POST /api/verify 를 호출해 심평원 의료 데이터 + 공공 검증 데이터를 받아온다.
 * Request shape: { "address": "<지번주소>", "months": 6 }
 * @param {string} address
 * @returns {Promise<object>}
 */
async function fetchVerify(address) {
  const resp = await fetch("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, months: 6 }),
  });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status}: ${txt || resp.statusText}`);
  }
  return resp.json();
}

/** 심평원 의료 데이터 그룹 렌더링 */
function renderMedicalGroup(medical, errors) {
  const div = document.createElement("div");
  div.className = "dp-hosp-group";

  const title = document.createElement("div");
  title.className = "dp-hosp-group-title";
  title.textContent = "주변 병원·약국 (심평원)";
  div.appendChild(title);

  if (errors && errors.medical) {
    const err = document.createElement("div");
    err.className = "dp-hosp-error";
    err.textContent = "심평원 데이터를 불러오지 못했습니다: " + escapeHtml(errors.medical);
    div.appendChild(err);
    return div;
  }

  if (!medical) {
    const na = document.createElement("div");
    na.className = "dp-hosp-error";
    na.textContent = "심평원 데이터 없음";
    div.appendChild(na);
    return div;
  }

  const stats = document.createElement("div");
  stats.className = "dp-hosp-stats";

  const makeStatCard = (val, label) => {
    const card = document.createElement("div");
    card.className = "dp-hosp-stat";
    card.innerHTML =
      `<div class="dp-hosp-stat-val">${escapeHtml(val === null || val === undefined ? "—" : String(val))}</div>` +
      `<div class="dp-hosp-stat-label">${escapeHtml(label)}</div>`;
    return card;
  };

  stats.appendChild(makeStatCard(medical.ortho_clinic_count, "같은동 정형외과 의원"));
  stats.appendChild(makeStatCard(medical.ortho_treating_count, "정형외과 진료 기관"));
  stats.appendChild(makeStatCard(medical.pharmacy_count, "약국"));
  div.appendChild(stats);

  const names = Array.isArray(medical.ortho_clinic_names) ? medical.ortho_clinic_names : [];
  if (names.length > 0) {
    const nameDiv = document.createElement("div");
    nameDiv.className = "dp-hosp-names";
    nameDiv.textContent = "경쟁 의원: " + names.map((n) => escapeHtml(n)).join(", ");
    div.appendChild(nameDiv);
  }

  return div;
}

/** 공공데이터 검증 요약 그룹 렌더링 */
function renderVerifyGroup(report) {
  const div = document.createElement("div");
  div.className = "dp-hosp-group";

  const title = document.createElement("div");
  title.className = "dp-hosp-group-title";
  title.textContent = "공공데이터 검증 요약";
  div.appendChild(title);

  const kv = document.createElement("div");
  kv.className = "dp-hosp-kv";

  const addRow = (key, val) => {
    const row = document.createElement("div");
    row.className = "dp-hosp-kv-row";
    row.innerHTML =
      `<span class="dp-hosp-kv-key">${escapeHtml(key)}</span>` +
      `<span class="dp-hosp-kv-val">${escapeHtml(val || "—")}</span>`;
    kv.appendChild(row);
  };

  const land = report.land || {};
  const building = report.building || {};

  if (land.zoning_names != null) addRow("용도지역", Array.isArray(land.zoning_names) ? land.zoning_names.join(", ") : String(land.zoning_names));
  if (land.road_side != null) addRow("도로접면", String(land.road_side));
  if (land.land_use_situation != null) addRow("이용상황", String(land.land_use_situation));
  if (land.terrain_shape != null || land.terrain_height != null) {
    const parts = [land.terrain_shape, land.terrain_height].filter(Boolean);
    addRow("지형", parts.join(" · "));
  }
  if (land.official_price_per_m2 != null) addRow("공시지가", won(land.official_price_per_m2) + "/㎡");
  if (building.main_purpose != null) addRow("건물 주용도", String(building.main_purpose));
  if (building.total_area_m2 != null) addRow("연면적", pyeong(building.total_area_m2));
  if (building.ground_floors != null) addRow("층수", `${building.ground_floors}층`);
  if (building.parking_spaces != null) addRow("주차 대수", `${building.parking_spaces}대`);
  if (building.elevator_count != null) addRow("승강기", building.elevator_count > 0 ? "있음" : "없음");
  if (building.approval_date != null) addRow("사용승인일", fmtY(String(building.approval_date).replace(/-/g, "")));

  div.appendChild(kv);
  return div;
}

/** 실거래 시세 그룹 렌더링 */
function renderMarketGroup(market, errors) {
  const div = document.createElement("div");
  div.className = "dp-hosp-group";

  const title = document.createElement("div");
  title.className = "dp-hosp-group-title";
  title.textContent = "실거래 시세";
  div.appendChild(title);

  if (errors && errors.market) {
    const err = document.createElement("div");
    err.className = "dp-hosp-error";
    err.textContent = "시세 데이터를 불러오지 못했습니다: " + escapeHtml(errors.market);
    div.appendChild(err);
    return div;
  }

  if (!market) {
    const na = document.createElement("div");
    na.className = "dp-hosp-error";
    na.textContent = "시세 데이터 없음";
    div.appendChild(na);
    return div;
  }

  const kv = document.createElement("div");
  kv.className = "dp-hosp-kv";

  const addRow = (key, val) => {
    const row = document.createElement("div");
    row.className = "dp-hosp-kv-row";
    row.innerHTML =
      `<span class="dp-hosp-kv-key">${escapeHtml(key)}</span>` +
      `<span class="dp-hosp-kv-val">${escapeHtml(val || "—")}</span>`;
    kv.appendChild(row);
  };

  if (market.avg_price_per_m2 != null) addRow("평균 ㎡당가", won(market.avg_price_per_m2) + "/㎡");
  if (market.trade_count != null) addRow("거래 건수", `${market.trade_count}건`);
  if (market.months != null) {
    const monthCount = Array.isArray(market.months) ? market.months.length : market.months;
    addRow("조회 기간", `최근 ${monthCount}개월`);
  }

  div.appendChild(kv);
  return div;
}

/**
 * 병원 분석 결과 전체 렌더링
 * @param {object} report  /api/verify 응답
 * @param {string} verifyAddr  검증에 사용한 주소
 */
function renderHospitalResult(report, verifyAddr) {
  const wrap = $("dp-hosp-result");
  wrap.innerHTML = "";

  wrap.appendChild(renderMedicalGroup(report.medical, report.errors));
  wrap.appendChild(renderVerifyGroup(report));
  wrap.appendChild(renderMarketGroup(report.market, report.errors));

  // 전체 체크리스트 링크
  const linkDiv = document.createElement("div");
  linkDiv.style.marginTop = "12px";
  const verifyUrl = `/?address=${encodeURIComponent(verifyAddr)}`;
  linkDiv.innerHTML =
    `<a class="dp-hosp-link-btn" href="${verifyUrl}" target="_blank" rel="noopener noreferrer">전체 검증 · 체크리스트 열기</a>`;
  wrap.appendChild(linkDiv);

  wrap.hidden = false;
}

/** 병원 분석 버튼 이벤트 초기화 */
function initHospitalAnalysis(addr) {
  const btn = $("dp-hosp-run-btn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.textContent = "분석 중…";

    const wrap = $("dp-hosp-result");
    wrap.hidden = true;
    wrap.innerHTML = "";

    try {
      const report = await fetchVerify(addr);
      renderHospitalResult(report, addr);
    } catch (err) {
      wrap.innerHTML =
        `<div class="dp-hosp-error">분석을 불러오지 못했습니다: ${escapeHtml(err && err.message ? err.message : String(err))}</div>`;
      wrap.hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = "분석 실행";
    }
  });
}

// ── 공식 문서 딥링크 (매각물건명세서) ──────────────────────────────────────────

/**
 * 매각물건명세서 링크: 클릭 시 서버가 courtauction에서 신선한 전자문서 뷰어
 * 딥링크(encParam)를 만들어 새 탭으로 연다. encParam이 단기 토큰이라 클릭 시점에
 * 생성한다. 팝업 차단을 피하려고 클릭 동기 시점에 빈 탭을 먼저 연다.
 */
function initDocLinks(params) {
  const el = $("dp-doc-sale-spec");
  if (!el) return;
  // cs/court가 없으면(법원물건 아님) 기존 courtauction 안내 링크 유지
  if (!params.cs || !params.court) return;

  el.addEventListener("click", async (e) => {
    e.preventDefault();
    // noopener를 주면 window.open이 null을 반환해 빈 탭이 남으므로, 참조를 받고
    // opener를 수동으로 끊는다(신뢰된 정부 도메인으로만 이동).
    const win = window.open("", "_blank");
    if (win) {
      try { win.opener = null; } catch (_) { /* noop */ }
      win.document.write(
        "<!DOCTYPE html><meta charset='utf-8'><title>매각물건명세서</title>" +
        "<p style='font-family:sans-serif;padding:24px;color:#3d5a73'>매각물건명세서를 불러오는 중…</p>"
      );
    }
    const fallback = "https://www.courtauction.go.kr";
    try {
      const qs = new URLSearchParams({
        cs: params.cs, court: params.court, seq: params.seq || "1", kind: "sale_spec",
      }).toString();
      const resp = await fetch(`/api/listing/doc-link?${qs}`);
      const data = await resp.json().catch(() => ({}));
      const target = data && data.url ? data.url : fallback;
      if (win) win.location.href = target;
      else window.open(target, "_blank", "noopener");
    } catch (err) {
      if (win) win.location.href = fallback;
    }
  });
}

// ── Tab nav ───────────────────────────────────────────────────────────────────

function initTabNav() {
  const nav = $("dp-tab-nav");
  if (!nav) return;

  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".dp-tab-btn");
    if (!btn) return;

    // Update active state
    nav.querySelectorAll(".dp-tab-btn").forEach((b) => b.classList.remove("dp-tab-active"));
    btn.classList.add("dp-tab-active");

    // Scroll to target section
    const targetId = btn.dataset.target;
    const sec = $(targetId);
    if (sec && !sec.hidden) {
      sec.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

// ── Lightbox events ───────────────────────────────────────────────────────────

function initLightbox() {
  const lb = $("dp-lightbox");
  const closeBtn = $("dp-lightbox-close");

  closeBtn.addEventListener("click", closeLightbox);
  lb.addEventListener("click", (e) => {
    if (e.target === lb) closeLightbox();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !lb.hidden) closeLightbox();
  });
}

// ── Show error state ──────────────────────────────────────────────────────────

function showError(msg, sub) {
  elLoading.hidden = true;
  elErrorMsg.textContent = msg || "데이터를 불러올 수 없습니다";
  elErrorSub.textContent = sub || "";
  elError.hidden = false;
}

// ── Main render orchestrator ──────────────────────────────────────────────────

function renderAll(d) {
  renderCaseHeader(d);
  renderGallery(d.photos);
  renderMap(d.latitude, d.longitude, fullAddress(d));
  renderBasicTable(d);
  renderPriceCards(d);
  renderRights(d.incumbrances);
  renderBidHistory(d.bid_history);
  renderStatusItems(d.status_items);
  renderPresentedOutside(d.presented_outside);
  renderBuildingDetail(d.building_detail);
  renderJibunList(d.jibun_list);
  renderSaleNotice(d.sale_notice);
}

// ── Boot ──────────────────────────────────────────────────────────────────────

async function boot() {
  initTabNav();
  initLightbox();

  const params = getParams();
  initDocLinks(params);

  if (!params.id) {
    showError("URL에 ?id= 파라미터가 없습니다", "목록 페이지에서 물건을 선택해 주세요.");
    return;
  }

  try {
    const data = await fetchDetail(params);

    if (data && data.error) {
      showError("서버 오류", data.error);
      return;
    }

    elLoading.hidden = true;
    renderAll(data);
    const addr = fullAddress(data);  // 시군구 포함 완전 주소(지역 파싱용)
    initHospitalAnalysis(addr);
    elBody.hidden = false;

    // 실거래 시세는 본문 표시 후 비동기로 채운다 (외부 API 지연이 페이지를 막지 않도록).
    loadMarket(addr);
    // 주변 경매 통계도 비동기로 집계 (자체 수집 데이터).
    loadNearbyStats(addr, params.id);
    // 주변 입주예정(청약홈)도 비동기로 로드.
    loadSupply(addr);
    // 임차인·점유관계(현황조사서)도 비동기로 로드.
    loadTenants(params.cs, params.court);
    // 매각물건명세서(법원 판단: 말소기준·확정·배당·대항력)도 비동기로 로드.
    loadSaleSpec(params.cs, params.court, params.seq);
  } catch (err) {
    showError(
      "데이터를 불러올 수 없습니다",
      err && err.message ? err.message : String(err)
    );
  }
}

document.addEventListener("DOMContentLoaded", boot);
