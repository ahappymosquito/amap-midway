// 本文件实现多点选址交互：网页定位、单起点搜索、地点历史、扫街榜与酒店属性/床型筛选、美团/携程外链、地铁末段出站骑行。
const state = {
  map: null,
  originMarkers: [],
  overlapCircles: [],
  markers: [],
  metroMarkers: [],
  viaMarkers: [],
  metroLineOverlays: [],
  routeOverlays: [],
  infoWindow: null,
  places: [],
  origins: [],
  metroStations: [],
  metroLines: [],
  selectedPlaceId: null,
  originCount: 1,
  routeToken: 0,
  travelMode: "transit",
  selectedPlanIndex: {},
  routeCache: {},
  activeRoutes: [],
  boardFilter: "all",
  hotelAttrFilter: "all",
  bedTypeFilter: "all",
  lastCategory: "",
  pulseTimer: null,
  focusedOriginIndex: 0,
  rankingUrl: "",
};

const elements = {
  meetForm: document.querySelector("#meetForm"),
  originsList: document.querySelector("#originsList"),
  locateButton: document.querySelector("#locateButton"),
  addOriginButton: document.querySelector("#addOriginButton"),
  peopleInput: document.querySelector("#peopleInput"),
  budgetInput: document.querySelector("#budgetInput"),
  budgetHint: document.querySelector("#budgetHint"),
  budgetLabelText: document.querySelector("#budgetLabelText"),
  meetSearchButton: document.querySelector("#meetSearchButton"),
  message: document.querySelector("#message"),
  mapStatus: document.querySelector("#mapStatus"),
  routePanel: document.querySelector("#routePanel"),
  boardBar: document.querySelector("#boardBar"),
  mapLegend: document.querySelector("#mapLegend"),
  resultCount: document.querySelector("#resultCount"),
  resultsList: document.querySelector("#resultsList"),
  moreResults: document.querySelector("#moreResults"),
  moreResultsSummary: document.querySelector("#moreResultsSummary"),
  moreResultsList: document.querySelector("#moreResultsList"),
  originHistory: document.querySelector("#originHistory"),
  originHistoryBar: document.querySelector("#originHistoryBar"),
};

const HOTEL_ATTRS = [
  ["hotspring", "温泉"],
  ["esports", "电竞"],
  ["exclusive", "独家"],
  ["huazhu", "华住会"],
  ["parent_child", "亲子"],
  ["homestay", "民宿"],
];
const HOTEL_BED_TYPES = [
  ["king", "大床房"],
  ["twin", "双床房"],
  ["family", "家庭房"],
  ["suite", "套房"],
];
const ORIGIN_COLORS = ["#0f766e", "#c2410c", "#7c3aed", "#0369a1", "#b45309", "#be185d"];
const RECOMMEND_COUNT = 3;
const MIN_ORIGINS = 1;
const MAX_ORIGINS = 6;
const WALK_COLOR = "#94a3b8";
const RIDING_COLOR = "#15803d";
const LAST_MILE_WALK_MAX_M = 400;
const LAST_MILE_WALK_MAX_S = 240;
const RIDING_SPEED_MPS = 3.5;
const WALK_SPEED_MPS = 1.25;
const ORIGIN_LAST_KEY = "amap_find.last_origins";
const ORIGIN_HISTORY_KEY = "amap_find.origin_history";
const LAST_FORM_KEY = "amap_find.last_form";
const ORIGIN_HISTORY_LIMIT = 24;
const BUS_COLOR = "#0f766e";
const METRO_LINE_COLORS = {
  "1号线": "#c23a30",
  八通线: "#c23a30",
  "2号线": "#004b87",
  "4号线": "#008c8c",
  大兴线: "#008c8c",
  "5号线": "#aa0061",
  "6号线": "#b58500",
  "7号线": "#ffc56e",
  "8号线": "#009b6b",
  "9号线": "#97d700",
  "10号线": "#0092bc",
  "11号线": "#ee697a",
  "12号线": "#c45a1e",
  "13号线": "#f9e300",
  "14号线": "#ca9a8e",
  "15号线": "#65318e",
  "16号线": "#6ba539",
  "17号线": "#00a9ce",
  "19号线": "#d6a461",
  亦庄线: "#e94724",
  房山线: "#d86018",
  昌平线: "#de82b3",
  燕房线: "#d86018",
  机场线: "#a192b2",
  首都机场线: "#a192b2",
  大兴机场线: "#004ea2",
  西郊线: "#d41367",
  S1线: "#b35a1f",
};
const LINE_NAME_RE =
  /(?:地铁)?(首都机场线|大兴机场线|机场线|亦庄线|房山线|昌平线|燕房线|西郊线|八通线|大兴线|S1线|\d+号线(?:支线)?)/g;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  restoreLastForm();
  renderOriginInputs([]);
  bindControls();
  updateBudgetHint();
  renderOriginHistory();
  try {
    const config = await fetchJson("/api/config");
    if (!config.amap_key_configured || !config.amap_js_key) {
      setMessage("缺少 AMAP_WEB_KEY 环境变量。配置后重启服务即可加载地图。", true);
      return;
    }
    await loadAmapScript(config.amap_js_key);
    initMap();
    if (elements.locateButton) {
      elements.locateButton.disabled = true;
      elements.locateButton.textContent = "定位中…";
    }
    const located = await locateCurrentPosition();
    if (located && !originAHasUserInput()) {
      applyCurrentPosition(located);
      setMessage("已按大致位置填入地点 A，可改或再添加其他人的地点。");
      elements.mapStatus.textContent = "已定位到大致位置，至少一个地点即可搜索餐馆或酒店";
      return;
    }
    if (!originAHasUserInput()) {
      restoreSavedOrigins();
      setMessage("至少一个地点即可搜索。可点「使用当前位置」或手动填写。");
    } else if (!located) {
      setMessage("未能自动定位，将使用你填写的地点。");
    }
  } finally {
    if (elements.locateButton) {
      elements.locateButton.disabled = false;
      elements.locateButton.textContent = "使用当前位置";
    }
  }
}

function bindControls() {
  if (elements.locateButton) {
    elements.locateButton.addEventListener("click", async () => {
      await locateAndFill({ announce: true });
    });
  }
  elements.addOriginButton.addEventListener("click", () => {
    if (state.originCount >= MAX_ORIGINS) {
      return;
    }
    state.originCount += 1;
    renderOriginInputs();
    persistOriginDraft();
  });
  elements.peopleInput.addEventListener("input", () => {
    updateBudgetHint();
    persistLastForm();
  });
  elements.budgetInput.addEventListener("input", () => {
    updateBudgetHint();
    persistLastForm();
  });
  document.querySelectorAll('input[name="category"]').forEach((input) => {
    input.addEventListener("change", () => {
      updateBudgetHint();
      persistLastForm();
    });
  });
  if (elements.originHistoryBar) {
    elements.originHistoryBar.addEventListener("click", (event) => {
      const clearButton = event.target.closest("[data-clear-history]");
      if (clearButton) {
        writeStorage(ORIGIN_HISTORY_KEY, []);
        renderOriginHistory();
        return;
      }
      const chip = event.target.closest("[data-history-place]");
      if (chip) {
        fillOriginFromHistory(chip.dataset.historyPlace);
      }
    });
  }
  elements.meetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await searchMeet();
  });
  elements.routePanel.addEventListener("click", (event) => {
    const modeButton = event.target.closest("[data-travel-mode]");
    if (modeButton) {
      setTravelMode(modeButton.dataset.travelMode);
      return;
    }
    const planButton = event.target.closest("[data-plan-index]");
    if (planButton) {
      const originIndex = Number(planButton.dataset.originIndex);
      const planIndex = Number(planButton.dataset.planIndex);
      state.selectedPlanIndex[originIndex] = planIndex;
      updateSchemeButtons();
      renderSelectedDetails();
      drawActiveScheme();
    }
  });
  elements.routePanel.addEventListener("mouseover", (event) => {
    const button = event.target.closest("[data-plan-index], [data-ride-detail]");
    if (button) {
      previewRouteDetail(button);
    }
  });
  elements.routePanel.addEventListener("mouseout", (event) => {
    if (!elements.routePanel.contains(event.relatedTarget)) {
      renderSelectedDetails();
    }
  });
  if (elements.boardBar) {
    elements.boardBar.addEventListener("click", (event) => {
      const attrChip = event.target.closest("[data-hotel-attr]");
      if (attrChip) {
        setHotelAttrFilter(attrChip.dataset.hotelAttr);
        return;
      }
      const bedChip = event.target.closest("[data-bed-type]");
      if (bedChip) {
        setBedTypeFilter(bedChip.dataset.bedType);
        return;
      }
      const chip = event.target.closest("[data-board]");
      if (chip) {
        setBoardFilter(chip.dataset.board);
      }
    });
  }
}

function readOriginRows() {
  return [...elements.originsList.querySelectorAll("input")].map((input) => originRowFromInput(input));
}

function originRowFromInput(input) {
  const lng = Number(input.dataset.lng);
  const lat = Number(input.dataset.lat);
  return {
    address: input.value.trim(),
    lng: Number.isFinite(lng) ? lng : null,
    lat: Number.isFinite(lat) ? lat : null,
  };
}

function renderOriginInputs(presetRows) {
  const previous = Array.isArray(presetRows) ? presetRows : readOriginRows();
  elements.originsList.innerHTML = "";
  for (let index = 0; index < state.originCount; index += 1) {
    const label = document.createElement("label");
    const letter = originLetter(index);
    const canRemove = state.originCount > MIN_ORIGINS && index >= 1;
    const placeholder = index === 0 ? "我的位置或地点 A" : `输入地点 ${letter}`;
    label.innerHTML = `
      地点 ${letter}
      <span class="origin-row">
        <input type="text" name="origin-${letter}" data-origin-index="${index}" list="originHistory" autocomplete="on" placeholder="${placeholder}" />
        ${canRemove ? `<button type="button" class="remove-origin" data-remove-index="${index}">删除</button>` : ""}
      </span>
    `;
    const input = label.querySelector("input");
    const row = previous[index] || {};
    input.value = row.address || "";
    if (Number.isFinite(row.lng) && Number.isFinite(row.lat)) {
      input.dataset.lng = String(row.lng);
      input.dataset.lat = String(row.lat);
    }
    input.addEventListener("input", () => {
      delete input.dataset.lng;
      delete input.dataset.lat;
      persistOriginDraft();
    });
    input.addEventListener("change", () => {
      persistOriginDraft();
      rememberOriginHistory();
    });
    input.addEventListener("focus", () => {
      state.focusedOriginIndex = index;
    });
    elements.originsList.appendChild(label);
  }
  elements.originsList.querySelectorAll("[data-remove-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.removeIndex);
      const values = readOriginRows();
      values.splice(index, 1);
      state.originCount = Math.max(MIN_ORIGINS, values.length);
      renderOriginInputs(values);
      persistOriginDraft();
    });
  });
  elements.addOriginButton.disabled = state.originCount >= MAX_ORIGINS;
}

function originAHasUserInput() {
  const input = document.querySelector("input[data-origin-index='0']");
  return Boolean(input && input.value.trim());
}

function restoreSavedOrigins() {
  const saved = loadLastOrigins();
  if (!saved.length) {
    state.originCount = MIN_ORIGINS;
    renderOriginInputs([]);
    return;
  }
  state.originCount = Math.min(MAX_ORIGINS, Math.max(MIN_ORIGINS, saved.length));
  renderOriginInputs(saved.map((address) => ({ address, lng: null, lat: null })));
}

async function locateAndFill({ announce = false } = {}) {
  if (!window.AMap) {
    if (announce) {
      setMessage("地图尚未加载，无法定位。", true);
    }
    return null;
  }
  if (elements.locateButton) {
    elements.locateButton.disabled = true;
    elements.locateButton.textContent = "定位中…";
  }
  try {
    const located = await locateCurrentPosition();
    if (!located) {
      if (announce) {
        setMessage("未能取得大致位置，请检查定位权限，或手动填写地点。", true);
      }
      return null;
    }
    applyCurrentPosition(located);
    if (announce) {
      setMessage("已按大致位置填入地点 A，可改成更精确的地点。");
    }
    return located;
  } finally {
    if (elements.locateButton) {
      elements.locateButton.disabled = false;
      elements.locateButton.textContent = "使用当前位置";
    }
  }
}

function applyCurrentPosition(located) {
  const rows = readOriginRows();
  rows[0] = { address: located.address, lng: located.lng, lat: located.lat };
  state.originCount = Math.max(state.originCount, MIN_ORIGINS);
  renderOriginInputs(rows);
  persistOriginDraft();
}

function locateCurrentPosition() {
  return new Promise((resolve) => {
    if (!window.AMap?.plugin) {
      resolve(null);
      return;
    }
    window.AMap.plugin(["AMap.Geolocation"], () => {
      const geolocation = new window.AMap.Geolocation({
        enableHighAccuracy: false,
        timeout: 8000,
        convert: true,
        getCityWhenFail: true,
        needAddress: true,
        showButton: false,
        showMarker: false,
        showCircle: false,
        panToLocation: false,
        zoomToAccuracy: false,
      });
      geolocation.getCurrentPosition((status, result) => {
        if (status !== "complete" || !result?.position) {
          resolve(null);
          return;
        }
        const lng = typeof result.position.getLng === "function" ? result.position.getLng() : result.position.lng;
        const lat = typeof result.position.getLat === "function" ? result.position.getLat() : result.position.lat;
        if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
          resolve(null);
          return;
        }
        const ready = (address) => resolve({ lng, lat, address: address || "当前位置" });
        const formatted = addressFromGeoResult(result);
        if (formatted) {
          ready(formatted);
          return;
        }
        reverseAddress(lng, lat).then(ready);
      });
    });
  });
}

function addressFromGeoResult(result) {
  if (!result || typeof result !== "object") {
    return "";
  }
  const direct = result.formattedAddress || result.formatted_address || "";
  if (direct) {
    return String(direct);
  }
  const component = result.addressComponent || result.address_component || {};
  return [component.province, component.city, component.district, component.township, component.street, component.streetNumber || component.street_number]
    .map((item) => String(item || "").trim())
    .filter((item, index, list) => item && list.indexOf(item) === index)
    .join("");
}

function reverseAddress(lng, lat) {
  return new Promise((resolve) => {
    if (!window.AMap?.plugin) {
      resolve("");
      return;
    }
    window.AMap.plugin(["AMap.Geocoder"], () => {
      const geocoder = new window.AMap.Geocoder();
      geocoder.getAddress([lng, lat], (status, result) => {
        if (status === "complete" && result?.regeocode?.formattedAddress) {
          resolve(result.regeocode.formattedAddress);
          return;
        }
        resolve("");
      });
    });
  });
}

function persistOriginDraft() {
  const values = collectOriginValues();
  writeStorage(ORIGIN_LAST_KEY, values);
}

function persistLastForm() {
  writeStorage(LAST_FORM_KEY, {
    category: getCategory(),
    people: Number(elements.peopleInput.value) || 2,
    budget: Number(elements.budgetInput.value) || 300,
  });
}

function restoreLastForm() {
  const form = readStorage(LAST_FORM_KEY, null);
  if (!form || typeof form !== "object") {
    return;
  }
  if (form.people) {
    elements.peopleInput.value = String(form.people);
  }
  if (form.budget) {
    elements.budgetInput.value = String(form.budget);
  }
  if (form.category === "hotel" || form.category === "restaurant") {
    const radio = document.querySelector(`input[name="category"][value="${form.category}"]`);
    if (radio) {
      radio.checked = true;
    }
  }
}

function collectOriginValues() {
  return [...elements.originsList.querySelectorAll("input")].map((input) => input.value.trim()).filter(Boolean);
}

function loadLastOrigins() {
  const saved = readStorage(ORIGIN_LAST_KEY, []);
  return Array.isArray(saved) ? saved.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function rememberOriginHistory(extraNames) {
  const current = loadOriginHistory();
  const incoming = [...collectOriginValues(), ...(extraNames || [])]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  const merged = [];
  for (const name of [...incoming, ...current]) {
    if (!merged.some((item) => item === name)) {
      merged.push(name);
    }
  }
  writeStorage(ORIGIN_HISTORY_KEY, merged.slice(0, ORIGIN_HISTORY_LIMIT));
  renderOriginHistory();
}

function loadOriginHistory() {
  const saved = readStorage(ORIGIN_HISTORY_KEY, []);
  return Array.isArray(saved) ? saved.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function renderOriginHistory() {
  const history = loadOriginHistory();
  if (elements.originHistory) {
    elements.originHistory.innerHTML = history
      .map((name) => `<option value="${escapeHtml(name)}"></option>`)
      .join("");
  }
  if (!elements.originHistoryBar) {
    return;
  }
  if (!history.length) {
    elements.originHistoryBar.hidden = true;
    elements.originHistoryBar.innerHTML = "";
    return;
  }
  const chips = history
    .slice(0, 12)
    .map(
      (name) =>
        `<button type="button" class="history-chip" data-history-place="${escapeHtml(name)}">${escapeHtml(name)}</button>`,
    )
    .join("");
  elements.originHistoryBar.hidden = false;
  elements.originHistoryBar.innerHTML = `
    <div class="history-head">
      <span>最近用过</span>
      <button type="button" class="history-clear" data-clear-history>清除</button>
    </div>
    <div class="history-chips">${chips}</div>
  `;
}

function fillOriginFromHistory(name) {
  const inputs = [...elements.originsList.querySelectorAll("input")];
  if (!inputs.length || !name) {
    return;
  }
  const empty = inputs.find((input) => !input.value.trim());
  const focused =
    Number.isInteger(state.focusedOriginIndex) && inputs[state.focusedOriginIndex]
      ? inputs[state.focusedOriginIndex]
      : null;
  const target = empty || focused || inputs[0];
  target.value = name;
  delete target.dataset.lng;
  delete target.dataset.lat;
  persistOriginDraft();
  target.focus();
}

function readStorage(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    /* 隐私模式或配额满时忽略 */
  }
}

function updateBudgetHint() {
  const people = Number(elements.peopleInput.value) || 2;
  const budget = Number(elements.budgetInput.value) || 300;
  const category = getCategory();
  if (category === "hotel") {
    if (elements.budgetLabelText) {
      elements.budgetLabelText.textContent = "人均差标（元）";
    }
    elements.budgetHint.textContent = `${people} 人合计 ${people * budget} 元。酒店按高德人均/参考价比较，无价格则请核价。`;
    return;
  }
  if (elements.budgetLabelText) {
    elements.budgetLabelText.textContent = "人均预算（元）";
  }
  elements.budgetHint.textContent = `按餐馆人均比较，预算 ${budget} 元。无人均则请到美团/点评核价。`;
}

function loadAmapScript(key) {
  return new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&plugin=AMap.Transfer,AMap.Riding,AMap.Scale,AMap.ToolBar,AMap.Geolocation,AMap.Geocoder`;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("高德 JS API 加载失败，请检查 Key、网络和域名白名单。"));
    document.head.appendChild(script);
  });
}

function initMap() {
  state.map = new AMap.Map("map", {
    zoom: 12,
    center: [116.448, 39.974],
    resizeEnable: true,
    viewMode: "2D",
  });
  state.infoWindow = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -28) });
  state.map.addControl(new AMap.Scale());
  state.map.addControl(new AMap.ToolBar({ position: "RT" }));
}

async function searchMeet() {
  if (!state.map) {
    setMessage("地图尚未加载，无法搜索。", true);
    return;
  }
  const origins = collectOrigins();
  if (origins.length < MIN_ORIGINS) {
    setMessage("请至少填写一个地点。", true);
    return;
  }
  setBusy(true);
  try {
    const result = await fetchJson("/api/places/search", {
      method: "POST",
      body: JSON.stringify({
        origins,
        category: getCategory(),
        people_count: Number(elements.peopleInput.value) || 2,
        budget_per_person: Number(elements.budgetInput.value) || 300,
      }),
    });
    clearOverlay();
    state.origins = result.origins;
    state.places = result.places;
    state.metroStations = result.metro_stations || [];
    state.metroLines = [];
    state.selectedPlaceId = null;
    state.routeCache = {};
    state.activeRoutes = [];
    state.selectedPlanIndex = {};
    state.boardFilter = "all";
    state.hotelAttrFilter = "all";
    state.bedTypeFilter = "all";
    state.lastCategory = result.category || "";
    state.rankingUrl = result.amap_ranking_url || "";
    persistOriginDraft();
    persistLastForm();
    rememberOriginHistory((result.origins || []).map((item) => item.formatted_address));
    cacheRecommendedRoutes(result.places.slice(0, RECOMMEND_COUNT));
    drawOrigins(result.radius_m);
    drawMetroNetwork();
    renderBoardBar(result.category);
    renderPlaces();
    renderLegend([]);
    const categoryLabel = result.category === "hotel" ? "酒店" : "餐馆";
    const cityLabel = result.origins[0]?.city ? `，城市 ${result.origins[0].city}` : "";
    const rangeLabel = result.origins.length === 1 ? "附近" : "之间";
    elements.mapStatus.textContent = `${result.origins.length} 个地点${rangeLabel}，${formatDistance(result.radius_m)} 范围${cityLabel}`;
    setMessage(
      result.places.length
        ? `找到 ${result.places.length} 个${categoryLabel}。前 ${Math.min(RECOMMEND_COUNT, result.places.length)} 名已预规划路线，点选后只显示一种出行方案。`
        : `当前范围内未找到${categoryLabel}。`,
    );
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setBusy(false);
  }
}

function collectOrigins() {
  return readOriginRows()
    .filter((row) => row.address || (row.lng != null && row.lat != null))
    .map((row) => {
      const origin = {};
      if (row.address) {
        origin.address = row.address;
      }
      if (row.lng != null && row.lat != null) {
        origin.lng = row.lng;
        origin.lat = row.lat;
      }
      return origin;
    });
}

function cacheRecommendedRoutes(places) {
  places.forEach((place) => {
    if (place.origin_routes?.length) {
      state.routeCache[place.id] = normalizeOriginRoutes(place.origin_routes);
    }
  });
}

function drawOrigins(radius) {
  state.originMarkers = state.origins.map((origin, index) => {
    return new AMap.Marker({
      position: [origin.lng, origin.lat],
      content: pinHtml(originLetter(index), "origin", ORIGIN_COLORS[index % ORIGIN_COLORS.length]),
      offset: new AMap.Pixel(-14, -14),
      title: origin.formatted_address,
      zIndex: 130,
    });
  });
  state.overlapCircles = state.origins.map((origin, index) => {
    return new AMap.Circle({
      center: [origin.lng, origin.lat],
      radius,
      strokeColor: ORIGIN_COLORS[index % ORIGIN_COLORS.length],
      strokeWeight: 1,
      fillColor: ORIGIN_COLORS[index % ORIGIN_COLORS.length],
      fillOpacity: 0.04,
      zIndex: 8,
    });
  });
  state.markers = state.places.map((place, index) => {
    const marker = new AMap.Marker({
      position: [place.lng, place.lat],
      content: pinHtml(String(index + 1), placePinKind(place)),
      offset: new AMap.Pixel(-14, -14),
      title: place.name,
      zIndex: 120,
    });
    marker.on("click", () => selectPlace(place.id));
    return marker;
  });
  state.map.add([...state.originMarkers, ...state.overlapCircles, ...state.markers]);
  state.map.setFitView([...state.originMarkers, ...state.overlapCircles], false, [48, 48, 48, 48]);
}

function drawMetroNetwork() {
  clearMetroNetwork();
  state.metroLineOverlays = [];
  state.metroMarkers = (state.metroStations || []).map((station) => {
    return new AMap.Marker({
      position: [station.lng, station.lat],
      content: metroPinHtml(station, false),
      offset: new AMap.Pixel(-12, -12),
      title: `${station.name} ${(station.lines || []).join("/")}`,
      zIndex: 90,
    });
  });
  if (state.metroMarkers.length) {
    state.map.add(state.metroMarkers);
  }
}

function renderPlaces() {
  elements.resultsList.innerHTML = "";
  elements.moreResultsList.innerHTML = "";
  const visible = visiblePlaces();
  elements.resultCount.textContent = `${visible.length} 个`;
  const recommended = visible.slice(0, RECOMMEND_COUNT);
  const rest = visible.slice(RECOMMEND_COUNT);
  recommended.forEach((place) => elements.resultsList.appendChild(placeItem(place, state.places.indexOf(place))));
  rest.forEach((place) => elements.moreResultsList.appendChild(placeItem(place, state.places.indexOf(place))));
  elements.moreResults.hidden = rest.length === 0;
  elements.moreResultsSummary.textContent = `其余 ${rest.length} 个结果`;
  applyBoardVisibility();
}

function visiblePlaces() {
  return state.places.filter((place) => placeMatchesFilters(place));
}

function placeMatchesFilters(place) {
  if ((place.category || state.lastCategory) === "hotel") {
    if (state.hotelAttrFilter !== "all" && !(place.hotel_attrs || []).includes(state.hotelAttrFilter)) {
      return false;
    }
    if (state.bedTypeFilter !== "all" && !(place.bed_types || []).includes(state.bedTypeFilter)) {
      return false;
    }
    return true;
  }
  if (state.boardFilter === "all") {
    return true;
  }
  return place.board === state.boardFilter;
}

function placePinKind(place) {
  if (place.over_budget) {
    return "over";
  }
  if (place.board === "champion") {
    return "champion";
  }
  if (place.board === "street") {
    return "street";
  }
  if (place.board === "select") {
    return "select";
  }
  const hotelAttr = (place.hotel_attrs || [])[0];
  if (hotelAttr === "hotspring" || hotelAttr === "esports" || hotelAttr === "huazhu") {
    return hotelAttr;
  }
  return "place";
}

function renderBoardBar(category) {
  if (!elements.boardBar) {
    return;
  }
  const ranking = state.rankingUrl || "https://www.amap.com/ranking/";
  if (category === "hotel") {
    const rankingLink = `<a class="board-link" href="${escapeHtml(ranking)}" target="_blank" rel="noopener">在高德打开必住榜</a>`;
    const attrChips = HOTEL_ATTRS.map(([key, label]) => {
      const count = state.places.filter((item) => (item.hotel_attrs || []).includes(key)).length;
      const active = state.hotelAttrFilter === key ? " active" : "";
      return `<button type="button" class="board-chip${active}" data-hotel-attr="${key}">${label} ${count}</button>`;
    }).join("");
    const bedChips = HOTEL_BED_TYPES.map(([key, label]) => {
      const count = state.places.filter((item) => (item.bed_types || []).includes(key)).length;
      const active = state.bedTypeFilter === key ? " active" : "";
      return `<button type="button" class="board-chip${active}" data-bed-type="${key}">${label} ${count}</button>`;
    }).join("");
    elements.boardBar.hidden = false;
    elements.boardBar.innerHTML = `
      <div class="board-group">
        <span class="board-group-label">酒店属性</span>
        <button type="button" class="board-chip${state.hotelAttrFilter === "all" ? " active" : ""}" data-hotel-attr="all">全部</button>
        ${attrChips}
      </div>
      <div class="board-group">
        <span class="board-group-label">一级床型</span>
        <button type="button" class="board-chip${state.bedTypeFilter === "all" ? " active" : ""}" data-bed-type="all">不限</button>
        ${bedChips}
      </div>
      ${rankingLink}
    `;
    return;
  }
  if (category !== "restaurant") {
    elements.boardBar.hidden = true;
    elements.boardBar.innerHTML = "";
    return;
  }
  const rankingLink = `<a class="board-link" href="${escapeHtml(ranking)}" target="_blank" rel="noopener">在高德打开扫街榜</a>`;
  const championCount = state.places.filter((item) => item.board === "champion").length;
  const streetCount = state.places.filter((item) => item.board === "street").length;
  const selectCount = state.places.filter((item) => item.board === "select").length;
  elements.boardBar.hidden = false;
  elements.boardBar.innerHTML = `
    <button type="button" class="board-chip${state.boardFilter === "all" ? " active" : ""}" data-board="all">全部</button>
    <button type="button" class="board-chip${state.boardFilter === "champion" ? " active" : ""}" data-board="champion">状元榜 ${championCount}</button>
    <button type="button" class="board-chip${state.boardFilter === "street" ? " active" : ""}" data-board="street">烟火小店 ${streetCount}</button>
    <button type="button" class="board-chip${state.boardFilter === "select" ? " active" : ""}" data-board="select">极致甄选 ${selectCount}</button>
    ${rankingLink}
  `;
}

function setBoardFilter(board) {
  state.boardFilter = board || "all";
  renderBoardBar(state.lastCategory || "restaurant");
  renderPlaces();
}

function setHotelAttrFilter(value) {
  state.hotelAttrFilter = value || "all";
  renderBoardBar("hotel");
  renderPlaces();
}

function setBedTypeFilter(value) {
  state.bedTypeFilter = value || "all";
  renderBoardBar("hotel");
  renderPlaces();
}

function applyBoardVisibility() {
  state.markers.forEach((marker, index) => {
    const place = state.places[index];
    const show = placeMatchesFilters(place || {});
    if (show) {
      marker.show?.();
    } else {
      marker.hide?.();
    }
    const root = marker.dom || marker.getOverlayDom?.();
    if (root && root.style) {
      root.style.display = show ? "" : "none";
    }
  });
}

function placeItem(place, index) {
  const item = document.createElement("li");
  item.className = `result-item${place.over_budget ? " over-budget" : ""}`;
  item.tabIndex = 0;
  item.dataset.id = place.id;
  const costLabel = "人均";
  const boardBadge = filterBadges(place);
  const badge = place.over_budget
    ? `<span class="badge warn">超差标</span>`
    : place.budget_unknown
      ? `<span class="badge warn">请核价</span>`
      : `<span class="badge">${place.cost ? `${costLabel}¥${place.cost}` : "达标"}</span>`;
  const commuteLines = (place.commutes || [])
    .map((commute, commuteIndex) => {
      return `<div class="commute-line">${originLetter(commuteIndex)} 地铁 ${formatDuration(commute.transit_s)} · 骑行 ${formatDuration(commute.riding_s)}</div>`;
    })
    .join("");
  const costMeta = place.cost ? ` · ${costLabel} ¥${place.cost}` : place.category === "restaurant" ? " · 暂无人均" : " · 暂无人均";
  item.innerHTML = `
    <div class="result-title">
      <span>${index + 1}. ${escapeHtml(place.name)}</span>
      <span class="result-badges">${boardBadge}${badge}</span>
    </div>
    <div class="address">${escapeHtml(place.address || "暂无详细地址")}</div>
    <div class="meta">${place.rating ? `评分 ${escapeHtml(place.rating)}` : "暂无评分"}${costMeta}</div>
    ${commuteLines}
    <div class="open-links">${renderOpenLinks(place)}</div>
  `;
  item.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      return;
    }
    selectPlace(place.id);
  });
  return item;
}

function filterBadges(place) {
  if (place.board === "champion") {
    return `<span class="badge">状元榜</span>`;
  }
  if (place.board === "street") {
    return `<span class="badge">烟火小店</span>`;
  }
  if (place.board === "select") {
    return `<span class="badge">极致甄选</span>`;
  }
  const labels = [];
  for (const [key, label] of HOTEL_ATTRS) {
    if ((place.hotel_attrs || []).includes(key)) {
      labels.push(label);
    }
  }
  for (const [key, label] of HOTEL_BED_TYPES) {
    if ((place.bed_types || []).includes(key)) {
      labels.push(label);
    }
  }
  return labels.slice(0, 3).map((label) => `<span class="badge">${escapeHtml(label)}</span>`).join("");
}

function isDesktop() {
  const ua = navigator.userAgent || "";
  if (/Android|iPhone|iPad|iPod|Mobile/i.test(ua)) {
    return false;
  }
  return window.innerWidth >= 768;
}

function renderOpenLinks(place) {
  const links = place.open_links;
  const amap = isDesktop() ? links.amap : links.amap_app || links.amap;
  const items = [
    ["在高德打开", amap],
    ["在美团看价", links.meituan],
  ];
  if (links.amap_board) {
    items.push(["在扫街榜看", links.amap_board]);
  }
  if (place.category === "hotel" && links.ctrip) {
    items.push(["在携程看价", links.ctrip]);
  }
  if (place.category === "restaurant" && links.dianping) {
    items.push(["在点评看价", links.dianping]);
  }
  return items
    .map(([label, href]) => `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">${label}</a>`)
    .join("");
}

async function selectPlace(id) {
  const place = state.places.find((item) => item.id === id);
  if (!place) {
    return;
  }
  state.selectedPlaceId = id;
  state.selectedPlanIndex = {};
  document.querySelectorAll(".result-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.id === id);
  });
  const tags = filterBadges(place);
  state.infoWindow.setContent(`
    <div class="info-card">
      <strong>${escapeHtml(place.name)}</strong>
      ${tags ? `<div class="info-tags">${tags}</div>` : ""}
      <div>${escapeHtml(place.address || "暂无详细地址")}</div>
      <div class="open-links">${renderOpenLinks(place)}</div>
    </div>
  `);
  state.infoWindow.open(state.map, [place.lng, place.lat]);
  const token = (state.routeToken += 1);
  const cached = state.routeCache[id];
  if (cached?.length) {
    state.activeRoutes = cached;
    if (token !== state.routeToken) {
      return;
    }
    renderRoutePanel();
    drawActiveScheme();
    if (!needsRouteEnrich(cached)) {
      return;
    }
  } else {
    elements.mapStatus.textContent = `正在规划「${place.name}」的出行方案...`;
  }
  const routes = await loadAllOriginRoutes(place);
  if (token !== state.routeToken) {
    return;
  }
  state.routeCache[id] = mergeOriginRoutes(cached, routes);
  state.activeRoutes = state.routeCache[id];
  renderRoutePanel();
  drawActiveScheme();
}

function needsRouteEnrich(routes) {
  return (routes || []).some((route) => !(route.transit_plans || []).length);
}

function mergeOriginRoutes(cached, fresh) {
  const base = cached?.length ? cached : fresh;
  return (fresh || []).map((route, index) => {
    const old = base[index] || {};
    const transitPlans = (route.transit_plans || []).length ? route.transit_plans : old.transit_plans || [];
    const ridingPath = (route.riding_path || []).length ? route.riding_path : old.riding_path || [];
    return {
      transit_plans: transitPlans,
      riding_s: route.riding_s ?? old.riding_s,
      riding_path: ridingPath,
    };
  });
}

async function loadAllOriginRoutes(place) {
  const city = transferCity(state.origins[0]?.city || "北京");
  return Promise.all(state.origins.map((origin) => loadOriginRoute(origin, place, city)));
}

function setTravelMode(mode) {
  if (mode !== "transit" && mode !== "riding") {
    return;
  }
  state.travelMode = mode;
  drawActiveScheme();
  renderRoutePanel();
}

function drawActiveScheme() {
  clearRouteOverlays();
  const place = state.places.find((item) => item.id === state.selectedPlaceId);
  if (!place || !state.activeRoutes.length) {
    return;
  }
  const overlays = [];
  const legendLines = state.metroLines.map((line) => line.name);
  state.activeRoutes.forEach((route, originIndex) => {
    if (state.travelMode === "riding") {
      overlays.push(...buildRidingOverlay(route));
      return;
    }
    const plan = selectedTransitPlan(route, originIndex);
    if (!plan) {
      return;
    }
    overlays.push(...buildTransitOverlays(plan));
    legendLines.push(...(plan.segments || []).map((segment) => segment.line).filter(Boolean));
  });
  state.routeOverlays = overlays.filter(Boolean);
  if (state.routeOverlays.length) {
    state.map.add(state.routeOverlays);
    startRoutePulse();
  }
  drawViaStations();
  renderLegend([...new Set(legendLines)]);
  const modeLabel = state.travelMode === "riding" ? "骑行" : "地铁";
  elements.mapStatus.textContent = state.routeOverlays.length
    ? `正在显示「${place.name}」的${modeLabel}方案，可在左上角切换`
    : `未获取到「${place.name}」的${modeLabel}折线，仍可查看时长`;
  const selectedMarker = state.markers.find((_, markerIndex) => state.places[markerIndex]?.id === place.id);
  const fitTargets = [...state.originMarkers, selectedMarker, ...state.routeOverlays].filter(Boolean);
  if (fitTargets.length) {
    state.map.setFitView(fitTargets, false, [80, 80, 80, 80]);
  }
}

function selectedTransitPlan(route, originIndex) {
  const plans = route.transit_plans || [];
  if (!plans.length) {
    return null;
  }
  const index = Number.isInteger(state.selectedPlanIndex[originIndex]) ? state.selectedPlanIndex[originIndex] : 0;
  return plans[Math.min(Math.max(index, 0), plans.length - 1)];
}

function buildTransitOverlays(plan) {
  const overlays = [];
  for (const segment of plan.segments || []) {
    const path = segment.path || [];
    if (path.length < 2) {
      continue;
    }
    const mode = String(segment.mode || "").toUpperCase();
    const subway = isSubwayMode(mode);
    const color = subway
      ? lineColor(segment.line)
      : mode === "RIDING"
        ? RIDING_COLOR
        : mode === "WALK"
          ? WALK_COLOR
          : BUS_COLOR;
    overlays.push(glowPolyline(path, subway ? 16 : 12, subway ? 58 : 52));
    overlays.push(
      new AMap.Polyline({
        path,
        strokeColor: color,
        strokeWeight: subway ? 9 : 6,
        strokeOpacity: 1,
        strokeStyle: subway ? "solid" : "dashed",
        strokeDasharray: subway ? undefined : [8, 6],
        isOutline: true,
        outlineColor: "#111827",
        borderWeight: 3,
        lineJoin: "round",
        lineCap: "round",
        zIndex: subway ? 80 : 70,
        showDir: true,
      }),
    );
    overlays[overlays.length - 1]._pulse = true;
  }
  return overlays;
}

function buildRidingOverlay(route) {
  if ((route.riding_path || []).length < 2) {
    return [];
  }
  const path = route.riding_path;
  const line = new AMap.Polyline({
    path,
    strokeColor: RIDING_COLOR,
    strokeWeight: 8,
    strokeOpacity: 1,
    strokeStyle: "dashed",
    strokeDasharray: [12, 8],
    isOutline: true,
    outlineColor: "#111827",
    borderWeight: 3,
    lineJoin: "round",
    lineCap: "round",
    zIndex: 75,
    showDir: true,
  });
  line._pulse = true;
  return [glowPolyline(path, 14, 55), line];
}

function glowPolyline(path, weight, zIndex) {
  return new AMap.Polyline({
    path,
    strokeColor: "#f8fafc",
    strokeWeight: weight,
    strokeOpacity: 0.72,
    lineJoin: "round",
    lineCap: "round",
    zIndex,
    extData: { glow: true },
  });
}

function startRoutePulse() {
  stopRoutePulse();
  let bright = true;
  state.pulseTimer = window.setInterval(() => {
    bright = !bright;
    state.routeOverlays.forEach((line) => {
      if (line._pulse) {
        line.setOptions({ strokeOpacity: bright ? 1 : 0.42 });
      }
    });
  }, 1200);
}

function stopRoutePulse() {
  if (state.pulseTimer) {
    window.clearInterval(state.pulseTimer);
    state.pulseTimer = null;
  }
}

async function loadOriginRoute(origin, place, city) {
  let transitPlans = [];
  let riding = { riding_s: null, path: [] };
  try {
    const start = new AMap.LngLat(origin.lng, origin.lat);
    const end = new AMap.LngLat(place.lng, place.lat);
    const [transitResult, ridingResult] = await Promise.all([
      searchPlanner(createTransfer(city), start, end),
      searchPlanner(createRiding(), [origin.lng, origin.lat], [place.lng, place.lat]),
    ]);
    transitPlans = extractTransitPlans(transitResult);
    riding = extractRiding(ridingResult);
  } catch (error) {
    transitPlans = [];
    riding = { riding_s: null, path: [] };
  }
  if (!transitPlans.length || !riding.path.length) {
    const fallback = await fetchRoute(origin, place, city);
    if (fallback) {
      if (!transitPlans.length && fallback.transit_plans?.length) {
        transitPlans = normalizeTransitPlans(fallback.transit_plans);
      } else if (!transitPlans.length && fallback.transit_segments?.length) {
        transitPlans = [
          {
            duration_s: fallback.transit_s,
            summary: planSummaryFromSegments(fallback.transit_segments),
            segments: backendSegments(fallback.transit_segments),
          },
        ];
      }
      if (!riding.path.length && fallback.riding_path?.length) {
        riding = { riding_s: fallback.riding_s, path: backendPath(fallback.riding_path) };
      } else if (fallback.riding_s != null && riding.riding_s == null) {
        riding.riding_s = fallback.riding_s;
      }
    }
  }
  return {
    transit_plans: transitPlans,
    riding_s: riding.riding_s,
    riding_path: riding.path,
  };
}

function createTransfer(city) {
  return new AMap.Transfer({
    city,
    cityd: city,
    nightflag: false,
    hideMarkers: true,
    autoFitView: false,
  });
}

function createRiding() {
  return new AMap.Riding({
    hideMarkers: true,
    autoFitView: false,
    policy: 0,
  });
}

function searchPlanner(planner, start, end) {
  return new Promise((resolve) => {
    try {
      planner.search(start, end, (status, result) => {
        resolve(status === "complete" ? result : null);
      });
    } catch (error) {
      resolve(null);
    }
  });
}

function extractTransitPlans(result) {
  const plans = [];
  for (const plan of (result?.plans || []).slice(0, 3)) {
    const extracted = extractOneTransitPlan(plan);
    if (extracted.segments.some((segment) => (segment.path || []).length >= 2)) {
      plans.push(extracted);
    }
  }
  return plans;
}

function extractOneTransitPlan(plan) {
  const seconds = Number(plan.time);
  const segments = (plan.segments || []).map((segment) => {
    const mode = String(segment.transit_mode || "").toUpperCase();
    const line = isSubwayMode(mode) ? segmentLineName(segment) : "";
    const duration = Number(segment.time);
    return {
      mode,
      line,
      duration_s: Number.isFinite(duration) ? duration : null,
      path: segmentPath(segment),
      stations: extractSegmentStations(segment, line),
    };
  });
  if (!segments.some((segment) => segment.path.length >= 2)) {
    const whole = normalizePath(plan.path);
    if (whole.length >= 2) {
      segments.push({ mode: "SUBWAY", line: "", path: whole, stations: [] });
    }
  }
  return fillPlanStats({
    duration_s: Number.isFinite(seconds) ? seconds : null,
    summary: planSummaryFromSegments(segments),
    segments,
  });
}

function extractRiding(result) {
  const route = result?.routes?.[0];
  if (!route) {
    return { riding_s: null, path: [] };
  }
  const seconds = Number(route.time);
  const path = [];
  for (const ride of route.rides || []) {
    path.push(...normalizePath(ride.path));
  }
  if (!path.length) {
    path.push(...normalizePath(route.path));
  }
  if (!path.length) {
    for (const step of route.steps || []) {
      path.push(...normalizePath(step.path));
    }
  }
  return {
    riding_s: Number.isFinite(seconds) ? seconds : null,
    path,
  };
}

function segmentPath(segment) {
  const transit = segment.transit || {};
  const walking = segment.walking || {};
  const candidates = [transit.path, segment.path, walking.path];
  for (const raw of candidates) {
    const path = normalizePath(raw);
    if (path.length >= 2) {
      return path;
    }
  }
  const stepPaths = [...(walking.steps || []), ...(transit.steps || [])].flatMap((step) => normalizePath(step.path));
  if (stepPaths.length >= 2) {
    return stepPaths;
  }
  const stops = [
    transit.origin,
    transit.on_station?.location,
    ...((transit.via_stops || []).map((stop) => stop.location)),
    transit.off_station?.location,
    transit.destination,
  ];
  return stops.map(lngLatToPair).filter(Boolean);
}

function segmentLineName(segment) {
  const transit = segment.transit || {};
  const lineObj = (transit.lines || [])[0] || {};
  const names = parseLineNames([lineObj.name, transit.name, segment.instruction].filter(Boolean).join(" "));
  return names[0] || "";
}

function extractSegmentStations(segment, line) {
  const transit = segment.transit || {};
  const stops = [transit.on_station, ...(transit.via_stops || []), transit.off_station].filter(Boolean);
  return stops
    .map((stop) => {
      const pair = lngLatToPair(stop.location);
      if (!pair) {
        return null;
      }
      return {
        name: String(stop.name || "地铁站").replace(/（地铁站）|\(地铁站\)|地铁站$/g, ""),
        lng: pair[0],
        lat: pair[1],
        lines: line ? [line] : parseLineNames(stop.name || ""),
      };
    })
    .filter(Boolean);
}

function normalizeOriginRoutes(routes) {
  return (routes || []).map((route) => ({
    transit_plans: normalizeTransitPlans(route.transit_plans),
    riding_s: route.riding_s,
    riding_path: backendPath(route.riding_path),
  }));
}

function normalizeTransitPlans(plans) {
  return (plans || []).map((plan) =>
    fillPlanStats({
      duration_s: plan.duration_s,
      summary: plan.summary || planSummaryFromSegments(plan.segments || []),
      walking_s: plan.walking_s,
      metro_s: plan.metro_s,
      transfer_s: plan.transfer_s,
      transfer_count: plan.transfer_count || 0,
      lastmile_s: plan.lastmile_s,
      lastmile_mode: plan.lastmile_mode || "",
      legs: plan.legs || [],
      segments: backendSegments(plan.segments),
    }),
  );
}

function backendSegments(segments) {
  return (segments || []).map((segment) => ({
    mode: segment.mode,
    line: segment.line || "",
    duration_s: segment.duration_s,
    path: backendPath(segment.path),
    stations: segment.stations || [],
  }));
}

function backendPath(points) {
  return (points || [])
    .map((point) => {
      if (Array.isArray(point) && point.length >= 2) {
        return [Number(point[0]), Number(point[1])];
      }
      return [Number(point?.lng), Number(point?.lat)];
    })
    .filter((pair) => Number.isFinite(pair[0]) && Number.isFinite(pair[1]));
}

function planSummaryFromSegments(segments) {
  const names = [];
  for (const segment of segments || []) {
    const mode = String(segment.mode || "").toUpperCase();
    if (mode === "WALK") {
      continue;
    }
    const label = segment.line || (mode === "BUS" ? "公交" : "");
    if (label && !names.includes(label)) {
      names.push(label);
    }
  }
  return names.join(" → ") || "公交地铁";
}

async function fetchRoute(origin, place, city) {
  try {
    return await fetchJson(
      `/api/places/route?origin_lng=${origin.lng}&origin_lat=${origin.lat}` +
        `&dest_lng=${place.lng}&dest_lat=${place.lat}&city=${encodeURIComponent(city)}`,
    );
  } catch (error) {
    return null;
  }
}

function renderRoutePanel() {
  const place = state.places.find((item) => item.id === state.selectedPlaceId);
  if (!place || !state.activeRoutes.length) {
    elements.routePanel.hidden = true;
    elements.routePanel.innerHTML = "";
    return;
  }
  const transitActive = state.travelMode === "transit";
  const originBlocks = state.activeRoutes
    .map((route, originIndex) => {
      const origin = state.origins[originIndex];
      const label = `${originLetter(originIndex)} · ${origin?.formatted_address || ""}`;
      if (!transitActive) {
        return `
          <div class="time-row" data-origin-block="${originIndex}">
            <div class="time-label">${escapeHtml(label)}</div>
            <div class="scheme-options">
              <button type="button" class="scheme-option active" disabled data-ride-detail="1" data-origin-index="${originIndex}">骑行 ${formatDuration(route.riding_s)}</button>
            </div>
            <div class="scheme-detail" data-detail-slot="${originIndex}"></div>
          </div>
        `;
      }
      const selected = Number.isInteger(state.selectedPlanIndex[originIndex]) ? state.selectedPlanIndex[originIndex] : 0;
      const options = (route.transit_plans || [])
        .map((plan, planIndex) => {
          const active = planIndex === selected ? " active" : "";
          return `<button type="button" class="scheme-option${active}" data-origin-index="${originIndex}" data-plan-index="${planIndex}">
            ${formatDuration(plan.duration_s)} · ${escapeHtml(plan.summary || "地铁")}
          </button>`;
        })
        .join("");
      return `
        <div class="time-row" data-origin-block="${originIndex}">
          <div class="time-label">${escapeHtml(label)}</div>
          <div class="scheme-options">${options || `<span class="scheme-empty">暂无地铁方案</span>`}</div>
          <div class="scheme-detail" data-detail-slot="${originIndex}"></div>
        </div>
      `;
    })
    .join("");
  elements.routePanel.hidden = false;
  elements.routePanel.innerHTML = `
    <div class="mode-switch" role="tablist" aria-label="出行方案">
      <button type="button" class="${transitActive ? "active" : ""}" data-travel-mode="transit">地铁</button>
      <button type="button" class="${transitActive ? "" : "active"}" data-travel-mode="riding">骑行</button>
    </div>
    ${originBlocks}
  `;
  renderSelectedDetails();
}

function updateSchemeButtons() {
  elements.routePanel.querySelectorAll("[data-plan-index]").forEach((button) => {
    const originIndex = Number(button.dataset.originIndex);
    const planIndex = Number(button.dataset.planIndex);
    const selected = Number.isInteger(state.selectedPlanIndex[originIndex]) ? state.selectedPlanIndex[originIndex] : 0;
    button.classList.toggle("active", planIndex === selected);
  });
}

function renderSelectedDetails() {
  state.activeRoutes.forEach((route, originIndex) => {
    if (state.travelMode === "riding") {
      fillDetailSlot(originIndex, ridingDetailHtml(route.riding_s));
      return;
    }
    const plan = selectedTransitPlan(route, originIndex);
    fillDetailSlot(originIndex, plan ? planDetailHtml(fillPlanStats(plan)) : "");
  });
}

function previewRouteDetail(button) {
  const originIndex = Number(button.dataset.originIndex);
  if (button.dataset.rideDetail) {
    fillDetailSlot(originIndex, ridingDetailHtml(state.activeRoutes[originIndex]?.riding_s));
    return;
  }
  const planIndex = Number(button.dataset.planIndex);
  const plan = state.activeRoutes[originIndex]?.transit_plans?.[planIndex];
  if (plan) {
    fillDetailSlot(originIndex, planDetailHtml(fillPlanStats(plan)));
  }
}

function fillDetailSlot(originIndex, html) {
  const slot = elements.routePanel.querySelector(`[data-detail-slot="${originIndex}"]`);
  if (slot) {
    slot.innerHTML = html;
  }
}

function ridingDetailHtml(seconds) {
  return `<div class="detail-block"><table class="route-detail-table"><caption>全程骑行</caption><tr><th>骑行</th><td>${formatDuration(seconds)}</td></tr></table></div>`;
}

function planDetailHtml(plan) {
  const lastmileLabel = plan.lastmile_mode === "RIDING" ? "骑行" : "走路";
  const lastmileValue = plan.lastmile_mode === "RIDING" ? plan.lastmile_s : plan.walking_s;
  const legs = (plan.legs || [])
    .map((leg) => `<tr><th>${escapeHtml(leg.label)}</th><td>${formatDuration(leg.duration_s)}</td></tr>`)
    .join("");
  return `
    <div class="detail-block">
      <table class="route-detail-table">
        <caption>${escapeHtml(plan.summary || "出行方案")}</caption>
        <tr><th>地铁</th><td>${formatDuration(plan.metro_s)}</td></tr>
        <tr><th>${lastmileLabel}</th><td>${formatDuration(lastmileValue)}</td></tr>
        <tr><th>换乘</th><td>${formatDuration(plan.transfer_s)}${plan.transfer_count ? `（${plan.transfer_count} 次）` : ""}</td></tr>
      </table>
    </div>
    <div class="detail-total"><span>合计</span><strong>${formatDuration(plan.duration_s)}</strong></div>
    <div class="detail-block">
      <table class="route-detail-table">
        ${legs || `<tr><th>分段</th><td>暂无</td></tr>`}
      </table>
    </div>
  `;
}

function fillPlanStats(plan) {
  if (!plan.legs?.length) {
    const segments = plan.segments || [];
    let walking = 0;
    let metro = 0;
    let transfer = 0;
    let transferCount = 0;
    const legs = [];
    segments.forEach((segment, index) => {
      const mode = String(segment.mode || "").toUpperCase();
      const duration = Number(segment.duration_s);
      const amount = Number.isFinite(duration) ? duration : 0;
      if (mode === "WALK") {
        walking += amount;
        const prevRide = segments.slice(0, index).some((item) => isTransitMode(item.mode));
        const nextRide = segments.slice(index + 1).some((item) => isTransitMode(item.mode));
        let label = "步行";
        if (prevRide && nextRide) {
          transfer += amount;
          transferCount += 1;
          label = "换乘步行";
        } else if (!prevRide) {
          label = "步行到站";
        } else {
          label = "步行到店";
        }
        legs.push({ label, mode: "WALK", duration_s: Number.isFinite(duration) ? duration : null });
      } else if (mode === "RIDING") {
        legs.push({
          label: segment.line || "骑行到店",
          mode: "RIDING",
          duration_s: Number.isFinite(duration) ? duration : null,
        });
      } else if (isSubwayMode(mode)) {
        metro += amount;
        legs.push({ label: segment.line || "地铁", mode: "SUBWAY", duration_s: Number.isFinite(duration) ? duration : null });
      } else {
        legs.push({ label: segment.line || (mode === "BUS" ? "公交" : mode), mode, duration_s: Number.isFinite(duration) ? duration : null });
      }
    });
    plan.walking_s = walking || plan.walking_s || null;
    plan.metro_s = metro || plan.metro_s || null;
    plan.transfer_s = transfer || plan.transfer_s || null;
    plan.transfer_count = transferCount;
    plan.legs = legs;
  }
  return applyLastMile(plan);
}

function applyLastMile(plan) {
  if (plan.lastmile_mode === "RIDING" || plan.lastmile_mode === "WALK") {
    return plan;
  }
  const segments = plan.segments || [];
  const lastIndex = lastMileWalkIndex(segments);
  if (lastIndex == null) {
    const lastRide = [...segments].reverse().find((item) => String(item.mode || "").toUpperCase() === "RIDING");
    if (lastRide) {
      plan.lastmile_mode = "RIDING";
      plan.lastmile_s = lastRide.duration_s ?? null;
    }
    return plan;
  }
  const segment = segments[lastIndex];
  const walkS = Number(segment.duration_s) || 0;
  const distanceM = pathLengthM(segment.path);
  if (isShortLastMile(walkS, distanceM)) {
    plan.lastmile_mode = "WALK";
    plan.lastmile_s = walkS || null;
    return plan;
  }
  const rideS = estimateRideSeconds(walkS, distanceM);
  if (Number.isFinite(Number(plan.duration_s))) {
    plan.duration_s = Math.max(0, Number(plan.duration_s) - walkS + rideS);
  }
  const remainingWalk = Math.max(0, (Number(plan.walking_s) || 0) - walkS);
  plan.walking_s = remainingWalk || null;
  plan.lastmile_mode = "RIDING";
  plan.lastmile_s = rideS;
  segment.mode = "RIDING";
  segment.duration_s = rideS;
  if (plan.legs?.[lastIndex]) {
    plan.legs[lastIndex] = { label: "骑行到店", mode: "RIDING", duration_s: rideS };
  }
  return plan;
}

function lastMileWalkIndex(segments) {
  let lastIndex = null;
  segments.forEach((segment, index) => {
    if (String(segment.mode || "").toUpperCase() !== "WALK") {
      return;
    }
    const prevTransit = segments.slice(0, index).some((item) => isTransitMode(item.mode));
    const nextTransit = segments.slice(index + 1).some((item) => isTransitMode(item.mode));
    if (prevTransit && !nextTransit) {
      lastIndex = index;
    }
  });
  return lastIndex;
}

function isShortLastMile(walkS, distanceM) {
  if (distanceM > 0) {
    return distanceM <= LAST_MILE_WALK_MAX_M;
  }
  return walkS <= LAST_MILE_WALK_MAX_S;
}

function estimateRideSeconds(walkS, distanceM) {
  if (distanceM > 0) {
    return Math.max(20, Math.round(distanceM / RIDING_SPEED_MPS));
  }
  if (walkS > 0) {
    return Math.max(20, Math.round((walkS * WALK_SPEED_MPS) / RIDING_SPEED_MPS));
  }
  return 20;
}

function pathLengthM(path) {
  let total = 0;
  for (let index = 1; index < (path || []).length; index += 1) {
    const prev = pointLngLat(path[index - 1]);
    const curr = pointLngLat(path[index]);
    if (prev && curr) {
      total += haversineM(prev[0], prev[1], curr[0], curr[1]);
    }
  }
  return total;
}

function pointLngLat(point) {
  if (Array.isArray(point) && point.length >= 2) {
    const lng = Number(point[0]);
    const lat = Number(point[1]);
    return Number.isFinite(lng) && Number.isFinite(lat) ? [lng, lat] : null;
  }
  const lng = Number(point?.lng);
  const lat = Number(point?.lat);
  return Number.isFinite(lng) && Number.isFinite(lat) ? [lng, lat] : null;
}

function haversineM(lng1, lat1, lng2, lat2) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371008.8 * Math.asin(Math.sqrt(a));
}

function isTransitMode(mode) {
  const value = String(mode || "").toUpperCase();
  return value !== "" && value !== "WALK" && value !== "RIDING";
}

function renderLegend(lineNames) {
  if (!elements.mapLegend) {
    return;
  }
  const unique = [];
  for (const name of lineNames || []) {
    if (name && !unique.includes(name)) {
      unique.push(name);
    }
  }
  const lineItems = unique
    .map((name) => {
      const color = lineColor(name);
      return `<span class="legend-item" style="--swatch:${color}">${escapeHtml(name)}</span>`;
    })
    .join("");
  const modeItem =
    state.selectedPlaceId && state.travelMode === "riding"
      ? `<span class="legend-item mode-riding">当前：全程骑行</span>`
      : selectedPlansHaveLastRide()
        ? `<span class="legend-item mode-riding">出站骑行</span>`
        : `<span class="legend-item mode-walk">步行换乘</span>`;
  elements.mapLegend.innerHTML = `${modeItem}${lineItems}`;
}

function pinHtml(text, kind, color) {
  const background = color || (kind === "over" ? "#94a3b8" : "#334155");
  return `<div class="map-pin ${kind}" style="background:${background}">${text}</div>`;
}

function metroPinHtml(station, via = false) {
  const lines = station.lines || [];
  const label = escapeHtml(station.name);
  const lineText = escapeHtml(lines.join("/"));
  return `<div class="metro-pin${via ? " via" : ""}" title="${via ? "途经 " : ""}${label} ${lineText}">
    <span class="metro-dot" style="${metroDotStyle(lines)}"></span>
    ${via ? `<span class="metro-via">途</span>` : ""}
    <span class="metro-name">${label}</span>
  </div>`;
}

function drawViaStations() {
  clearViaMarkers();
  if (state.travelMode !== "transit") {
    return;
  }
  const stations = [];
  const seen = new Set();
  state.activeRoutes.forEach((route, originIndex) => {
    const plan = selectedTransitPlan(route, originIndex);
    for (const segment of plan?.segments || []) {
      for (const stop of segment.stations || []) {
        const key = `${stop.name}|${Number(stop.lng).toFixed(4)}|${Number(stop.lat).toFixed(4)}`;
        if (seen.has(key) || stop.lng == null || stop.lat == null) {
          continue;
        }
        seen.add(key);
        stations.push(stop);
      }
    }
  });
  state.viaMarkers = stations.map((station) => {
    return new AMap.Marker({
      position: [station.lng, station.lat],
      content: metroPinHtml(station, true),
      offset: new AMap.Pixel(-12, -18),
      title: `途经 ${station.name}`,
      zIndex: 100,
    });
  });
  if (state.viaMarkers.length) {
    state.map.add(state.viaMarkers);
  }
}

function clearViaMarkers() {
  if (state.viaMarkers.length && state.map) {
    state.map.remove(state.viaMarkers);
  }
  state.viaMarkers = [];
}

function metroDotStyle(lines) {
  const colors = (lines.length ? lines : [""]).map(lineColor);
  if (colors.length === 1) {
    return `background:${colors[0]}`;
  }
  const step = 100 / colors.length;
  const stops = colors.map((color, index) => `${color} ${index * step}% ${(index + 1) * step}%`).join(",");
  return `background:conic-gradient(${stops})`;
}

function parseLineNames(text) {
  const names = [];
  const source = String(text || "");
  LINE_NAME_RE.lastIndex = 0;
  let match = LINE_NAME_RE.exec(source);
  while (match) {
    if (!names.includes(match[1])) {
      names.push(match[1]);
    }
    match = LINE_NAME_RE.exec(source);
  }
  return names;
}

function lineColor(name) {
  const key = String(name || "").replace(/^地铁/, "");
  if (METRO_LINE_COLORS[key]) {
    return METRO_LINE_COLORS[key];
  }
  if (!key) {
    return "#2563eb";
  }
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = (hash * 31 + key.charCodeAt(index)) >>> 0;
  }
  const hues = [12, 32, 48, 162, 188, 208, 258, 312];
  return `hsl(${hues[hash % hues.length]} 68% 38%)`;
}

function selectedPlansHaveLastRide() {
  return state.activeRoutes.some((route, originIndex) => {
    const plan = selectedTransitPlan(route, originIndex);
    return plan?.lastmile_mode === "RIDING";
  });
}

function isSubwayMode(mode) {
  return mode === "SUBWAY" || mode === "METRO" || mode === "METRO_RAIL";
}

function lngLatToPair(value) {
  if (!value) {
    return null;
  }
  if (Array.isArray(value) && value.length >= 2 && typeof value[0] === "number") {
    return [value[0], value[1]];
  }
  if (typeof value.getLng === "function" && typeof value.getLat === "function") {
    return [value.getLng(), value.getLat()];
  }
  if (typeof value.lng === "number" && typeof value.lat === "number") {
    return [value.lng, value.lat];
  }
  if (typeof value === "string" && value.includes(",")) {
    const [lngText, latText] = value.split(",", 2);
    const lng = Number(lngText);
    const lat = Number(latText);
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      return [lng, lat];
    }
  }
  return null;
}

function normalizePath(raw) {
  if (!raw) {
    return [];
  }
  if (typeof raw === "string") {
    return raw.split(";").map(lngLatToPair).filter(Boolean);
  }
  if (!Array.isArray(raw)) {
    const one = lngLatToPair(raw);
    return one ? [one] : [];
  }
  const path = [];
  for (const item of raw) {
    if (Array.isArray(item) && item.length && Array.isArray(item[0])) {
      path.push(...normalizePath(item));
    } else {
      const pair = lngLatToPair(item);
      if (pair) {
        path.push(pair);
      }
    }
  }
  return path;
}

function clearOverlay() {
  state.routeToken += 1;
  clearRouteOverlays();
  clearMetroNetwork();
  const leftovers = [...state.originMarkers, ...state.overlapCircles, ...state.markers];
  if (leftovers.length && state.map) {
    state.map.remove(leftovers);
  }
  state.originMarkers = [];
  state.overlapCircles = [];
  state.markers = [];
  state.metroStations = [];
  state.metroLines = [];
  state.activeRoutes = [];
  if (state.infoWindow) {
    state.infoWindow.close();
  }
  elements.routePanel.hidden = true;
  elements.routePanel.innerHTML = "";
  if (elements.boardBar) {
    elements.boardBar.hidden = true;
    elements.boardBar.innerHTML = "";
  }
  renderLegend([]);
}

function clearRouteOverlays() {
  stopRoutePulse();
  clearViaMarkers();
  if (state.routeOverlays.length && state.map) {
    state.map.remove(state.routeOverlays);
  }
  state.routeOverlays = [];
}

function clearMetroNetwork() {
  const leftovers = [...state.metroLineOverlays, ...state.metroMarkers];
  if (leftovers.length && state.map) {
    state.map.remove(leftovers);
  }
  state.metroLineOverlays = [];
  state.metroMarkers = [];
}

function getCategory() {
  return document.querySelector('input[name="category"]:checked')?.value || "restaurant";
}

function originLetter(index) {
  return String.fromCharCode(65 + index);
}

function transferCity(city) {
  const name = (city || "北京").trim();
  if (["北京", "上海", "天津", "重庆"].includes(name)) {
    return `${name}市`;
  }
  return name || "北京市";
}

async function fetchJson(url, options = {}) {
  const init = { ...options };
  if (init.body && !init.headers) {
    init.headers = { "Content-Type": "application/json" };
  }
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(formatErrorDetail(payload.detail));
  }
  return payload;
}

function setBusy(isBusy) {
  elements.meetSearchButton.disabled = isBusy;
  elements.meetSearchButton.textContent = isBusy ? "搜索中..." : "搜索";
}

function setMessage(text, isError = false) {
  elements.message.textContent = text;
  elements.message.classList.toggle("error", isError);
}

function formatErrorDetail(detail) {
  if (typeof detail === "string" && detail) {
    return detail;
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail[0].msg;
  }
  return "请求失败。";
}

function formatDistance(meters) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${meters}m`;
}

function formatDuration(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) {
    return "--";
  }
  const total = Math.max(1, Math.round(Number(seconds) / 60));
  if (total >= 60) {
    const hours = Math.floor(total / 60);
    const minutes = total % 60;
    return minutes ? `${hours}小时${minutes}分` : `${hours}小时`;
  }
  return `${total}分`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
