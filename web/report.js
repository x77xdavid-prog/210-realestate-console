/* 매물 투자검토 리포트 렌더러 — /api/report 데이터로 투자제안서 서식의 리포트를 생성.
 * 대시보드가 localStorage(rea210:reportTarget)에 {identity, listing, profile}을 넣고
 * report.html?identity=... 를 새 창으로 연다. 서버 API에만 의존한다. */

const REPORT_TARGET_KEY = "rea210:reportTarget";
const PY = 0.3025; // ㎡ → 평
const STATUS = {
  pass: ["적합", "b-pos"], warn: ["경고", "b-warn"], fail: ["부적합", "b-neg"],
  info: ["정보", "b-neu"], unknown: ["미확인", "b-neu"],
  unchecked: ["미체크", "b-neu"], na: ["해당없음", "b-neu"],
};

const els = {
  root: document.querySelector("#reportRoot"),
  printBtn: document.querySelector("#printBtn"),
  htmlBtn: document.querySelector("#htmlBtn"),
  closeBtn: document.querySelector("#closeBtn"),
};

function escapeHtml(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
function getParam(n) { return new URLSearchParams(location.search).get(n) || ""; }
async function postJson(path, body) {
  const r = await fetch(path, { method: "POST", cache: "no-store",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`API ${path} ${r.status}`);
  return r.json();
}

/* ===== 숫자 포맷 ===== */
const nf = new Intl.NumberFormat("ko-KR");
function eok(won) { return won ? `${(won / 1e8).toFixed(won >= 1e9 ? 1 : 2).replace(/\.0$/, "")}억` : "-"; }
function manM2(perM2) { return perM2 ? `${nf.format(Math.round(perM2 / 1e4))}만원` : "-"; }
function manPyeong(perM2) { return perM2 ? `${nf.format(Math.round((perM2 / PY) / 1e4))}만원` : "-"; }
function py(m2) { return m2 ? `${(m2 * PY).toFixed(2)}평` : "-"; }
function m2py(m2) { return m2 ? `${nf.format(Math.round(m2 * 100) / 100)}㎡ (${(m2 * PY).toFixed(1)}평)` : "-"; }

/* ===== 초기화 ===== */
async function init() {
  const identity = getParam("identity").trim();
  let target = null;
  try { const raw = localStorage.getItem(REPORT_TARGET_KEY); if (raw) target = JSON.parse(raw); } catch { /* noop */ }
  if (target && target.identity !== identity) target = null;
  const listing = (target && target.listing) || {};
  const profile = (target && target.profile) || "building";
  if (!listing.location) {
    els.root.innerHTML = `<div class="report-loading">매물 정보를 찾을 수 없습니다. 매물장의 검토 화면에서 ‘리포트 생성’으로 다시 열어주세요.</div>`;
    return;
  }
  let data;
  try {
    data = await postJson("/api/report", { identity, listing, profile });
  } catch {
    els.root.innerHTML = `<div class="report-loading">리포트 데이터를 불러오지 못했습니다. serve-web 실행 상태에서 다시 시도해주세요.</div>`;
    return;
  }
  render(data);
  els.printBtn.addEventListener("click", () => window.print());
  els.htmlBtn.addEventListener("click", () => downloadHtml(data));
  els.closeBtn.addEventListener("click", () => window.close());
  document.title = `리포트 · ${listing.title || identity}`;
}

/* ===== 가격 산출 ===== */
function priceOf(l) {
  if ((l.monthly_rent || 0) === 0 && (l.deposit || 0) > 0) return l.deposit;
  return l.appraisal_price || l.min_bid_price || l.deposit || 0;
}
function priceLabel(l) {
  if ((l.monthly_rent || 0) === 0 && (l.deposit || 0) > 0) return "매매가";
  if (l.appraisal_price) return "감정가";
  if (l.min_bid_price) return "최저입찰가";
  return "가격";
}

/* ===== 렌더 ===== */
function render(d) {
  const l = d.listing || {};
  const b = d.building || {};
  const land = d.land || {};
  const market = d.market || {};
  const med = d.medical || {};
  const review = d.review || {};
  const html = [
    hero(d, l, b, land, med, review),
    summary(d, l, b, land, market, med, review),
    overview(l, b, land),
    locationMedical(l, land, med),
    priceSection(l, b, market),
    landValueSection(l, b, land, market),
    financingScenarios(l),
    newBuildSection(l, b, land),
    verification(review),
    swot(l, b, review, med),
    conclusion(l, review),
    footer(d, l),
  ].join("");
  els.root.innerHTML = html;
}

function gradeClass(g) {
  if (g === "부적합") return "b-neg";
  if (g === "A" || g === "B") return "b-pos";
  if (g === "C" || g === "D") return "b-warn";
  return "b-neu";
}
function district(loc) {
  const m = String(loc || "").match(/(\S+구)\s+(\S+동)/);
  return m ? `${m[1]} ${m[2]}` : (loc || "");
}
function zoningText(l, land) {
  const names = (land.zoning_names || []).filter(Boolean);
  if (names.length) return names.join(", ");
  return l.zoning || "-";
}
function primaryZoning(l, land) {
  const names = (land.zoning_names || []);
  const commercial = names.find((n) => String(n).includes("상업"));
  return commercial || names[0] || l.zoning || "용도지역 미확인";
}

function hero(d, l, b, land, med, review) {
  const price = priceOf(l);
  const landArea = b.plat_area_m2 || l.land_area_m2;
  const totalArea = b.total_area_m2 || l.building_area_m2;
  const officialPerM2 = land.official_price_per_m2;
  const isLand = l.property_type === "land" || l.floor === "토지/건물";
  const chips = [
    review.grade ? `<span class="chip gold">종합 등급 ${escapeHtml(review.grade)}${review.score != null ? ` · ${review.score}점` : ""}</span>` : "",
    `<span class="chip">${escapeHtml(primaryZoning(l, land))}</span>`,
    `<span class="chip">${isLand ? "토지" : "건물"}</span>`,
    b.approval_year ? `<span class="chip">${b.approval_year}년 준공</span>` : "",
    `<span class="chip">국토부·심평원 공공데이터 검증</span>`,
  ].filter(Boolean).join("");
  const stats = [
    { k: priceLabel(l), v: eok(price), sub: officialPerM2 ? `공시 평당 ${manPyeong(officialPerM2)}` : "" },
    { k: isLand ? "대지면적" : "연면적", v: isLand ? py(landArea).replace("평", "") : (totalArea ? (totalArea * PY).toFixed(1) : "-"), unit: "평", sub: isLand ? (landArea ? `${Math.round(landArea)}㎡` : "") : (landArea ? `대지 ${(landArea * PY).toFixed(1)}평` : "") },
    { k: "종합 등급", v: review.grade || "미검토", sub: review.score != null ? `${review.score}점 / 100` : "자동 검증 기준" },
    { k: "주변 정형외과", v: med.ortho_clinic_count != null ? String(med.ortho_clinic_count) : "-", unit: med.ortho_clinic_count != null ? "곳" : "", sub: med.pharmacy_count != null ? `약국 ${med.pharmacy_count}곳` : "심평원 데이터" },
  ];
  return `
  <header class="hero"><div class="wrap hero-inner">
    <div class="eyebrow">${escapeHtml(district(l.location))} · 병원 입지 검토 리포트</div>
    <h1>${escapeHtml(String(l.title || "매물").replace(/^\[.*?\]\s*/, ""))}</h1>
    <p class="addr"><b>${escapeHtml(l.location || "")}</b></p>
    <div class="hero-tags">${chips}</div>
    <div class="hero-stats">
      ${stats.map((s) => `<div class="st"><div class="k">${escapeHtml(s.k)}</div>
        <div class="v">${escapeHtml(s.v)}${s.unit ? `<small>${s.unit}</small>` : ""}</div>
        ${s.sub ? `<div class="sub">${escapeHtml(s.sub)}</div>` : ""}</div>`).join("")}
    </div>
  </div></header>`;
}

function summary(d, l, b, land, market, med, review) {
  const price = priceOf(l);
  const totalArea = b.total_area_m2 || l.building_area_m2;
  const perM2 = price && totalArea ? price / totalArea : null;
  const avg = market.avg_price_per_m2;
  const ratio = perM2 && avg ? perM2 / avg : null;
  const officialPerM2 = land.official_price_per_m2;
  const landArea = b.plat_area_m2 || l.land_area_m2;
  const officialTotal = officialPerM2 && landArea ? officialPerM2 * landArea : null;
  const priceVsOfficial = officialTotal && price ? price / officialTotal : null;
  const metrics = [
    avg ? { lab: "실거래 대비 (건물 ㎡당)", num: `${Math.round(ratio * 100)}`, unit: "%", note: `매물 ${manM2(perM2)} vs 주변 평균 ${manM2(avg)}` }
        : { lab: "실거래 비교", num: "데이터", unit: "준비", note: "주변 실거래 자동 조회 (키/지역 확인)" },
    officialPerM2 ? { lab: "공시지가", num: manPyeong(officialPerM2).replace("만원", ""), unit: "만원/평", note: `${land.official_price_year || ""} 개별공시지가${priceVsOfficial ? ` · 매물가 ${priceVsOfficial.toFixed(2)}배` : ""}` }
        : { lab: "공시지가", num: "-", unit: "", note: "토지정보 확인 필요" },
    { lab: "종합 등급 / 점수", num: review.grade || "—", unit: review.score != null ? `${review.score}점` : "", note: `자동 ${review.progress?.auto_done ?? 0}/${review.progress?.auto_total ?? 0} 판정` },
    med.ortho_clinic_count != null ? { lab: "의료 경쟁 (같은 동)", num: `${med.ortho_clinic_count}`, unit: "곳", note: `정형외과 전문의원${med.ortho_treating_count ? ` · 진료 의원 ${med.ortho_treating_count}곳` : ""}` }
        : { lab: "의료 경쟁", num: "-", unit: "", note: "심평원 의원·약국 데이터 확인 필요" },
  ];
  const verdictLine = review.no_go
    ? "치명 항목 부적합 — 현 상태로는 병원 용도 진입에 큰 제약이 있습니다. 아래 검증 근거의 부적합 항목을 먼저 해소해야 합니다."
    : (review.grade === "A" || review.grade === "B")
      ? "공공데이터 자동 검증 기준 양호 — 현장 실사·등기·자금 조건 확정 후 적극 검토할 만한 물건입니다."
      : "일부 항목에 확인·보완이 필요합니다. 아래 검증 근거의 경고·미확인 항목을 점검하세요.";
  return `
  <section><div class="wrap">
    <div class="sec-tag">Executive Summary</div>
    <h2 class="sec">핵심 요약</h2>
    <p class="lead">공공데이터(건축물대장·토지·국토부 실거래·심평원)와 병원 입지 체크리스트로 자동 검증한 결과입니다.</p>
    <div class="grid g4" style="margin-top:30px">
      ${metrics.map((m) => `<div class="metric"><div class="accent-bar"></div>
        <div class="lab">${escapeHtml(m.lab)}</div>
        <div class="num">${escapeHtml(m.num)}<small>${escapeHtml(m.unit)}</small></div>
        <div class="note">${escapeHtml(m.note)}</div></div>`).join("")}
    </div>
    <div class="callout ${review.no_go ? "warn" : "gold"}" style="margin-top:22px">
      <div class="ic">${review.no_go ? "▲" : "◆"}</div>
      <div><h4>한 줄 종합 — 등급 ${escapeHtml(review.grade || "미검토")}</h4><p>${escapeHtml(verdictLine)}</p></div>
    </div>
  </div></section>`;
}

function overview(l, b, land) {
  const landArea = b.plat_area_m2 || l.land_area_m2;
  const archArea = b.arch_area_m2 || l.building_area_m2;
  const totalArea = b.total_area_m2 || l.building_area_m2;
  const floors = b.ground_floors || l.floors_total;
  const ug = b.underground_floors;
  const parking = b.parking_spaces ?? l.parking_spaces;
  const ev = b.elevator_count != null ? `${b.elevator_count}대` : (l.elevator === true ? "있음" : l.elevator === false ? "없음" : "-");
  const bcr = b.building_coverage_ratio ?? l.building_coverage_ratio;
  const far = b.floor_area_ratio ?? l.floor_area_ratio;
  const off = land.official_price_per_m2;
  const offTotal = off && landArea ? off * landArea : null;
  const rows1 = [
    ["소재지", escapeHtml(l.location || "-")],
    ["용도지역", `<b>${escapeHtml(zoningText(l, land))}</b>`],
    ["대지면적", m2py(landArea)],
    ["건축면적", m2py(archArea)],
    ["연면적", m2py(totalArea)],
    ["규모", floors ? `지상 ${floors}층${ug ? ` / 지하 ${ug}층` : ""}` : "-"],
  ];
  const rows2 = [
    ["준공연도", b.approval_year ? `${b.approval_year}년${b.approval_year ? ` (약 ${2026 - b.approval_year}년)` : ""}` : (l.approval_year ? `${l.approval_year}년` : "-")],
    ["주차 / 승강기", `${parking != null ? `${parking}대` : "-"} · ${ev}`],
    ["건폐율 / 용적률", `${bcr != null ? `${bcr}%` : "-"} / ${far != null ? `${far}%` : "-"}`],
    ["주용도", escapeHtml(b.main_purpose || l.main_purpose || "-")],
    ["도로 접면", escapeHtml(land.road_side || l.road_access || "-")],
    ["공시지가", off ? `평당 ${manPyeong(off)}${offTotal ? ` / 합계 약 ${eok(offTotal)}` : ""}` : "-"],
  ];
  const tbl = (rows) => `<table class="spec-table">${rows.map(([k, v]) => `<tr><td class="lab">${escapeHtml(k)}</td><td>${v}</td></tr>`).join("")}</table>`;
  return `
  <section><div class="wrap">
    <div class="sec-tag">Property Overview</div>
    <h2 class="sec">물건 제원</h2>
    <p class="lead">건축물대장·토지정보(공공데이터) 기준 제원입니다. 빈 값은 자동 검증으로 채워지지 않은 항목입니다.</p>
    <div class="spec-grid" style="margin-top:28px">${tbl(rows1)}${tbl(rows2)}</div>
  </div></section>`;
}

function locationMedical(l, land, med) {
  const orthoNames = (med.ortho_clinic_names || []).slice(0, 6).join(", ");
  const cards = [
    `<div class="card"><h3>① 용도·입지</h3><p style="font-size:.88rem;color:var(--muted);margin-top:6px">
      용도지역 <b style="color:var(--navy)">${escapeHtml(primaryZoning(l, land))}</b>.
      ${land.road_side ? `도로 접면 ${escapeHtml(land.road_side)}${land.road_width_hint_m ? ` (약 ${land.road_width_hint_m}m급)` : ""}.` : "도로 접면 정보 확인 필요."}
      의원·병원 개설 가능 용도지역인지, 현재 주용도(${escapeHtml(land.main_purpose || "")})에서 용도변경 필요 여부를 확인하세요.</p></div>`,
    `<div class="card"><h3>② 경쟁 의원</h3><p style="font-size:.88rem;color:var(--muted);margin-top:6px">
      ${med.ortho_clinic_count != null
        ? `같은 동 <b style="color:var(--navy)">정형외과 전문의원 ${med.ortho_clinic_count}곳</b>${med.ortho_treating_count ? ` (정형외과 진료 의원 ${med.ortho_treating_count}곳)` : ""}.${orthoNames ? `<br>${escapeHtml(orthoNames)} 등.` : ""}`
        : "심평원 병원정보 데이터가 없습니다 — 활용신청·키 설정 또는 네이버지도로 직접 확인하세요."}</p></div>`,
    `<div class="card"><h3>③ 약국 연계</h3><p style="font-size:.88rem;color:var(--muted);margin-top:6px">
      ${med.pharmacy_count != null
        ? `같은 동 <b style="color:var(--navy)">약국 ${med.pharmacy_count}곳</b> — 처방 연계 가능.`
        : "심평원 약국정보 데이터가 없습니다 — 활용신청·키 설정 후 자동 채워집니다."}</p></div>`,
  ].join("");
  return `
  <section><div class="wrap">
    <div class="sec-tag">Location &amp; Medical</div>
    <h2 class="sec">입지 · 의료 환경</h2>
    <p class="lead">병원(정형외과) 개원 관점의 입지 — 용도·도로 조건과 같은 동 의료기관 밀집도입니다.</p>
    <div class="grid g3" style="margin-top:28px">${cards}</div>
  </div></section>`;
}

const ASSUMED_CAP = 0.045; // 임대 정보가 없을 때 가정하는 표면수익률(환원율)
function zoningInfo(l, land) {
  const far0 = l.floor_area_ratio || (land && land.floor_area_ratio);
  const bcr0 = l.building_coverage_ratio || (land && land.building_coverage_ratio);
  const names = (((land && land.zoning_names) || []).join(" ") + " " + (l.zoning || ""));
  const TBL = [["중심상업", 1000, 60], ["일반상업", 800, 60], ["근린상업", 600, 60], ["유통상업", 600, 60],
    ["준주거", 400, 60], ["제3종일반주거", 250, 50], ["제2종일반주거", 200, 60], ["제1종일반주거", 150, 60], ["준공업", 400, 60]];
  let std = null;
  for (const [k, f, c] of TBL) if (names.includes(k)) { std = [k, f, c]; break; }
  return { far: far0 || (std && std[1]) || null, bcr: bcr0 || (std && std[2]) || 60,
    label: std ? std[0] : (l.zoning || "용도지역"), fromStd: !far0 };
}

function priceSection(l, b, market) {
  const price = priceOf(l);
  const totalArea = b.total_area_m2 || l.building_area_m2;
  const perM2 = price && totalArea ? price / totalArea : null;
  if (!market.avg_price_per_m2) {
    return `
    <section><div class="wrap"><div class="sec-tag">Price &amp; Market</div><h2 class="sec">가격 · 시세 비교</h2>
      <div style="margin-top:24px" class="callout warn"><div class="ic">ℹ️</div><div><h4>주변 실거래 데이터 없음</h4>
      <p>국토부 실거래 자동 조회 결과가 없습니다(해당 지역 미지원이거나 거래 부족). 관리자에게 법정동코드 추가를 요청하거나 키를 확인하세요.</p></div></div>
    </div></section>`;
  }
  const trades = (market.recent_trades || []).slice()
    .sort((a, bb) => String(bb.deal_date || "").localeCompare(String(a.deal_date || "")));
  const vals = [
    { nm: "주변 최고", small: "최근 실거래", v: market.max_price_per_m2 },
    { nm: "주변 평균", small: `최근 ${market.trade_count || ""}건`, v: market.avg_price_per_m2 },
    { nm: "주변 최저", small: "최근 실거래", v: market.min_price_per_m2 },
    { nm: "본 매물", small: priceLabel(l), v: perM2, me: true },
  ].filter((x) => x.v);
  const max = Math.max(...vals.map((x) => x.v));
  const bars = `<div class="card"><div class="cmp">${vals.map((x) => `
    <div class="cmp-row${x.me ? " me" : ""}"><div class="top">
      <div class="nm">${x.nm} <small>${escapeHtml(x.small)}</small></div><div class="val">${manM2(x.v)}/㎡</div></div>
    <div class="track"><div class="fill" style="width:${Math.max(12, Math.round((x.v / max) * 100))}%">${manM2(x.v)}</div></div></div>`).join("")}</div></div>`;
  const diff = (base) => perM2 && base ? Math.round((perM2 / base - 1) * 100) : null;
  const metric = (lab, base) => {
    const d = diff(base);
    const color = d == null ? "" : d > 0 ? "var(--neg)" : "var(--pos)";
    return `<div class="metric"><div class="accent-bar"></div><div class="lab">${lab}</div>
      <div class="num" style="color:${color}">${d == null ? "-" : (d > 0 ? "+" : "") + d}<small>%</small></div>
      <div class="note">주변 ${manM2(base)}/㎡ 대비</div></div>`;
  };
  const withPrice = trades.filter((t) => t.price_per_building_m2);
  const below = perM2 ? withPrice.filter((t) => t.price_per_building_m2 < perM2).length : 0;
  const pctile = withPrice.length ? Math.round((below / withPrice.length) * 100) : null;
  const posLabel = pctile == null ? "" : pctile <= 33 ? "시세 하단(저평가 구간)" : pctile <= 66 ? "시세 중단" : "시세 상단";
  const tbl = trades.length ? `
    <h3 style="margin:32px 0 14px;font-size:1.05rem;color:var(--navy);font-weight:700">최근 실거래 전수 <span style="font-weight:500;color:var(--muted);font-size:.85rem">[국토부 OpenAPI · ${trades.length}건]</span></h3>
    <div class="dt"><table>
      <thead><tr><th>거래시점</th><th>용도</th><th>거래액</th><th>건물 ㎡당</th><th>건물 평당</th><th>준공</th></tr></thead>
      <tbody>
        ${trades.slice(0, 14).map((t) => `<tr>
          <td>${escapeHtml((t.deal_date || "").slice(0, 7))}</td>
          <td style="text-align:right;color:var(--muted)">${escapeHtml(t.building_use || "-")}</td>
          <td>${eok(t.deal_amount_won)}</td>
          <td>${manM2(t.price_per_building_m2)}</td>
          <td>${manPyeong(t.price_per_building_m2)}</td>
          <td style="text-align:right;color:var(--muted)">${escapeHtml(String(t.build_year || "-"))}</td></tr>`).join("")}
        ${perM2 ? `<tr class="me"><td>본 매물</td><td style="text-align:right">${escapeHtml(priceLabel(l))}</td><td>${eok(price)}</td><td><b>${manM2(perM2)}</b></td><td><b>${manPyeong(perM2)}</b></td><td style="text-align:right">${escapeHtml(String(b.approval_year || l.approval_year || "-"))}</td></tr>` : ""}
      </tbody>
    </table></div>` : "";
  return `
  <section><div class="wrap">
    <div class="sec-tag">Price &amp; Market</div>
    <h2 class="sec">가격 · 시세 비교</h2>
    <p class="lead">국토교통부 실거래가(상업·업무용)를 직접 조회해 본 매물의 건물 ㎡당 가격을 주변과 비교합니다.</p>
    <div style="margin-top:28px">${bars}</div>
    ${perM2 ? `<div class="grid g3" style="margin-top:20px">${metric("vs 주변 평균", market.avg_price_per_m2)}${metric("vs 주변 최저", market.min_price_per_m2)}${metric("vs 주변 최고", market.max_price_per_m2)}</div>` : ""}
    ${pctile != null ? `<div class="callout ${pctile <= 50 ? "gold" : "warn"}" style="margin-top:20px"><div class="ic">${pctile <= 50 ? "◆" : "▲"}</div>
      <div><h4>시세 포지션 — ${escapeHtml(posLabel)}</h4><p>본 매물 건물 ㎡당 ${manM2(perM2)}은 최근 실거래 ${withPrice.length}건 중 <b>하위 ${pctile}% 수준</b>입니다. ${pctile <= 33 ? "동급 대비 저가 매입 여지가 있으나, 노후도·용도 차이를 함께 보세요." : pctile >= 67 ? "주변 대비 높은 편이라 협상 여지·근거를 확인하세요." : "주변 시세 중간 수준입니다."}</p></div></div>` : ""}
    ${tbl}
    <p class="note-inline">※ 건물 연면적 ㎡당 단가 기준입니다. 토지가치(평당)는 다음 섹션을 참고하세요. 집합건물(호실)은 동 전체 면적이 잡힐 수 있습니다.</p>
  </div></section>`;
}

function landValueSection(l, b, land, market) {
  const off = land.official_price_per_m2;
  const landArea = b.plat_area_m2 || l.land_area_m2;
  if (!off && !landArea) return "";
  const price = priceOf(l);
  const landPy = landArea ? landArea * PY : null;
  const landPerPy = price && landPy ? price / landPy : null;       // 토지 평당가(매물가 기준)
  const offTotal = off && landArea ? off * landArea : null;
  const multiple = price && offTotal ? price / offTotal : null;
  const metrics = [
    { lab: "토지 평당가 (매물가 기준)", num: landPerPy ? nf.format(Math.round(landPerPy / 1e4)) : "-", unit: "만원", note: landPy ? `대지 ${landPy.toFixed(1)}평 기준` : "대지면적 확인 필요" },
    { lab: "개별공시지가", num: off ? nf.format(Math.round((off / PY) / 1e4)) : "-", unit: "만원/평", note: land.official_price_year ? `${land.official_price_year}년${offTotal ? ` · 합계 ${eok(offTotal)}` : ""}` : "" },
    { lab: "공시지가 대비 매물가", num: multiple ? multiple.toFixed(2) : "-", unit: "배", note: multiple ? (multiple < 2 ? "상업지로서 낮은 배수 — 저평가 시그널" : "공시지가 대비 통상 수준") : "공시지가·대지면적 확인 필요" },
  ];
  const note = (landPerPy && market.avg_price_per_m2)
    ? `토지 평당 약 ${nf.format(Math.round(landPerPy / 1e4))}만원으로, 건물면적당 시세와는 별개로 토지가치 관점의 비교가 필요합니다.`
    : "토지 평당가는 매물가를 토지면적으로 나눈 근사치입니다(건물값 포함). 철거·신축 전제면 토지가치 관점이 더 적합합니다.";
  return `
  <section><div class="wrap">
    <div class="sec-tag">Land Value</div>
    <h2 class="sec">공시지가 · 토지가치 분석</h2>
    <p class="lead">개별공시지가와 토지면적으로 본 매물의 토지가치 포지션을 봅니다 (철거·신축 검토 시 핵심 잣대).</p>
    <div class="grid g3" style="margin-top:28px">
      ${metrics.map((m) => `<div class="metric"><div class="accent-bar"></div><div class="lab">${escapeHtml(m.lab)}</div>
        <div class="num">${escapeHtml(m.num)}<small>${escapeHtml(m.unit)}</small></div><div class="note">${escapeHtml(m.note)}</div></div>`).join("")}
    </div>
    <div class="callout gold" style="margin-top:20px"><div class="ic">◆</div><div><h4>토지가치 관점</h4><p>${escapeHtml(note)}</p></div></div>
  </div></section>`;
}

function financingScenarios(l) {
  const price = priceOf(l);
  if (!price) return "";
  const acq = price * 0.046, brokerage = price * 0.009;
  const scen = (ltv) => { const loan = Math.round(price * ltv); return { ltv, loan, cash: price - loan + acq + brokerage }; };
  const A = scen(0.5), B = scen(0.7);
  const tbl = (s, name) => `<div class="card"><h3>${name} (LTV ${Math.round(s.ltv * 100)}%)</h3>
    <table class="spec-table" style="margin-top:12px;box-shadow:none;border:1px solid var(--line)">
      <tr><td class="lab">매입가</td><td>${eok(price)}</td></tr>
      <tr><td class="lab">취득세(4.6%)</td><td>+ ${eok(acq)}</td></tr>
      <tr><td class="lab">중개보수(0.9%)</td><td>+ ${eok(brokerage)}</td></tr>
      <tr><td class="lab">대출</td><td>− ${eok(s.loan)}</td></tr>
      <tr><td class="lab">필요 현금</td><td><b style="color:var(--gold)">약 ${eok(s.cash)}</b></td></tr>
    </table></div>`;
  const noi = price * ASSUMED_CAP;
  const rates = [3.5, 4.0, 4.5, 5.0, 5.5];
  const coc = (s, rate) => (noi - s.loan * rate / 100) / s.cash * 100;
  const cell = (v) => `<b style="color:${v >= 5 ? "var(--pos)" : v >= 3 ? "var(--navy)" : "var(--neg)"}">${v.toFixed(1)}%</b>`;
  const sens = `<div class="dt" style="margin-top:14px"><table>
    <thead><tr><th>대출 금리</th><th>시나리오 A · LTV 50%</th><th>시나리오 B · LTV 70%</th></tr></thead>
    <tbody>${rates.map((r) => `<tr><td>${r.toFixed(1)}%</td><td>${cell(coc(A, r))}</td><td>${cell(coc(B, r))}</td></tr>`).join("")}</tbody></table></div>`;
  const caps = [4.0, 4.5, 5.0];
  const exitTbl = `<div class="dt" style="margin-top:14px"><table>
    <thead><tr><th>환원율(Cap)</th><th>가정 안정화 연임대</th><th>예상 매도가</th><th>매입가 대비</th></tr></thead>
    <tbody>${caps.map((c) => { const v = noi / (c / 100); const g = v - price;
      return `<tr><td>${c.toFixed(1)}%</td><td>${eok(noi)}</td><td><b>${eok(v)}</b></td><td style="color:${g >= 0 ? "var(--pos)" : "var(--neg)"}">${g >= 0 ? "+" : ""}${eok(g)}</td></tr>`; }).join("")}</tbody></table></div>`;
  return `
  <section><div class="wrap">
    <div class="sec-tag">Financing &amp; Yield</div>
    <h2 class="sec">자금조달 · 수익 시나리오 <span style="font-weight:500;color:var(--muted);font-size:.9rem">(모델 산출)</span></h2>
    <p class="lead">취득세 4.6%·중개 0.9% 가정. 임대 정보가 없어 <b>표면수익률 ${(ASSUMED_CAP * 100).toFixed(1)}% 가정</b>으로 NOI를 역산한 모델입니다 — 실제 임대료·담보감정·금리로 재계산이 필요합니다.</p>
    <div class="grid g2" style="margin-top:26px">${tbl(A, "시나리오 A")}${tbl(B, "시나리오 B")}</div>
    <h3 style="margin:30px 0 6px;font-size:1.05rem;color:var(--navy);font-weight:700">금리별 자기자본 수익률(현금배당) 민감도</h3>
    <p class="note-inline" style="margin-bottom:6px">현금배당 = (가정 NOI ${eok(noi)} − 대출이자) ÷ 필요현금. 금리가 가정수익률(${(ASSUMED_CAP * 100).toFixed(1)}%)보다 낮을 때만 레버리지가 유리합니다.</p>
    ${sens}
    <h3 style="margin:28px 0 6px;font-size:1.05rem;color:var(--navy);font-weight:700">환원율별 예상 매도가 (Exit)</h3>
    <p class="note-inline" style="margin-bottom:6px">직접환원법: 매도가 = 안정화 연임대 ÷ Cap. 안정화 임대·Cap 가정값이며 리모델링비·세금·공실은 별도입니다.</p>
    ${exitTbl}
    <div class="callout warn" style="margin-top:18px"><div class="ic">⚖</div><div><h4>모델 한계</h4>
      <p>수익률·매도가는 <b>가정 표면수익률 ${(ASSUMED_CAP * 100).toFixed(1)}%</b>에 따른 산출값으로, 실제 임대료가 반영되지 않았습니다. 임대차계약서·시장 임대 시세로 NOI를 확정한 뒤 재계산하세요.</p></div></div>
  </div></section>`;
}

function newBuildSection(l, b, land) {
  const landArea = b.plat_area_m2 || l.land_area_m2;
  const zi = zoningInfo(l, land);
  if (!landArea || !zi.far) return "";
  const archArea = landArea * (zi.bcr / 100);
  const steps = [Math.round((zi.far * 0.7) / 50) * 50, Math.round((zi.far * 0.85) / 50) * 50, zi.far]
    .filter((v, i, a) => v > 0 && a.indexOf(v) === i);
  const rows = steps.map((far) => {
    const gfa = landArea * far / 100;
    const floors = Math.max(1, Math.round(gfa / archArea));
    const units = Math.round((gfa * 0.7) / 40);
    const parking = Math.round(units * 0.5);
    return { far, gfa, floors, units, parking, top: far === zi.far };
  });
  return `
  <section><div class="wrap">
    <div class="sec-tag">New-Build Feasibility</div>
    <h2 class="sec">신축 가설계 (개략)</h2>
    <p class="lead">대지면적 ${landArea.toFixed(1)}㎡(${(landArea * PY).toFixed(1)}평)에 <b>${escapeHtml(zi.label)}</b> 기준 건폐율 ${zi.bcr}%·용적률 ${zi.far}%${zi.fromStd ? "(용도지역 표준 가정)" : "(대장값)"}를 단순 적용한 <b>개략 규모 추정</b>입니다.</p>
    <div class="dt" style="margin-top:26px"><table>
      <thead><tr><th>용적률</th><th>지상 연면적</th><th>추정 지상층수</th><th>추정 세대수(원룸형)</th><th>필요 주차(0.5대/실)</th></tr></thead>
      <tbody>${rows.map((r) => `<tr class="${r.top ? "me" : ""}"><td>${r.far}%</td>
        <td>약 ${Math.round(r.gfa)}㎡ (${Math.round(r.gfa * PY)}평)</td>
        <td>약 ${r.floors}층</td><td>${r.top ? `<b>약 ${r.units}세대</b>` : `약 ${r.units}세대`}</td><td>약 ${r.parking}대</td></tr>`).join("")}</tbody>
    </table></div>
    <p class="note-inline">※ 1층 근생 + 상층부 도시형생활주택 가정, 호당 계약면적 약 40㎡(전용률 50%)·주차 0.5대/실 기준. 지하층 별도.</p>
    <div class="callout warn" style="margin-top:18px"><div class="ic">▲</div><div><h4>반드시 선행되어야 할 검토</h4>
      <p><b>건축사 정식 가설계</b>(일조·정북·도로사선·주차장법·지구단위계획)가 필수입니다. 실제 용적률은 도로폭·지구단위로 차등 적용되며, 명도·철거비·건축비·금융비·사업기간이 별도로 듭니다. 본 수치는 용적률 단순 적용 개략치입니다.</p></div></div>
  </div></section>`;
}

function verification(review) {
  const items = review.items || [];
  const auto = items.filter((i) => i.kind === "auto" || i.kind === "info");
  const ev = auto.filter((i) => i.evidence);
  const counts = { pass: 0, warn: 0, fail: 0, unknown: 0, info: 0 };
  auto.forEach((i) => { counts[i.status] = (counts[i.status] || 0) + 1; });
  const kpis = `
    <div class="grid g4" style="margin-top:6px">
      <div class="metric"><div class="lab">종합 등급</div><div class="num">${escapeHtml(review.grade || "—")}</div><div class="note">치명 항목 부적합 시 즉시 부적합</div></div>
      <div class="metric"><div class="lab">점수</div><div class="num">${review.score != null ? review.score : "—"}<small>점</small></div><div class="note">판정 항목 가중 평균</div></div>
      <div class="metric"><div class="lab">자동 판정</div><div class="num">${counts.pass}<small> 적합</small></div><div class="note">경고 ${counts.warn} · 부적합 ${counts.fail} · 미확인 ${counts.unknown}</div></div>
      <div class="metric"><div class="lab">진행</div><div class="num">${review.progress?.auto_done ?? 0}/${review.progress?.auto_total ?? 0}</div><div class="note">수동 ${review.progress?.manual_done ?? 0}/${review.progress?.manual_total ?? 0}</div></div>
    </div>`;
  const cards = ev.map((i) => {
    const [label, cls] = i.kind === "info" ? ["정보", "b-neu"] : (STATUS[i.status] || STATUS.unknown);
    const manual = i.source === "manual" ? `<span class="src-badge">제공 자료</span>` : "";
    return `<div class="ev-card${i.source === "manual" ? " manual" : ""}">
      <div class="ev-head"><strong>${escapeHtml(i.label)}</strong><span class="ev-pills">${manual}<span class="badge ${cls}">${label}</span></span></div>
      <p>${escapeHtml(i.evidence)}</p></div>`;
  }).join("");
  const actions = [];
  items.filter((i) => i.critical && (i.status === "fail")).forEach((i) => actions.push(`치명 부적합 — ${i.label}: ${i.evidence || i.description}`));
  items.filter((i) => i.status === "warn" || (i.status === "fail" && !i.critical)).forEach((i) => actions.push(`보완 확인 — ${i.label}: ${i.evidence || ""}`));
  items.filter((i) => i.kind === "auto" && i.status === "unknown").slice(0, 1).forEach(() => {
    const names = items.filter((i) => i.kind === "auto" && i.status === "unknown").map((i) => i.label).join(", ");
    if (names) actions.push(`공공데이터로 못 채운 항목 직접 확인: ${names}`);
  });
  if (!actions.length) actions.push("자동 검증 기준 큰 결격 없음 — 현장 실사·등기·자금 조건 확정 단계로 진행");
  return `
  <section><div class="wrap">
    <div class="sec-tag">Public-Data Verification</div>
    <h2 class="sec">공공데이터 자동 검증</h2>
    <p class="lead">건축물대장·토지·실거래·심평원 데이터로 병원 입지 체크리스트를 자동 판정한 근거입니다. ‘제공 자료’ 배지는 수동 입력 값입니다.</p>
    ${kpis}
    <h3 style="margin:30px 0 14px;font-size:1.05rem;color:var(--navy);font-weight:700">자동 검증 근거</h3>
    <div class="ev-grid">${cards || '<div class="ev-card"><p>자동 검증 근거가 없습니다. 매물장에서 ‘자동 검증 실행’ 후 다시 생성하세요.</p></div>'}</div>
    <h3 style="margin:30px 0 14px;font-size:1.05rem;color:var(--navy);font-weight:700">추천 액션</h3>
    <div class="dt"><table><tbody>${actions.slice(0, 8).map((a) => `<tr><td style="text-align:left">${escapeHtml(a)}</td></tr>`).join("")}</tbody></table></div>
  </div></section>`;
}

function swot(l, b, review, med) {
  const items = review.items || [];
  const strengths = items.filter((i) => i.status === "pass" && i.evidence).map((i) => `${i.label} — ${shorten(i.evidence)}`);
  const weaknesses = items.filter((i) => (i.status === "fail" || i.status === "warn") && i.evidence).map((i) => `${i.label} — ${shorten(i.evidence)}`);
  const opp = [];
  if ((b.floor_area_ratio || 0) === 0 || String(primaryZoningName(l)).includes("상업")) opp.push("용적률 높은 상업지역 — 임대 정상화·리모델링·신축 전환 여지");
  if (med.ortho_clinic_count === 0) opp.push("같은 동 정형외과 공백 — 선점 기회");
  if (med.pharmacy_count > 0) opp.push("주변 약국 다수 — 처방 연계 용이");
  opp.push("공실 해소·인테리어로 병원 동선 최적화 시 가치 상승");
  const threats = [];
  if (b.approval_year && 2026 - b.approval_year >= 30) threats.push(`${b.approval_year}년 노후 건물 — 유지보수·리모델링 비용`);
  if (med.ortho_treating_count >= 3) threats.push(`정형외과 진료 의원 ${med.ortho_treating_count}곳 — 경쟁 밀집`);
  threats.push("금리 상승 시 레버리지 부담 / 시세 조정 가능성");
  const block = (cls, t, title, list, empty) => `
    <div class="q ${cls}"><h4><span class="t">${t}</span> ${title}</h4>
    <ul>${(list.length ? list : [empty]).slice(0, 6).map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>`;
  return `
  <section><div class="wrap">
    <div class="sec-tag">SWOT</div>
    <h2 class="sec">강점 · 약점 · 기회 · 위협</h2>
    <p class="lead">자동 검증 결과에서 도출한 요약입니다 (강점=적합 / 약점=경고·부적합 항목 기반).</p>
    <div class="swot" style="margin-top:28px">
      ${block("s", "S", "강점", strengths, "적합 판정 항목이 아직 없습니다")}
      ${block("w", "W", "약점", weaknesses, "경고·부적합 항목 없음")}
      ${block("o", "O", "기회", opp, "")}
      ${block("tt", "T", "위협", threats, "")}
    </div>
  </div></section>`;
}
function primaryZoningName(l) { return l.zoning || ""; }
function shorten(s) { s = String(s || ""); return s.length > 46 ? s.slice(0, 44) + "…" : s; }

function conclusion(l, review) {
  const manualItems = (review.items || []).filter((i) => i.kind === "manual");
  const checks = manualItems.length ? manualItems.slice(0, 8).map((i) => i.label)
    : ["등기부등본 — 권리관계·근저당 확인", "건축물대장 — 위반건축물·면적 일치", "토지이용계획 — 용적률·지구단위 확인",
       "임대차계약 — 보증금·만기·명도 조건", "현장 실사 — 누수·균열·설비 노후", "용도변경·주차 추가 확보 가능 여부",
       "담보감정가·LTV·금리 확정", "장비(MRI 등) 하중·반입 동선"];
  const line = review.no_go
    ? "치명 항목에서 부적합이 확인되어, 현 상태로는 병원 용도 진입에 큰 제약이 있는 물건입니다. 부적합 항목 해소 가능성을 먼저 검토하세요."
    : (review.grade === "A" || review.grade === "B")
      ? "공공데이터 자동 검증 기준으로 병원 입지 적합도가 양호합니다. 아래 실사 항목을 확정하면 본격 검토 단계로 진행할 수 있습니다."
      : "공공데이터 자동 검증에서 일부 보완·확인이 필요한 물건입니다. 경고·미확인 항목을 점검한 뒤 판단하세요.";
  // 카테고리별 가중 점수
  const EARN = { pass: 1, warn: 0.5, fail: 0 };
  const cat = new Map();
  (review.items || []).forEach((i) => {
    if (!(i.status in EARN)) return;
    const c = cat.get(i.category) || { earned: 0, possible: 0 };
    c.earned += EARN[i.status] * (i.weight || 1);
    c.possible += (i.weight || 1);
    cat.set(i.category, c);
  });
  const catBars = [...cat.entries()].map(([name, c]) => {
    const pct = c.possible > 0 ? Math.round((c.earned / c.possible) * 100) : 0;
    const fill = pct >= 85 ? "var(--pos)" : pct >= 50 ? "var(--gold)" : "var(--neg)";
    return `<div class="cmp-row"><div class="top"><div class="nm">${escapeHtml(name)}</div><div class="val">${pct}%</div></div>
      <div class="track"><div class="fill" style="width:${Math.max(8, pct)}%;background:${fill}">${pct}%</div></div></div>`;
  }).join("");
  return `
  <section><div class="wrap">
    <div class="sec-tag">Conclusion</div>
    <h2 class="sec">종합 의견</h2>
    <div class="verdict" style="margin-top:26px">
      <h3><span class="grade-big">${escapeHtml(review.grade || "미검토")}</span>병원 입지 자동 검증 종합</h3>
      <p>${escapeHtml(line)}</p>
    </div>
    ${catBars ? `<h3 style="margin:32px 0 14px;font-size:1.05rem;color:var(--navy);font-weight:700">카테고리별 검증 점수</h3>
      <div class="card"><div class="cmp">${catBars}</div></div>` : ""}
    <h3 style="margin:32px 0 14px;font-size:1.05rem;color:var(--navy);font-weight:700">계약 전 실사 체크리스트</h3>
    <div class="check">${checks.map((c) => `<div class="ci"><div class="box"></div>${escapeHtml(c)}</div>`).join("")}</div>
  </div></section>`;
}

function footer(d, l) {
  const errs = Object.keys(d.errors || {});
  return `
  <footer><div class="wrap">
    <div class="src"><h4>데이터 출처</h4>
      <ul>
        <li>국토교통부 건축HUB 건축물대장 (data.go.kr)</li>
        <li>국토교통부 상업·업무용 실거래가 OpenAPI (data.go.kr)</li>
        <li>건강보험심사평가원 병원·약국 정보서비스 (data.go.kr)</li>
        <li>브이월드 토지이용계획·개별공시지가 (vworld.kr)</li>
      </ul>
      ${errs.length ? `<p class="note-inline" style="color:var(--muted-2)">자동 조회 실패: ${escapeHtml(errs.join(", "))} — 해당 항목은 키 발급·지역 지원 후 채워집니다.</p>` : ""}
    </div>
    <div class="disc">※ 본 리포트는 공공데이터를 자동 조회해 <b>투자 검토 목적</b>으로 생성한 참고자료입니다. 면적·준공일·시세·감정가 등 일부 수치는 추정치를 포함하며 자료 간 차이가 있을 수 있습니다. 실제 매입 의사결정은 반드시 <b>등기부등본·건축물대장·토지이용계획·현장 실사·금융기관 대출조건 확정</b> 후 진행하세요. 자금조달·SWOT·종합 의견은 자동 산출·요약값으로 투자 권유나 수익 보장을 의미하지 않습니다.</div>
    <div class="meta"><span>${escapeHtml(l.title || "매물")} · 병원 입지 검토 리포트</span><span>생성일 ${escapeHtml(d.generated_at || "")} · ${escapeHtml(l.location || "")}</span></div>
  </div></footer>`;
}

/* ===== HTML 다운로드 (자체 포함 파일) ===== */
function downloadHtml(d) {
  const css = document.querySelector('link[href="report.css"]');
  let cssText = "";
  try { cssText = [...document.styleSheets].filter((s) => (s.href || "").includes("report.css"))
    .flatMap((s) => [...s.cssRules].map((r) => r.cssText)).join("\n"); } catch { /* CORS */ }
  const title = `${(d.listing.title || "매물").replace(/[\\/:*?"<>|]/g, "_")}_리포트_${d.generated_at || ""}`;
  const doc = `<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>${cssText}</style></head><body>${els.root.innerHTML}</body></html>`;
  const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${title}.html`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

init();
