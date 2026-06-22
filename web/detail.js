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
  $("dp-court-badge").textContent = escapeHtml(d.court || "");
  $("dp-case-no").textContent     = escapeHtml(d.case_no || "");
  $("dp-case-type").textContent   = escapeHtml(d.auction_type || "");
  $("dp-addr-road").textContent   = escapeHtml(d.addr_road || "");
  $("dp-addr-jibun").textContent  = escapeHtml(d.addr_jibun || "");
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
    mainImg.addEventListener("click", () => openLightbox(idx), { once: true });
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

/** Map: OpenStreetMap iframe or placeholder */
function renderMap(lat, lng) {
  const wrap = $("dp-map-wrap");
  wrap.innerHTML = "";

  if (lat && lng) {
    const bbox = 0.003;
    const left = Number(lng) - bbox;
    const bottom = Number(lat) - bbox;
    const right = Number(lng) + bbox;
    const top = Number(lat) + bbox;
    const src =
      `https://www.openstreetmap.org/export/embed.html` +
      `?bbox=${left}%2C${bottom}%2C${right}%2C${top}` +
      `&layer=mapnik` +
      `&marker=${lat}%2C${lng}`;
    const iframe = document.createElement("iframe");
    iframe.className = "dp-map-iframe";
    iframe.src = src;
    iframe.title = "물건 위치 지도";
    iframe.loading = "lazy";
    iframe.setAttribute("allowfullscreen", "");
    wrap.appendChild(iframe);
  } else {
    const ph = document.createElement("div");
    ph.className = "dp-map-placeholder";
    ph.textContent = "위치 정보 없음";
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
  renderMap(d.latitude, d.longitude);
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

  if (!params.id) {
    showError("URL에 ?id= 파라미터가 없습니다", "목록 페이지에서 물건을 선택해 주세요.");
    return;
  }

  try {
    const data = await fetchDetail(params);

    if (data && data.error) {
      showError("서버 오류", escapeHtml(data.error));
      return;
    }

    elLoading.hidden = true;
    renderAll(data);
    elBody.hidden = false;
  } catch (err) {
    showError(
      "데이터를 불러올 수 없습니다",
      err && err.message ? err.message : String(err)
    );
  }
}

document.addEventListener("DOMContentLoaded", boot);
