const navButtons = [...document.querySelectorAll("[data-view]")];
const views = [...document.querySelectorAll(".view")];
const breadcrumb = document.getElementById("breadcrumb-current");
const toast = document.getElementById("toast");
let toastTimer;
let lastRequirement = null;
let currentRunId = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function showView(name) {
  const titles = {
    overview: "Overview",
    library: "Asset library",
    workflows: "Workflows",
    templates: "Allen Knows Ball",
    sources: "Sources",
    runs: "Runs & queue",
  };
  views.forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  navButtons.forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  breadcrumb.textContent = titles[name] || "Overview";
  history.replaceState(null, "", `#${name}`);
  if (name === "library") loadAssets();
  if (name === "templates") loadTemplateFoundation();
  if (name === "workflows") loadWorkflowStatus();
  if (name === "overview") { loadOverview(); loadStats(); loadRuns(); }
  if (name === "runs") loadRuns();
}

navButtons.forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.go)));

function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

async function loadTemplateFoundation() {
  try {
    const response = await fetch("/api/template-foundation", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load the channel template package.");
    const data = await response.json();
    const shortPackage = data.templates.short;
    const longPackage = data.templates.long;
    document.getElementById("template-draft-status").textContent = "SHORT + LONG · DRAFT FOR OWNER AUDIT";
    document.getElementById("template-version").textContent = `Short v${shortPackage.manifest.version} · ${shortPackage.manifest.output.aspect_ratio} / ${shortPackage.manifest.duration_seconds.minimum}–${shortPackage.manifest.duration_seconds.maximum}s   |   Long v${longPackage.manifest.version} · ${longPackage.manifest.output.aspect_ratio} / ${Math.round(longPackage.manifest.duration_seconds.minimum / 60)}–${Math.round(longPackage.manifest.duration_seconds.maximum / 60)} min`;
    document.getElementById("template-tagline").textContent = data.channel.tagline;
    document.getElementById("template-promise").textContent = data.channel.brand_promise;
  } catch (error) {
    showToast(error.message || "Could not load the Template Foundation.");
  }
}

async function loadOverview() {
  try {
    const response = await fetch("/api/overview", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load engine data.");
    const data = await response.json();
    document.getElementById("metric-total").textContent = data.asset_count;
    document.getElementById("metric-verified").textContent = data.verified_rights_count;
    document.getElementById("metric-active").textContent = data.active_count;
    document.getElementById("nav-asset-count").textContent = data.asset_count;
  } catch (error) {
    showToast(error.message || "Could not connect to the local engine.");
  }
}

function statusPill(value, successValue) {
  const success = value === successValue;
  return `<span class="status-pill ${success ? "status-ok" : "status-muted"}">${escapeHtml(value || "unknown")}</span>`;
}

function thumbIcon(type) {
  const map = { image: "i-image", video: "i-video", audio: "i-audio", font: "i-type" };
  return `<svg class="ic" aria-hidden="true"><use href="#${map[type] || "i-file"}"/></svg>`;
}

async function loadAssets() {
  const body = document.getElementById("asset-rows");
  body.innerHTML = '<tr><td colspan="9" class="empty-cell">Loading library inventory…</td></tr>';
  try {
    const response = await fetch("/api/assets", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load assets.");
    const { assets } = await response.json();
    document.getElementById("inventory-count").textContent = `${assets.length}${assets.length === 200 ? "+" : ""} assets`;
    if (!assets.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty-cell">No assets are registered yet. Add approved resources through the library ingest workflow.</td></tr>';
      return;
    }
    body.innerHTML = assets.map((asset) => {
      const fileUrl = `/api/assets/file/${encodeURIComponent(asset.asset_id)}`;
      const thumb = asset.asset_type === "image"
        ? `<img class="asset-thumb-img" src="${fileUrl}" alt="" loading="lazy" data-preview="${escapeHtml(asset.asset_id)}" data-kind="image" title="Click to preview" />`
        : `<span class="asset-thumb">${thumbIcon(asset.asset_type)}</span>`;
      return `<tr>
      <td><div class="asset-name">${thumb}<button class="text-button asset-view" type="button" data-preview="${escapeHtml(asset.asset_id)}" data-kind="${escapeHtml(asset.asset_type)}">${escapeHtml(asset.original_name)}</button></div></td>
      <td>${escapeHtml(asset.asset_type)}</td>
      <td>${escapeHtml(asset.purpose_code || "?")}</td>
      <td>${statusPill(asset.rights_state, "verified")}</td>
      <td>${escapeHtml(asset.license_type || "?")}</td>
      <td>${asset.source_url ? `<a href="${escapeHtml(asset.source_url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : "?"}</td>
      <td>${statusPill(asset.lifecycle_state, "active")}</td>
      <td>${escapeHtml(formatDate(asset.created_at))}</td>
      <td>${asset.rights_state !== "verified" ? `<button class="button button-secondary button-small" type="button" data-review-rights="${escapeHtml(asset.asset_id)}" title="Review the source and license for your intended use before confirming">Review rights</button>` : '<span class="review-complete">Reviewed</span>'}</td>
    </tr>`;
    }).join("");
    body.querySelectorAll("[data-review-rights]").forEach((button) => button.addEventListener("click", () => reviewAssetRights(button)));
    body.querySelectorAll("[data-preview]").forEach((el) => el.addEventListener("click", () => previewAsset(el)));
  } catch (error) {
    body.innerHTML = `<tr><td colspan="9" class="empty-cell">${escapeHtml(error.message || "Could not load inventory.")}</td></tr>`;
  }
}

function showEvaluation(result, requirement) {
  const panel = document.getElementById("evaluation-result");
  const classes = {
    REUSE: "result-reuse",
    VERIFY: "result-verify",
    ACQUIRE: "result-acquire",
    DO_NOT_RECOMMEND: "result-block",
  };
  const explanation = {
    REUSE: `Library recommends asset ${result.recommended_asset}. The resource need is satisfied by existing inventory.`,
    VERIFY: `Asset ${result.recommended_asset} may fit, but its context needs verification before use.`,
    ACQUIRE: "No suitable asset was found in the current inventory. Search across Openverse's indexed collections and choose whether to save one.",
    DO_NOT_RECOMMEND: "Inventory contains assets, but none match the required context. The library will not recommend one.",
  };
  const reasons = (result.reasons || []).map((reason) => `<span class="reason-chip">${escapeHtml(reason.replaceAll("_", " "))}</span>`).join("");
  const discovery = result.recommendation === "ACQUIRE" && ["image", "video"].includes(requirement.resource_type)
    ? `<div class="discovery-section"><div class="eyebrow">EXTERNAL DISCOVERY</div><h4>Search openly licensed collections</h4><p>Openverse and Pexels images, Wikimedia Commons images and video. Large commercial-use files are prioritized and sources are interleaved for variety. Results are suggestions only; nothing downloads until you choose.</p><div class="discovery-tabs" role="group" aria-label="Media type">${["image", "video"].map((t) => `<button type="button" class="range-tab${requirement.resource_type === t ? " active" : ""}" data-dtype="${t}">${t === "image" ? "Images" : "Videos"}</button>`).join("")}</div><div class="discovery-tabs" role="group" aria-label="Sort order"><button type="button" class="range-tab active" data-sort="relevance">Relevance</button><button type="button" class="range-tab" data-sort="newest">Newest first</button></div><form id="discovery-form" class="discovery-form"><input name="query" required maxlength="250" value="${escapeHtml(requirement.discovery_query || requirement.context || requirement.entity_id || requirement.purpose || requirement.content_objective || requirement.requirement_id)}" aria-label="Web search query" /><button class="button button-secondary" type="submit">Search</button></form><div class="candidate-grid" id="candidate-grid"></div></div>`
    : result.recommendation === "ACQUIRE"
      ? '<p class="result-detail">External discovery currently supports images and video.</p>'
      : "";
  panel.innerHTML = `<div class="result-header"><h3 class="result-title">${escapeHtml(result.status.replaceAll("_", " "))}</h3><span class="result-badge ${classes[result.recommendation] || "result-block"}">${escapeHtml(result.recommendation)}</span></div>
    <p class="result-detail">${escapeHtml(explanation[result.recommendation] || "Review the library evaluation before proceeding.")}</p>
    <div class="result-reasons">${reasons}</div>${discovery}`;
  panel.hidden = false;
  const searchForm = panel.querySelector("#discovery-form");
  if (searchForm) searchForm.addEventListener("submit", (event) => searchCandidates(event, requirement));
  const dtypeButtons = panel.querySelectorAll("[data-dtype]");
  dtypeButtons.forEach((tab) => tab.addEventListener("click", () => {
    dtypeButtons.forEach((item) => item.classList.toggle("active", item === tab));
    if (searchForm) searchForm.dataset.dtype = tab.dataset.dtype;
  }));
  if (searchForm && !searchForm.dataset.dtype) {
    searchForm.dataset.dtype = requirement.resource_type === "video" ? "video" : "image";
  }
  const sortButtons = panel.querySelectorAll("[data-sort]");
  sortButtons.forEach((tab) => tab.addEventListener("click", () => {
    sortButtons.forEach((item) => item.classList.toggle("active", item === tab));
    if (searchForm) searchForm.dataset.sort = tab.dataset.sort;
  }));
  if (searchForm && !searchForm.dataset.sort) searchForm.dataset.sort = "relevance";
  panel.querySelectorAll("[data-approve]").forEach((button) => button.addEventListener("click", () => approveCandidate(button, requirement)));
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function candidateCard(candidate) {
  const dimensions = candidate.width && candidate.height ? `${candidate.width} × ${candidate.height}` : "Dimensions unavailable";
  const size = candidate.size_bytes ? `${(candidate.size_bytes / 1024 / 1024).toFixed(1)} MB` : "Size unavailable";
  const duration = candidate.duration_seconds ? `${candidate.duration_seconds}s` : "";
  const license = candidate.license_name || "No license metadata found";
  const creator = candidate.creator || "Creator not listed";
  const sourceUrl = safeExternalUrl(candidate.source_url);
  const licenseUrl = safeExternalUrl(candidate.license_url);
  const thumbnailUrl = safeExternalUrl(candidate.thumbnail_url);
  return `<article class="candidate-card" data-candidate-card="${escapeHtml(candidate.candidate_id)}">
    ${thumbnailUrl ? `<img class="candidate-image" src="${escapeHtml(thumbnailUrl)}" alt="Preview of ${escapeHtml(candidate.title)}" loading="lazy" />` : '<div class="candidate-image candidate-image-empty">Preview unavailable</div>'}
    <div class="candidate-content"><div class="candidate-provider">${escapeHtml(candidate.provider)}${candidate.media_type === "VIDEO" ? ' <span class="candidate-kind">VIDEO</span>' : ""}${candidate.identity === "uncertain" ? ' <span class="candidate-flag">UNCERTAIN ID</span>' : ""}</div>${sourceUrl ? `<a class="candidate-title" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(candidate.title)}</a>` : `<strong class="candidate-title">${escapeHtml(candidate.title)}</strong>`}
      <div class="candidate-meta">${escapeHtml(dimensions)} · ${escapeHtml(size)}${duration ? ` · ${escapeHtml(duration)}` : ""}${candidate.uploaded_at ? ` · up ${escapeHtml(candidate.uploaded_at)}` : ""}</div>
      <div class="candidate-license"><strong>License</strong><span>${licenseUrl ? `<a href="${escapeHtml(licenseUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(license)}</a>` : escapeHtml(license)}</span></div>
      <div class="candidate-meta"><strong>Creator:</strong> ${escapeHtml(creator)}</div>
      ${candidate.credit ? `<div class="candidate-meta"><strong>Attribution:</strong> ${escapeHtml(candidate.credit)}</div>` : ""}
      ${sourceUrl ? `<div class="candidate-meta"><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">View original source ?</a></div>` : ""}
      <div class="candidate-actions"><button class="button button-secondary" type="button" data-approve="${escapeHtml(candidate.candidate_id)}" data-rights="false">Save for review</button><button class="button button-primary" type="button" data-approve="${escapeHtml(candidate.candidate_id)}" data-rights="true" title="Confirm that you reviewed the license and approve this asset for use">Approve rights &amp; save</button></div>
      <small class="candidate-action-note">Saving downloads this candidate and registers its source. ?Save for review? keeps rights unverified.</small>
    </div>
  </article>`;
}

async function searchCandidates(event, requirement) {
  event.preventDefault();
  const form = event.currentTarget;
  const query = new FormData(form).get("query").trim();
  const dtype = form.dataset.dtype === "video" ? "video" : "image";
  const sort = form.dataset.sort === "newest" ? "newest" : "relevance";
  const button = form.querySelector("button[type=submit]");
  const grid = document.getElementById("candidate-grid");
  button.disabled = true;
  button.textContent = "Searching…";
  grid.innerHTML = `<div class="candidate-message">Searching ${dtype === "video" ? "videos" : "images"}…</div>`;
  try {
    const response = await fetch("/api/discovery-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 24, resource_type: dtype, sort, entity_id: requirement.entity_id || "" }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Web discovery failed.");
    const sources = (result.provider_status || []).map((s) => {
      const state = s.state === "ready" ? "ready" : s.state === "needs_key" ? "needs key" : s.state;
      return `${s.label} (${s.media}): ${state}`;
    }).join(" · ");
    const header = sources ? `<div class="provider-line">Sources — ${escapeHtml(sources)}</div>` : "";
    let identityLine = "";
    if (result.identity && result.identity.status === "screened") {
      const removed = result.identity.removed || [];
      identityLine = removed.length
        ? `<div class="identity-line">Identity (${escapeHtml(result.identity.display_name || result.identity.entity_id)}): removed ${removed.length} — ${removed.map((r) => `${escapeHtml(r.title)} (${escapeHtml(r.reason)})`).join("; ")}</div>`
        : `<div class="identity-line identity-clean">Identity (${escapeHtml(result.identity.display_name || result.identity.entity_id)}): all ${result.identity.kept} match, nothing removed.</div>`;
    }
    grid.innerHTML = header + identityLine + (result.candidates.length
      ? result.candidates.map(candidateCard).join("")
      : `<div class="candidate-message">No supported ${dtype === "video" ? "videos" : "images"} found. Try a broader search phrase.</div>`);
    grid.querySelectorAll("[data-approve]").forEach((approveButton) => approveButton.addEventListener("click", () => approveCandidate(approveButton, requirement)));
  } catch (error) {
    grid.innerHTML = `<div class="candidate-message candidate-error">${escapeHtml(error.message || "Web discovery failed.")}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Search";
  }
}

async function approveCandidate(button, requirement) {
  const candidateId = button.dataset.approve;
  const rightsReviewed = button.dataset.rights === "true";
  const card = button.closest("[data-candidate-card]");
  card.querySelectorAll("button").forEach((item) => { item.disabled = true; });
  button.textContent = rightsReviewed ? "Saving approved asset…" : "Saving unverified…";
  try {
    const response = await fetch("/api/assets/approve-candidate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: candidateId,
        requirement,
        rights_reviewed: rightsReviewed,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save this candidate.");
    const message = result.status === "ALREADY_IN_LIBRARY"
      ? `Already in library as ${result.asset_id}; existing rights metadata was left unchanged.`
      : `Saved ${result.asset_id} with rights state “${result.rights_state}”.`;
    card.innerHTML = `<div class="candidate-saved"><span><svg class="ic" aria-hidden="true"><use href="#i-check"/></svg></span><div><strong>${escapeHtml(result.status.replaceAll("_", " "))}</strong><small>${escapeHtml(message)}</small></div></div>`;
    showToast(message);
    await loadAssets();
    if (rightsReviewed && result.status === "SAVED") await evaluateRequirement(requirement);
  } catch (error) {
    card.querySelectorAll("button").forEach((item) => { item.disabled = false; });
    button.textContent = rightsReviewed ? "Approve rights & save" : "Save for review";
    showToast(error.message || "Could not save this candidate.");
  }
}

function previewAsset(el) {
  const assetId = el.dataset.preview || "";
  const kind = el.dataset.kind || "";
  if (!assetId) return;
  const fileUrl = `/api/assets/file/${encodeURIComponent(assetId)}`;
  if (kind !== "image") {
    window.open(fileUrl, "_blank", "noopener");
    return;
  }
  const box = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-image");
  const caption = document.getElementById("lightbox-caption");
  const row = el.closest("tr");
  const name = row ? row.querySelector(".asset-view")?.textContent?.trim() : "";
  img.src = fileUrl;
  caption.textContent = name ? `${name} · ${assetId}` : assetId;
  box.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  const box = document.getElementById("lightbox");
  if (!box || box.hidden) return;
  box.hidden = true;
  document.getElementById("lightbox-image").removeAttribute("src");
  document.body.style.overflow = "";
}

document.querySelectorAll("[data-lightbox-close]").forEach((el) => el.addEventListener("click", closeLightbox));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeLightbox();
});

async function reviewAssetRights(button) {
  const assetId = button.dataset.reviewRights;
  if (!window.confirm("Confirm only after reviewing the asset source and license for your intended use. Mark rights as verified?")) return;
  button.disabled = true;
  button.textContent = "Updating?";
  try {
    const response = await fetch("/api/assets/review-rights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: assetId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not update rights status.");
    await Promise.all([loadAssets(), loadOverview()]);
    if (lastRequirement) await evaluateRequirement(lastRequirement);
    showToast(result.status === "ALREADY_VERIFIED" ? "Rights were already verified." : "Rights marked verified after your review.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Review rights";
    showToast(error.message || "Could not update rights status.");
  }
}

async function evaluateRequirement(requirement) {
  const response = await fetch("/api/resource-evaluations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requirement),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not evaluate the requirement.");
  showEvaluation(result, requirement);
}

document.getElementById("requirement-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    requirement_id: form.get("requirement_id").trim(),
    resource_type: form.get("resource_type"),
  };
  for (const name of ["entity_id", "purpose", "context", "discovery_query", "rights_state", "lifecycle_state"]) {
    const value = form.get(name);
    if (value) payload[name] = value.trim();
  }
  payload.content_objective = form.get("content_objective").trim();
  lastRequirement = payload;

  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  button.innerHTML = "<span>…</span> Checking inventory";
  try {
    await evaluateRequirement(payload);
  } catch (error) {
    showToast(error.message || "Could not evaluate the requirement.");
  } finally {
    button.disabled = false;
    button.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-search"/></svg> Check library inventory';
  }
});

let lastStats = null;
let chartRange = 14;

function dayKey(offsetDays) {
  return new Date(Date.now() - offsetDays * 864e5).toISOString().slice(0, 10);
}

function backfill(series, days) {
  const map = Object.fromEntries((series || []).map((d) => [d.day, d.count]));
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const day = dayKey(i);
    out.push({ day, count: map[day] || 0 });
  }
  return out;
}

function sparkSvg(values) {
  const w = 120, h = 34;
  if (!values.length) return "";
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? w / (values.length - 1) : 0;
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 3 - (v / max) * (h - 8)).toFixed(1)}`);
  if (pts.length === 1) return `<circle cx="${pts[0].split(",")[0]}" cy="${pts[0].split(",")[1]}" r="2.6" fill="#8b7cff"/>`;
  const last = pts[pts.length - 1].split(",");
  return `<polyline points="${pts.join(" ")}" fill="none" stroke="#8b7cff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${last[0]}" cy="${last[1]}" r="2.8" fill="#8b7cff"/>`;
}

function barChartSvg(entries) {
  const W = 560, H = 190, padL = 36, padB = 26, padT = 14;
  const counts = entries.map((d) => d.count);
  const max = Math.max(1, ...counts);
  const n = Math.max(1, entries.length);
  const innerW = W - padL - 12, innerH = H - padT - padB;
  const slot = innerW / n;
  const barW = Math.max(4, Math.min(30, slot * 0.55));
  let svg = `<defs><linearGradient id="assetBarGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#4d7cfe"/></linearGradient></defs>`;
  [0, 0.5, 1].forEach((f) => {
    const y = (padT + innerH * (1 - f)).toFixed(1);
    svg += `<line x1="${padL}" y1="${y}" x2="${W - 8}" y2="${y}" stroke="#262c3d" stroke-width="1"/><text x="${padL - 7}" y="${+y + 3.5}" text-anchor="end" font-size="10" fill="#7c86a0">${Math.round(max * f)}</text>`;
  });
  entries.forEach((d, i) => {
    const h = d.count > 0 ? Math.max(3, (d.count / max) * innerH) : 0;
    const x = padL + i * slot + (slot - barW) / 2;
    const y = padT + innerH - h;
    if (h > 0) svg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="3.5" fill="url(#assetBarGrad)"><title>${escapeHtml(d.day)}: ${d.count} asset(s)</title></rect>`;
  });
  const labelAt = (i) => {
    const x = padL + i * slot + slot / 2;
    return `<text x="${x.toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="10" fill="#7c86a0">${escapeHtml(entries[i].day.slice(5))}</text>`;
  };
  svg += labelAt(0);
  if (n > 2) svg += labelAt(Math.floor((n - 1) / 2));
  if (n > 1) svg += labelAt(n - 1);
  return svg;
}

const STATUS_PATTERNS = [
  [/APPROVED|RENDERED|COMPLETE|VERIFIED/, "#8b7cff"],
  [/WAITING|REVIEW|AUDIT/, "#f5a524"],
  [/FAIL|ERROR|BLOCK|REJECT/, "#ff5e7a"],
];

function statusColor(status) {
  const s = String(status || "");
  for (const [pattern, color] of STATUS_PATTERNS) if (pattern.test(s)) return color;
  return "#59617a";
}

function statusGrad(status) {
  const s = String(status || "");
  if (/APPROVED|RENDERED|COMPLETE|VERIFIED/.test(s)) return "url(#dgrad-ok)";
  if (/WAITING|REVIEW|AUDIT/.test(s)) return "url(#dgrad-wait)";
  if (/FAIL|ERROR|BLOCK|REJECT/.test(s)) return "url(#dgrad-fail)";
  return "url(#dgrad-muted)";
}

function donutSvg(byStatus) {
  const entries = Object.entries(byStatus || {});
  const total = entries.reduce((sum, [, c]) => sum + c, 0);
  if (!total) return "";
  let offset = 25, segs = "";
  entries.forEach(([name, count]) => {
    const frac = count / total;
    segs += `<circle cx="60" cy="60" r="42" fill="none" stroke="${statusGrad(name)}" stroke-width="20" stroke-dasharray="${(frac * 100).toFixed(1)} 100" stroke-dashoffset="${offset.toFixed(1)}" pathLength="100"><title>${escapeHtml(name)}: ${count}</title></circle>`;
    offset -= frac * 100;
  });
  return `<defs>`
    + `<linearGradient id="dgrad-ok" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b7cff"/><stop offset="1" stop-color="#4d7cfe"/></linearGradient>`
    + `<linearGradient id="dgrad-wait" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f5c04c"/><stop offset="1" stop-color="#ffa44d"/></linearGradient>`
    + `<linearGradient id="dgrad-fail" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5e7a"/><stop offset="1" stop-color="#ffa44d"/></linearGradient>`
    + `<linearGradient id="dgrad-muted" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a5268"/><stop offset="1" stop-color="#333a4d"/></linearGradient>`
    + `</defs><circle cx="60" cy="60" r="31" fill="#161b28"/>${segs}`
    + `<text x="60" y="58" text-anchor="middle" font-size="21" font-weight="800" fill="#f3f5fa">${total}</text><text x="60" y="73" text-anchor="middle" font-size="9.5" fill="#8f99ad">runs</text>`;
}

function renderAssetChart() {
  const svg = document.getElementById("chart-assets");
  const empty = document.getElementById("chart-assets-empty");
  if (!svg || !lastStats) return;
  const entries = backfill(lastStats.assets_by_day, chartRange);
  const hasData = entries.some((d) => d.count > 0);
  svg.innerHTML = hasData ? barChartSvg(entries) : "";
  svg.style.display = hasData ? "" : "none";
  if (empty) empty.hidden = hasData;
}

function renderRunsDonut() {
  const svg = document.getElementById("chart-runs");
  const legend = document.getElementById("runs-legend");
  const empty = document.getElementById("chart-runs-empty");
  if (!svg || !lastStats) return;
  const byStatus = lastStats.runs_by_status || {};
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
  svg.innerHTML = total ? donutSvg(byStatus) : "";
  svg.style.display = total ? "" : "none";
  if (empty) empty.hidden = total > 0;
  if (legend) {
    legend.innerHTML = total
      ? Object.entries(byStatus).sort((a, b) => b[1] - a[1]).map(([name, count]) =>
        `<div class="legend-row"><span class="legend-dot" style="background:${statusColor(name)}"></span><span class="legend-name">${escapeHtml(name.replaceAll("_", " "))}</span><span class="legend-count">${count}</span></div>`).join("")
      : "";
  }
}

function renderLicenseBars() {
  const box = document.getElementById("license-bars");
  const empty = document.getElementById("license-empty");
  if (!box || !lastStats) return;
  const items = lastStats.assets_by_license || [];
  const max = Math.max(1, ...items.map((d) => d.count));
  box.innerHTML = items.map((d) =>
    `<div class="hbar-row"><span class="hbar-label">${escapeHtml(d.license)}</span><span class="hbar-track"><span class="hbar-fill" style="width:${Math.max(3, Math.round((d.count / max) * 100))}%"></span></span><span class="hbar-count">${d.count}</span></div>`).join("");
  if (empty) empty.hidden = items.length > 0;
}

function paintSpark(svgId, deltaId, series) {
  const svg = document.getElementById(svgId);
  if (svg) svg.innerHTML = sparkSvg(backfill(series, 14).map((d) => d.count));
  const delta = document.getElementById(deltaId);
  if (delta) {
    const cutoff = dayKey(6);
    const recent = (series || []).filter((d) => d.day >= cutoff).reduce((a, d) => a + d.count, 0);
    delta.innerHTML = recent > 0 ? `<strong class="delta-up">+${recent}</strong> in last 7 days` : "No change in last 7 days";
  }
}

async function loadStats() {
  try {
    const response = await fetch("/api/stats", { cache: "no-store" });
    if (!response.ok) throw new Error("stats unavailable");
    lastStats = await response.json();
  } catch {
    return;
  }
  paintSpark("spark-total", "delta-total", lastStats.assets_by_day);
  paintSpark("spark-verified", "delta-verified", lastStats.verified_by_day);
  paintSpark("spark-active", "delta-active", lastStats.active_by_day);
  renderAssetChart();
  renderRunsDonut();
  renderLicenseBars();
}

function runStatusPill(status) {
  const s = String(status || "unknown");
  let cls = "status-muted";
  if (/APPROVED|RENDERED|COMPLETE|VERIFIED/.test(s)) cls = "status-ok";
  else if (/DRAFTING|CHECKING|RENDERING/.test(s)) cls = "status-live";
  return `<span class="status-pill ${cls}" title="${escapeHtml(s)}">${escapeHtml(s.replaceAll("_", " ").slice(0, 28))}</span>`;
}

function outputLinks(run) {
  const labels = { "template-preview.mp4": "Preview", "visual-benchmark-silent.mp4": "Benchmark", "full-render.mp4": "Full" };
  const links = [];
  const videos = run.videos || {};
  for (const [file, label] of Object.entries(labels)) {
    if (videos[file]) links.push(`<a href="${escapeHtml(videos[file])}" target="_blank" rel="noopener noreferrer">${label}</a>`);
  }
  if (run.has_report) links.push(`<a href="/api/render/${escapeHtml(run.run_id)}/report" target="_blank" rel="noopener noreferrer">Report</a>`);
  return links.length ? links.join(" · ") : "—";
}

function runRow(run, compact) {
  const cells = [
    `<td><code class="run-id">${escapeHtml(String(run.run_id || "").slice(0, 8))}</code></td>`,
    `<td class="run-topic">${escapeHtml(run.topic || "—")}</td>`,
    `<td>${escapeHtml(run.content_type || "—")}</td>`,
    `<td>${runStatusPill(run.status)}</td>`,
  ];
  if (!compact) {
    cells.push(
      `<td>${escapeHtml(formatDate(run.created_at))}</td>`,
      `<td>${run.segment_count}</td>`,
    );
  }
  cells.push(
    `<td>${run.media_count}</td>`,
  );
  if (!compact) {
    cells.push(`<td>${run.voice_preview_audited ? "Audited" : run.voice_preview ? "Preview" : "—"}</td>`);
  }
  cells.push(`<td class="run-links">${outputLinks(run)}</td>`);
  return `<tr>${cells.join("")}</tr>`;
}

async function loadRuns() {
  let runs = [];
  try {
    const response = await fetch("/api/runs", { cache: "no-store" });
    if (!response.ok) throw new Error("runs unavailable");
    runs = (await response.json()).runs || [];
  } catch {
    const body = document.getElementById("run-rows");
    if (body) body.innerHTML = '<tr><td colspan="9" class="empty-cell">Could not load runs.</td></tr>';
    return;
  }
  const count = document.getElementById("runs-count");
  if (count) count.textContent = `${runs.length} run${runs.length === 1 ? "" : "s"}`;
  const body = document.getElementById("run-rows");
  if (body) {
    body.innerHTML = runs.length
      ? runs.map((run) => runRow(run, false)).join("")
      : '<tr><td colspan="9" class="empty-cell">No runs yet — create a video draft.</td></tr>';
  }
  const recent = document.getElementById("recent-runs-rows");
  if (recent) {
    recent.innerHTML = runs.length
      ? runs.slice(0, 6).map((run) => runRow(run, true)).join("")
      : '<tr><td colspan="6" class="empty-cell">No runs yet — create a video draft.</td></tr>';
  }
}

document.getElementById("refresh-overview").addEventListener("click", loadOverview);
document.getElementById("refresh-library").addEventListener("click", () => { loadOverview(); loadAssets(); });
document.getElementById("refresh-runs").addEventListener("click", loadRuns);
document.querySelectorAll(".range-tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".range-tab").forEach((item) => item.classList.toggle("active", item === tab));
  chartRange = parseInt(tab.dataset.range, 10) || 14;
  renderAssetChart();
}));

async function loadWorkflowStatus() {
  const pill = document.getElementById("workflow-runtime-status");
  if (!pill) return;
  try {
    const response = await fetch("/api/content/status", { cache: "no-store" });
    if (!response.ok) throw new Error("status unavailable");
    const status = await response.json();
    pill.textContent = status.script_model_ready ? "LOCAL SCRIPT MODEL READY" : "LOCAL OUTLINE MODE";
    pill.title = status.script_model_ready ? `Local model: ${status.model}` : "Set LLM_MODEL and start local Ollama to draft full scripts.";
  } catch {
    pill.textContent = "LOCAL ENGINE";
  }
  try {
    const response = await fetch("/api/voice/status", { cache: "no-store" });
    const status = await response.json();
    document.getElementById("voice-profile-heading").textContent = status.reference_ready ? "Allen voice reference saved locally" : "Voice sample not set up";
    document.getElementById("voice-runtime-note").textContent = status.tts_runtime_installed
      ? `${status.tts_model} runtime ready; preview is processed locally.`
      : `Local TTS runtime not installed yet. Selected recording remains local; planned engine: ${status.tts_model}.`;
  } catch { /* Keep the local-first guidance visible if status lookup fails. */ }
}

const storyFormDefinitions = {
  short: [
    ["one-moment-one-read", "Một tình huống, một góc nhìn"],
    ["explain-the-pattern", "Giải thích một ý chiến thuật"],
    ["player-role-read", "Cầu thủ và vai trò"],
  ],
  long: [
    ["longform-tactical-deep-dive", "Phân tích chiến thuật chuyên sâu · 8–20 phút"],
    ["longform-player-role-study", "Hồ sơ vai trò cầu thủ · 8–15 phút"],
  ],
};

const contentTypeSelect = document.querySelector('[name="content_type"]');
const storyFormSelect = document.getElementById("story-form-select");
if (contentTypeSelect && storyFormSelect) {
  contentTypeSelect.addEventListener("change", () => {
    const previous = storyFormSelect.value;
    const options = storyFormDefinitions[contentTypeSelect.value] || storyFormDefinitions.short;
    storyFormSelect.replaceChildren(...options.map(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      return option;
    }));
    const retained = options.find(([value]) => value === previous);
    storyFormSelect.value = retained ? previous : options[0][0];
  });
}

const draftForm = document.getElementById("content-draft-form");
if (draftForm) draftForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(draftForm);
  const button = draftForm.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Drafting locally and checking the library…";
  const progress = document.getElementById("draft-progress");
  if (progress) progress.textContent = "Engine đang draft — xem tiến trình live ở tab Runs & queue.";
  const draftPoll = setInterval(async () => {
    try {
      const poll = await fetch("/api/runs", { cache: "no-store" });
      const data = await poll.json();
      const active = (data.runs || []).find((run) => /DRAFTING|CHECKING/.test(String(run.status || "")));
      if (active && progress) {
        const beat = active.current_beat && active.total_beats ? ` · beat ${active.current_beat}/${active.total_beats}` : "";
        progress.textContent = `Đang chạy: ${active.status.replaceAll("_", " ")}${beat} · run ${String(active.run_id).slice(0, 8)}…`;
      }
      loadRuns();
    } catch { /* the main draft request is still the source of truth */ }
  }, 5000);
  try {
    const response = await fetch("/api/content/agent-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: String(form.get("topic") || "").normalize("NFC"),
        content_type: form.get("content_type"),
        story_form: form.get("story_form"),
        evidence: String(form.get("evidence") || "").normalize("NFC"),
        colorway: form.get("colorway"),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not create a script draft.");
    const draft = result.draft;
    document.getElementById("draft-mode-pill").textContent = `${draft.content_type.toUpperCase()} · ${draft.generation_mode === "local_ollama" ? "LOCAL MODEL" : draft.generation_mode === "local_ollama_partial" ? "LOCAL MODEL · PARTIAL" : "OUTLINE ONLY"}`;
    currentRunId = result.run_id;
    document.getElementById("evidence-verified").checked = false;
    document.getElementById("approve-script").disabled = false;
    document.getElementById("create-voice-preview").disabled = true;
    document.getElementById("render-template-preview").disabled = false;
    document.getElementById("render-full-video").disabled = true;
    document.getElementById("voice-preview-audited").checked = false;
    document.getElementById("voice-preview-audited").disabled = true;
    document.getElementById("render-preview-result").hidden = true;
    document.getElementById("render-visual-result").hidden = true;
    document.getElementById("render-full-result").hidden = true;
    document.getElementById("script-review-status").textContent = "";
    document.getElementById("voice-preview-status").textContent = "";
    document.getElementById("voice-preview-audio").hidden = true;
    document.getElementById("render-preview-status").textContent = "";
    document.getElementById("render-visual-status").textContent = "";
    document.getElementById("render-full-status").textContent = "";
    document.getElementById("draft-status-heading").textContent = `${draft.content_type.toUpperCase()} · ${draft.duration_target_seconds}s · ${draft.status.replaceAll("_", " ")} · run ${result.run_id}`;
    document.getElementById("script-segments").innerHTML = draft.segments.map((segment, index) => `
      <article class="script-segment" data-segment-id="${escapeHtml(segment.id)}"><div class="script-segment-top"><span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(segment.id.replaceAll("-", " "))}</strong><small>${escapeHtml(segment.start_seconds)}–${escapeHtml(segment.end_seconds)} sec · ${escapeHtml(segment.duration_seconds)} sec</small></div>
      <label>Voiceover<textarea lang="vi">${escapeHtml(segment.narration)}</textarea></label><small>${escapeHtml(segment.visual)}</small>
      <div class="segment-media"><label>Library image (verified, active)<input name="media_asset_id" placeholder="Copy an asset ID from the library" value="${escapeHtml(segment.media_asset_id || "")}" /></label><label>On-screen caption<input name="media_caption" maxlength="500" placeholder="Vietnamese caption shown with the photo" value="${escapeHtml(segment.media_caption || "")}" /></label><div class="voice-preview-actions"><button class="button button-secondary button-small" type="button" data-attach-media="${escapeHtml(segment.id)}">Attach media</button><span class="segment-media-status" role="status">${segment.media_asset_id ? `Attached: ${escapeHtml(segment.media_asset_id)}` : ""}</span></div><small>Only rights-verified, active library images. The photo is contextual B-roll, never presented as match footage. Leave the asset ID empty to detach.</small></div>
      ${(segment.timeline_events || []).map((item) => `<div class="timeline-event"><strong>${escapeHtml(item.item_type)} · ${escapeHtml(item.item_id)}</strong><span>${escapeHtml(item.start_seconds)}–${escapeHtml(item.end_seconds)}s · ${escapeHtml(item.enter)} / ${escapeHtml(item.exit)} · ${escapeHtml(item.transition_in)} · ${escapeHtml(item.effect)}</span><small>${escapeHtml(item.text || "")}</small></div>`).join("")}</article>`).join("");
    document.querySelectorAll("[data-attach-media]").forEach((button) => button.addEventListener("click", () => attachSegmentMedia(button)));
    document.getElementById("render-visual-benchmark").disabled = false;
    const chapterEvents = draft.chapter_events || [];
    document.getElementById("draft-timeline").hidden = !chapterEvents.length;
    document.getElementById("draft-timeline").innerHTML = chapterEvents.length
      ? `<strong>Template chapter map</strong><div>${chapterEvents.map((item) => `<span>${escapeHtml(item.start_seconds)}s · ${escapeHtml(item.item_id.replaceAll("_", " "))}</span>`).join("")}</div>`
      : "";
    const note = draft.evidence_needed.length
      ? `Research still needed: ${draft.evidence_needed.map(escapeHtml).join("; ")}. This draft is not ready for voice or final rendering.`
      : "Evidence notes attached. Verify every factual statement and source before voice production.";
    document.getElementById("draft-evidence-note").textContent = `${note} · Template ${draft.template_id} v${draft.template_version}`;
    if (typeof draft.llm_cost_usd === "number" && draft.llm_calls) {
      const provider = [draft.llm_provider, draft.llm_model].filter(Boolean).join(" ").trim();
      document.getElementById("draft-evidence-note").textContent +=
        ` · Model${provider ? ` ${provider}` : ""} cost $${draft.llm_cost_usd.toFixed(4)} across ${draft.llm_calls} calls.`;
    }
    const panel = document.getElementById("draft-asset-check");
    const fixedOnly = draft.asset_needs.length === 0;
    panel.innerHTML = `<div>${fixedOnly
      ? `Asset plan: 0 variable assets. ${escapeHtml(draft.asset_need_reason)}`
      : `Asset plan: ${draft.asset_needs.reduce((sum, need) => sum + need.quantity, 0)} required variable asset(s) across ${draft.asset_needs.length} slot(s).`}</div>`;
    for (const check of result.asset_checks) {
      const block = document.createElement("div");
      block.className = "agent-asset-check";
      const evaluation = check.evaluation;
      const inventoryCount = (evaluation.eligible_assets || []).length;
      block.innerHTML = `<strong>${escapeHtml(check.need.discovery_query)}</strong><span>${inventoryCount
        ? `Library has ${inventoryCount}/${check.required_count} eligible saved asset(s); choose which to use.`
        : ["image", "video"].includes(check.need.resource_type)
          ? `No eligible library match. ${check.web_candidates.length} web suggestion(s) found; choose which to save/use.`
          : "No eligible library match. Web discovery supports images and video for this slot."}${check.discovery_error ? ` Search issue: ${escapeHtml(check.discovery_error)}` : ""}</span>`;
      if (check.web_candidates.length) {
        const grid = document.createElement("div");
        grid.className = "candidate-grid";
        grid.innerHTML = check.web_candidates.map(candidateCard).join("");
        grid.querySelectorAll("[data-approve]").forEach((button) => button.addEventListener("click", () => approveCandidate(button, check.requirement)));
        block.append(grid);
      }
      panel.append(block);
    }
    if (fixedOnly) panel.insertAdjacentHTML("beforeend", '<span class="status-pill status-ok">TEMPLATE COVERS VISUALS</span>');
    document.getElementById("script-result-panel").hidden = false;
    document.getElementById("script-result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message || "Could not create a script draft.");
  } finally {
    clearInterval(draftPoll);
    if (progress) progress.textContent = "";
    button.disabled = false;
    button.innerHTML = 'Draft script &amp; check assets <svg class="ic" aria-hidden="true"><use href="#i-chev"/></svg>';
  }
});

const voiceProfileForm = document.getElementById("voice-profile-form");
if (voiceProfileForm) voiceProfileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = new FormData(voiceProfileForm).get("voice_file");
  if (!(file instanceof File) || !file.size) return showToast("Choose a voice recording first.");
  const button = voiceProfileForm.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Saving locally…";
  try {
    const suffix = file.name.includes(".") ? `.${file.name.split(".").pop().toLowerCase()}` : "";
    const response = await fetch("/api/voice/profile", {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream", "X-Voice-Suffix": suffix },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save the voice sample.");
    document.getElementById("voice-profile-heading").textContent = "Allen voice reference saved locally";
    showToast("Voice reference saved to this workspace only.");
    await loadWorkflowStatus();
  } catch (error) {
    showToast(error.message || "Could not save the voice sample.");
  } finally {
    button.disabled = false;
    button.textContent = "Save voice locally";
  }
});

const voicePreviewButton = document.getElementById("create-voice-preview");
if (voicePreviewButton) voicePreviewButton.addEventListener("click", async () => {
  if (!currentRunId) return showToast("Create a script draft first.");
  const status = document.getElementById("voice-preview-status");
  const audio = document.getElementById("voice-preview-audio");
  voicePreviewButton.disabled = true;
  status.textContent = "Generating on this machine…";
  try {
    const response = await fetch("/api/voice/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not generate the local voice preview.");
    audio.src = result.audio_url;
    audio.hidden = false;
    document.getElementById("voice-preview-audited").disabled = false;
    await audio.play();
    status.textContent = "Preview generated locally. Listen for pronunciation, pace, and tone.";
  } catch (error) {
    status.textContent = error.message || "Local voice preview is not ready.";
  } finally {
    voicePreviewButton.disabled = false;
  }
});

const voiceAuditCheckbox = document.getElementById("voice-preview-audited");
if (voiceAuditCheckbox) voiceAuditCheckbox.addEventListener("change", async () => {
  const fullRenderButton = document.getElementById("render-full-video");
  if (!voiceAuditCheckbox.checked) {
    fullRenderButton.disabled = true;
    return;
  }
  voiceAuditCheckbox.disabled = true;
  const status = document.getElementById("render-full-status");
  status.textContent = "Recording local voice review…";
  try {
    const response = await fetch("/api/content/voice-review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId, voice_audited: true }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not record voice review.");
    fullRenderButton.disabled = false;
    status.textContent = "Voice preview review recorded. Full rendering is available.";
  } catch (error) {
    voiceAuditCheckbox.checked = false;
    status.textContent = error.message || "Could not record voice review.";
  } finally {
    voiceAuditCheckbox.disabled = false;
  }
});

async function attachSegmentMedia(button) {
  if (!currentRunId) return showToast("Create a script draft first.");
  const card = button.closest(".script-segment");
  if (!card) return;
  const segmentId = card.dataset.segmentId;
  const assetInput = card.querySelector('input[name="media_asset_id"]');
  const captionInput = card.querySelector('input[name="media_caption"]');
  const status = card.querySelector(".segment-media-status");
  const assetId = assetInput ? assetInput.value.trim() : "";
  const caption = captionInput ? captionInput.value.trim().normalize("NFC") : "";
  button.disabled = true;
  if (status) status.textContent = assetId ? "Attaching…" : "Detaching…";
  try {
    const response = await fetch("/api/content/attach-media", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId, segment_id: segmentId, asset_id: assetId, media_caption: caption }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not attach media.");
    if (status) status.textContent = result.status === "MEDIA_DETACHED" ? "Detached." : `Attached: ${result.asset_id}`;
    showToast(result.status === "MEDIA_DETACHED" ? "Media detached from segment." : "Media attached to segment.");
  } catch (error) {
    if (status) status.textContent = error.message || "Could not attach media.";
  } finally {
    button.disabled = false;
  }
}

async function renderVideo(endpoint, button, status, resultPanel, video, isPreview, reportElementId = "render-quality-report") {
  if (!currentRunId) return showToast("Create a script draft first.");
  button.disabled = true;
  status.textContent = "Rendering locally with FFmpeg…";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not render the video.");
    video.src = `${result.video_url}?v=${Date.now()}`;
    resultPanel.hidden = false;
    if (isPreview) {
      const report = result.report;
      document.getElementById(reportElementId).innerHTML = `
        <div class="render-report-heading"><strong>Visual render report</strong><a href="/api/render/${escapeHtml(currentRunId)}/report" target="_blank" rel="noopener noreferrer">Open JSON</a></div>
        <div class="render-report-grid">${report.quality_checks.map((check) => `<div class="render-check"><span class="render-check-status ${escapeHtml(check.status.toLowerCase().replaceAll(" ", "-"))}">${escapeHtml(check.status)}</span><strong>${escapeHtml(check.criterion)}</strong><small>${escapeHtml(check.detail)}</small></div>`).join("")}</div>
        <p class="render-limitations">${report.limitations.map(escapeHtml).join(" ")}</p>`;
    }
    status.textContent = isPreview ? "Preview ready. Play it here, then audit the checks below." : "Full video rendered. Review the output before treating it as complete.";
  } catch (error) {
    status.textContent = error.message || "Render did not complete.";
  } finally {
    button.disabled = false;
  }
}

const renderPreviewButton = document.getElementById("render-template-preview");
if (renderPreviewButton) renderPreviewButton.addEventListener("click", () => renderVideo(
  "/api/content/render-preview", renderPreviewButton,
  document.getElementById("render-preview-status"),
  document.getElementById("render-preview-result"),
  document.getElementById("render-preview-video"), true,
));

const renderVisualButton = document.getElementById("render-visual-benchmark");
if (renderVisualButton) renderVisualButton.addEventListener("click", () => renderVideo(
  "/api/content/render-visual-benchmark", renderVisualButton,
  document.getElementById("render-visual-status"),
  document.getElementById("render-visual-result"),
  document.getElementById("render-visual-video"), true,
  "render-visual-report",
));

const renderFullButton = document.getElementById("render-full-video");
if (renderFullButton) renderFullButton.addEventListener("click", () => renderVideo(
  "/api/content/render-full", renderFullButton,
  document.getElementById("render-full-status"),
  document.getElementById("render-full-result"),
  document.getElementById("render-full-video-player"), false,
));

const approveScriptButton = document.getElementById("approve-script");
if (approveScriptButton) approveScriptButton.addEventListener("click", async () => {
  if (!currentRunId) return showToast("Create a script draft first.");
  const status = document.getElementById("script-review-status");
  const segments = [...document.querySelectorAll("#script-segments .script-segment")].map((card) => ({
    id: card.dataset.segmentId,
    narration: card.querySelector("textarea").value.trim().normalize("NFC"),
  }));
  const evidence = document.querySelector('[name="evidence"]').value.normalize("NFC");
  approveScriptButton.disabled = true;
  status.textContent = "Saving reviewed script locally…";
  try {
    const response = await fetch("/api/content/script-review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId, segments, evidence, evidence_verified: document.getElementById("evidence-verified").checked }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not approve the reviewed script.");
    status.textContent = "Script approved locally. The voice preview is now available.";
    document.getElementById("create-voice-preview").disabled = false;
    document.getElementById("draft-status-heading").textContent = `SCRIPT APPROVED · run ${result.run_id}`;
  } catch (error) {
    status.textContent = error.message || "Could not approve the reviewed script.";
    approveScriptButton.disabled = false;
  }
});

loadOverview();
loadStats();
loadRuns();
if (location.hash.length > 1) showView(location.hash.slice(1));
