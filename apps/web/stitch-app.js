(() => {
  "use strict";

  const API = "/api/v1";
  const state = { view: "overview", dashboard: null, cases: [], selected: null, health: null, version: null, filter: "", modal: null, loading: true };
  document.body.innerHTML = '<div id="app" class="app-shell"></div><div id="toast-region" class="toast-region" aria-live="polite" aria-atomic="true"></div>';
  const root = document.getElementById("app");
  const toasts = document.getElementById("toast-region");
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const icon = (name) => `<span class="px-icon" aria-hidden="true">${name}</span>`;
  const date = (v) => v ? new Date(v).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—";
  const bytes = (v) => !Number.isFinite(v) ? "—" : v < 1024 ? `${v} B` : v < 1048576 ? `${(v / 1024).toFixed(1)} KB` : `${(v / 1048576).toFixed(1)} MB`;
  const hash = (v) => v ? `${v.slice(0, 12)}…${v.slice(-6)}` : "Hash unavailable";
  const label = (v) => String(v ?? "").replaceAll("_", " ");
  const suggestedReference = () => `CYB-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${Math.floor(100 + Math.random() * 900)}`;

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "The request could not be completed safely.");
    return payload;
  }
  function toast(message, error = false) {
    const node = document.createElement("div");
    node.className = `px-toast${error ? " error" : ""}`;
    node.innerHTML = `${icon(error ? "error" : "verified")}<span>${esc(message)}</span>`;
    toasts.append(node); setTimeout(() => node.remove(), 5000);
  }
  function status(detail) {
    const outcome = detail?.assessment?.outcome;
    const labels = { high_integrity_concern: ["High integrity concern", "concern"], needs_expert_review: ["Needs expert review", "review"], no_integrity_concern_detected: ["No concern detected", "good"], inconclusive: ["Inconclusive", "neutral"] };
    if (labels[outcome]) return labels[outcome];
    const findings = (detail?.evidence || []).flatMap((x) => x.analyses || []).flatMap((x) => x.findings || []);
    if (findings.some((x) => x.severity === "review")) return ["Needs expert review", "review"];
    if (findings.length) return ["No concern detected", "good"];
    return ["Awaiting analysis", "active"];
  }
  const chip = (text, tone = "neutral") => `<span class="px-status ${tone}">${esc(text)}</span>`;
  function nav(view, text, symbol, count = "") { return `<button class="${state.view === view ? "active" : ""}" type="button" data-nav="${view}">${icon(symbol)}<span>${text}</span>${count !== "" ? `<b class="pill-count">${esc(count)}</b>` : ""}</button>`; }
  function header(eyebrow, title, subtitle, action = "") { return `<header class="px-page-head"><div><p class="px-eyebrow">${esc(eyebrow)}</p><h1 class="px-page-title">${esc(title)}</h1><p class="px-page-subtitle">${esc(subtitle)}</p></div>${action}</header>`; }
  function empty(symbol, title, text, button = "", view = "intake") { return `<section class="px-card px-empty">${icon(symbol)}<h3>${esc(title)}</h3><p>${esc(text)}</p>${button ? `<button class="px-button" type="button" data-nav="${view}">${esc(button)}</button>` : ""}</section>`; }

  function shell(content) {
    const reviewCount = state.dashboard?.needs_expert_review ?? "";
    return `<div class="stitch-shell"><aside class="px-sidebar" aria-label="Primary navigation"><div class="px-brand"><div class="px-logo"></div><div class="px-brand-copy"><div class="px-brand-name">PARALLAX</div><div class="px-brand-sub">Evidence integrity</div></div></div><div class="px-side-scroll"><p class="px-side-label">Forensic workspace</p><nav class="px-nav">${nav("overview", "Overview", "grid_view")}${nav("cases", "Investigations", "folder_special", reviewCount)}</nav><p class="px-side-label">Evidence operations</p><nav class="px-nav">${nav("intake", "Secure intake", "cloud_upload")}${nav("case", "Case review", "verified_user")}</nav><p class="px-side-label">Modality analysis</p><nav class="px-nav">${nav("image", "Image forensics", "filter_center_focus")}${nav("video", "Video & CCTV", "movie")}${nav("audio", "Audio integrity", "graphic_eq")}</nav><p class="px-side-label">Audits & records</p><nav class="px-nav">${nav("audit", "Custody audit", "link")}${nav("reports", "Integrity dossiers", "description")}${nav("notes", "Notes & decision", "edit_note")}</nav><p class="px-side-label">System</p><nav class="px-nav">${nav("settings", "Settings & security", "settings")}</nav></div><div class="px-sidebar-footer"><div class="px-ledger"><i class="px-live-dot"></i><span>SECURE WORKSPACE</span></div><small>LOCAL INTEGRITY NODE</small></div></aside><main class="px-main"><header class="px-topbar"><button class="px-menu-toggle" type="button" data-action="menu" aria-label="Toggle navigation">${icon("menu")}</button><label class="px-search">${icon("search")}<input id="globalSearch" value="${esc(state.filter)}" placeholder="Search case, evidence, or title…" aria-label="Search cases"/><kbd>⌘K</kbd></label><div class="px-top-status"><i class="px-live-dot"></i>Secure workspace</div><div class="px-top-actions"><button class="px-outline-button" type="button" data-action="refresh">${icon("refresh")}<span>Refresh</span></button><button class="px-button" type="button" data-action="intake">${icon("add_circle")}<span>New analysis</span></button><div class="px-avatar" title="Demo forensic analyst">AK</div></div></header><section class="px-content">${content}</section></main>${modal()}</div>`;
  }

  function table(items) {
    if (!items.length) return empty("folder_open", "No cases found", "Create a secure case to begin original evidence preservation.", "New analysis");
    return `<div class="px-table-wrap"><table class="px-table"><thead><tr><th>Case</th><th>Evidence</th><th>Integrity state</th><th>Updated</th><th></th></tr></thead><tbody>${items.map((item) => { const detail = state.selected?.id === item.id ? state.selected : null; const [text, tone] = detail ? status(detail) : [item.evidence_count ? "Open for review" : "Awaiting evidence", item.evidence_count ? "active" : "neutral"]; return `<tr><td><strong>${esc(item.reference)}</strong><small>${esc(item.title)}</small></td><td>${item.evidence_count} item${item.evidence_count === 1 ? "" : "s"}</td><td>${chip(text, tone)}</td><td>${date(item.updated_at)}</td><td><button class="px-row-action" type="button" data-case="${esc(item.id)}">Review ${icon("arrow_forward")}</button></td></tr>`; }).join("")}</tbody></table></div>`;
  }

  function overview() {
    const dash = state.dashboard || { active_cases: 0, evidence_analysed: 0, needs_expert_review: 0, custody_integrity_percent: 0, recent_cases: [] };
    const selected = state.selected;
    const [st, tone] = selected ? status(selected) : ["Ready for intake", "neutral"];
    const bars = [31, 47, 38, 63, 45, 76, 59].map((height, i) => `<div class="px-bar-unit"><i class="px-bar" style="height:${height}%"></i><small>${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i]}</small></div>`).join("");
    return `${header("Investigation workspace", "Evidence integrity, explained.", "Preserve originals, surface reproducible integrity signals, and prioritise authorised human review.", `<button class="px-button" type="button" data-action="intake">${icon("add_circle")}New analysis</button>`)}<section class="px-metrics"><article class="px-card px-metric"><span class="px-metric-label">Active cases</span><strong class="px-metric-value">${dash.active_cases}</strong><span class="px-metric-meta good">Live case registry</span></article><article class="px-card px-metric"><span class="px-metric-label">Evidence preserved</span><strong class="px-metric-value">${dash.evidence_analysed}</strong><span class="px-metric-meta">SHA-256 recorded at intake</span></article><article class="px-card px-metric"><span class="px-metric-label">Needs expert review</span><strong class="px-metric-value">${dash.needs_expert_review}</strong><span class="px-metric-meta review">Signals need human context</span></article><article class="px-card px-metric"><span class="px-metric-label">Hash record coverage</span><strong class="px-metric-value">${dash.custody_integrity_percent}%</strong><span class="px-metric-meta good">Verify originals on demand</span></article></section><section class="px-grid-main"><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Cases requiring attention</h2><p class="px-card-sub">Live evidence registry — open any case to inspect source material.</p></div><button class="px-outline-button" type="button" data-nav="cases">View all ${icon("arrow_forward")}</button></header>${table(dash.recent_cases || [])}</article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Integrity signal monitor</h2><p class="px-card-sub">Review-level signals in this workspace.</p></div>${chip("7 day view", "active")}</header><div class="px-chart"><div class="px-chart-bars">${bars}</div><div class="px-chart-foot"><span class="px-legend"><i></i>Review signals</span><span>Context before conclusions</span></div></div></article><article class="px-card px-case-highlight">${selected ? preview(selected, st, tone) : empty("inventory_2", "No active case", "Create a secure record to see its evidence summary here.", "Create case")}</article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Evidence lifecycle</h2><p class="px-card-sub">Traceable by design</p></div></header><div class="px-card-body"><ol class="px-audit-list"><li><strong>Secure intake</strong><span>Signature validation, SHA-256, read-only original</span></li><li><strong>Integrity analysis</strong><span>Derived artifacts remain separate from evidence</span></li><li><strong>Human review</strong><span>Analyst rationale and disposition recorded</span></li><li><strong>Integrity dossier</strong><span>JSON, HTML, and PDF reports are hashed</span></li></ol></div></article></section>`;
  }
  function preview(detail, st, tone) { const item = detail.evidence?.[0]; const fs = (detail.evidence || []).flatMap((x) => x.analyses || []).flatMap((x) => x.findings || []).slice(0, 3); return `<div class="px-case-highlight-top"><div><p class="px-eyebrow">Active investigation</p><h2 class="px-card-title">${esc(detail.reference)}</h2></div>${chip(st, tone)}</div>${item ? `<div class="px-file-hero"><div class="px-evidence-art"></div><div><strong>${esc(item.original_filename)}</strong><small>${bytes(item.size_bytes)} · ${esc(item.media_type)} evidence</small><small>SHA-256 · ${hash(item.sha256)}</small></div></div>` : ""}<div class="px-findings">${fs.length ? fs.map((f) => `<div class="px-finding"><i class="px-finding-dot ${f.severity === "review" ? "review" : ""}"></i><p><strong>${esc(f.title)}</strong><span>${esc(f.detail)}</span></p></div>`).join("") : "<p class='px-card-sub'>No completed findings recorded yet.</p>"}</div><button class="px-outline-button px-full-action" type="button" data-case="${esc(detail.id)}">Open evidence review ${icon("arrow_forward")}</button>`; }
  function cases() { const needle = state.filter.trim().toLowerCase(); const filtered = state.cases.filter((x) => `${x.reference} ${x.title}`.toLowerCase().includes(needle)); return `${header("Case management", "Investigations", "Search live cases, preserve evidence sources, and open a complete forensic review workspace.", `<button class="px-button" type="button" data-action="intake">${icon("add_circle")}New secure intake</button>`)}<section class="px-card"><div class="px-card-body"><div class="px-filter-row"><label class="px-search">${icon("search")}<input id="caseSearch" value="${esc(state.filter)}" placeholder="Filter case reference or title…"/></label><select class="px-select" disabled><option>All integrity states</option></select><select class="px-select" disabled><option>All evidence types</option></select></div></div>${table(filtered)}</section>`; }

  function analysis(item, run) {
    const findings = run.findings || []; const artifacts = run.artifacts || [];
    return `<section class="px-analysis-run"><div class="px-analysis-head"><strong>${esc(run.module)}</strong><small>v${esc(run.module_version)} · ${date(run.created_at)}</small></div><ul class="px-signal-list">${findings.map((f) => `<li class="${f.severity === "review" ? "review" : ""}"><strong>${esc(f.title)}</strong>${esc(f.detail)}</li>`).join("") || "<li>No stored signals.</li>"}</ul>${artifacts.map((a) => `<a class="px-artifact-link" href="${API}/cases/artifacts/${encodeURIComponent(a.id)}" target="_blank" rel="noopener">${icon("image")}View ${esc(a.artifact_type)} · ${hash(a.sha256)}</a>`).join("<br/>")}</section>`;
  }
  function evidence(item) {
    const type = item.media_type === "video" ? "video" : item.media_type === "audio" ? "audio" : "";
    return `<article class="px-card px-evidence-card"><header class="px-evidence-header"><div class="px-evidence-name"><div class="px-file-icon ${type}">${esc(item.media_type.slice(0, 3).toUpperCase())}</div><div><strong>${esc(item.original_filename)}</strong><small>${esc(item.mime_type)} · ${bytes(item.size_bytes)} · ${date(item.created_at)}</small></div></div><div class="px-action-row"><a class="px-outline-button" href="${API}/cases/evidence/${encodeURIComponent(item.id)}/original" target="_blank" rel="noopener">${icon("download")}Original</a><button class="px-outline-button" type="button" data-action="verify-evidence" data-id="${esc(item.id)}">${icon("fingerprint")}Re-hash</button></div></header><div class="px-card-body"><code class="px-hash-chip">${esc(item.sha256)}</code>${item.analyses?.length ? item.analyses.map((run) => analysis(item, run)).join("") : `<section class="px-analysis-run"><strong>No completed ${esc(item.media_type)} analysis</strong><p class="px-card-sub">The original is preserved. Run a bounded review when ready.</p><button class="px-outline-button" type="button" data-action="run-analysis" data-id="${esc(item.id)}" data-media="${esc(item.media_type)}">${icon("play_circle")}Run review</button></section>`}</div></article>`;
  }
  function assessment(detail) {
    const [text, tone] = status(detail); const a = detail.assessment;
    return `<article class="px-card px-assessment"><p class="px-eyebrow">Review recommendation</p><div class="px-assessment-score">${icon(a ? "insights" : "pending_actions")}<div><strong>${esc(text)}</strong><p>${a ? `${a.signals.length} contributing review signal(s)` : "Human assessment pending"}</p></div></div>${a ? a.reasons.map((r) => `<p class="px-card-sub">${esc(r)}</p>`).join("") : "<p class='px-card-sub'>No assessment is recorded. Review source evidence, then request a recommendation.</p>"}<div class="px-section-rule"></div>${chip("Human review required", tone)}</article>`;
  }
  function reportsCard(detail) {
    const reports = detail.reports || [];
    return `<article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Integrity dossiers</h2><p class="px-card-sub">Every generated output is hashed.</p></div></header><div class="px-card-body">${reports.length ? `<div class="px-report-list">${reports.map((r) => `<div class="px-report"><div class="px-report-info"><i class="px-report-icon">${esc(r.report_format.toUpperCase())}</i><div><strong>${esc(r.report_format.toUpperCase())} dossier</strong><small>${hash(r.sha256)}</small></div></div><a href="${API}/cases/reports/${encodeURIComponent(r.id)}" target="_blank" rel="noopener">Open</a></div>`).join("")}</div>` : "<p class='px-card-sub'>No dossier generated yet.</p>"}</div></article>`;
  }
  function auditsCard(detail) { return `<article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Recent custody events</h2><p class="px-card-sub">Hash-linked case history.</p></div></header><div class="px-card-body"><ol class="px-audit-list">${detail.audit_events.slice(0, 5).map((e) => `<li><strong>${esc(e.event_type)}</strong><span>${date(e.created_at)} · ${esc(e.actor)}</span></li>`).join("") || "<li><span>No events available.</span></li>"}</ol></div></article>`; }
  function selectedEmpty() { return empty("folder_special", "Choose an investigation", "Open a live case from Overview or Investigations to inspect its evidence, custody chain, reports, and analyst decisions.", "View investigations", "cases"); }

  function caseView() {
    const detail = state.selected; if (!detail) return `${header("Investigation record", "Case review", "A multi-pane workspace for source evidence, findings, custody, and human decisions.")}${selectedEmpty()}`;
    const [st, tone] = status(detail);
    return `<div class="px-card px-case-banner"><div class="px-case-banner-row"><div><span class="px-case-id">${esc(detail.reference)}</span><h1>${esc(detail.title)}</h1><p class="px-card-sub">Created ${date(detail.created_at)} · ${detail.evidence.length} evidence item${detail.evidence.length === 1 ? "" : "s"}</p></div><div class="px-action-row">${chip(st, tone)}<button class="px-outline-button" type="button" data-action="verify-audit">${icon("verified")}Verify custody audit</button><button class="px-outline-button" type="button" data-action="assessment">${icon("rate_review")}Update recommendation</button><button class="px-button" type="button" data-action="report">${icon("picture_as_pdf")}Generate dossier</button></div></div><div class="px-notice">${icon("gavel")}<span><strong>Human forensic review required.</strong> Automated findings are investigation leads, not a legal authenticity determination.</span></div></div><div class="px-tabs"><button class="px-tab active">${icon("biotech")}Evidence & findings</button><button class="px-tab" data-nav="audit">${icon("link")}Custody timeline (${detail.audit_events.length})</button><button class="px-tab" data-nav="reports">${icon("description")}Dossiers</button><button class="px-tab" data-nav="notes">${icon("edit_note")}Notes & decision</button></div><section class="px-grid-case"><div class="px-stack">${detail.evidence.length ? detail.evidence.map(evidence).join("") : empty("upload_file", "No evidence uploaded", "This case is ready for a securely preserved source file.", "Add evidence")}</div><aside class="px-inspector px-stack">${assessment(detail)}${reportsCard(detail)}${auditsCard(detail)}</aside></section>`;
  }

  function modality(kind) {
    const detail = state.selected; const media = kind === "image" ? "image" : kind === "video" ? "video" : "audio"; const info = { image: ["Image & metadata forensics", "Inspect EXIF, timestamps, JPEG recompression signals, bounded copy-move candidates, and derived ELA artifacts."], video: ["Video & CCTV integrity", "Review sampled frames, near-duplicate candidates, transition leads, and contact sheets."], audio: ["Audio integrity review", "Inspect WAV waveform, spectral context, silence, energy transitions, and clipping leads."] }[kind]; const items = detail?.evidence.filter((x) => x.media_type === media) || [];
    const visual = kind === "audio" ? "<div class='px-wave'></div>" : kind === "video" ? "<div class='px-frame-strip'><i class='px-frame'></i><i class='px-frame flag'></i><i class='px-frame'></i><i class='px-frame flag'></i><i class='px-frame'></i></div><i class='px-scanline'></i>" : "<i class='px-scanline'></i>";
    return `${header("Modality analysis", info[0], info[1])}<section class="px-card px-module-hero"><div><p class="px-eyebrow">${kind.toUpperCase()} MODULE</p><h1 class="px-page-title">${esc(detail?.reference || "Select a case")}</h1><p class="px-page-subtitle">${detail ? "Live source evidence is shown below. Every output is a review signal and is retained separately from the original." : "Select an investigation to load stored module analysis."}</p></div><div class="px-module-meta"><span>Current capability</span><strong>${kind === "image" ? "EXIF · timestamps · JPEG ELA · ORB review" : kind === "video" ? "sampling · duplicates · transitions" : "WAV waveform · spectrogram · energy"}</strong><span>Original evidence remains read-only</span></div></section><section class="px-grid-2"><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Forensic visual workspace</h2><p class="px-card-sub">Derived visual layer, not source evidence.</p></div></header><div class="px-card-body"><div class="px-visual-canvas ${kind === "image" ? "" : kind}"><div class="px-grid-overlay"></div>${visual}</div></div></article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Stored source evidence</h2><p class="px-card-sub">Open the full case to inspect all context.</p></div></header><div class="px-card-body">${items.length ? items.map(evidence).join("") : empty("pageview", `No ${media} evidence selected`, "Select a case containing this media type, or safely upload an original file.", "Open cases", "cases")}</div></article></section>`;
  }

  function auditView() {
    const detail = state.selected; if (!detail) return `${header("Audits & ledger", "Custody audit verification", "Verify the linked event history that protects case handling.")}${selectedEmpty()}`;
    return `${header("Audits & ledger", "Custody audit verification", "New local events are hash-chained per case. A change to stored event data will be flagged by verification.", `<button class="px-button" type="button" data-action="verify-audit">${icon("verified")}Verify now</button>`)}<section class="px-grid-2"><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Linked custody history</h2><p class="px-card-sub">${esc(detail.reference)} · ${detail.audit_events.length} recorded events</p></div></header><div class="px-card-body"><div class="px-custody-chain">${detail.audit_events.slice().reverse().map((e) => `<div class="px-chain-node"><div class="px-chain-badge">${icon("check")}</div><article class="px-card"><h3>${esc(e.event_type)}</h3><p>${date(e.created_at)} · ${esc(e.actor)}</p><code>${e.event_hash ? `sealed: ${hash(e.event_hash)}` : "legacy event: no chain hash"}</code></article></div>`).join("")}</div></div></article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Verification boundary</h2><p class="px-card-sub">What the local check proves.</p></div></header><div class="px-card-body"><div class="px-notice">${icon("info")}<span>Parallax validates stored case events against a local hash chain. Production needs external anchoring or managed signing keys as an additional protection.</span></div><div class="px-section-rule"></div><p class="px-card-sub">If a mismatch is shown, preserve the database and source evidence, then escalate to an authorised forensic reviewer.</p></div></article></section>`;
  }
  function reportsView() { const detail = state.selected; if (!detail) return `${header("Evidence reporting", "Integrity dossiers", "Generate structured records with original hashes, findings, custody events, and limitations.")}${selectedEmpty()}`; return `${header("Evidence reporting", "Integrity dossiers", "Dossiers are derived, hashed investigation records — not legal authenticity verdicts.", `<button class="px-button" type="button" data-action="report">${icon("picture_as_pdf")}Generate set</button>`)}<section class="px-grid-2">${reportsCard(detail)}<article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Fixed report contents</h2><p class="px-card-sub">Evidence-linked output for human review.</p></div></header><div class="px-card-body"><ol class="px-audit-list"><li><strong>Original evidence hashes</strong><span>SHA-256 values and intake records</span></li><li><strong>Methods & findings</strong><span>Module versions, signals, and derived artifacts</span></li><li><strong>Custody event history</strong><span>Actors and timestamps for case operations</span></li><li><strong>Limitations statement</strong><span>Human-review boundary included in every output</span></li></ol></div></article></section>`; }
  function notesView() { const detail = state.selected; if (!detail) return `${header("Human decision layer", "Analyst notes & decisions", "Record context, follow-up, and disposition separately from automated signals.")}${selectedEmpty()}`; return `${header("Human decision layer", "Analyst notes & decisions", "Analyst judgment is auditable and remains visible in the custody history.")}<section class="px-grid-case"><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Record analyst decision</h2><p class="px-card-sub">Saving this note adds an audit event to the case.</p></div></header><form id="noteForm" class="px-card-body"><label class="px-form-label">Analyst note<textarea class="px-textarea" name="note" required placeholder="Explain the source context, limitation, required follow-up, or human decision…"></textarea></label><label class="px-form-label" style="margin-top:14px">Disposition<select class="px-select" name="disposition" style="width:100%"><option value="">No disposition selected</option><option>Continue investigation</option><option>Escalate for forensic examination</option><option>No further automated action</option><option>Request original source file</option></select></label><div class="px-modal-actions" style="padding:18px 0 0;border:0"><button class="px-button" type="submit">${icon("save")}Record note and decision</button></div></form></article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Recorded analyst context</h2><p class="px-card-sub">${detail.notes.length} note${detail.notes.length === 1 ? "" : "s"} stored</p></div></header><div class="px-card-body"><div class="px-note-list">${detail.notes.length ? detail.notes.map((n) => `<article class="px-note"><strong>${esc(n.disposition || "Analyst note")}</strong><span>${esc(n.note)}</span><small>${esc(n.author)} · ${date(n.created_at)}</small></article>`).join("") : "<p class='px-card-sub'>No notes recorded for this case.</p>"}</div></div></article></section>`; }
  function settings() { const h = state.health || { status: "checking" }; const v = state.version || { api_version: "—", forensic_engine_version: "—" }; return `${header("System configuration", "Settings & security", "Local hackathon environment and current evidence-handling safeguards.")}<section class="px-settings-grid"><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">Runtime status</h2><p class="px-card-sub">Connectivity and local service profile.</p></div>${chip(h.status === "ok" ? "API healthy" : "Checking API", h.status === "ok" ? "good" : "active")}</header><div class="px-card-body"><div class="px-kv"><div><strong>API version</strong><span>Current FastAPI contract</span></div><code>${esc(v.api_version)}</code></div><div class="px-kv"><div><strong>Forensic engine</strong><span>Bounded local analysis modules</span></div><code>${esc(v.forensic_engine_version)}</code></div><div class="px-kv"><div><strong>Storage mode</strong><span>Local original evidence vault</span></div><code>SQLite WAL + filesystem</code></div></div></article><article class="px-card"><header class="px-card-header"><div><h2 class="px-card-title">MVP safeguards</h2><p class="px-card-sub">Clear operational boundaries.</p></div></header><div class="px-card-body"><div class="px-kv"><div><strong>Original evidence</strong><span>Read-only after complete intake write</span></div>${chip("Protected", "good")}</div><div class="px-kv"><div><strong>Custody audit</strong><span>Hash-chain verification per case</span></div>${chip("On demand", "active")}</div><div class="px-kv"><div><strong>Authentication</strong><span>Demo analyst header is not production RBAC</span></div>${chip("Hardening required", "review")}</div><div class="px-kv"><div><strong>Media processing</strong><span>Runs synchronously in the local MVP</span></div>${chip("Worker queue planned", "review")}</div></div></article></section>`; }
  function modal() { if (state.modal !== "intake") return ""; return `<div class="px-modal" role="dialog" aria-modal="true" aria-labelledby="intake-title"><section class="px-modal-panel"><header class="px-modal-head"><div><p class="px-eyebrow">New forensic analysis</p><h2 id="intake-title">Create a secure evidence record</h2><p>File signature and SHA-256 are recorded before analysis starts.</p></div><button type="button" class="px-close" data-action="close">${icon("close")}</button></header><div class="px-steps"><span class="px-step active"><b>1</b>Case details</span><span class="px-step active"><b>2</b>Original evidence</span><span class="px-step"><b>3</b>Preservation</span><span class="px-step"><b>4</b>Module review</span></div><form id="intakeForm"><div class="px-modal-body"><div class="px-form-grid"><label class="px-form-label">Case reference<input class="px-input" name="reference" value="${suggestedReference()}" required pattern="[A-Za-z0-9_-]{3,64}"/></label><label class="px-form-label">Case title<input class="px-input" name="title" value="Digital evidence intake" required/></label></div><label class="px-upload" for="intakeFile">${icon("upload_file")}<strong>Choose original evidence</strong><span>JPEG, PNG, WAV, MP3, MP4, AVI, or MKV · original stored separately from derived artifacts</span><input id="intakeFile" name="file" type="file" accept="image/*,audio/*,video/*" required hidden/></label><p class="px-card-sub" id="fileHint" style="margin:12px 0 0">WAV supports local audio analysis. Other supported originals are safely preserved; an approved decoder is needed before local audio review.</p></div><footer class="px-modal-actions"><button type="button" class="px-outline-button" data-action="close">Cancel</button><button class="px-button" type="submit">${icon("lock")}Preserve & analyse</button></footer></form></section></div>`; }

  function currentView() {
    const views = { overview, cases, case: caseView, image: () => modality("image"), video: () => modality("video"), audio: () => modality("audio"), audit: auditView, reports: reportsView, notes: notesView, settings };
    return (views[state.view] || overview)();
  }
  function render() {
    root.innerHTML = shell(state.loading ? `<section class="px-card px-empty">${icon("sync")}<h3>Loading secure workspace</h3><p>Retrieving case registry and integrity records.</p></section>` : currentView());
  }
  async function refresh({ preserveView = true } = {}) {
    state.loading = true; render();
    const selectedId = state.selected?.id;
    const [dashboard, cases, health, version] = await Promise.all([
      api("/dashboard"), api("/cases"), api("/health"), api("/version"),
    ]);
    state.dashboard = dashboard; state.cases = cases; state.health = health; state.version = version;
    if (selectedId) state.selected = await api(`/cases/${encodeURIComponent(selectedId)}`).catch(() => null);
    if (!state.selected && cases.length) state.selected = await api(`/cases/${encodeURIComponent(cases[0].id)}`).catch(() => null);
    state.loading = false;
    if (!preserveView) state.view = "overview";
    render();
  }
  async function openCase(id) {
    state.selected = await api(`/cases/${encodeURIComponent(id)}`);
    state.view = "case"; state.modal = null; render();
  }
  function selectedOrThrow() {
    if (!state.selected) throw new Error("Select a case before running this operation.");
    return state.selected;
  }
  async function runAnalysis(evidenceId, media) {
    const result = await api(`/cases/evidence/${encodeURIComponent(evidenceId)}/analysis/${encodeURIComponent(media)}`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
    toast(`${label(media)} analysis completed: ${result.findings?.length || 0} signal(s) recorded.`);
    await refresh();
  }
  async function dispatchAction(action, node) {
    if (action === "menu") { document.querySelector(".px-sidebar")?.classList.toggle("open"); return; }
    if (action === "intake") { state.modal = "intake"; render(); return; }
    if (action === "close") { state.modal = null; render(); return; }
    if (action === "refresh") { await refresh(); toast("Workspace refreshed."); return; }
    if (action === "run-analysis") { await runAnalysis(node.dataset.id, node.dataset.media); return; }
    const detail = selectedOrThrow();
    if (action === "verify-evidence") {
      const result = await api(`/cases/evidence/${encodeURIComponent(node.dataset.id)}/verify-integrity`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
      toast(result.matches ? "Original SHA-256 matches the intake record." : "Integrity mismatch recorded — preserve and escalate.", !result.matches);
      await refresh(); return;
    }
    if (action === "verify-audit") {
      const result = await api(`/cases/${encodeURIComponent(detail.id)}/verify-audit-chain`);
      toast(result.chain_intact ? "Custody audit chain verified." : "Custody audit chain mismatch detected.", !result.chain_intact);
      return;
    }
    if (action === "assessment") {
      await api(`/cases/${encodeURIComponent(detail.id)}/assessment`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
      toast("Review recommendation updated. Human context remains required."); await refresh(); return;
    }
    if (action === "report") {
      const reports = await api(`/cases/${encodeURIComponent(detail.id)}/reports`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
      toast(`${reports.length} integrity dossier(s) generated and hashed.`); await refresh(); return;
    }
  }

  document.addEventListener("click", async (event) => {
    const caseButton = event.target.closest("[data-case]");
    const navButton = event.target.closest("[data-nav]");
    const actionButton = event.target.closest("[data-action]");
    try {
      if (caseButton) { await openCase(caseButton.dataset.case); return; }
      if (navButton) {
        const next = navButton.dataset.nav;
        if (next === "intake") { state.modal = "intake"; render(); return; }
        state.view = next; state.modal = null; render(); return;
      }
      if (actionButton) await dispatchAction(actionButton.dataset.action, actionButton);
    } catch (error) { toast(error.message || "Operation failed safely.", true); }
  });
  document.addEventListener("input", (event) => {
    if (event.target.id === "globalSearch" || event.target.id === "caseSearch") {
      state.filter = event.target.value; if (state.view === "cases") render();
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.id !== "intakeFile") return;
    const file = event.target.files?.[0];
    const hint = document.getElementById("fileHint");
    if (hint) hint.textContent = file ? `${file.name} · ${bytes(file.size)} · original source will be preserved before analysis.` : "No file selected.";
  });
  document.addEventListener("submit", async (event) => {
    if (event.target.id === "intakeForm") {
      event.preventDefault();
      const form = new FormData(event.target);
      const reference = String(form.get("reference") || "").trim();
      const title = String(form.get("title") || "").trim();
      const file = form.get("file");
      if (!(file instanceof File) || !file.size) { toast("Choose an original evidence file first.", true); return; }
      try {
        const created = await api("/cases", { method: "POST", headers: { "Content-Type": "application/json", "X-Analyst-ID": "demo-analyst" }, body: JSON.stringify({ reference, title }) });
        const source = new FormData(); source.append("file", file, file.name);
        const evidence = await api(`/cases/${encodeURIComponent(created.id)}/evidence`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" }, body: source });
        state.selected = await api(`/cases/${encodeURIComponent(created.id)}`);
        state.view = "case"; state.modal = null; render();
        toast("Original preserved and SHA-256 recorded. Starting bounded analysis…");
        try { await runAnalysis(evidence.id, evidence.media_type); } catch (analysisError) { toast(`Original is preserved. ${analysisError.message}`, true); await refresh(); }
      } catch (error) { toast(error.message || "Secure intake could not be completed.", true); }
      return;
    }
    if (event.target.id === "noteForm") {
      event.preventDefault();
      try {
        const detail = selectedOrThrow(); const form = new FormData(event.target);
        await api(`/cases/${encodeURIComponent(detail.id)}/notes`, { method: "POST", headers: { "Content-Type": "application/json", "X-Analyst-ID": "demo-analyst" }, body: JSON.stringify({ note: String(form.get("note") || ""), disposition: String(form.get("disposition") || "") || null }) });
        toast("Analyst note and audit event recorded."); await refresh();
      } catch (error) { toast(error.message || "Note could not be recorded.", true); }
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); document.getElementById("globalSearch")?.focus(); }
    if (event.key === "Escape" && state.modal) { state.modal = null; render(); }
  });

  refresh().catch((error) => {
    state.loading = false;
    root.innerHTML = shell(`<section class="px-card px-empty">${icon("error")}<h3>Workspace unavailable</h3><p>${esc(error.message || "The API could not be reached.")}</p><button class="px-button" data-action="refresh">Retry connection</button></section>`);
  });
})();



