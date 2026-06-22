/* 수동 검증 입력 페이지 — 미확인 자동검증 카드를 제공 자료 근거로 채운다.
 * 대시보드(app.js)가 localStorage(rea210:verifyTarget)에 {identity, listing, profile}을
 * 넣고 verify.html?identity=... 로 연다. 이 페이지는 서버 API에만 의존한다. */

const VERIFY_TARGET_KEY = "rea210:verifyTarget";
const STATUS_OPTIONS = [
  ["pass", "적합"],
  ["warn", "경고"],
  ["fail", "부적합"],
  ["info", "정보"],
  ["unknown", "미확인"],
];
const HIRA_SIGNUP_URL = "https://www.data.go.kr/data/15001698/openapi.do";

const els = {
  subtitle: document.querySelector("#verifySubtitle"),
  alert: document.querySelector("#verifyAlert"),
  cardList: document.querySelector("#cardList"),
  suggestButton: document.querySelector("#suggestButton"),
  suggestNote: document.querySelector("#suggestNote"),
  saveButton: document.querySelector("#saveButton"),
  saveNote: document.querySelector("#saveNote"),
  medicalNotice: document.querySelector("#medicalNotice"),
};

const page = {
  identity: "",
  listing: {},
  profile: "building",
  items: [], // 이 프로필에서 수동 입력 가능한 auto·info 항목 정의
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function apiJson(path, options) {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new Error(`API ${path} 실패: ${response.status}`);
  }
  return response.json();
}

function postJson(path, payload) {
  return apiJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function getParam(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function loadTarget(identity) {
  try {
    const raw = localStorage.getItem(VERIFY_TARGET_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.identity === identity) return parsed;
  } catch {
    /* 무시 — 핸드오프 없이도 동작 */
  }
  return null;
}

function showAlert(message) {
  els.alert.textContent = message;
  els.alert.hidden = false;
}

function numVal(id) {
  const raw = document.querySelector(`#${id}`).value.trim();
  if (raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function textVal(id) {
  return document.querySelector(`#${id}`).value.trim();
}

/* ===== 초기화 ===== */

async function init() {
  page.identity = getParam("identity").trim();
  if (!page.identity) {
    showAlert("매물 식별자(identity)가 없습니다. 매물장의 검토 화면에서 ‘미확인 직접 채우기’로 다시 열어주세요.");
    return;
  }
  const target = loadTarget(page.identity);
  if (target) {
    page.listing = target.listing || {};
    page.profile = target.profile || page.profile;
  }

  let definition;
  try {
    definition = await apiJson("/api/checklist/definition");
  } catch {
    showAlert("서버에 연결할 수 없습니다. serve-web으로 대시보드를 실행한 상태에서 이용해주세요.");
    return;
  }

  let review = null;
  try {
    const payload = await apiJson(
      `/api/checklist/review?identity=${encodeURIComponent(page.identity)}`,
    );
    review = payload.review;
    if (review && review.profile) page.profile = review.profile;
  } catch {
    /* 저장된 검토가 없으면 빈 상태로 시작 */
  }

  const title = page.listing.title || page.identity;
  const location = page.listing.location || "주소 미상";
  els.subtitle.textContent = `${title} · ${location} · 검토 유형: ${profileLabel(definition, page.profile)}`;

  page.items = (definition.items || []).filter(
    (item) =>
      (item.kind === "auto" || item.kind === "info") &&
      (item.profiles || []).includes(page.profile),
  );

  prefillFacts(page.listing);
  renderCards(review);

  els.suggestButton.addEventListener("click", onSuggest);
  els.saveButton.addEventListener("click", onSave);
}

function profileLabel(definition, profile) {
  return (definition.profiles && definition.profiles[profile]) || profile;
}

function prefillFacts(listing) {
  const set = (id, value) => {
    if (value !== undefined && value !== null && value !== "") {
      document.querySelector(`#${id}`).value = value;
    }
  };
  set("factZoning", listing.zoning);
  set("factYear", listing.approval_year);
  set("factArea", listing.building_area_m2);
  set("factLand", listing.land_area_m2);
  set("factFloors", listing.floors_total);
  set("factParking", listing.parking_spaces);
  set("factPurpose", listing.main_purpose);
  if (listing.elevator === true) document.querySelector("#factElevator").value = "true";
  else if (listing.elevator === false) document.querySelector("#factElevator").value = "false";
  if (listing.monthly_rent === 0 || listing.monthly_rent == null) {
    if (typeof listing.deposit === "number" && listing.deposit > 0) {
      document.querySelector("#factPrice").value = (listing.deposit / 1e8).toFixed(1).replace(/\.0$/, "");
    }
  }
}

/* ===== 카드 렌더 ===== */

function renderCards(review) {
  const byId = new Map();
  (review?.items || []).forEach((row) => byId.set(row.item_id, row));

  els.cardList.innerHTML = page.items
    .map((item) => {
      const row = byId.get(item.item_id);
      const status = row?.status || (item.kind === "info" ? "info" : "unknown");
      const evidence = row?.evidence || "";
      const sourceBadge =
        row?.source === "manual"
          ? `<span class="src-badge">제공 자료</span>`
          : "";
      const options = STATUS_OPTIONS.map(
        ([value, label]) =>
          `<option value="${value}"${value === status ? " selected" : ""}>${label}</option>`,
      ).join("");
      return `
        <div class="override-row" data-item="${escapeHtml(item.item_id)}">
          <div class="override-meta">
            <div class="override-title">
              <strong>${escapeHtml(item.label)}</strong>
              <span class="override-cat">${escapeHtml(item.category)}</span>
              ${sourceBadge}
            </div>
            <p class="override-desc">${escapeHtml(item.description)}</p>
          </div>
          <div class="override-inputs">
            <select class="override-status" aria-label="${escapeHtml(item.label)} 상태">${options}</select>
            <textarea class="override-evidence" rows="2"
              placeholder="근거 문구 (예: 일반상업지역 — 의원·병원 허용)">${escapeHtml(evidence)}</textarea>
          </div>
        </div>`;
    })
    .join("");
}

function collectFacts() {
  const facts = {};
  const zoning = textVal("factZoning");
  if (zoning) facts.zoning = zoning;
  const year = numVal("factYear");
  if (year != null) facts.approval_year = year;
  const area = numVal("factArea");
  if (area != null) facts.building_area_m2 = area;
  const land = numVal("factLand");
  if (land != null) facts.land_area_m2 = land;
  const floors = numVal("factFloors");
  if (floors != null) facts.floors_total = floors;
  const parking = numVal("factParking");
  if (parking != null) facts.parking_spaces = parking;
  const elevator = textVal("factElevator");
  if (elevator === "true") facts.elevator = true;
  else if (elevator === "false") facts.elevator = false;
  const purpose = textVal("factPurpose");
  if (purpose) facts.main_purpose = purpose;
  const priceEok = numVal("factPrice");
  if (priceEok != null) {
    facts.deposit = Math.round(priceEok * 1e8);
    facts.monthly_rent = 0;
  }
  return facts;
}

/* ===== 자동 작성 (suggest) ===== */

async function onSuggest() {
  const facts = collectFacts();
  els.suggestButton.disabled = true;
  els.suggestNote.textContent = "공공데이터 조회 중…";
  try {
    const res = await postJson("/api/checklist/suggest", {
      listing: page.listing || {},
      profile: page.profile,
      facts,
    });
    applySuggestion(res.auto || {});
    renderMedicalNotice(res.errors || {});
    const filled = Object.values(res.auto || {}).filter((r) => r && r.status !== "unknown").length;
    els.suggestNote.textContent = `자동 작성 완료 — ${filled}개 항목 채움. 내용을 확인 후 저장하세요.`;
  } catch (error) {
    els.suggestNote.textContent = "자동 작성 실패 — 물건 정보만 입력해 직접 채워주세요.";
  } finally {
    els.suggestButton.disabled = false;
  }
}

function applySuggestion(auto) {
  els.cardList.querySelectorAll(".override-row").forEach((rowEl) => {
    const itemId = rowEl.dataset.item;
    const suggestion = auto[itemId];
    if (!suggestion) return;
    // 미확인 제안은 사용자가 채운 값을 덮어쓰지 않는다 (의원·약국 등)
    if (suggestion.status === "unknown") return;
    rowEl.querySelector(".override-status").value = suggestion.status;
    rowEl.querySelector(".override-evidence").value = suggestion.evidence || "";
  });
}

function renderMedicalNotice(errors) {
  if (!errors.medical) {
    els.medicalNotice.hidden = true;
    return;
  }
  els.medicalNotice.hidden = false;
  els.medicalNotice.innerHTML = `
    <strong>경쟁 의원·약국 자동조회 실패</strong>
    <p>${escapeHtml(errors.medical)}</p>
    <p>data.go.kr에서 <b>‘건강보험심사평가원 병원정보서비스’</b>와 <b>‘약국정보서비스’</b>를 활용신청하고
    <code>DATA_GO_KR_API_KEY</code>를 설정하면 자동으로 채워집니다.
    지금은 네이버지도/심평원에서 직접 확인한 값을 ‘경쟁 의원 분석’·‘약국 연계’ 카드에 입력해 저장하세요.
    <a href="${HIRA_SIGNUP_URL}" target="_blank" rel="noopener">활용신청 바로가기 →</a></p>`;
}

/* ===== 저장 (auto-override) ===== */

async function onSave() {
  const overrides = [];
  els.cardList.querySelectorAll(".override-row").forEach((rowEl) => {
    const itemId = rowEl.dataset.item;
    const status = rowEl.querySelector(".override-status").value;
    const evidence = rowEl.querySelector(".override-evidence").value.trim();
    // 미확인 + 근거 없음 = 수동 입력 해제(자동값으로 복귀)
    if (status === "unknown" && evidence === "") {
      overrides.push({ item_id: itemId, status: "", evidence: "" });
    } else {
      overrides.push({ item_id: itemId, status, evidence });
    }
  });

  els.saveButton.disabled = true;
  els.saveNote.textContent = "저장 중…";
  try {
    const res = await postJson("/api/checklist/auto-override", {
      identity: page.identity,
      profile: page.profile,
      overrides,
    });
    const grade = res.review?.grade ?? "—";
    const score = res.review?.score != null ? `${res.review.score}점` : "—";
    els.saveNote.innerHTML = `저장 완료 — 종합 등급 <b>${escapeHtml(grade)}</b> · ${escapeHtml(score)}. 대시보드의 검토 리포트에 반영됩니다.`;
    renderCards(res.review); // 저장된 source 배지 갱신
  } catch (error) {
    els.saveNote.textContent = "저장 실패 — 다시 시도해주세요.";
  } finally {
    els.saveButton.disabled = false;
  }
}

init();
