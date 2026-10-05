const state = {
  jobs: [],
  updated: "",
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
};

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

async function boot() {
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

  for (const el of [els.q, els.seniority, els.jobType, els.location]) {
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  }
  render();
}

boot().catch((err) => {
  els.meta.textContent = "Failed to load data";
  els.list.innerHTML = `<p class="empty">${err.message}</p>`;
});
