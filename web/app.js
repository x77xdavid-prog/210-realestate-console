const sampleListings = [
  {
    source: "manual",
    external_id: "yc-001",
    title: "양천구 목동 병원 가능 근린상가",
    location: "서울 양천구 목동 917-9",
    deposit: 120000000,
    monthly_rent: 5400000,
    area_m2: 118,
    floor: "2층",
    premium: 30000000,
    url: "https://example.test/listings/yc-001",
    registryText: "소유자 홍길동 근저당권 설정",
    property_type: "building",
    land_area_m2: 242,
    building_area_m2: 386,
    floors_total: 5,
    parking_spaces: 4,
    zoning: "제2종일반주거지역",
    road_access: "8m 도로 접함",
    building_coverage_ratio: 52,
    floor_area_ratio: 183,
    approval_year: 2008,
    elevator: true,
    buildable_note: "기존 건물 매입 후 용도변경 및 주차 동선 확인 필요",
    is_new: true,
  },
  {
    source: "manual",
    external_id: "yc-002",
    title: "양천구 신정동 토지 및 건물 매입 후보",
    location: "서울 양천구 신정동 321-6",
    deposit: 0,
    monthly_rent: 0,
    area_m2: 164,
    floor: "토지/건물",
    premium: 0,
    url: "https://example.test/listings/yc-002",
    registryText: "소유자 김철수 특이사항 없음",
    property_type: "land",
    land_area_m2: 331,
    building_area_m2: 0,
    floors_total: null,
    parking_spaces: 0,
    zoning: "준주거지역",
    road_access: "12m 도로 접함",
    building_coverage_ratio: 60,
    floor_area_ratio: 400,
    approval_year: null,
    elevator: null,
    buildable_note: "신축 가능성 검토: 용도지역, 접도, 주차장 설치 기준, 병원 용도 가능 여부 확인",
    is_new: false,
  },
  {
    source: "manual",
    external_id: "yc-003",
    title: "강남구 제외 샘플",
    location: "서울 강남구 역삼동 123-4",
    deposit: 140000000,
    monthly_rent: 5800000,
    area_m2: 105,
    floor: "1층",
    premium: 45000000,
    url: "https://example.test/listings/sample-003",
    registryText: "",
    property_type: "building",
    land_area_m2: 180,
    building_area_m2: 290,
    floors_total: 4,
    parking_spaces: 2,
    zoning: "일반상업지역",
    road_access: "6m 도로 접함",
    building_coverage_ratio: 58,
    floor_area_ratio: 260,
    approval_year: 2011,
    elevator: false,
    buildable_note: "양천구 외 지역이라 현재 검토 대상 제외",
    is_new: false,
  },
];

const riskKeywords = ["근저당권", "압류", "가압류", "전세권", "가처분", "임차권등기"];
const currency = new Intl.NumberFormat("ko-KR");
const pyeongPerSquareMeter = 0.3025;
const LEDGER_STATUSES = ["검토중", "연락 완료", "방문 예정", "협상중", "보류", "계약 검토"];
const LEDGER_TONES = { 보류: "tone-hold", "계약 검토": "tone-done" };
const STORAGE_FAVORITES = "rea210:favorites";
const STORAGE_LEDGER = "rea210:ledger";
const STORAGE_CRITERIA = "rea210:assetCriteria";
const MEMO_SAVE_DELAY_MS = 600;
const FRESH_HOURS = 24;
const CHECKLIST_CATEGORIES = ["입지", "법규", "권리", "물리", "신축", "철거", "재무"];
const MANUAL_CHECK_LABELS = { pass: "적합", fail: "부적합", na: "해당없음" };
const AUTO_STATUS_PILLS = {
  pass: ["적합", "ok"],
  warn: ["경고", "need"],
  fail: ["부적합", "risk"],
  unknown: ["미확인", "neutral"],
  info: ["정보", "neutral"],
};

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(pointer: fine)").matches;

const elements = {
  fetchedCount: document.querySelector("#fetchedCount"),
  matchedCount: document.querySelector("#matchedCount"),
  newCount: document.querySelector("#newCount"),
  favoriteCount: document.querySelector("#favoriteCount"),
  boardGrid: document.querySelector("#boardGrid"),
  regionFilter: document.querySelector("#regionFilter"),
  ledgerRows: document.querySelector("#ledgerRows"),
  ledgerSummary: document.querySelector("#ledgerSummary"),
  priorityList: document.querySelector("#priorityList"),
  scanStatus: document.querySelector("#scanStatus"),
  scanButton: document.querySelector("#scanButton"),
  scanProgress: document.querySelector("#scanProgress"),
  scanProgressTitle: document.querySelector("#scanProgressTitle"),
  scanProgressCount: document.querySelector("#scanProgressCount"),
  scanProgressFill: document.querySelector("#scanProgressFill"),
  scanProgressSources: document.querySelector("#scanProgressSources"),
  estimateGrid: document.querySelector("#estimateGrid"),
  mapAddressInput: document.querySelector("#mapAddressInput"),
  naverMapFrame: document.querySelector("#naverMapFrame"),
  naverMapLink: document.querySelector("#naverMapLink"),
  mapInfoTitle: document.querySelector("#mapInfoTitle"),
  mapInfoDetails: document.querySelector("#mapInfoDetails"),
  assetCriteriaGrid: document.querySelector("#assetCriteriaGrid"),
  criteriaForm: document.querySelector("#criteriaForm"),
  toastStack: document.querySelector("#toastStack"),
  verifyPublicDataButton: document.querySelector("#verifyPublicDataButton"),
  publicDataResult: document.querySelector("#publicDataResult"),
  newBanner: document.querySelector("#newBanner"),
  newBannerTitle: document.querySelector("#newBannerTitle"),
  newBannerSources: document.querySelector("#newBannerSources"),
  checklistModal: document.querySelector("#checklistModal"),
  checklistSubtitle: document.querySelector("#checklistSubtitle"),
  checklistGrade: document.querySelector("#checklistGrade"),
  checklistScore: document.querySelector("#checklistScore"),
  checklistProgress: document.querySelector("#checklistProgress"),
  checklistProfile: document.querySelector("#checklistProfile"),
  checklistSections: document.querySelector("#checklistSections"),
  checklistReport: document.querySelector("#checklistReport"),
  verifyStage: document.querySelector("#verifyStage"),
  verifySteps: document.querySelector("#verifySteps"),
  verifyStamps: document.querySelector("#verifyStamps"),
  manualModal: document.querySelector("#manualModal"),
  manualForm: document.querySelector("#manualForm"),
  docsModal: document.querySelector("#docsModal"),
  docsList: document.querySelector("#docsList"),
  docsSubtitle: document.querySelector("#docsSubtitle"),
};

const state = {
  listings: [],
  unmatched: [],
  stats: null,
  favorites: new Map(),
  ledger: new Map(),
  boardFilter: "all",
  regionFilter: "all",
  hasServer: false,
  selectedListing: null,
  checklist: {
    definition: null,
    reviews: new Map(),
    current: null,
    currentIdentity: null,
    view: "items",
    reportEntrance: false,
  },
  documentCounts: new Map(),
  docsIdentity: null,
};

const defaultFinanceValues = {
  purchasePrice: "5000000000",
  cashAvailable: "2000000000",
  interiorBudget: "500000000",
  taxRate: "0.046",
  brokerageRate: "0.009",
  interestRate: "4.5",
  loanYears: "25",
};
const LTV_WARN_RATIO = 0.8; // 통상 담보대출 한도(60~80%) 상단
const defaultAssetCriteria = {
  minLandArea: 200,
  minBuildingArea: 300,
  minFloors: 3,
  minParking: 3,
  elevator: "preferred",
  minApprovalYear: 2000,
  zoning: ["준주거지역", "제2종일반주거지역", "일반상업지역"],
  minRoadWidth: 6,
  maxCoverage: 70,
  minFar: 180,
  landRequiredChecks: ["건축 가능", "주차장 설치", "병원 용도 가능", "도로 접함"],
};
const CRITERIA_PRESETS = {
  // 대지 150평(≈496㎡) · 연면적 600평(≈1,983㎡) · 주차 13대(연면적/150㎡)
  building: {
    ...defaultAssetCriteria,
    minLandArea: 496,
    minBuildingArea: 1983,
    minFloors: 3,
    minParking: 13,
    elevator: "required",
  },
  land: {
    ...defaultAssetCriteria,
    minLandArea: 496,
    minBuildingArea: 0,
    minFloors: 0,
    minParking: 0,
    elevator: "any",
    minRoadWidth: 6,
  },
};

function loadStoredCriteria() {
  try {
    const raw = localStorage.getItem(STORAGE_CRITERIA);
    if (!raw) return { ...defaultAssetCriteria };
    return { ...defaultAssetCriteria, ...JSON.parse(raw) };
  } catch {
    return { ...defaultAssetCriteria };
  }
}

function persistCriteria() {
  localStorage.setItem(STORAGE_CRITERIA, JSON.stringify(assetCriteria));
}

let assetCriteria = loadStoredCriteria();
const memoTimers = new Map();

/* ===== Helpers ===== */

function identityOf(listing) {
  return listing.identity || `${listing.source}:${listing.external_id}`;
}

function naverLandUrl(listing) {
  const url = listing.naver_land_url || `https://new.land.naver.com/search?query=${encodeURIComponent(listing.location ?? "")}`;
  return safeHref(url);
}

function safeHref(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? url : "#";
  } catch {
    return "#";
  }
}

function naverMapSearchUrl(address) {
  return `https://map.naver.com/p/search/${encodeURIComponent(address)}`;
}

function osmEmbedUrl(latitude, longitude) {
  const delta = 0.0035;
  const bbox = [longitude - delta, latitude - delta, longitude + delta, latitude + delta].join(",");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${latitude},${longitude}`)}`;
}

async function resolveCoords(listing) {
  if (Number.isFinite(listing?.latitude) && Number.isFinite(listing?.longitude)) {
    return [listing.latitude, listing.longitude];
  }
  if (!state.hasServer || !listing?.location) {
    return null;
  }
  try {
    const payload = await apiJson(`/api/geocode?address=${encodeURIComponent(listing.location)}`);
    if (Number.isFinite(payload.latitude) && Number.isFinite(payload.longitude)) {
      return [payload.latitude, payload.longitude];
    }
  } catch {
    // 지오코딩 실패 시 네이버 지도 검색 임베드로 대체
  }
  return null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function money(value) {
  return `${currency.format(value)}원`;
}

function formatArea(value) {
  if (value === undefined || value === null || value === "-") {
    return "-";
  }
  return `${currency.format(value)}㎡ / ${formatPyeong(value)}`;
}

function formatPyeong(squareMeters) {
  const pyeong = Number(squareMeters) * pyeongPerSquareMeter;
  if (!Number.isFinite(pyeong)) {
    return "-";
  }
  return `${Math.round(pyeong * 10) / 10}평`;
}

function numberValue(id) {
  const raw = document.querySelector(`#${id}`).value || "0";
  return Number(String(raw).replaceAll(",", "")) || 0;
}

/* ===== 금액 입력 포맷팅 (쉼표 + 억/만원 힌트) ===== */

function koreanMoneyLabel(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0원";
  }
  const eok = Math.floor(value / 100000000);
  const man = Math.floor((value % 100000000) / 10000);
  const won = value % 10000;
  const parts = [];
  if (eok > 0) parts.push(`${currency.format(eok)}억`);
  if (man > 0) parts.push(`${currency.format(man)}만`);
  if (won > 0 || parts.length === 0) parts.push(currency.format(won));
  return `${parts.join(" ")}원`;
}

function formatMoneyInput(input) {
  const digits = input.value.replace(/[^\d]/g, "");
  const amount = digits ? Number(digits) : 0;
  input.value = digits ? currency.format(amount) : "";
  const hint = document.querySelector(`[data-money-hint="${input.id}"]`);
  if (hint) {
    hint.textContent = koreanMoneyLabel(amount);
  }
}

function setupMoneyInputs() {
  document.querySelectorAll("input[data-money]").forEach((input) => {
    input.addEventListener("input", () => formatMoneyInput(input));
    formatMoneyInput(input);
  });
}

function refreshMoneyInputs() {
  document.querySelectorAll("input[data-money]").forEach((input) => formatMoneyInput(input));
}

function splitText(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  elements.toastStack.appendChild(toast);
  setTimeout(() => toast.remove(), 2900);
}

/* ===== Criteria matching ===== */

// 정적 모드(서버 없음) 샘플 필터용 기본값 — 서버 모드에서는 config의 criteria가 적용된다
const DEFAULT_SEARCH_CRITERIA = {
  locations: ["양천구"],
  keywords: ["건물", "토지", "상가", "병원", "의원"],
  maxDeposit: 150000000,
  maxRent: 6000000,
  minArea: 70,
};

function readCriteria() {
  return DEFAULT_SEARCH_CRITERIA;
}

function matchesCriteria(listing, criteria) {
  const locationMatch = criteria.locations.some((location) => listing.location.includes(location));
  const keywordMatch = criteria.keywords.some((keyword) => {
    const text = `${listing.title} ${listing.location}`.toLowerCase();
    return text.includes(keyword.toLowerCase());
  });
  return (
    locationMatch &&
    keywordMatch &&
    listing.deposit <= criteria.maxDeposit &&
    listing.monthly_rent <= criteria.maxRent &&
    listing.area_m2 >= criteria.minArea
  );
}

function isYangcheonAddress(address) {
  return address.includes("서울") && address.includes("양천구");
}

/* ===== Asset fit ===== */

function evaluateAssetFit(listing) {
  const roadWidth = extractRoadWidth(listing.road_access);
  const isLand = listing.property_type === "land" || listing.floor === "토지/건물";
  const buildingChecks = [
    checkResult("대지", listing.land_area_m2 >= assetCriteria.minLandArea),
    checkResult("건평", listing.building_area_m2 >= assetCriteria.minBuildingArea),
    checkResult("층수", (listing.floors_total ?? 0) >= assetCriteria.minFloors),
    checkResult("주차", (listing.parking_spaces ?? 0) >= assetCriteria.minParking),
    checkResult("엘리베이터", assetCriteria.elevator !== "required" || listing.elevator === true),
    checkResult("연식", !listing.approval_year || listing.approval_year >= assetCriteria.minApprovalYear),
  ];
  const landChecks = [
    checkResult("용도지역", assetCriteria.zoning.some((zone) => listing.zoning?.includes(zone))),
    checkResult("접도", roadWidth >= assetCriteria.minRoadWidth),
    checkResult("건폐율", !listing.building_coverage_ratio || listing.building_coverage_ratio <= assetCriteria.maxCoverage),
    checkResult("용적률", !listing.floor_area_ratio || listing.floor_area_ratio >= assetCriteria.minFar),
  ];
  const checks = isLand ? landChecks : buildingChecks;
  const passed = checks.filter((item) => item.ok).length;
  const label = passed === checks.length ? "조건 적합" : passed >= Math.ceil(checks.length / 2) ? "추가 검토" : "조건 부족";
  const className = passed === checks.length ? "ok" : passed >= Math.ceil(checks.length / 2) ? "need" : "risk";
  return { label, className, checks };
}

function checkResult(label, ok) {
  return { label, ok: Boolean(ok) };
}

function extractRoadWidth(value) {
  if (!value) return 0;
  const match = String(value).match(/(\d+(?:\.\d+)?)\s*m/i);
  return match ? Number(match[1]) : 0;
}

function registryStatus(listing) {
  if (listing.registry_status) {
    if (listing.registry_status === "위험 권리 있음") {
      return { label: listing.registry_status, className: "risk", risks: listing.registry_risks || [] };
    }
    if (listing.registry_status === "확인 완료") {
      return { label: listing.registry_status, className: "ok", risks: [] };
    }
    return { label: listing.registry_status, className: "need", risks: [] };
  }
  if (!listing.registryText) {
    return { label: "등기 확인 필요", className: "need", risks: [] };
  }
  const risks = riskKeywords.filter((keyword) => listing.registryText.includes(keyword));
  if (risks.length > 0) {
    return { label: "위험 권리 있음", className: "risk", risks };
  }
  return { label: "확인 완료", className: "ok", risks: [] };
}

/* ===== Server API + localStorage fallback ===== */

async function apiJson(path, options) {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}

async function loadServerListings() {
  try {
    const payload = await apiJson("/api/listings");
    state.hasServer = true;
    state.listings = payload.listings || [];
    state.unmatched = payload.unmatched_listings || [];
    state.stats = payload;
    // 서버가 첫 수집 중이면 잠시 후 자동으로 다시 불러온다
    if (payload.collecting) {
      scheduleCollectingReload();
    }
    return true;
  } catch {
    state.hasServer = false;
    return false;
  }
}

let collectingReloadTimer = null;
function scheduleCollectingReload() {
  clearTimeout(collectingReloadTimer);
  elements.scanStatus.textContent = "매물 수집 중... (잠시 후 자동 표시)";
  elements.scanStatus.className = "status-pill need";
  collectingReloadTimer = setTimeout(async () => {
    await loadServerListings();
    if (!state.stats?.collecting) {
      elements.scanStatus.textContent = "서버 연결됨";
      elements.scanStatus.className = "status-pill ok";
    }
    renderDashboard();
  }, 2000);
}

async function loadFavorites() {
  if (state.hasServer) {
    try {
      const payload = await apiJson("/api/favorites");
      state.favorites = new Map(payload.favorites.map((item) => [item.identity, item.listing]));
      return;
    } catch {
      // 서버 즐겨찾기 로드 실패 시 로컬 데이터로 유지
    }
  }
  state.favorites = readStoredMap(STORAGE_FAVORITES);
}

async function loadLedger() {
  if (state.hasServer) {
    try {
      const payload = await apiJson("/api/ledger");
      state.ledger = new Map(payload.entries.map((entry) => [entry.identity, entry]));
      return;
    } catch {
      // 서버 매물장 로드 실패 시 로컬 데이터로 유지
    }
  }
  state.ledger = readStoredMap(STORAGE_LEDGER);
}

function readStoredMap(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Map();
    const parsed = JSON.parse(raw);
    return new Map(Object.entries(parsed));
  } catch {
    return new Map();
  }
}

function persistMap(key, map) {
  localStorage.setItem(key, JSON.stringify(Object.fromEntries(map)));
}

async function toggleFavorite(listing) {
  const identity = identityOf(listing);
  let isFavorite;
  if (state.hasServer) {
    try {
      const payload = await apiJson("/api/favorites/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity, listing }),
      });
      isFavorite = payload.is_favorite;
    } catch {
      showToast("관심매물 저장에 실패했습니다.");
      return;
    }
    if (isFavorite) {
      state.favorites.set(identity, listing);
    } else {
      state.favorites.delete(identity);
    }
  } else {
    if (state.favorites.has(identity)) {
      state.favorites.delete(identity);
      isFavorite = false;
    } else {
      state.favorites.set(identity, listing);
      isFavorite = true;
    }
    persistMap(STORAGE_FAVORITES, state.favorites);
  }
  showToast(isFavorite ? "관심매물에 추가했습니다 ♥" : "관심매물에서 제외했습니다");
  renderBoard();
  renderMetrics();
}

async function saveLedgerEntry(identity, listing, status, memo) {
  const entry = { identity, listing, status, memo, updated_at: new Date().toISOString() };
  if (state.hasServer) {
    try {
      await apiJson("/api/ledger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity, listing, status, memo }),
      });
    } catch {
      showToast("매물장 저장에 실패했습니다.");
      return null;
    }
  }
  state.ledger.set(identity, entry);
  if (!state.hasServer) {
    persistMap(STORAGE_LEDGER, state.ledger);
  }
  return entry;
}

async function deleteLedgerEntry(identity) {
  if (state.hasServer) {
    try {
      await apiJson("/api/ledger/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity }),
      });
    } catch {
      showToast("매물장 삭제에 실패했습니다.");
      return;
    }
  }
  state.ledger.delete(identity);
  if (!state.hasServer) {
    persistMap(STORAGE_LEDGER, state.ledger);
  }
  showToast("매물장에서 삭제했습니다");
  renderLedger();
  renderBoard();
}

/* ===== Scan ===== */

async function runScan() {
  if (state.hasServer) {
    setScanningButton(true);  // 클릭 즉시 버튼 반응 (진행 상황은 폴링이 채운다)
    try {
      const result = await apiJson("/api/scan", { method: "POST" });
      if (result.scanning) {
        showToast("매물 수집을 시작했습니다 — 잠시 후 자동으로 갱신됩니다");
        scheduleCollectingReload();
      } else {
        showToast("이미 수집이 진행 중입니다");
      }
      await loadServerListings();
      renderDashboard();
      return;
    } catch {
      state.hasServer = false;
    }
  }
  applyStaticListings();
  elements.scanStatus.textContent = `최근 실행 ${new Date().toLocaleTimeString("ko-KR")}`;
  elements.scanStatus.className = "status-pill ok";
  renderDashboard();
}

function applyStaticListings() {
  const criteria = readCriteria();
  state.listings = sampleListings.filter((listing) => matchesCriteria(listing, criteria));
  state.unmatched = sampleListings
    .filter((listing) => !matchesCriteria(listing, criteria))
    .map((listing) => ({ ...listing, is_match: false }));
  state.stats = {
    fetched_count: sampleListings.length,
    matched_count: state.listings.length,
  };
}

/* ===== 신규 매물 강조 ===== */

function relativeTimeFrom(firstSeenAt) {
  if (!firstSeenAt) return "";
  const seen = new Date(`${String(firstSeenAt).replace(" ", "T")}Z`);
  if (Number.isNaN(seen.getTime())) return "";
  const hours = Math.floor((Date.now() - seen.getTime()) / 3600000);
  if (hours < 1) return "방금 등록";
  if (hours < 24) return `${hours}시간 전 등록`;
  return `${Math.floor(hours / 24)}일 전 등록`;
}

function isFresh24h(listing) {
  if (!listing.first_seen_at) return Boolean(listing.is_new);
  const seen = new Date(`${String(listing.first_seen_at).replace(" ", "T")}Z`);
  if (Number.isNaN(seen.getTime())) return false;
  return Date.now() - seen.getTime() < FRESH_HOURS * 3600000;
}

function sortNewFirst(listings) {
  return [...listings].sort((a, b) => {
    if (Boolean(a.is_new) !== Boolean(b.is_new)) return a.is_new ? -1 : 1;
    return String(b.first_seen_at ?? "").localeCompare(String(a.first_seen_at ?? ""));
  });
}

function sourceLabel(source) {
  return {
    naver: "네이버",
    onbid: "온비드",
    court: "법원경매",
    lh: "LH",
    manual: "수동 등록",
    json_file: "파일",
  }[source] ?? source;
}

function renderNewBanner() {
  const all = [...state.listings, ...state.unmatched];
  const fresh = all.filter((listing) => listing.is_new);
  elements.newBanner.hidden = fresh.length === 0;
  if (fresh.length === 0) return;
  const bySource = new Map();
  fresh.forEach((listing) => bySource.set(listing.source, (bySource.get(listing.source) || 0) + 1));
  elements.newBannerTitle.textContent = `신규 매물 ${fresh.length}건`;
  const sources = [...bySource.entries()]
    .map(([source, count]) => `${sourceLabel(source)} ${count}건`)
    .join(" · ");
  elements.newBannerSources.textContent = `${sources} · 최근 72시간`;
}

/* ===== 필수조건 검색 ===== */

function triCheck(label, value, predicate) {
  if (value === null || value === undefined || value === "" || Number.isNaN(value)) {
    return { label, state: "unknown" };
  }
  return { label, state: predicate(value) ? "ok" : "fail" };
}

function evaluateRequiredFit(listing) {
  const isLand = listing.property_type === "land" || listing.floor === "토지/건물";
  const checks = [];
  if (assetCriteria.minLandArea > 0) {
    checks.push(triCheck("대지", listing.land_area_m2, (v) => v >= assetCriteria.minLandArea));
  }
  if (isLand) {
    if (assetCriteria.zoning.length > 0) {
      checks.push(
        triCheck("용도지역", listing.zoning, (v) =>
          assetCriteria.zoning.some((zone) => String(v).includes(zone)),
        ),
      );
    }
    if (assetCriteria.minRoadWidth > 0) {
      checks.push(
        triCheck(
          "접도",
          listing.road_access ? extractRoadWidth(listing.road_access) : null,
          (v) => v >= assetCriteria.minRoadWidth,
        ),
      );
    }
  } else {
    if (assetCriteria.minBuildingArea > 0) {
      checks.push(triCheck("연면적", listing.building_area_m2, (v) => v >= assetCriteria.minBuildingArea));
    }
    if (assetCriteria.minParking > 0) {
      checks.push(triCheck("주차", listing.parking_spaces, (v) => v >= assetCriteria.minParking));
    }
    if (assetCriteria.minFloors > 0) {
      checks.push(triCheck("층수", listing.floors_total, (v) => v >= assetCriteria.minFloors));
    }
    if (assetCriteria.elevator === "required") {
      checks.push(triCheck("승강기", listing.elevator, (v) => v === true));
    }
  }
  if (checks.some((check) => check.state === "fail")) return { group: "fail", checks };
  if (checks.some((check) => check.state === "unknown")) return { group: "unknown", checks };
  return { group: "met", checks };
}

function fitGroups() {
  const all = [...state.listings, ...state.unmatched];
  const groups = { met: [], unknown: [], fail: [] };
  all.forEach((listing) => {
    groups[evaluateRequiredFit(listing).group].push(listing);
  });
  return groups;
}

function fitCardsHtml(listings) {
  return listings.length > 0
    ? listings.map(listingCardHtml).join("")
    : `<div class="empty-state">해당 매물이 없습니다.</div>`;
}

function renderFitBoard() {
  const groups = fitGroups();
  elements.boardGrid.innerHTML = `
    <div class="fit-results">
      <section class="fit-group">
        <h3 class="fit-group-head ok-head">✅ 필수조건 충족 <span class="fit-count">${groups.met.length}건</span></h3>
        <div class="board-grid fit-grid">${fitCardsHtml(sortNewFirst(groups.met))}</div>
      </section>
      <details class="fit-group"${groups.met.length === 0 ? " open" : ""}>
        <summary class="fit-group-head need-head">❓ 확인 필요 <span class="fit-count">${groups.unknown.length}건</span> — 데이터 부족, 공공데이터 검증 시 판정 가능</summary>
        <div class="board-grid fit-grid">${fitCardsHtml(sortNewFirst(groups.unknown))}</div>
      </details>
      <details class="fit-group">
        <summary class="fit-group-head risk-head">조건 미달 <span class="fit-count">${groups.fail.length}건</span></summary>
        <div class="board-grid fit-grid">${fitCardsHtml(sortNewFirst(groups.fail))}</div>
      </details>
    </div>
  `;
}

/* ===== Rendering ===== */

function renderDashboard() {
  renderScanProgress();
  renderMetrics();
  renderNewBanner();
  renderBoard();
  renderLedger();
  renderPriority();
  renderAssetCriteria();
  if (state.listings.length > 0 && !state.selectedListing) {
    selectListingForMap(state.listings[0]);
  }
}

function renderMetrics() {
  const progress = state.stats?.progress;
  const collecting = Boolean(state.stats?.collecting) && progress;
  const newCount = state.stats?.new_count ?? state.listings.filter((listing) => listing.is_new).length;
  // 수집 중에는 진행률의 누적 건수를 보여줘 "수집 갯수가 올라가는" 연출을 한다.
  const fetched = collecting ? progress.fetched : (state.stats?.fetched_count ?? state.listings.length);
  setMetric(elements.fetchedCount, fetched);
  setMetric(elements.matchedCount, state.stats?.matched_count ?? state.listings.length);
  setMetric(elements.newCount, newCount);
  setMetric(elements.favoriteCount, state.favorites.size);
}

function renderScanProgress() {
  const progress = state.stats?.progress;
  const active = Boolean(state.stats?.collecting) && progress && progress.phase !== "done";
  setScanningButton(active);
  if (!active) {
    elements.scanProgress.hidden = true;
    showLastCollected();
    return;
  }
  elements.scanProgress.hidden = false;
  const done = progress.sources_done ?? 0;
  const total = progress.sources_total ?? 0;
  elements.scanProgressTitle.textContent = total
    ? `매물 수집 중… (${done}/${total} 소스)`
    : "매물 수집 중…";
  elements.scanProgressCount.textContent = `${progress.fetched}건`;
  setProgressBar(total ? done / total : 0);
  elements.scanProgressSources.textContent = formatSourceBreakdown(progress.by_source);
}

function showLastCollected() {
  const iso = state.stats?.collected_at;
  if (!state.hasServer || !iso) return;
  const when = new Date(`${String(iso).replace(" ", "T")}Z`);
  if (Number.isNaN(when.getTime())) return;
  const hhmm = when.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
  elements.scanStatus.textContent = `마지막 수집 ${hhmm} · 10분마다 자동 갱신`;
  elements.scanStatus.className = "status-pill ok";
}

function setProgressBar(fraction) {
  const clamped = Math.max(0, Math.min(1, fraction));
  // 합성기 친화적 속성(transform)만 애니메이션한다.
  elements.scanProgressFill.style.transform = `scaleX(${clamped})`;
}

function setScanningButton(scanning) {
  const button = elements.scanButton;
  if (!button) return;
  button.classList.toggle("is-scanning", scanning);
  button.disabled = scanning;
  const label = button.querySelector(".scan-label");
  if (label) label.textContent = scanning ? "수집 중…" : "신규 매물 스캔";
}

function formatSourceBreakdown(bySource) {
  if (!bySource) return "";
  const order = ["onbid", "court", "lh", "manual", "naver", "json_file"];
  const rank = (key) => {
    const index = order.indexOf(key);
    return index === -1 ? order.length : index;
  };
  return Object.keys(bySource)
    .sort((a, b) => rank(a) - rank(b))
    .map((key) => `${sourceLabel(key)} ${bySource[key]}`)
    .join(" · ");
}

function setMetric(element, value) {
  const target = Number(value) || 0;
  if (reducedMotion) {
    element.textContent = String(target);
    return;
  }
  const start = Number(element.dataset.current || 0);
  if (start === target) {
    element.textContent = String(target);
    return;
  }
  element.dataset.current = String(target);
  const duration = 600;
  const startTime = performance.now();
  function tick(now) {
    const progress = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = String(Math.round(start + (target - start) * eased));
    if (progress < 1) {
      requestAnimationFrame(tick);
    }
  }
  requestAnimationFrame(tick);
}

function boardListings() {
  if (state.boardFilter === "new") {
    return state.listings.filter((listing) => listing.is_new);
  }
  if (state.boardFilter === "favorite") {
    return state.listings.filter((listing) => state.favorites.has(identityOf(listing)));
  }
  if (state.boardFilter === "fetched") {
    return [...state.listings, ...state.unmatched];
  }
  return state.listings;
}

function renderBoard() {
  const all = state.listings;
  const newOnes = all.filter((listing) => listing.is_new);
  const favorites = all.filter((listing) => state.favorites.has(identityOf(listing)));
  document.querySelector("#countAll").textContent = all.length;
  document.querySelector("#countNew").textContent = newOnes.length;
  document.querySelector("#countFavorite").textContent = favorites.length;
  document.querySelector("#countFetched").textContent = all.length + state.unmatched.length;
  document.querySelector("#countFit").textContent = fitGroups().met.length;

  // '수집 전체'는 수백 건이라 3D 카드 대신 소스별 컴팩트 표로 보여준다(빠르게 뜨고 한눈에).
  elements.regionFilter.hidden = state.boardFilter !== "fetched";

  if (state.boardFilter === "fit") {
    renderFitBoard();
  } else if (state.boardFilter === "fetched") {
    renderFetchedTable();
  } else {
    const visible = sortNewFirst(boardListings());
    if (visible.length === 0) {
      const messages = {
        all: "조건에 맞는 매물이 없습니다. 스캔을 실행하거나 검색 조건을 조정하세요.",
        new: "최근 발견된 신규 매물이 없습니다.",
        favorite: "관심매물이 비어 있습니다. 카드의 ♥ 버튼으로 추가하세요.",
      };
      elements.boardGrid.innerHTML = `<div class="empty-state">${messages[state.boardFilter]}</div>`;
      return;
    }
    elements.boardGrid.innerHTML = visible.map(listingCardHtml).join("");
  }

  elements.boardGrid.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const listing = [...state.listings, ...state.unmatched].find(
        (item) => identityOf(item) === button.dataset.identity,
      );
      if (!listing) return;
      handleCardAction(button.dataset.action, listing);
    });
  });
  // 카드의 버튼/링크가 아닌 영역을 클릭하면 상세 정보(지도 패널)로 이동한다
  elements.boardGrid.querySelectorAll("[data-card-identity]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a, select, input")) {
        return;
      }
      const listing = [...state.listings, ...state.unmatched].find(
        (item) => identityOf(item) === card.dataset.cardIdentity,
      );
      if (!listing) return;
      handleCardAction("map", listing);
    });
  });
  attachTilt(elements.boardGrid.querySelectorAll(".listing-card"));
}

function listingCardHtml(listing) {
  const identity = identityOf(listing);
  const isFavorite = state.favorites.has(identity);
  const inLedger = state.ledger.has(identity);
  const fit = evaluateAssetFit(listing);
  const registry = registryStatus(listing);
  const isLand = listing.property_type === "land" || listing.floor === "토지/건물";
  const priceText = listing.monthly_rent > 0
    ? `${money(listing.deposit)} / ${money(listing.monthly_rent)}`
    : "매입가 협의";
  return `
    <article class="listing-card${isFavorite ? " is-favorite" : ""}" data-tilt
      data-card-identity="${escapeHtml(identity)}" title="클릭하면 상세 정보로 이동">
      <div class="card-top">
        ${listing.is_new ? `<span class="badge-new${isFresh24h(listing) ? " fresh" : ""}">NEW</span><span class="new-ago">${relativeTimeFrom(listing.first_seen_at)}</span>` : ""}
        <span class="type-chip">${isLand ? "토지" : "건물"}</span>
        <span class="spacer"></span>
        <button type="button" class="fav-button${isFavorite ? " active" : ""}" data-action="favorite"
          data-identity="${escapeHtml(identity)}" aria-label="관심매물 ${isFavorite ? "해제" : "추가"}"
          aria-pressed="${isFavorite}">♥</button>
      </div>
      <h3>${escapeHtml(listing.title)}</h3>
      <p class="card-location">${escapeHtml(listing.location)} · ${escapeHtml(listing.floor ?? "-")}</p>
      <dl class="card-stats">
        <div><dt>보증금/월세</dt><dd>${priceText}</dd></div>
        <div><dt>전용 면적</dt><dd>${formatArea(listing.area_m2)}</dd></div>
        <div><dt>대지</dt><dd>${formatArea(listing.land_area_m2)}</dd></div>
        <div><dt>층수 · 주차</dt><dd>${listing.floors_total ? `${listing.floors_total}층` : "-"} · ${listing.parking_spaces ?? "-"}대</dd></div>
      </dl>
      <div class="card-pills">
        ${listing.is_match === false ? '<span class="status-pill risk">검색 조건 불일치</span>' : ""}
        <span class="status-pill ${fit.className}">${escapeHtml(fit.label)}</span>
        <span class="status-pill ${registry.className}">${escapeHtml(registry.label)}</span>
      </div>
      <div class="card-actions">
        <a class="button primary compact" href="${escapeHtml(naverLandUrl(listing))}" target="_blank" rel="noreferrer">네이버 부동산</a>
        <button type="button" class="button secondary compact" data-action="map" data-identity="${escapeHtml(identity)}">지도/토지</button>
        <button type="button" class="button secondary compact" data-action="ledger" data-identity="${escapeHtml(identity)}">
          ${inLedger ? "매물장 ✓" : "매물장 추가"}
        </button>
      </div>
    </article>
  `;
}

/* ===== 수집 전체 — 소스별 컴팩트 표 (수백 건을 한눈에) ===== */

const REGION_ORDER = ["양천구", "강서구", "구로구", "영등포구"];
const SOURCE_ORDER = ["onbid", "court", "lh", "manual", "naver", "json_file"];

function regionOf(location) {
  const match = String(location || "").match(/(\S+?[구군])(?:\s|$)/);
  return match ? match[1] : "기타";
}

function sortByOrder(values, order) {
  const rank = (value) => {
    const index = order.indexOf(value);
    return index === -1 ? order.length : index;
  };
  return [...values].sort((a, b) => rank(a) - rank(b) || String(a).localeCompare(String(b)));
}

function renderFetchedTable() {
  const all = [...state.listings, ...state.unmatched];
  const regions = sortByOrder([...new Set(all.map((item) => regionOf(item.location)))], REGION_ORDER);
  renderRegionChips(regions);

  const region = state.regionFilter;
  const filtered = region === "all" ? all : all.filter((item) => regionOf(item.location) === region);
  if (filtered.length === 0) {
    elements.boardGrid.innerHTML = '<div class="empty-state">해당 지역에 수집된 매물이 없습니다.</div>';
    return;
  }

  const groups = new Map();
  for (const item of filtered) {
    if (!groups.has(item.source)) groups.set(item.source, []);
    groups.get(item.source).push(item);
  }
  const orderedKeys = sortByOrder([...groups.keys()], SOURCE_ORDER);

  const head =
    "<thead><tr><th>유형</th><th>제목</th><th>위치</th><th>전용/대지</th>" +
    "<th>층·주차</th><th>조건</th><th>메모</th><th>링크</th></tr></thead>";
  const bodies = orderedKeys
    .map((key) => {
      const rows = sortNewFirst(groups.get(key));
      const header = `<tr class="collect-group-head"><td colspan="8">${escapeHtml(
        sourceLabel(key),
      )} <span class="chip-count">${rows.length}</span></td></tr>`;
      return `<tbody>${header}${rows.map(collectRowHtml).join("")}</tbody>`;
    })
    .join("");
  elements.boardGrid.innerHTML = `<div class="table-wrap collect-table-wrap"><table class="collect-table">${head}${bodies}</table></div>`;
}

function renderRegionChips(regions) {
  const chip = (value, label, count) =>
    `<button type="button" class="filter-chip${state.regionFilter === value ? " active" : ""}" data-region="${escapeHtml(value)}">${escapeHtml(label)} <span class="chip-count">${count}</span></button>`;
  const all = [...state.listings, ...state.unmatched];
  const parts = [chip("all", "전체 지역", all.length)];
  for (const region of regions) {
    const count = all.filter((item) => regionOf(item.location) === region).length;
    parts.push(chip(region, region, count));
  }
  elements.regionFilter.innerHTML = parts.join("");
  elements.regionFilter.querySelectorAll("[data-region]").forEach((button) => {
    button.addEventListener("click", () => {
      state.regionFilter = button.dataset.region;
      renderBoard();
    });
  });
}

function collectRowHtml(listing) {
  const identity = identityOf(listing);
  const isLand = listing.property_type === "land" || listing.floor === "토지/건물";
  const inLedger = state.ledger.has(identity);
  const newBadge = listing.is_new ? '<span class="badge-new">NEW</span> ' : "";
  const matchBadge =
    listing.is_match === false
      ? '<span class="status-pill risk">불일치</span>'
      : '<span class="status-pill ok">일치</span>';
  const area = listing.area_m2 ? formatArea(listing.area_m2) : "-";
  const land = listing.land_area_m2 ? formatArea(listing.land_area_m2) : "-";
  const floorsParking = `${listing.floors_total ? `${listing.floors_total}층` : "-"} · ${
    listing.parking_spaces ?? "-"
  }대`;
  return `
    <tr data-row-identity="${escapeHtml(identity)}">
      <td><span class="type-chip">${isLand ? "토지" : "건물"}</span></td>
      <td class="collect-title">${newBadge}${escapeHtml(listing.title)}</td>
      <td>${escapeHtml(listing.location)}</td>
      <td class="collect-area">${area}<br /><span>${land}</span></td>
      <td>${floorsParking}</td>
      <td>${matchBadge}</td>
      <td class="collect-note">${escapeHtml(listing.buildable_note ?? "-")}</td>
      <td class="collect-links">
        <a class="button secondary compact" href="${escapeHtml(naverLandUrl(listing))}" target="_blank" rel="noreferrer">네이버</a>
        <button type="button" class="button secondary compact" data-action="map" data-identity="${escapeHtml(identity)}">지도</button>
        <button type="button" class="button ${inLedger ? "secondary" : "primary"} compact" data-action="ledger" data-identity="${escapeHtml(identity)}">${inLedger ? "장 ✓" : "장 +"}</button>
      </td>
    </tr>`;
}

function handleCardAction(action, listing) {
  if (action === "favorite") {
    void toggleFavorite(listing);
    return;
  }
  if (action === "map") {
    selectListingForMap(listing);
    document.querySelector("#map").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (action === "ledger") {
    const identity = identityOf(listing);
    if (state.ledger.has(identity)) {
      document.querySelector("#ledger").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    void saveLedgerEntry(identity, listing, LEDGER_STATUSES[0], "").then((entry) => {
      if (entry) {
        showToast("매물장에 추가했습니다");
        renderLedger();
        renderBoard();
      }
    });
  }
}

function renderLedger() {
  const entries = [...state.ledger.values()];
  renderLedgerSummary(entries);
  if (entries.length === 0) {
    elements.ledgerRows.innerHTML = `<tr><td colspan="7"><div class="empty-state">매물 보드에서 "매물장 추가"를 누르면 검토 이력이 여기에 쌓입니다.</div></td></tr>`;
    return;
  }
  elements.ledgerRows.innerHTML = entries
    .map((entry) => {
      const listing = entry.listing || {};
      const priceText = (listing.monthly_rent ?? 0) > 0
        ? `${money(listing.deposit ?? 0)} / ${money(listing.monthly_rent ?? 0)}`
        : "매입가 협의";
      const tone = LEDGER_TONES[entry.status] || "tone-active";
      const options = LEDGER_STATUSES
        .map((status) => `<option value="${status}"${status === entry.status ? " selected" : ""}>${status}</option>`)
        .join("");
      return `
        <tr data-identity="${escapeHtml(entry.identity)}">
          <td><strong>${escapeHtml(listing.title ?? entry.identity)}</strong><br /><span>${escapeHtml(listing.location ?? "-")}</span></td>
          <td>${priceText}</td>
          <td>
            <select class="ledger-status-select ${tone}" data-ledger-status data-identity="${escapeHtml(entry.identity)}">
              ${options}
            </select>
          </td>
          <td>
            <input class="ledger-memo-input" type="text" placeholder="메모 입력 (자동 저장)"
              value="${escapeHtml(entry.memo ?? "")}" data-ledger-memo data-identity="${escapeHtml(entry.identity)}" />
          </td>
          <td>
            <div class="ledger-review-cell">
              ${gradeBadgeHtml(entry.identity)}
              <div class="ledger-row-actions">
                <button type="button" class="button secondary compact" data-checklist-open
                  data-identity="${escapeHtml(entry.identity)}">체크리스트</button>
                <button type="button" class="button secondary compact" data-docs-open
                  data-identity="${escapeHtml(entry.identity)}" title="받은 서류 보기/추가">📄 ${documentCountFor(entry.identity)}</button>
              </div>
            </div>
          </td>
          <td>
            <a class="button secondary compact" href="${escapeHtml(naverLandUrl(listing))}" target="_blank" rel="noreferrer">네이버</a>
          </td>
          <td>
            <button type="button" class="button ghost-danger compact" data-ledger-delete data-identity="${escapeHtml(entry.identity)}">삭제</button>
          </td>
        </tr>
      `;
    })
    .join("");

  elements.ledgerRows.querySelectorAll("[data-ledger-status]").forEach((select) => {
    select.addEventListener("change", () => {
      const entry = state.ledger.get(select.dataset.identity);
      if (!entry) return;
      void saveLedgerEntry(entry.identity, entry.listing, select.value, entry.memo).then((saved) => {
        if (saved) {
          showToast(`상태를 "${select.value}"(으)로 변경했습니다`);
          renderLedger();
        }
      });
    });
  });
  elements.ledgerRows.querySelectorAll("[data-ledger-memo]").forEach((input) => {
    input.addEventListener("input", () => {
      const identity = input.dataset.identity;
      clearTimeout(memoTimers.get(identity));
      memoTimers.set(
        identity,
        setTimeout(() => {
          const current = state.ledger.get(identity);
          if (!current) return;
          void saveLedgerEntry(identity, current.listing, current.status, input.value);
        }, MEMO_SAVE_DELAY_MS),
      );
    });
  });
  elements.ledgerRows.querySelectorAll("[data-ledger-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      void deleteLedgerEntry(button.dataset.identity);
    });
  });
  elements.ledgerRows.querySelectorAll("[data-checklist-open]").forEach((button) => {
    button.addEventListener("click", () => {
      void openChecklistModal(button.dataset.identity);
    });
  });
  elements.ledgerRows.querySelectorAll("[data-docs-open]").forEach((button) => {
    button.addEventListener("click", () => {
      void openDocsModal(button.dataset.identity);
    });
  });
}

function renderLedgerSummary(entries) {
  if (entries.length === 0) {
    elements.ledgerSummary.innerHTML = "";
    return;
  }
  const counts = new Map();
  entries.forEach((entry) => {
    counts.set(entry.status, (counts.get(entry.status) || 0) + 1);
  });
  elements.ledgerSummary.innerHTML = [...counts.entries()]
    .map(([status, count]) => {
      const tone = status === "보류" ? "need" : status === "계약 검토" ? "ok" : "neutral";
      return `<span class="status-pill ${tone}">${escapeHtml(status)} ${count}</span>`;
    })
    .join("");
}

function renderPriority() {
  const sorted = [...state.listings].sort((a, b) => a.monthly_rent - b.monthly_rent);
  if (sorted.length === 0) {
    elements.priorityList.innerHTML = `<div class="empty-state">스캔 실행 후 우선순위가 표시됩니다.</div>`;
    return;
  }
  elements.priorityList.innerHTML = sorted
    .slice(0, 3)
    .map(
      (listing, index) => `
        <article class="priority-item" role="listitem" tabindex="0"
          data-priority-identity="${escapeHtml(identityOf(listing))}" title="클릭하면 매물 카드로 이동">
          <strong>${index + 1}. ${escapeHtml(listing.title)}</strong>
          <span>${money(listing.deposit)} / ${money(listing.monthly_rent)} · ${formatArea(listing.area_m2)}</span>
        </article>
      `,
    )
    .join("");
  elements.priorityList.querySelectorAll("[data-priority-identity]").forEach((item) => {
    const goToCard = () => focusListingCard(item.dataset.priorityIdentity);
    item.addEventListener("click", goToCard);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        goToCard();
      }
    });
  });
}

function focusListingCard(identity) {
  const listing = [...state.listings, ...state.unmatched].find(
    (item) => identityOf(item) === identity,
  );
  if (!listing) return;
  const findCard = () =>
    elements.boardGrid.querySelector(`[data-card-identity="${CSS.escape(identity)}"]`);
  let card = findCard();
  if (!card) {
    // 현재 보드 필터에 없는 매물이면 전체 보기로 전환 후 찾는다
    setBoardFilter("all");
    card = findCard();
  }
  if (!card) {
    setBoardFilter("fetched");
    card = findCard();
  }
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("card-spotlight");
  setTimeout(() => card.classList.remove("card-spotlight"), 2200);
  selectListingForMap(listing);
}

function renderAssetCriteria() {
  if (!elements.assetCriteriaGrid) {
    return;
  }
  elements.assetCriteriaGrid.innerHTML = `
    <article class="criteria-card">
      <h3>건물 매입 조건</h3>
      <dl>
        ${criteriaRow("최소 대지", formatArea(assetCriteria.minLandArea))}
        ${criteriaRow("최소 건평/연면적", formatArea(assetCriteria.minBuildingArea))}
        ${criteriaRow("최소 층수", `${assetCriteria.minFloors}층 이상`)}
        ${criteriaRow("최소 주차", `${assetCriteria.minParking}대 이상`)}
        ${criteriaRow("엘리베이터", elevatorLabel(assetCriteria.elevator))}
        ${criteriaRow("승인연도", `${assetCriteria.minApprovalYear}년 이후 우선`)}
      </dl>
    </article>
    <article class="criteria-card">
      <h3>토지 신축 조건</h3>
      <dl>
        ${criteriaRow("허용 용도지역", escapeHtml(assetCriteria.zoning.join(", ")))}
        ${criteriaRow("접도 폭", `${assetCriteria.minRoadWidth}m 이상`)}
        ${criteriaRow("건폐율", `${assetCriteria.maxCoverage}% 이하`)}
        ${criteriaRow("용적률", `${assetCriteria.minFar}% 이상`)}
        ${criteriaRow("필수 확인", escapeHtml(assetCriteria.landRequiredChecks.join(", ")))}
      </dl>
    </article>
  `;
}

function criteriaRow(label, value) {
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function elevatorLabel(value) {
  if (value === "required") return "필수";
  if (value === "any") return "무관";
  return "있으면 우선";
}

/* ===== 부동산 서류 · 직접 등록 ===== */

function safeIdentityKey(identity) {
  // 서버의 documents 폴더명 규칙과 동일 (콜론 등을 _로 치환)
  return String(identity).replace(/[^0-9A-Za-z._-]/g, "_");
}

function documentCountFor(identity) {
  return state.documentCounts.get(safeIdentityKey(identity)) || 0;
}

async function loadDocumentCounts() {
  if (!state.hasServer) return;
  try {
    const payload = await apiJson("/api/documents/counts");
    state.documentCounts = new Map(Object.entries(payload.counts || {}));
  } catch {
    // 서류 수 표시는 부가 기능 — 실패해도 대시보드는 동작
  }
}

async function uploadDocument(identity, file) {
  const url = `/api/documents/upload?identity=${encodeURIComponent(identity)}&name=${encodeURIComponent(file.name)}`;
  const response = await fetch(url, { method: "POST", body: file, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`업로드 실패: ${response.status}`);
  }
  return response.json();
}

function formatFileSize(bytes) {
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

function manualNumberOrNull(id) {
  const raw = document.querySelector(`#${id}`).value.trim();
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

async function submitManualListing(event) {
  event.preventDefault();
  if (!state.hasServer) {
    showToast("직접 등록은 serve-web 실행 시에만 동작합니다");
    return;
  }
  const title = document.querySelector("#manualTitle").value.trim();
  const location = document.querySelector("#manualLocation").value.trim();
  if (!title || !location) {
    showToast("매물명과 지번 주소는 필수입니다");
    return;
  }
  const externalId = `d${Date.now()}`;
  const identity = `direct:${externalId}`;
  const listing = {
    source: "direct",
    external_id: externalId,
    title,
    location,
    deposit: numberValue("manualPrice"),
    monthly_rent: 0,
    area_m2: manualNumberOrNull("manualBuildingArea") ?? 0,
    floor: null,
    premium: 0,
    url: "",
    property_type: document.querySelector("#manualType").value,
    land_area_m2: manualNumberOrNull("manualLandArea"),
    building_area_m2: manualNumberOrNull("manualBuildingArea"),
    floors_total: manualNumberOrNull("manualFloors"),
    parking_spaces: manualNumberOrNull("manualParking"),
  };
  const memo = document.querySelector("#manualMemo").value.trim();
  const saved = await saveLedgerEntry(identity, listing, LEDGER_STATUSES[0], memo);
  if (!saved) return;

  const files = [...document.querySelector("#manualFiles").files];
  let uploadedCount = 0;
  for (const file of files) {
    try {
      await uploadDocument(identity, file);
      uploadedCount += 1;
    } catch {
      showToast(`"${file.name}" 업로드에 실패했습니다`);
    }
  }
  await loadDocumentCounts();
  elements.manualForm.reset();
  refreshMoneyInputs();
  elements.manualModal.close();
  renderLedger();
  showToast(
    files.length > 0
      ? `매물장에 등록했습니다 · 서류 ${uploadedCount}/${files.length}건 첨부`
      : "매물장에 등록했습니다",
  );
  document.querySelector("#ledger").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function openDocsModal(identity) {
  state.docsIdentity = identity;
  const entry = state.ledger.get(identity);
  elements.docsSubtitle.textContent = entry?.listing?.title ?? identity;
  await renderDocsList();
  elements.docsModal.showModal();
}

async function renderDocsList() {
  const identity = state.docsIdentity;
  if (!identity) return;
  try {
    const payload = await apiJson(`/api/documents?identity=${encodeURIComponent(identity)}`);
    const docs = payload.documents || [];
    elements.docsList.innerHTML = docs.length
      ? docs
          .map(
            (doc) => `
              <div class="doc-row">
                <a href="/api/documents/file?identity=${encodeURIComponent(identity)}&name=${encodeURIComponent(doc.name)}"
                  target="_blank" rel="noreferrer" title="새 탭에서 열기">📄 ${escapeHtml(doc.name)}</a>
                <span class="doc-size">${formatFileSize(doc.size)}</span>
                <button type="button" class="button ghost-danger compact" data-doc-delete="${escapeHtml(doc.name)}">삭제</button>
              </div>
            `,
          )
          .join("")
      : `<div class="empty-state">첨부된 서류가 없습니다. 아래에서 파일을 추가하세요.</div>`;
    elements.docsList.querySelectorAll("[data-doc-delete]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await apiJson("/api/documents/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ identity, name: button.dataset.docDelete }),
          });
          await loadDocumentCounts();
          renderLedger();
          await renderDocsList();
          showToast("서류를 삭제했습니다");
        } catch {
          showToast("서류 삭제에 실패했습니다");
        }
      });
    });
  } catch {
    elements.docsList.innerHTML = `<div class="empty-state">서류 목록을 불러오지 못했습니다.</div>`;
  }
}

async function addDocsFromInput(input) {
  const identity = state.docsIdentity;
  const files = [...input.files];
  if (!identity || files.length === 0) return;
  let uploaded = 0;
  for (const file of files) {
    try {
      await uploadDocument(identity, file);
      uploaded += 1;
    } catch {
      showToast(`"${file.name}" 업로드에 실패했습니다`);
    }
  }
  input.value = "";
  await loadDocumentCounts();
  renderLedger();
  await renderDocsList();
  if (uploaded > 0) {
    showToast(`서류 ${uploaded}건을 추가했습니다`);
  }
}

/* ===== 체크리스트 검토 ===== */

async function loadChecklistData() {
  if (!state.hasServer) return;
  try {
    state.checklist.definition = await apiJson("/api/checklist/definition");
    await refreshChecklistSummaries();
  } catch {
    // 검토 데이터 없이도 대시보드는 동작한다
  }
}

async function refreshChecklistSummaries() {
  if (!state.hasServer) return;
  try {
    const payload = await apiJson("/api/checklist/reviews");
    state.checklist.reviews = new Map(Object.entries(payload.reviews || {}));
  } catch {
    // 요약 로드 실패 시 기존 표시 유지
  }
}

function gradeClass(grade) {
  if (grade === "부적합") return "grade-x";
  if (grade === "A") return "grade-a";
  if (grade === "B") return "grade-b";
  if (grade === "C") return "grade-c";
  if (grade === "D") return "grade-d";
  return "grade-none";
}

function gradeBadgeHtml(identity) {
  const summary = state.checklist.reviews.get(identity);
  const grade = summary?.grade ?? null;
  const progress = summary
    ? `<span class="review-progress">자동 ${summary.progress.auto_done}/${summary.progress.auto_total} · 수동 ${summary.progress.manual_done}/${summary.progress.manual_total}</span>`
    : "";
  return `<span class="grade-badge ${gradeClass(grade)}">${escapeHtml(grade ?? "미검토")}</span>${progress}`;
}

function setGradeBadge(grade, animate) {
  const badge = elements.checklistGrade;
  badge.textContent = grade ?? "미검토";
  badge.className = `grade-badge ${gradeClass(grade)}`;
  if (animate && !reducedMotion) {
    void badge.offsetWidth; // 리플로 강제로 플립 애니메이션 재시작
    badge.classList.add("grade-flip");
  }
}

function defaultProfileFor(listing) {
  return listing.property_type === "land" || listing.floor === "토지/건물" ? "land" : "building";
}

async function openChecklistModal(identity) {
  const entry = state.ledger.get(identity);
  if (!entry) return;
  state.checklist.currentIdentity = identity;
  state.checklist.current = null;
  const listing = entry.listing || {};
  elements.checklistSubtitle.textContent = `${listing.title ?? identity} · ${listing.location ?? "-"}`;
  if (state.hasServer) {
    try {
      const payload = await apiJson(`/api/checklist/review?identity=${encodeURIComponent(identity)}`);
      state.checklist.current = payload.review;
    } catch {
      // 저장된 검토가 없으면 새로 시작
    }
  }
  elements.checklistProfile.value = state.checklist.current?.profile ?? defaultProfileFor(listing);
  // 검토 이력이 있으면 리포트부터, 처음이면 항목 체크부터 보여준다
  setChecklistView(state.checklist.current ? "report" : "items");
  renderChecklistModal(false);
  elements.checklistModal.showModal();
}

function setChecklistView(view) {
  state.checklist.view = view;
  document.querySelector("#viewReportTab").classList.toggle("active", view === "report");
  document.querySelector("#viewItemsTab").classList.toggle("active", view === "items");
  elements.checklistReport.hidden = view !== "report";
  elements.checklistSections.hidden = view !== "items";
}

/* ===== 자동 검증 연출 ===== */

const VERIFY_STEPS = [
  "주소 분석 · 필지 식별",
  "건축물대장 조회",
  "토지이용계획 · 공시지가 조회",
  "주변 실거래가 분석",
  "주변 정형외과 · 약국 조회",
  "체크리스트 판정 작성",
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function showVerifyStage() {
  elements.verifySteps.innerHTML = VERIFY_STEPS.map(
    (label) => `<li><span class="step-icon" aria-hidden="true"></span>${label}</li>`,
  ).join("");
  elements.verifyStamps.innerHTML = "";
  elements.verifyStage.hidden = false;
  document.querySelector(".checklist-view-toggle").hidden = true;
  elements.checklistReport.hidden = true;
  elements.checklistSections.hidden = true;
}

function hideVerifyStage() {
  elements.verifyStage.hidden = true;
  document.querySelector(".checklist-view-toggle").hidden = false;
}

async function animateVerifySteps(fetchPromise) {
  const steps = [...elements.verifySteps.children];
  for (let i = 0; i < steps.length - 1; i += 1) {
    steps[i].classList.add("active");
    await sleep(550);
    steps[i].classList.remove("active");
    steps[i].classList.add("done");
  }
  const last = steps[steps.length - 1];
  last.classList.add("active");
  await fetchPromise; // 실제 공공데이터 조회가 끝날 때까지 마지막 단계 유지
  last.classList.remove("active");
  last.classList.add("done");
}

async function playStampSequence(review) {
  const stamped = review.items.filter(
    (item) => (item.kind === "auto" || item.kind === "info") && item.evidence,
  );
  for (const item of stamped) {
    const [label, tone] = item.kind === "info" ? AUTO_STATUS_PILLS.info : itemStatusPill(item);
    const row = document.createElement("div");
    row.className = "stamp-row";
    row.innerHTML = `<strong>${escapeHtml(item.label)}</strong><span class="status-pill ${tone}">${label}</span>`;
    elements.verifyStamps.appendChild(row);
    elements.verifyStamps.scrollTop = elements.verifyStamps.scrollHeight;
    await sleep(300);
  }
  await sleep(450);
}

/* ===== 체크리스트 리포트 (대시보드형) ===== */

function itemStatusPill(item) {
  if (item.kind === "auto") {
    return AUTO_STATUS_PILLS[item.status] ?? AUTO_STATUS_PILLS.unknown;
  }
  if (item.status === "pass") return ["적합", "ok"];
  if (item.status === "fail") return ["부적합", "risk"];
  if (item.status === "na") return ["해당없음", "neutral"];
  return ["미체크", "neutral"];
}

function categorySummaries(items) {
  const map = new Map();
  items.forEach((item) => {
    if (!map.has(item.category)) {
      map.set(item.category, { earned: 0, possible: 0, judged: 0, total: 0 });
    }
    const cat = map.get(item.category);
    cat.total += 1;
    if (item.status === "pass") {
      cat.earned += item.weight;
      cat.possible += item.weight;
      cat.judged += 1;
    } else if (item.status === "warn") {
      cat.earned += item.weight * 0.5;
      cat.possible += item.weight;
      cat.judged += 1;
    } else if (item.status === "fail") {
      cat.possible += item.weight;
      cat.judged += 1;
    } else if (item.status === "na") {
      cat.judged += 1;
    }
  });
  return map;
}

// 항목별 경고/부적합 시 권장 대응 (없으면 일반 문구 사용)
const ACTION_HINTS = {
  parking: "법정 주차대수 부족 가능 — 용도변경 시 추가 주차 확보 방안을 구청에 확인",
  price_market: "시세 대비 고평가 — 가격 협상 여지와 최근 거래 사례 확인",
  building_age: "노후 건물 — 구조 보강·리모델링 견적을 계약 전에 확보",
  zoning: "용도지역 제한 우려 — 관할 구청에 의원 개설(용도) 가능 여부 질의",
  elevator: "승강기 없음 — 설치 가능 여부·비용 확인 (거동불편 환자 접근 필수)",
  road_access: "도로 접면 문제 — 맹지는 건축 불가, 진입로 확보 가능성 확인",
};

function buildActionItems(review) {
  const actions = [];
  const items = review.items;
  const failedCritical = items.filter((i) => i.critical && i.status === "fail");
  if (failedCritical.length > 0) {
    actions.push({
      tone: "risk",
      text: `검토 중단 권장 — 치명 항목 부적합: ${failedCritical.map((i) => i.label).join(", ")}`,
    });
  }
  items
    .filter((i) => i.critical && (i.status === "unchecked" || i.status === "unknown"))
    .forEach((i) => {
      actions.push({ tone: "need", text: `치명 항목 우선 확인: ${i.label} — 결과에 따라 즉시 탈락 여부 결정` });
    });
  items
    .filter((i) => i.status === "warn" || (i.status === "fail" && !i.critical))
    .forEach((i) => {
      actions.push({ tone: "need", text: ACTION_HINTS[i.item_id] ?? `${i.label} — 경고 사항 확인: ${i.evidence || i.description}` });
    });
  const unknownAuto = items.filter((i) => i.kind === "auto" && i.status === "unknown");
  if (unknownAuto.length > 0) {
    actions.push({
      tone: "neutral",
      text: `공공데이터로 확인 안 된 항목 ${unknownAuto.length}건 직접 확인: ${unknownAuto.map((i) => i.label).join(", ")} (세움터·토지이음)`,
    });
  }
  const unchecked = items.filter((i) => i.kind !== "auto" && i.status === "unchecked");
  if (unchecked.length > 0) {
    actions.push({ tone: "neutral", text: `수동 체크 ${unchecked.length}건 진행 — 항목 체크 탭에서 적합/부적합 판정` });
  }
  if (failedCritical.length === 0 && (review.grade === "A" || review.grade === "B")) {
    actions.push({
      tone: "ok",
      text: "다음 단계 진행: 현장 실사 → 장비업체(MRI) 실사 → 등기부 확인 → 전문가(세무·건축) 검토",
    });
  }
  return actions;
}

function renderChecklistReport() {
  const container = elements.checklistReport;
  const current = state.checklist.current;
  if (!current || current.profile !== elements.checklistProfile.value) {
    container.innerHTML = `<div class="empty-state">"자동 검증 실행"을 누르면 공공데이터 판정과 함께 리포트가 자동 생성됩니다.</div>`;
    return;
  }
  const items = current.items;
  const autoCounts = { pass: 0, warn: 0, fail: 0, unknown: 0 };
  items.filter((i) => i.kind === "auto").forEach((i) => {
    autoCounts[i.status] = (autoCounts[i.status] || 0) + 1;
  });
  const actions = buildActionItems(current);
  const cats = categorySummaries(items);
  const evidenceItems = items.filter((i) => (i.kind === "auto" || i.kind === "info") && i.evidence);
  const criticalItems = items.filter((i) => i.critical);
  const pending = items.filter((i) => i.status === "unknown" || i.status === "unchecked");

  const actionHtml = actions.length > 0
    ? actions.map((action) => `
        <li class="action-item tone-${action.tone}">
          <span class="action-dot" aria-hidden="true"></span>${escapeHtml(action.text)}
        </li>
      `).join("")
    : `<li class="action-item tone-ok"><span class="action-dot" aria-hidden="true"></span>모든 항목 판정 완료 — 추가 액션 없음</li>`;

  const catHtml = [...cats.entries()].map(([name, cat]) => {
    const pct = cat.possible > 0 ? Math.round((cat.earned / cat.possible) * 100) : null;
    const tone = pct === null ? "" : pct >= 85 ? "bar-ok" : pct >= 50 ? "bar-need" : "bar-risk";
    return `
      <div class="cat-row">
        <span class="cat-name">${escapeHtml(name)}</span>
        <div class="cat-bar"><div class="cat-bar-fill ${tone}" style="width:${pct ?? 0}%"></div></div>
        <span class="cat-meta">${pct === null ? "미판정" : `${pct}%`} · ${cat.judged}/${cat.total}</span>
      </div>
    `;
  }).join("");

  const evidenceHtml = evidenceItems.map((item) => {
    const [label, tone] = item.kind === "info" ? AUTO_STATUS_PILLS.info : itemStatusPill(item);
    return `
      <div class="evidence-card">
        <div class="evidence-head">
          <strong>${escapeHtml(item.label)}</strong>
          <span class="status-pill ${tone}">${label}</span>
        </div>
        <p>${escapeHtml(item.evidence)}</p>
      </div>
    `;
  }).join("");

  const criticalHtml = criticalItems.map((item) => {
    const [label, tone] = itemStatusPill(item);
    return `<li><span class="status-pill ${tone}">${label}</span> ${escapeHtml(item.label)}</li>`;
  }).join("");

  container.innerHTML = `
    <div class="report-kpis">
      <div class="report-kpi">
        <span class="kpi-label">종합 등급</span>
        <span class="grade-badge ${gradeClass(current.grade)}">${escapeHtml(current.grade ?? "미검토")}</span>
      </div>
      <div class="report-kpi">
        <span class="kpi-label">점수</span>
        <strong>${current.score !== null ? `${current.score}점` : "—"}</strong>
        <span class="kpi-sub">판정 항목 가중 평균</span>
      </div>
      <div class="report-kpi">
        <span class="kpi-label">자동 판정</span>
        <strong>적합 ${autoCounts.pass}</strong>
        <span class="kpi-sub">경고 ${autoCounts.warn} · 부적합 ${autoCounts.fail} · 미확인 ${autoCounts.unknown}</span>
      </div>
      <div class="report-kpi">
        <span class="kpi-label">수동 체크</span>
        <strong>${current.progress.manual_done}/${current.progress.manual_total}</strong>
        <span class="kpi-sub">남은 확인 ${pending.length}건</span>
      </div>
    </div>
    <div class="report-section report-actions">
      <h4>⚡ 추천 액션</h4>
      <ul class="action-list">${actionHtml}</ul>
    </div>
    <div class="report-section">
      <h4>카테고리별 진행</h4>
      <div class="cat-list">${catHtml}</div>
    </div>
    <div class="report-section">
      <h4>자동 검증 근거</h4>
      ${evidenceHtml
        ? `<div class="report-evidence-grid">${evidenceHtml}</div>`
        : `<div class="empty-state">자동 검증을 실행하면 공공데이터 근거가 여기에 표시됩니다.</div>`}
    </div>
    <div class="report-section">
      <h4>치명 항목 현황 <span class="kpi-sub">(하나라도 부적합이면 즉시 탈락)</span></h4>
      <ul class="critical-list">${criticalHtml}</ul>
    </div>
  `;

  if (state.checklist.reportEntrance) {
    state.checklist.reportEntrance = false;
    container.classList.add("report-enter");
    // 카테고리 바를 0%에서 목표치까지 채우는 연출
    container.querySelectorAll(".cat-bar-fill").forEach((fill) => {
      const target = fill.style.width;
      fill.style.width = "0%";
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          fill.style.width = target;
        });
      });
    });
    setTimeout(() => container.classList.remove("report-enter"), 1800);
  }
}

function checklistItemsForRender() {
  const profile = elements.checklistProfile.value;
  const current = state.checklist.current;
  if (current && current.profile === profile) {
    return current.items;
  }
  const definition = state.checklist.definition;
  if (!definition) return [];
  return definition.items
    .filter((item) => item.profiles.includes(profile))
    .map((item) => ({
      ...item,
      status: item.kind === "auto" ? "unknown" : "unchecked",
      evidence: "",
      memo: "",
    }));
}

function renderChecklistModal(animateGrade) {
  const current = state.checklist.current;
  const profileMatches = current && current.profile === elements.checklistProfile.value;
  setGradeBadge(profileMatches ? current.grade : null, animateGrade);
  elements.checklistScore.textContent =
    profileMatches && current.score !== null ? `점수 ${current.score}점` : "점수 —";
  elements.checklistProgress.textContent = profileMatches
    ? `자동 ${current.progress.auto_done}/${current.progress.auto_total} 확인 · 수동 ${current.progress.manual_done}/${current.progress.manual_total} 체크`
    : "자동 검증 실행 또는 수동 체크로 검토를 시작하세요";

  renderChecklistReport();

  const items = checklistItemsForRender();
  if (items.length === 0) {
    elements.checklistSections.innerHTML =
      `<div class="empty-state">serve-web으로 실행하면 체크리스트 검토를 사용할 수 있습니다.</div>`;
    return;
  }
  const byCategory = new Map();
  items.forEach((item) => {
    if (!byCategory.has(item.category)) byCategory.set(item.category, []);
    byCategory.get(item.category).push(item);
  });
  const manualItems = items.filter((item) => item.kind !== "auto");
  const remaining = manualItems.filter((item) => item.status === "unchecked").length;
  const bulkBar = `
    <div class="bulk-bar">
      <span class="bulk-info">수동 항목 ${manualItems.length}건 · 미체크 ${remaining}건</span>
      <div class="bulk-actions">
        <button type="button" class="button primary compact" data-bulk-evaluate>자동 검증 실행</button>
        <button type="button" class="button ghost-danger compact" data-bulk="reset">체크 초기화</button>
      </div>
    </div>
  `;
  const order = state.checklist.definition?.categories ?? CHECKLIST_CATEGORIES;
  const scrollPos = elements.checklistSections.scrollTop;
  elements.checklistSections.innerHTML = bulkBar + order
    .filter((category) => byCategory.has(category))
    .map(
      (category, index) => `
        <section class="checklist-section" style="--depth:${index}">
          <h3>${escapeHtml(category)}</h3>
          <div class="checklist-items">
            ${byCategory.get(category).map(checklistItemHtml).join("")}
          </div>
        </section>
      `,
    )
    .join("");
  elements.checklistSections.scrollTop = scrollPos;
  wireChecklistInputs();
}

function checklistItemHtml(item) {
  const critical = item.critical
    ? '<span class="critical-flag" title="치명 항목 — 부적합 시 즉시 탈락">치명</span>'
    : "";
  if (item.kind === "auto") {
    const [label, tone] = AUTO_STATUS_PILLS[item.status] ?? AUTO_STATUS_PILLS.unknown;
    return `
      <article class="checklist-item kind-auto">
        <div class="item-head">
          <strong>${escapeHtml(item.label)}</strong>${critical}
          <span class="status-pill ${tone}">${label}</span>
        </div>
        <p class="item-desc">${escapeHtml(item.description)}</p>
        ${item.evidence ? `<p class="item-evidence">${escapeHtml(item.evidence)}</p>` : ""}
      </article>
    `;
  }
  const buttons = ["pass", "fail", "na"]
    .map(
      (value) => `
        <button type="button" class="check-button check-${value}${item.status === value ? " active" : ""}"
          data-check-item="${escapeHtml(item.item_id)}" data-check-status="${value}">
          ${MANUAL_CHECK_LABELS[value]}
        </button>
      `,
    )
    .join("");
  return `
    <article class="checklist-item kind-manual">
      <div class="item-head">
        <strong>${escapeHtml(item.label)}</strong>${critical}
        <div class="check-buttons">${buttons}</div>
      </div>
      <p class="item-desc">${escapeHtml(item.description)}</p>
      ${item.evidence ? `<p class="item-evidence">${escapeHtml(item.evidence)}</p>` : ""}
      <input class="check-memo" type="text" placeholder="메모 (자동 저장)"
        value="${escapeHtml(item.memo ?? "")}" data-check-memo="${escapeHtml(item.item_id)}" />
    </article>
  `;
}

async function bulkManualCheck(mode) {
  if (!state.hasServer) {
    showToast("체크리스트 저장은 serve-web 실행 시에만 동작합니다");
    return;
  }
  const identity = state.checklist.currentIdentity;
  if (!identity) return;
  const manualItems = checklistItemsForRender().filter((item) => item.kind !== "auto");
  const status = mode === "reset" ? "unchecked" : mode;
  const targets = mode === "reset"
    ? manualItems.filter((item) => item.status !== "unchecked")
    : manualItems.filter((item) => item.status === "unchecked");
  if (targets.length === 0) {
    showToast(mode === "reset" ? "초기화할 체크가 없습니다" : "남은 미체크 항목이 없습니다");
    return;
  }
  try {
    const payload = await apiJson("/api/checklist/manual-bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identity,
        status,
        item_ids: targets.map((item) => item.item_id),
        profile: elements.checklistProfile.value,
      }),
    });
    const previousGrade = state.checklist.current?.grade;
    state.checklist.current = payload.review;
    await refreshChecklistSummaries();
    renderLedger();
    renderChecklistModal(previousGrade !== payload.review.grade);
    const labels = { pass: "적합", na: "해당없음", reset: "미체크로 초기화" };
    showToast(`${payload.updated}건을 ${labels[mode]} 처리했습니다`);
  } catch {
    showToast("일괄 체크에 실패했습니다");
  }
}

function wireChecklistInputs() {
  elements.checklistSections.querySelectorAll("[data-bulk]").forEach((button) => {
    button.addEventListener("click", () => {
      void bulkManualCheck(button.dataset.bulk);
    });
  });
  elements.checklistSections.querySelectorAll("[data-bulk-evaluate]").forEach((button) => {
    button.addEventListener("click", () => {
      void runChecklistEvaluate();
    });
  });
  elements.checklistSections.querySelectorAll("[data-check-item]").forEach((button) => {
    button.addEventListener("click", () => {
      const itemId = button.dataset.checkItem;
      // 같은 버튼을 다시 누르면 체크 해제
      const status = button.classList.contains("active") ? "unchecked" : button.dataset.checkStatus;
      const memoInput = elements.checklistSections.querySelector(`[data-check-memo="${itemId}"]`);
      void saveManualCheck(itemId, status, memoInput ? memoInput.value : "");
    });
  });
  elements.checklistSections.querySelectorAll("[data-check-memo]").forEach((input) => {
    input.addEventListener("input", () => {
      const itemId = input.dataset.checkMemo;
      clearTimeout(memoTimers.get(`check:${itemId}`));
      memoTimers.set(
        `check:${itemId}`,
        setTimeout(() => {
          const row = state.checklist.current?.items?.find((item) => item.item_id === itemId);
          const status = row && row.status !== "unknown" && row.status !== "info" ? row.status : "unchecked";
          void saveManualCheck(itemId, status, input.value, { silent: true });
        }, MEMO_SAVE_DELAY_MS),
      );
    });
  });
}

async function saveManualCheck(itemId, status, memo, options = {}) {
  if (!state.hasServer) {
    showToast("체크리스트 저장은 serve-web 실행 시에만 동작합니다");
    return;
  }
  const identity = state.checklist.currentIdentity;
  if (!identity) return;
  try {
    const payload = await apiJson("/api/checklist/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identity,
        item_id: itemId,
        status,
        memo,
        profile: elements.checklistProfile.value,
      }),
    });
    const previousGrade = state.checklist.current?.grade;
    state.checklist.current = payload.review;
    await refreshChecklistSummaries();
    renderLedger();
    if (options.silent) {
      return; // 메모 저장은 입력 포커스를 유지해야 하므로 재렌더하지 않는다
    }
    renderChecklistModal(previousGrade !== payload.review.grade);
  } catch {
    showToast("체크 저장에 실패했습니다");
  }
}

async function runChecklistEvaluate() {
  if (!state.hasServer) {
    showToast("자동 검증은 serve-web 실행 시에만 동작합니다");
    return;
  }
  const identity = state.checklist.currentIdentity;
  const entry = state.ledger.get(identity);
  if (!entry) return;
  const button = document.querySelector("#checklistEvaluateButton");
  button.disabled = true;
  const originalLabel = button.textContent;
  button.textContent = "검증 진행 중...";
  const request = apiJson("/api/checklist/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identity,
      listing: entry.listing || {},
      profile: elements.checklistProfile.value,
    }),
  });
  const cinematic = !reducedMotion;
  try {
    let payload;
    if (cinematic) {
      showVerifyStage();
      await animateVerifySteps(request); // 단계 연출 + 실제 조회 대기
      payload = await request;
      await playStampSequence(payload.review); // 판정 도장 연출
      hideVerifyStage();
    } else {
      payload = await request;
    }
    const previousGrade = state.checklist.current?.grade;
    state.checklist.current = payload.review;
    await refreshChecklistSummaries();
    renderLedger();
    // 검증이 끝나면 대시보드형 리포트를 등장 연출과 함께 보여준다
    state.checklist.reportEntrance = cinematic;
    setChecklistView("report");
    renderChecklistModal(previousGrade !== payload.review.grade);
    elements.checklistReport.scrollTop = 0;
    const errorCount = Object.keys(payload.errors || {}).length;
    showToast(
      errorCount > 0
        ? `리포트 생성 완료 — 데이터 미확인 ${errorCount}건은 수동 확인이 필요합니다`
        : "자동 검증 완료 — 리포트가 생성되었습니다",
    );
  } catch {
    if (cinematic) {
      hideVerifyStage();
      setChecklistView(state.checklist.view);
    }
    showToast("자동 검증에 실패했습니다");
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

async function switchChecklistProfile() {
  const identity = state.checklist.currentIdentity;
  if (state.hasServer && identity) {
    try {
      const payload = await apiJson(
        `/api/checklist/review?identity=${encodeURIComponent(identity)}&profile=${elements.checklistProfile.value}`,
      );
      if (payload.review) {
        state.checklist.current = payload.review;
      }
    } catch {
      // 저장된 검토가 없으면 정의 기반 빈 화면으로 진행
    }
  }
  renderChecklistModal(false);
}

/* ===== Map ===== */

function selectListingForMap(listing) {
  state.selectedListing = listing;
  elements.mapAddressInput.value = listing.location;
  elements.publicDataResult.innerHTML = "";
  void renderMap(listing);
  renderMapInfo(listing);
}

/* ===== 공공데이터 검증 ===== */

async function runPublicDataVerification() {
  if (!state.selectedListing) {
    showToast("먼저 매물을 선택하세요");
    return;
  }
  if (!state.hasServer) {
    showToast("공공데이터 검증은 serve-web 실행 시에만 동작합니다");
    return;
  }
  const button = elements.verifyPublicDataButton;
  button.disabled = true;
  const originalLabel = button.textContent;
  button.textContent = "공공데이터 조회 중...";
  try {
    const report = await apiJson("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address: state.selectedListing.location, months: 6 }),
    });
    renderPublicDataReport(report);
    applyReportToListing(report);
    showToast("공공데이터 검증이 완료되었습니다 — 아래 결과를 확인하세요");
    elements.publicDataResult.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    showToast("공공데이터 검증에 실패했습니다");
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function applyReportToListing(report) {
  const current = state.selectedListing;
  if (!current || !report) return;
  const building = report.building || {};
  const land = report.land || {};
  const fillIfEmpty = (existing, value) =>
    (existing === null || existing === undefined) && value !== null && value !== undefined
      ? value
      : existing;
  const updated = {
    ...current,
    land_area_m2: fillIfEmpty(current.land_area_m2, building.plat_area_m2),
    building_area_m2: fillIfEmpty(current.building_area_m2, building.total_area_m2),
    floors_total: fillIfEmpty(current.floors_total, building.ground_floors),
    parking_spaces: fillIfEmpty(current.parking_spaces, building.parking_spaces),
    building_coverage_ratio: fillIfEmpty(current.building_coverage_ratio, building.building_coverage_ratio),
    floor_area_ratio: fillIfEmpty(current.floor_area_ratio, building.floor_area_ratio),
    approval_year: fillIfEmpty(current.approval_year, building.approval_year),
    elevator: fillIfEmpty(
      current.elevator,
      building.elevator_count !== null && building.elevator_count !== undefined
        ? building.elevator_count > 0
        : null,
    ),
    zoning: fillIfEmpty(
      current.zoning,
      land.zoning_names && land.zoning_names.length ? land.zoning_names.join(", ") : null,
    ),
    road_access: fillIfEmpty(
      current.road_access,
      land.road_side
        ? `${land.road_side}${land.road_width_hint_m ? ` (약 ${land.road_width_hint_m}m급)` : ""}`
        : null,
    ),
  };
  state.listings = state.listings.map((item) =>
    identityOf(item) === identityOf(current) ? updated : item,
  );
  state.selectedListing = updated;
  renderMapInfo(updated);
  renderBoard();
}

function renderPublicDataReport(report) {
  const sections = [];
  const building = report.building;
  if (building) {
    sections.push(`
      <h4>건축물대장</h4>
      <dl>
        ${pdRow("건물명 · 주용도", `${building.building_name || "-"} · ${building.main_purpose || "-"}`)}
        ${pdRow("대지/연면적", `${formatArea(building.plat_area_m2)} / ${formatArea(building.total_area_m2)}`)}
        ${pdRow("층수", `지상 ${building.ground_floors ?? "-"}층 / 지하 ${building.underground_floors ?? "-"}층`)}
        ${pdRow("주차 · 승강기", `${building.parking_spaces ?? "-"}대 · ${building.elevator_count ?? "-"}대`)}
        ${pdRow("사용승인", building.approval_date || "-")}
        ${pdRow("건폐율/용적률", `${building.building_coverage_ratio ?? "-"}% / ${building.floor_area_ratio ?? "-"}%`)}
      </dl>
    `);
  }
  const land = report.land;
  if (land) {
    const price = land.official_price_per_m2
      ? `${currency.format(Math.round(land.official_price_per_m2))}원/㎡ (${land.official_price_year}년)`
      : "-";
    sections.push(`
      <h4>토지 · 용도지역</h4>
      <dl>
        ${pdRow("용도지역", (land.zoning_names || []).join(", ") || "-")}
        ${pdRow("도로접면", land.road_side ? `${land.road_side}${land.road_width_hint_m ? ` · 약 ${land.road_width_hint_m}m급` : ""}` : "-")}
        ${pdRow("이용상황 · 지형", `${land.land_use_situation || "-"} · ${land.terrain_height || "-"}`)}
        ${pdRow("개별공시지가", price)}
      </dl>
    `);
  }
  const market = report.market;
  if (market) {
    const per = (value) => (value ? `${currency.format(Math.round(value / 10000))}만원/㎡` : "-");
    const recent = (market.recent_trades || [])
      .slice(0, 3)
      .map(
        (trade) =>
          `<li>${escapeHtml(trade.deal_date)} · ${escapeHtml(trade.dong)} ${escapeHtml(trade.building_use || "")} · ${currency.format(Math.round(trade.deal_amount_won / 100000000 * 10) / 10)}억원 (${formatArea(trade.building_area_m2)})</li>`,
      )
      .join("");
    sections.push(`
      <h4>주변 실거래 (최근 ${market.months.length}개월)</h4>
      <dl>
        ${pdRow("거래 건수", `${market.trade_count}건`)}
        ${pdRow("㎡당 평균", per(market.avg_price_per_m2))}
        ${pdRow("㎡당 범위", `${per(market.min_price_per_m2)} ~ ${per(market.max_price_per_m2)}`)}
      </dl>
      ${recent ? `<ul class="trade-list">${recent}</ul>` : ""}
    `);
  }
  const errors = report.errors || {};
  const errorLabels = { address: "주소", building: "건축물대장", land: "토지정보", market: "실거래가" };
  const errorLines = Object.entries(errors)
    .map(([key, message]) => `<li><strong>${errorLabels[key] || key}</strong>: ${escapeHtml(message)}</li>`)
    .join("");
  if (errorLines) {
    sections.push(`<h4>확인 필요</h4><ul class="pd-errors">${errorLines}</ul>`);
  }
  const header = `<div class="pd-header">📋 공공데이터 검증 결과</div>`;
  elements.publicDataResult.innerHTML =
    header + (sections.join("") || `<p class="empty-state">조회된 공공데이터가 없습니다.</p>`);
}

function pdRow(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd></div>`;
}

async function renderMap(listing) {
  const address = listing.location;
  const naverMapUrl = naverMapSearchUrl(address);
  elements.naverMapLink.href = naverMapUrl;
  const newTabLink = document.querySelector("#mapNewTabLink");
  if (newTabLink) {
    newTabLink.href = naverMapUrl;
  }
  const landLink = document.querySelector("#naverLandLink");
  if (landLink) {
    // 서버가 좌표 기반 링크를 내려준 매물이면 그 링크를 우선 사용한다
    landLink.href = listing.naver_land_url
      ? safeHref(listing.naver_land_url)
      : naverLandUrl({ location: address });
  }
  // 좌표를 알면 핀이 표시되는 임베드 지도, 아니면 네이버 지도 검색 화면
  const coords = await resolveCoords(listing);
  elements.naverMapFrame.src = coords ? osmEmbedUrl(coords[0], coords[1]) : naverMapUrl;
}

function renderMapInfo(listing) {
  const addressOk = isYangcheonAddress(listing.location);
  const fit = evaluateAssetFit(listing);
  elements.mapInfoTitle.textContent = listing.title || "주소 직접 검색";
  elements.mapInfoDetails.innerHTML = [
    ["주소", escapeHtml(listing.location)],
    ["검토 구역", addressOk ? "서울 양천구 대상" : "대상 외 지역"],
    ["매물 형태", listing.floor === "토지/건물" ? "토지 또는 건물 매입 후보" : "상가/건물 사용 후보"],
    ["조건 판정", `${fit.label} (${fit.checks.map((item) => `${item.label}:${item.ok ? "OK" : "확인"}`).join(", ")})`],
    ["대지", formatArea(listing.land_area_m2)],
    ["면적", formatArea(listing.area_m2)],
    ["건평/연면적", formatArea(listing.building_area_m2)],
    ["층수", listing.floors_total ? `${escapeHtml(String(listing.floors_total))}층` : "-"],
    ["주차", listing.parking_spaces !== undefined && listing.parking_spaces !== null ? `${escapeHtml(String(listing.parking_spaces))}대` : "-"],
    ["용도지역", escapeHtml(listing.zoning || "-")],
    ["접도", escapeHtml(listing.road_access || "-")],
    ["건폐율/용적률", escapeHtml(`${listing.building_coverage_ratio ?? "-"}% / ${listing.floor_area_ratio ?? "-"}%`)],
    ["신축/매입 메모", escapeHtml(listing.buildable_note || "-")],
    ["현재 비용 정보", listing.monthly_rent > 0 ? `${money(listing.deposit)} / ${money(listing.monthly_rent)}` : "매입가 직접 입력 필요"],
    ["네이버 확인", `<a href="${escapeHtml(naverLandUrl(listing))}" target="_blank" rel="noreferrer">네이버 부동산에서 시세·매물 보기</a>`],
  ]
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  const pill = document.querySelector("#mapInfoPanel .status-pill");
  pill.textContent = addressOk ? "양천구 검토 대상" : "양천구 외 지역";
  pill.className = `status-pill ${addressOk ? "ok" : "risk"}`;
}

/* ===== Finance ===== */

function calculateEstimate() {
  const purchasePrice = numberValue("purchasePrice");
  const cashAvailable = numberValue("cashAvailable");
  const interiorBudget = numberValue("interiorBudget");
  const taxRate = Number(document.querySelector("#taxRate").value || 0);
  const brokerageRate = Number(document.querySelector("#brokerageRate").value || 0);
  const interestRate = Number(document.querySelector("#interestRate").value || 0);
  const loanYears = Number(document.querySelector("#loanYears").value || 0);

  const acquisitionTax = Math.round(purchasePrice * taxRate);
  const brokerage = Math.round(purchasePrice * brokerageRate);
  const totalCost = purchasePrice + acquisitionTax + brokerage + interiorBudget;
  // 자기자본을 먼저 쓰고 모자라는 만큼이 필요 대출액
  const loanNeeded = Math.max(0, totalCost - cashAvailable);
  const ltv = purchasePrice > 0 ? loanNeeded / purchasePrice : 0;
  const equityRatio = totalCost > 0 ? Math.min(1, cashAvailable / totalCost) : 0;

  // 원리금균등 월 상환액: P·r(1+r)^n / ((1+r)^n − 1)
  const monthlyRate = interestRate / 100 / 12;
  const months = loanYears * 12;
  let monthlyPayment = 0;
  if (loanNeeded > 0 && months > 0) {
    monthlyPayment = monthlyRate > 0
      ? (loanNeeded * monthlyRate * Math.pow(1 + monthlyRate, months)) / (Math.pow(1 + monthlyRate, months) - 1)
      : loanNeeded / months;
  }
  const totalInterest = monthlyPayment > 0 ? monthlyPayment * months - loanNeeded : 0;
  const firstMonthInterest = loanNeeded * monthlyRate;

  const pct = (value) => `${Math.round(value * 1000) / 10}%`;
  const rows = [
    ["총 취득비용 (매입+세금+중개+인테리어)", money(totalCost), true],
    ["· 취득세 추정", money(acquisitionTax), false],
    ["· 중개보수 추정", money(brokerage), false],
    ["· 인테리어·장비", money(interiorBudget), false],
    ["필요 대출액", loanNeeded > 0 ? money(loanNeeded) : "0원 — 자기자본으로 충분", true],
    ["LTV (매입가 대비 대출)", pct(ltv), false],
    [`월 상환액 (원리금균등 ${loanYears}년 · 연 ${interestRate}%)`, money(Math.round(monthlyPayment)), true],
    ["첫 달 이자", money(Math.round(firstMonthInterest)), false],
    ["총 이자 (기간 전체)", money(Math.round(totalInterest)), false],
    ["자기자본 비율 (총비용 대비)", pct(equityRatio), false],
  ];
  elements.estimateGrid.innerHTML = rows
    .map(([label, value, isKey]) => `<div${isKey ? ' class="key-row"' : ""}><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");

  const warnings = [];
  if (loanNeeded === 0) {
    warnings.push({ tone: "ok", text: "대출 없이 자기자본만으로 매입 가능한 구성입니다." });
  } else {
    if (ltv > LTV_WARN_RATIO) {
      warnings.push({
        tone: "risk",
        text: `LTV ${pct(ltv)} — 통상 담보대출 한도(매입가의 60~80%)를 초과할 수 있습니다. 메디컬론 등 신용 보강이나 자기자본 추가를 검토하세요.`,
      });
    } else if (ltv > 0.7) {
      warnings.push({
        tone: "need",
        text: `LTV ${pct(ltv)} — 담보 한도 상단에 가깝습니다. 은행 사전 한도 조회를 권합니다.`,
      });
    }
    warnings.push({
      tone: "neutral",
      text: `월 상환액 ${money(Math.round(monthlyPayment))}을 병원 월 순이익과 비교해 상환 여력을 확인하세요.`,
    });
  }
  const warningsBox = document.querySelector("#financeWarnings");
  if (warningsBox) {
    warningsBox.innerHTML = warnings
      .map((item) => `<p class="finance-note tone-${item.tone}">${escapeHtml(item.text)}</p>`)
      .join("");
  }
}

/* ===== CSV export ===== */

function exportLedgerCsv() {
  const rows = [["identity", "title", "address", "price", "status", "memo", "naver_url"]];
  [...state.ledger.values()].forEach((entry) => {
    const listing = entry.listing || {};
    rows.push([
      entry.identity,
      listing.title ?? "",
      listing.location ?? "",
      (listing.monthly_rent ?? 0) > 0 ? `${listing.deposit}/${listing.monthly_rent}` : "매입가 협의",
      entry.status,
      entry.memo ?? "",
      naverLandUrl(listing),
    ]);
  });
  downloadCsv(rows, "property-ledger.csv");
}

function downloadCsv(rows, filename) {
  const csv = rows.map((row) => row.map(escapeCsv).join(",")).join("\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function escapeCsv(value) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

/* ===== 건물·토지 조건 패널 ===== */

function setCriteriaFormValues(criteria) {
  document.querySelector("#minLandAreaInput").value = criteria.minLandArea;
  document.querySelector("#minBuildingAreaInput").value = criteria.minBuildingArea;
  document.querySelector("#minFloorsInput").value = criteria.minFloors;
  document.querySelector("#minParkingInput").value = criteria.minParking;
  document.querySelector("#elevatorInput").value = criteria.elevator;
  document.querySelector("#minApprovalYearInput").value = criteria.minApprovalYear;
  document.querySelector("#zoningInput").value = criteria.zoning.join(", ");
  document.querySelector("#minRoadWidthInput").value = criteria.minRoadWidth;
  document.querySelector("#maxCoverageInput").value = criteria.maxCoverage;
  document.querySelector("#minFarInput").value = criteria.minFar;
  document.querySelector("#landRequiredChecksInput").value = criteria.landRequiredChecks.join(", ");
  updateAreaHints();
}

function readCriteriaFormValues() {
  return {
    minLandArea: Number(document.querySelector("#minLandAreaInput").value || 0),
    minBuildingArea: Number(document.querySelector("#minBuildingAreaInput").value || 0),
    minFloors: Number(document.querySelector("#minFloorsInput").value || 0),
    minParking: Number(document.querySelector("#minParkingInput").value || 0),
    elevator: document.querySelector("#elevatorInput").value,
    minApprovalYear: Number(document.querySelector("#minApprovalYearInput").value || 0),
    zoning: splitText(document.querySelector("#zoningInput").value),
    minRoadWidth: Number(document.querySelector("#minRoadWidthInput").value || 0),
    maxCoverage: Number(document.querySelector("#maxCoverageInput").value || 0),
    minFar: Number(document.querySelector("#minFarInput").value || 0),
    landRequiredChecks: splitText(document.querySelector("#landRequiredChecksInput").value),
  };
}

function roundedPyeong(squareMeters) {
  const value = Number(squareMeters) * pyeongPerSquareMeter;
  return Number.isFinite(value) ? String(Math.round(value * 10) / 10) : "0";
}

function roundedSquareMeters(pyeong) {
  const value = Number(pyeong) / pyeongPerSquareMeter;
  return Number.isFinite(value) ? String(Math.round(value)) : "0";
}

function updateAreaHints() {
  const landValue = Number(document.querySelector("#minLandAreaInput").value || 0);
  const buildingValue = Number(document.querySelector("#minBuildingAreaInput").value || 0);
  document.querySelector("#minLandAreaPyeongInput").value = roundedPyeong(landValue);
  document.querySelector("#minBuildingAreaPyeongInput").value = roundedPyeong(buildingValue);
}

function updateSquareMetersFromPyeong(pyeongInputId, squareMeterInputId) {
  const pyeongValue = Number(document.querySelector(`#${pyeongInputId}`).value || 0);
  document.querySelector(`#${squareMeterInputId}`).value = roundedSquareMeters(pyeongValue);
}

function refreshAssetViews() {
  renderAssetCriteria();
  renderBoard();
  if (state.selectedListing) {
    renderMapInfo(state.selectedListing);
  }
}

/* ===== 3D tilt & scroll reveal ===== */

function attachTilt(cards) {
  if (reducedMotion || !finePointer) {
    return;
  }
  cards.forEach((card) => {
    let frame = null;
    card.addEventListener("pointermove", (event) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width;
        const y = (event.clientY - rect.top) / rect.height;
        const rotateY = (x - 0.5) * 10;
        const rotateX = (0.5 - y) * 8;
        card.style.transform = `rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(0)`;
        card.style.setProperty("--glare-x", `${Math.round(x * 100)}%`);
        card.style.setProperty("--glare-y", `${Math.round(y * 100)}%`);
      });
    });
    card.addEventListener("pointerleave", () => {
      if (frame) {
        cancelAnimationFrame(frame);
        frame = null;
      }
      card.style.transform = "";
    });
  });
}

function setupReveal() {
  const targets = document.querySelectorAll(".reveal");
  if (reducedMotion || !("IntersectionObserver" in window)) {
    targets.forEach((target) => target.classList.add("visible"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 },
  );
  targets.forEach((target) => observer.observe(target));
}

function setupNavHighlight() {
  const links = [...document.querySelectorAll(".nav-link")];
  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);
  if (!("IntersectionObserver" in window)) {
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((link) => {
          link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`);
        });
      });
    },
    { rootMargin: "-30% 0px -60% 0px" },
  );
  sections.forEach((section) => observer.observe(section));
}

/* ===== Reset ===== */

function resetDashboard() {
  document.querySelector("#purchasePrice").value = defaultFinanceValues.purchasePrice;
  document.querySelector("#cashAvailable").value = defaultFinanceValues.cashAvailable;
  document.querySelector("#interiorBudget").value = defaultFinanceValues.interiorBudget;
  document.querySelector("#taxRate").value = defaultFinanceValues.taxRate;
  document.querySelector("#brokerageRate").value = defaultFinanceValues.brokerageRate;
  document.querySelector("#interestRate").value = defaultFinanceValues.interestRate;
  document.querySelector("#loanYears").value = defaultFinanceValues.loanYears;
  refreshMoneyInputs();
  assetCriteria = { ...defaultAssetCriteria };
  persistCriteria();
  setCriteriaFormValues(assetCriteria);
  state.selectedListing = null;
  if (!state.hasServer) {
    applyStaticListings();
  }
  calculateEstimate();
  renderDashboard();
  elements.scanStatus.textContent = state.hasServer ? "서버 연결됨" : "초기화 완료";
  elements.scanStatus.className = "status-pill ok";
}

/* ===== Event wiring ===== */

document.querySelector("#scanButton").addEventListener("click", () => {
  void runScan();
});
document.querySelector("#resetButton").addEventListener("click", resetDashboard);
document.querySelector("#ledgerExportButton").addEventListener("click", exportLedgerCsv);
document.querySelector("#financeForm").addEventListener("input", calculateEstimate);

function setBoardFilter(filter) {
  state.boardFilter = filter;
  document.querySelectorAll("[data-board-filter]").forEach((item) => {
    item.classList.toggle("active", item.dataset.boardFilter === filter);
  });
  renderBoard();
}

document.querySelectorAll("[data-board-filter]").forEach((chip) => {
  chip.addEventListener("click", () => {
    setBoardFilter(chip.dataset.boardFilter);
  });
});

document.querySelectorAll("[data-metric-link]").forEach((panel) => {
  const goToBoard = () => {
    setBoardFilter(panel.dataset.metricLink);
    document.querySelector("#board").scrollIntoView({ behavior: "smooth", block: "start" });
  };
  panel.addEventListener("click", goToBoard);
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      goToBoard();
    }
  });
});

document.querySelector("#minLandAreaInput").addEventListener("input", updateAreaHints);
document.querySelector("#minBuildingAreaInput").addEventListener("input", updateAreaHints);
document.querySelector("#minLandAreaPyeongInput").addEventListener("input", () => {
  updateSquareMetersFromPyeong("minLandAreaPyeongInput", "minLandAreaInput");
});
document.querySelector("#minBuildingAreaPyeongInput").addEventListener("input", () => {
  updateSquareMetersFromPyeong("minBuildingAreaPyeongInput", "minBuildingAreaInput");
});
document.querySelector("#criteriaResetButton").addEventListener("click", () => {
  assetCriteria = { ...defaultAssetCriteria };
  persistCriteria();
  setCriteriaFormValues(assetCriteria);
  refreshAssetViews();
  showToast("건물·토지 조건을 기본값으로 되돌렸습니다");
});
function applyCriteriaForm(showConfirmation) {
  assetCriteria = readCriteriaFormValues();
  persistCriteria();
  refreshAssetViews();
  const note = document.querySelector("#criteriaSavedNote");
  if (note) {
    note.textContent = `✓ 저장됨 ${new Date().toLocaleTimeString("ko-KR")}`;
  }
  if (showConfirmation) {
    showToast("건물·토지 조건을 저장했습니다");
  }
}

// 입력 즉시 적용 (타이핑 중 잦은 재렌더를 막기 위해 짧게 디바운스)
let criteriaApplyTimer = null;
elements.criteriaForm.addEventListener("input", () => {
  clearTimeout(criteriaApplyTimer);
  criteriaApplyTimer = setTimeout(() => applyCriteriaForm(false), 300);
});
// 저장 버튼 — 즉시 확정 + 확인 메시지
elements.criteriaForm.addEventListener("submit", (event) => {
  event.preventDefault();
  clearTimeout(criteriaApplyTimer);
  applyCriteriaForm(true);
});
document.querySelector("#presetBuildingButton").addEventListener("click", () => {
  assetCriteria = { ...CRITERIA_PRESETS.building };
  persistCriteria();
  setCriteriaFormValues(assetCriteria);
  refreshAssetViews();
  showToast("기존 건물 프리셋을 적용했습니다");
});
document.querySelector("#presetLandButton").addEventListener("click", () => {
  assetCriteria = { ...CRITERIA_PRESETS.land };
  persistCriteria();
  setCriteriaFormValues(assetCriteria);
  refreshAssetViews();
  showToast("신축용 토지 프리셋을 적용했습니다");
});
document.querySelector("#newBannerButton").addEventListener("click", () => {
  setBoardFilter("new");
  document.querySelector("#board").scrollIntoView({ behavior: "smooth", block: "start" });
});
document.querySelector("#checklistModalClose").addEventListener("click", () => {
  elements.checklistModal.close();
});
document.querySelector("#checklistEvaluateButton").addEventListener("click", () => {
  void runChecklistEvaluate();
});
elements.checklistProfile.addEventListener("change", () => {
  void switchChecklistProfile();
});
document.querySelector("#viewReportTab").addEventListener("click", () => {
  setChecklistView("report");
});
document.querySelector("#viewItemsTab").addEventListener("click", () => {
  setChecklistView("items");
});
document.querySelector("#manualAddButton").addEventListener("click", () => {
  elements.manualModal.showModal();
});
document.querySelector("#manualModalClose").addEventListener("click", () => {
  elements.manualModal.close();
});
elements.manualForm.addEventListener("submit", (event) => {
  void submitManualListing(event);
});
document.querySelector("#docsModalClose").addEventListener("click", () => {
  elements.docsModal.close();
});
document.querySelector("#docsAddFiles").addEventListener("change", (event) => {
  void addDocsFromInput(event.target);
});

document.querySelector("#mapSearchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const address = elements.mapAddressInput.value.trim();
  selectListingForMap({
    source: "manual",
    external_id: "manual-address",
    title: "직접 입력 주소",
    location: address,
    deposit: 0,
    monthly_rent: 0,
    area_m2: "-",
    floor: "토지/건물",
    premium: 0,
    url: naverMapSearchUrl(address),
  });
});
elements.verifyPublicDataButton.addEventListener("click", () => {
  void runPublicDataVerification();
});
document.querySelector("#reloadMapButton").addEventListener("click", () => {
  const current = elements.naverMapFrame.src;
  elements.naverMapFrame.src = "about:blank";
  setTimeout(() => {
    elements.naverMapFrame.src = current;
  }, 100);
});
document.querySelector("#copyAddressButton").addEventListener("click", async () => {
  if (!state.selectedListing) {
    return;
  }
  await navigator.clipboard.writeText(state.selectedListing.location);
  showToast("주소를 복사했습니다");
});
document.querySelector("#useFinanceButton").addEventListener("click", () => {
  if (!state.selectedListing) {
    return;
  }
  const basePrice = state.selectedListing.monthly_rent > 0
    ? Math.max(500000000, state.selectedListing.deposit * 8)
    : 1000000000;
  document.querySelector("#purchasePrice").value = String(basePrice);
  calculateEstimate();
  document.querySelector("#finance").scrollIntoView({ behavior: "smooth", block: "start" });
});
/* ===== Boot ===== */

setupReveal();
setupNavHighlight();
setupMoneyInputs();
setCriteriaFormValues(assetCriteria);
attachTilt(document.querySelectorAll(".metric-panel"));

try {
  const serverAvailable = await loadServerListings();
  if (serverAvailable) {
    elements.scanStatus.textContent = "서버 연결됨";
    elements.scanStatus.className = "status-pill ok";
  } else {
    applyStaticListings();
    document.querySelector("#mailNote").textContent =
      "정적 모드입니다. serve-web으로 실행하면 관심매물·매물장이 서버에 저장되고 Gmail 알림이 동작합니다.";
  }
  await loadFavorites();
  await loadLedger();
  await loadChecklistData();
  await loadDocumentCounts();
} catch {
  elements.scanStatus.textContent = "초기 로드 실패";
  elements.scanStatus.className = "status-pill risk";
  showToast("대시보드 초기 로드 중 오류가 발생했습니다.");
}
renderDashboard();
calculateEstimate();
