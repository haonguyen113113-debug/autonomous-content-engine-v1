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
    body.innerHTML = assets.map((asset) => `<tr>
      <td><div class="asset-name"><span class="asset-thumb">${asset.asset_type === "image" ? "?" : "?"}</span>${escapeHtml(asset.original_name)}</div></td>
      <td>${escapeHtml(asset.asset_type)}</td>
      <td>${escapeHtml(asset.purpose_code || "?")}</td>
      <td>${statusPill(asset.rights_state, "verified")}</td>
      <td>${escapeHtml(asset.license_type || "?")}</td>
      <td>${asset.source_url ? `<a href="${escapeHtml(asset.source_url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : "?"}</td>
      <td>${statusPill(asset.lifecycle_state, "active")}</td>
      <td>${escapeHtml(formatDate(asset.created_at))}</td>
      <td>${asset.rights_state !== "verified" ? `<button class="button button-secondary button-small" type="button" data-review-rights="${escapeHtml(asset.asset_id)}" title="Review the source and license for your intended use before confirming">Review rights</button>` : '<span class="review-complete">Reviewed</span>'}</td>
    </tr>`).join("");
    body.querySelectorAll("[data-review-rights]").forEach((button) => button.addEventListener("click", () => reviewAssetRights(button)));
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
  const discovery = result.recommendation === "ACQUIRE" && requirement.resource_type === "image"
    ? `<div class="discovery-section"><div class="eyebrow">EXTERNAL DISCOVERY</div><h4>Search openly licensed image collections</h4><p>Openverse searches across multiple indexed providers. Large images with commercial-use licenses are prioritized, then the dominant provider is excluded for a more varied second pass. Wikimedia Commons is a fallback. Results are suggestions only; nothing downloads until you choose.</p><form id="discovery-form" class="discovery-form"><input name="query" required maxlength="250" value="${escapeHtml(requirement.discovery_query || requirement.context || requirement.entity_id || requirement.purpose || requirement.content_objective || requirement.requirement_id)}" aria-label="Web search query" /><button class="button button-secondary" type="submit">Search images</button></form><div class="candidate-grid" id="candidate-grid"></div></div>`
    : result.recommendation === "ACQUIRE"
      ? '<p class="result-detail">External discovery currently supports images only.</p>'
      : "";
  panel.innerHTML = `<div class="result-header"><h3 class="result-title">${escapeHtml(result.status.replaceAll("_", " "))}</h3><span class="result-badge ${classes[result.recommendation] || "result-block"}">${escapeHtml(result.recommendation)}</span></div>
    <p class="result-detail">${escapeHtml(explanation[result.recommendation] || "Review the library evaluation before proceeding.")}</p>
    <div class="result-reasons">${reasons}</div>${discovery}`;
  panel.hidden = false;
  const searchForm = panel.querySelector("#discovery-form");
  if (searchForm) searchForm.addEventListener("submit", (event) => searchCandidates(event, requirement));
  panel.querySelectorAll("[data-approve]").forEach((button) => button.addEventListener("click", () => approveCandidate(button, requirement)));
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function candidateCard(candidate) {
  const dimensions = candidate.width && candidate.height ? `${candidate.width} ? ${candidate.height}` : "Dimensions unavailable";
  const size = candidate.size_bytes ? `${(candidate.size_bytes / 1024 / 1024).toFixed(1)} MB` : "Size unavailable";
  const license = candidate.license_name || "No license metadata found";
  const creator = candidate.creator || "Creator not listed";
  const sourceUrl = safeExternalUrl(candidate.source_url);
  const licenseUrl = safeExternalUrl(candidate.license_url);
  const thumbnailUrl = safeExternalUrl(candidate.thumbnail_url);
  return `<article class="candidate-card" data-candidate-card="${escapeHtml(candidate.candidate_id)}">
    ${thumbnailUrl ? `<img class="candidate-image" src="${escapeHtml(thumbnailUrl)}" alt="Preview of ${escapeHtml(candidate.title)}" loading="lazy" />` : '<div class="candidate-image candidate-image-empty">Preview unavailable</div>'}
    <div class="candidate-content"><div class="candidate-provider">${escapeHtml(candidate.provider)}</div>${sourceUrl ? `<a class="candidate-title" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(candidate.title)}</a>` : `<strong class="candidate-title">${escapeHtml(candidate.title)}</strong>`}
      <div class="candidate-meta">${escapeHtml(dimensions)} ? ${escapeHtml(size)}</div>
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
  const button = form.querySelector("button[type=submit]");
  const grid = document.getElementById("candidate-grid");
  button.disabled = true;
  button.textContent = "Searching…";
  grid.innerHTML = '<div class="candidate-message">Searching Wikimedia Commons…</div>';
  try {
    const response = await fetch("/api/discovery-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 24 }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Web discovery failed.");
    grid.innerHTML = result.candidates.length
      ? result.candidates.map(candidateCard).join("")
      : '<div class="candidate-message">No supported images found. Try a broader search phrase.</div>';
    grid.querySelectorAll("[data-approve]").forEach((approveButton) => approveButton.addEventListener("click", () => approveCandidate(approveButton, requirement)));
  } catch (error) {
    grid.innerHTML = `<div class="candidate-message candidate-error">${escapeHtml(error.message || "Web discovery failed.")}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Search images";
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
    card.innerHTML = `<div class="candidate-saved"><span>✓</span><div><strong>${escapeHtml(result.status.replaceAll("_", " "))}</strong><small>${escapeHtml(message)}</small></div></div>`;
    showToast(message);
    await loadAssets();
    if (rightsReviewed && result.status === "SAVED") await evaluateRequirement(requirement);
  } catch (error) {
    card.querySelectorAll("button").forEach((item) => { item.disabled = false; });
    button.textContent = rightsReviewed ? "Approve rights & save" : "Save for review";
    showToast(error.message || "Could not save this candidate.");
  }
}

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
    button.innerHTML = "<span>⌕</span> Check library inventory";
  }
});

document.getElementById("refresh-overview").addEventListener("click", loadOverview);
document.getElementById("refresh-library").addEventListener("click", () => { loadOverview(); loadAssets(); });

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
    document.getElementById("draft-mode-pill").textContent = `${draft.content_type.toUpperCase()} · ${draft.generation_mode === "local_ollama" ? "LOCAL MODEL" : "OUTLINE ONLY"}`;
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
        : check.need.resource_type === "image"
          ? `No eligible library match. ${check.web_candidates.length} web suggestion(s) found; choose which to save/use.`
          : "No eligible library match. Current web discovery supports still images for this slot."}${check.discovery_error ? ` Search issue: ${escapeHtml(check.discovery_error)}` : ""}</span>`;
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
    button.disabled = false;
    button.innerHTML = "Draft script &amp; check assets <span>&rarr;</span>";
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
if (location.hash.length > 1) showView(location.hash.slice(1));
