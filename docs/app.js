const LOCAL_API = "http://127.0.0.1:8787";

const state = {
  jobs: [],
  updated: "",
  localOnline: false,
  running: false,
};

const els = {
  meta: document.getElementById("meta"),
  count: document.getElementById("count"),
  list: document.getElementById("list"),
  q: document.getElementById("q"),
  seniority: document.getElementById("seniority"),
  jobType: document.getElementById("jobType"),
  location: document.getElementById("location"),
  tpl: document.getElementById("card-tpl"),
  runBtn: document.getElementById("runBtn"),
  pipeline: document.getElementById("pipeline"),
  pipelineStatus: document.getElementById("pipelineStatus"),
  pipelineHint: document.getElementById("pipelineHint"),
  pipelineLog: document.getElementById("pipelineLog"),
  readyBanner: document.getElementById("readyBanner"),
  readyDetail: document.getElementById("readyDetail"),
};

function apiBase() {
  // Prefer same-origin when served by local dashboard; else talk to localhost API
  if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
    return location.origin;
  }
  return LOCAL_API;
}

function cityKey(location) {
  if (!location) return "Germany";
  const first = location.split(",")[0].trim();
  return first || "Germany";
}

function fillSelect(select, values, allLabel) {
  const current = select.value;
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = allLabel;
  select.appendChild(all);
  for (const value of values) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    select.appendChild(opt);
  }
  if ([...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
}

function uniqueSorted(items) {
  return [...new Set(items.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function matches(job) {
  const q = els.q.value.trim().toLowerCase();
  const sen = els.seniority.value;
  const type = els.jobType.value;
  const loc = els.location.value;

  if (sen && job.seniority !== sen) return false;
  if (type && job.job_type !== type) return false;
  if (loc && cityKey(job.location) !== loc) return false;

  if (!q) return true;
  const hay = [job.title, job.company, job.location, job.seniority, job.description]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function render() {
  const filtered = state.jobs.filter(matches);
  els.count.textContent = `${filtered.length} of ${state.jobs.length} roles`;
  els.list.innerHTML = "";

  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No roles match these filters. Try clearing search or seniority.";
    els.list.appendChild(empty);
    return;
  }

  filtered.forEach((job, index) => {
    const node = els.tpl.content.firstElementChild.cloneNode(true);
    node.style.animationDelay = `${Math.min(index, 12) * 0.03}s`;
    node.querySelector(".title").textContent = job.title || "Untitled role";
    node.querySelector(".company").textContent = job.company || "Company undisclosed";
    node.querySelector(".where").textContent = job.location || "Germany";
    node.querySelector(".snippet").textContent =
      job.description || "Open the LinkedIn posting for the full description.";
    node.querySelector(".posted").textContent = job.published
      ? `Posted ${job.published}`
      : "";

    const tags = node.querySelector(".tags");
    for (const [label, accent] of [
      [job.seniority, true],
      [job.job_type && job.job_type !== "Unknown" ? job.job_type : "", false],
      [job.employment, false],
    ]) {
      if (!label) continue;
      const tag = document.createElement("span");
      tag.className = accent ? "tag accent" : "tag";
      tag.textContent = label;
      tags.appendChild(tag);
    }

    const link = node.querySelector(".btn");
    const href = job.url || job.apply;
    if (href) {
      link.href = href;
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
      link.textContent = "No link";
    }

    els.list.appendChild(node);
  });
}

function appendLog(message, stage) {
  if (!message) return;
  const li = document.createElement("li");
  li.dataset.stage = stage || "info";
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString();
  const text = document.createElement("span");
  text.textContent = message;
  li.append(time, text);
  els.pipelineLog.appendChild(li);
  els.pipelineLog.scrollTop = els.pipelineLog.scrollHeight;
}

function setRunning(running) {
  state.running = running;
  els.runBtn.disabled = !state.localOnline || running;
  els.runBtn.textContent = running ? "Scraping…" : "Run scrape";
  els.pipeline.hidden = false;
}

function showReady(detail) {
  els.readyBanner.hidden = false;
  els.pipelineStatus.textContent = "Ready to apply";
  els.readyDetail.textContent = detail || "Board updated — start applying.";
  els.pipeline.classList.add("is-ready");
}

function showIdleLocal() {
  els.pipeline.hidden = false;
  els.pipelineHint.textContent = "Local dashboard connected.";
  els.pipelineStatus.textContent = "Idle — click Run scrape";
}

function showOfflineHint() {
  els.pipeline.hidden = false;
  els.pipelineStatus.textContent = "Local pipeline offline";
  els.pipelineHint.textContent =
    "Start on your PC: python -m src --dashboard  →  then open http://127.0.0.1:8787/";
  els.runBtn.disabled = true;
  els.runBtn.title = "Start local dashboard first";
}

async function loadJobs() {
  const res = await fetch("./jobs.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load jobs.json (${res.status})`);
  const data = await res.json();
  state.jobs = data.jobs || [];
  state.updated = data.updated || "";
  els.meta.textContent = state.updated
    ? `${state.jobs.length} roles · updated ${state.updated}`
    : `${state.jobs.length} roles`;

  fillSelect(
    els.seniority,
    uniqueSorted(state.jobs.map((j) => j.seniority)),
    "All"
  );
  fillSelect(
    els.jobType,
    uniqueSorted(state.jobs.map((j) => j.job_type).filter((v) => v && v !== "Unknown")),
    "All"
  );
  fillSelect(
    els.location,
    uniqueSorted(state.jobs.map((j) => cityKey(j.location))),
    "All Germany"
  );
  render();
}

function handleEvent(data) {
  if (data.type === "ping") return;

  if (data.type === "status") {
    els.pipelineStatus.textContent = data.message || data.status || "Connected";
    if (data.status === "running") setRunning(true);
    if (data.status === "done") {
      setRunning(false);
      showReady(
        data.result && typeof data.result.saved === "number"
          ? `${data.result.saved} new qualified job(s) saved.`
          : ""
      );
    }
    return;
  }

  if (data.type === "progress" || data.stage) {
    appendLog(data.message, data.stage);
    if (data.stage && data.stage !== "done" && data.stage !== "error") {
      els.pipelineStatus.textContent = data.message || data.stage;
      els.readyBanner.hidden = true;
      els.pipeline.classList.remove("is-ready");
    }
    if (data.stage === "done") {
      setRunning(false);
      showReady(
        typeof data.saved === "number" ? `${data.saved} new qualified job(s) saved.` : ""
      );
      loadJobs().catch(() => {});
    }
    if (data.stage === "error") {
      setRunning(false);
      els.pipelineStatus.textContent = "Failed";
      els.pipeline.classList.remove("is-ready");
      els.readyBanner.hidden = true;
    }
  }
}

function connectEvents() {
  const es = new EventSource(`${apiBase()}/api/events`);
  es.onmessage = (ev) => {
    try {
      handleEvent(JSON.parse(ev.data));
    } catch (_) {
      /* ignore */
    }
  };
  es.onerror = () => {
    /* browser will retry; keep UI as-is */
  };
  return es;
}

async function probeLocal() {
  try {
    const res = await fetch(`${apiBase()}/api/health`, { cache: "no-store" });
    if (!res.ok) throw new Error("offline");
    state.localOnline = true;
    els.runBtn.disabled = false;
    els.runBtn.title = "Run LinkedIn guest + SerpAPI + Apify locally";
    showIdleLocal();
    connectEvents();
    return true;
  } catch (_) {
    state.localOnline = false;
    showOfflineHint();
    return false;
  }
}

async function startRun() {
  if (!state.localOnline || state.running) return;
  els.pipelineLog.innerHTML = "";
  els.readyBanner.hidden = true;
  els.pipeline.classList.remove("is-ready");
  setRunning(true);
  els.pipelineStatus.textContent = "Starting…";
  try {
    const res = await fetch(`${apiBase()}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dry_run: false }),
    });
    if (res.status === 409) {
      appendLog("Pipeline already running", "warning");
      return;
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }
  } catch (err) {
    setRunning(false);
    els.pipelineStatus.textContent = "Failed to start";
    appendLog(String(err.message || err), "error");
  }
}

async function boot() {
  for (const el of [els.q, els.seniority, els.jobType, els.location]) {
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  }
  els.runBtn.addEventListener("click", startRun);

  await loadJobs();
  await probeLocal();
}

boot().catch((err) => {
  els.meta.textContent = "Failed to load data";
  els.list.innerHTML = `<p class="empty">${err.message}</p>`;
});
