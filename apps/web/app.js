const API_BASE = "/api/v1";
const navButtons = document.querySelectorAll("[data-view]");
const dashboardView = document.getElementById("dashboardView");
const alternateView = document.getElementById("alternateView");
const alternateTitle = document.getElementById("alternateTitle");
const alternateEyebrow = document.getElementById("alternateEyebrow");
const alternateSubtitle = document.getElementById("alternateSubtitle");
const alternatePanelTitle = document.getElementById("alternatePanelTitle");
const alternatePanelText = document.getElementById("alternatePanelText");
const alternatePanel = document.getElementById("alternatePanel");
const uploadModal = document.getElementById("uploadModal");
const toast = document.getElementById("toast");
const uploadButton = document.getElementById("startAnalysis");
const caseQueue = document.getElementById("caseQueue");
const activeCasePanel = document.getElementById("activeCasePanel");

const views = {
  dashboard: ["Investigation workspace", "Good morning, Analyst.", "Review evidence integrity signals and prioritise what needs human attention.", "Parallax overview", "Your active evidence and integrity queue appear here."],
  cases: ["Case management", "All investigations", "Open a case to review evidence, findings, and custody records.", "Choose an investigation", "This workspace will surface the selected case, its evidence timeline, and explainable integrity findings."],
  evidence: ["Secure storage", "Evidence vault", "Every original is preserved separately from derived forensic artifacts.", "Evidence integrity first", "Browse immutable originals, derived artifacts, hashes, and custody events from one secure view."],
  reports: ["Decision support", "Integrity dossiers", "Generate a structured record with methods, findings, limitations, and review notes.", "No report selected", "Choose a completed analysis to create an explainable PDF and JSON Evidence Integrity Dossier."]
};

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 3600);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
}

function displayDate(isoValue) {
  return new Date(isoValue).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function renderCaseQueue(cases) {
  if (!cases.length) {
    caseQueue.innerHTML = `<tr><td colspan="5" class="empty-row">No cases yet. Create a case and upload original evidence to begin.</td></tr>`;
    return;
  }
  caseQueue.innerHTML = cases.map((item) => `
    <tr>
      <td><strong>${escapeHtml(item.reference)}</strong><small>${escapeHtml(item.title)}</small></td>
      <td><span class="file-icon image-file">${item.evidence_count}</span>${item.evidence_count === 1 ? "evidence item" : "evidence items"}</td>
      <td><span class="status-pill neutral">Awaiting analysis</span></td>
      <td>${displayDate(item.updated_at)}</td>
      <td><button class="row-button" type="button" data-case="${item.id}">Review →</button></td>
    </tr>`).join("");
}

async function renderActiveCase(cases) {
  if (!cases.length) {
    activeCasePanel.innerHTML = `<div class="panel-heading compact"><div><p class="eyebrow">Active investigation</p><h2>No active case</h2></div><span class="status-pill neutral">Ready</span></div><p class="muted-copy panel-empty-copy">Create a secure case record to see its live evidence summary and integrity signals here.</p>`;
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(cases[0].id)}`);
    const detail = await responseJson(response);
    const [label, tone] = reportStatus(detail);
    const firstEvidence = detail.evidence[0];
    const findings = detail.evidence.flatMap((item) => item.analyses || []).flatMap((analysis) => analysis.findings || []).slice(0, 3);
    const evidenceSummary = firstEvidence ? `<div class="evidence-file"><div class="image-preview" aria-hidden="true"><span class="preview-frame"></span><span class="preview-person"></span><span class="preview-tamper"></span></div><div><strong>${escapeHtml(firstEvidence.original_filename)}</strong><small>${escapeHtml(firstEvidence.media_type)} evidence · ${(firstEvidence.size_bytes / 1024).toFixed(1)} KB</small><code>SHA-256 · ${escapeHtml(firstEvidence.sha256.slice(0, 12))}…</code></div></div>` : "<p class='muted-copy panel-empty-copy'>No evidence has been uploaded yet.</p>";
    const findingList = findings.length ? `<div class="finding-list">${findings.map((finding) => `<div><span class="finding-marker ${finding.severity === "review" ? "medium" : "low"}"></span><p><strong>${escapeHtml(finding.title)}</strong><small>${escapeHtml(finding.detail)}</small></p></div>`).join("")}</div>` : "<p class='muted-copy panel-empty-copy'>No completed forensic findings for this case yet.</p>";
    activeCasePanel.innerHTML = `<div class="panel-heading compact"><div><p class="eyebrow">Active investigation</p><h2>${escapeHtml(detail.reference)}</h2></div><span class="status-pill ${tone}">${label}</span></div>${evidenceSummary}${findingList}<button class="full-review-button" type="button" data-case="${escapeHtml(detail.id)}">Open evidence review <span>→</span></button>`;
  } catch (error) {
    activeCasePanel.innerHTML = `<div class="panel-heading compact"><div><p class="eyebrow">Active investigation</p><h2>Case preview unavailable</h2></div></div><p class="muted-copy panel-empty-copy">The case list loaded, but this evidence summary could not be retrieved.</p>`;
  }
}

function reportStatus(detail) {
  if (detail.assessment) {
    const assessmentLabels = {
      high_integrity_concern: ["High integrity concern", "concern"],
      needs_expert_review: ["Needs expert review", "review"],
      no_integrity_concern_detected: ["No concern detected", "neutral"],
      inconclusive: ["Inconclusive", "neutral"]
    };
    return assessmentLabels[detail.assessment.outcome] || ["Assessment recorded", "neutral"];
  }
  const findings = detail.evidence.flatMap((item) => item.analyses || []).flatMap((analysis) => analysis.findings || []);
  if (!detail.evidence.length) return ["Inconclusive", "neutral"];
  if (findings.some((finding) => finding.severity === "review")) return ["Needs expert review", "review"];
  if (findings.length) return ["No integrity concern detected", "neutral"];
  return ["Awaiting analysis", "neutral"];
}

function renderCaseReview(detail) {
  const [label, tone] = reportStatus(detail);
  const evidenceMarkup = detail.evidence.map((item) => {
    const analyses = (item.analyses || []).map((analysis) => {
      const findings = analysis.findings.map((finding) => `
        <li class="review-finding ${escapeHtml(finding.severity)}"><strong>${escapeHtml(finding.title)}</strong><span>${escapeHtml(finding.detail)}</span></li>`).join("");
      const artifacts = analysis.artifacts.map((artifact) => `<a class="artifact-link" href="${API_BASE}/cases/artifacts/${encodeURIComponent(artifact.id)}" target="_blank" rel="noopener">View ${escapeHtml(artifact.artifact_type)} · ${escapeHtml(artifact.sha256.slice(0, 12))}…</a>`).join("");
      return `<div class="analysis-block"><div class="analysis-heading"><strong>${escapeHtml(analysis.module)}</strong><small>v${escapeHtml(analysis.module_version)} · ${displayDate(analysis.created_at)}</small></div><ul class="review-findings">${findings || "<li class='review-finding info'><strong>No findings stored</strong></li>"}</ul>${artifacts}</div>`;
    }).join("");
    return `<article class="evidence-review-card"><div class="evidence-review-head"><div><span class="file-icon ${escapeHtml(item.media_type)}-file">${escapeHtml(item.media_type.slice(0, 3).toUpperCase())}</span><strong>${escapeHtml(item.original_filename)}</strong><small>${escapeHtml(item.mime_type)} · ${(item.size_bytes / 1024).toFixed(1)} KB</small></div><a class="original-link" href="${API_BASE}/cases/evidence/${encodeURIComponent(item.id)}/original" target="_blank" rel="noopener">Download original</a></div><code>SHA-256 · ${escapeHtml(item.sha256)}</code><button class="verify-button" type="button" data-verify-evidence="${escapeHtml(item.id)}">Re-hash stored original</button>${analyses || "<p class='muted-copy'>No analysis run is recorded for this evidence item yet.</p>"}</article>`;
  }).join("") || "<p class='muted-copy'>No evidence has been added to this case.</p>";
  const reports = (detail.reports || []).map((report) => `<a class="artifact-link" href="${API_BASE}/cases/reports/${encodeURIComponent(report.id)}" target="_blank" rel="noopener">Download ${escapeHtml(report.report_format.toUpperCase())} dossier · ${escapeHtml(report.sha256.slice(0, 12))}…</a>`).join("");
  const audit = detail.audit_events.slice(0, 8).map((event) => `<li><strong>${escapeHtml(event.event_type)}</strong><span>${escapeHtml(displayDate(event.created_at))} · ${escapeHtml(event.actor)}</span></li>`).join("");
  alternatePanel.className = "panel review-panel";
  const assessmentNote = detail.assessment ? `<p class="assessment-reasons">${detail.assessment.reasons.map(escapeHtml).join(" ")}</p>` : "";
  alternatePanel.innerHTML = `<div class="review-panel-header"><div><p class="eyebrow">Case review</p><h2>${escapeHtml(detail.reference)}</h2><p>${escapeHtml(detail.title)}</p></div><div><span class="status-pill ${tone}">${label}</span><button class="assessment-button" type="button" data-verify-audit-case="${escapeHtml(detail.id)}">Verify custody audit</button><button class="assessment-button" type="button" data-assess-case="${escapeHtml(detail.id)}">Update review recommendation</button><button class="new-analysis-button report-button" type="button" data-report-case="${escapeHtml(detail.id)}">Generate dossier</button></div></div>${assessmentNote}<p class="review-notice">Automated findings are leads for an authorised reviewer. They are not a finding that evidence is authentic, manipulated, or legally admissible.</p><div class="review-columns"><section><h3>Evidence and findings</h3>${evidenceMarkup}</section><aside><h3>Generated dossiers</h3><div class="report-links">${reports || "<p class='muted-copy'>No dossier generated yet.</p>"}</div><h3>Recent custody events</h3><ol class="audit-list">${audit || "<li><span>No custody events found.</span></li>"}</ol></aside></div>`;
}

async function openCaseDetail(caseId) {
  dashboardView.classList.add("hidden-view");
  alternateView.classList.remove("hidden-view");
  alternateEyebrow.textContent = "Investigation record";
  alternateTitle.textContent = "Case review";
  alternateSubtitle.textContent = "Evidence, derived forensic signals, custody records, and exportable dossiers.";
  alternatePanel.className = "panel empty-panel";
  alternatePanel.innerHTML = "<p class='muted-copy'>Loading secure case record…</p>";
  try {
    const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}`);
    renderCaseReview(await responseJson(response));
  } catch (error) {
    alternatePanel.innerHTML = `<p class="muted-copy">Unable to load this case: ${escapeHtml(error.message || "Unknown error")}</p>`;
  }
}

async function renderCaseList() {
  alternatePanel.className = "panel review-panel";
  alternatePanel.innerHTML = "<p class='muted-copy'>Loading investigations…</p>";
  try {
    const response = await fetch(`${API_BASE}/cases`);
    const cases = await responseJson(response);
    alternatePanel.innerHTML = cases.length ? `<div class="case-list">${cases.map((item) => `<button type="button" class="case-list-item" data-case="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.reference)}</strong><small>${escapeHtml(item.title)}</small></span><span>${item.evidence_count} evidence · Review →</span></button>`).join("")}</div>` : "<p class='muted-copy'>No cases yet. Create a case to begin secure evidence intake.</p>";
  } catch (error) {
    alternatePanel.innerHTML = "<p class='muted-copy'>Cases are unavailable while the API is offline.</p>";
  }
}

async function responseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "The request could not be completed.");
  return payload;
}

async function loadDashboard() {
  try {
    const response = await fetch(`${API_BASE}/dashboard`);
    const dashboard = await responseJson(response);
    document.getElementById("activeCasesCount").textContent = dashboard.active_cases;
    document.getElementById("evidenceAnalysedCount").textContent = dashboard.evidence_analysed;
    document.getElementById("reviewCount").textContent = String(dashboard.needs_expert_review).padStart(2, "0");
    document.getElementById("custodyIntegrityCount").textContent = `${dashboard.custody_integrity_percent}%`;
    renderCaseQueue(dashboard.recent_cases);
    renderActiveCase(dashboard.recent_cases);
  } catch (error) {
    renderCaseQueue([]);
    showToast("Parallax API is unavailable. Start the FastAPI server, then refresh.", true);
  }
}

function switchView(viewName) {
  const copy = views[viewName] || views.dashboard;
  navButtons.forEach((button) => {
    const selected = button.dataset.view === viewName;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-current", selected ? "page" : "false");
  });

  if (viewName === "dashboard") {
    alternateView.classList.add("hidden-view");
    dashboardView.classList.remove("hidden-view");
    loadDashboard();
    return;
  }

  dashboardView.classList.add("hidden-view");
  alternateView.classList.remove("hidden-view");
  alternateEyebrow.textContent = copy[0];
  alternateTitle.textContent = copy[1];
  alternateSubtitle.textContent = copy[2];
  alternatePanelTitle.textContent = copy[3];
  alternatePanelText.textContent = copy[4];
  alternatePanel.className = "panel empty-panel";
  alternatePanel.innerHTML = `<div class="empty-orbit"><span></span><span></span><span></span></div><h2 id="alternatePanelTitle">${escapeHtml(copy[3])}</h2><p id="alternatePanelText">${escapeHtml(copy[4])}</p><button class="full-review-button" type="button" id="returnDashboard">Return to overview <span>→</span></button>`;
  if (viewName === "cases") renderCaseList();
}

navButtons.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll(".module-link").forEach((button) => {
  button.addEventListener("click", () => showToast(`${button.dataset.module} analysis is scheduled for a later phase.`));
});
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-case]");
  if (target) openCaseDetail(target.dataset.case);
  const reportTarget = event.target.closest("[data-report-case]");
  if (reportTarget) generateReport(reportTarget.dataset.reportCase);
  const assessmentTarget = event.target.closest("[data-assess-case]");
  if (assessmentTarget) runAssessment(assessmentTarget.dataset.assessCase);
  const auditTarget = event.target.closest("[data-verify-audit-case]");
  if (auditTarget) verifyAuditChain(auditTarget.dataset.verifyAuditCase);
  const verifyTarget = event.target.closest("[data-verify-evidence]");
  if (verifyTarget) verifyOriginal(verifyTarget.dataset.verifyEvidence);
  if (event.target.closest("#returnDashboard")) switchView("dashboard");
});

async function generateReport(caseId) {
  try {
    const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/reports`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
    const reports = await responseJson(response);
    showToast(`Integrity dossier generated: ${reports.map((report) => report.report_format.toUpperCase()).join(" + ")}.`);
    openCaseDetail(caseId);
  } catch (error) {
    showToast(error.message || "Dossier generation failed.", true);
  }
}

async function runAssessment(caseId) {
  try {
    const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/assessment`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
    const assessment = await responseJson(response);
    showToast(`Recommendation updated: ${assessment.outcome.replaceAll("_", " ")}.`);
    openCaseDetail(caseId);
  } catch (error) {
    showToast(error.message || "Review recommendation failed.", true);
  }
}

async function verifyAuditChain(caseId) {
  try {
    const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/verify-audit-chain`);
    const result = await responseJson(response);
    let message;
    if (result.chain_intact && result.legacy_unsealed_events === 0) {
      message = `Custody audit verified: ${result.sealed_events} linked event(s) match their stored data.`;
    } else if (result.chain_intact) {
      message = `Sealed custody audit verified. ${result.legacy_unsealed_events} earlier legacy event(s) predate chain sealing.`;
    } else if (result.sealed_events === 0) {
      message = "This case contains only pre-chain legacy events; no custody-chain verification is available for its earlier history.";
    } else {
      message = "Custody-audit mismatch found. Preserve the database and escalate for review.";
    }
    showToast(message, !result.chain_intact);
  } catch (error) {
    showToast(error.message || "Custody audit verification failed.", true);
  }
}

async function verifyOriginal(evidenceId) {
  try {
    const response = await fetch(`${API_BASE}/cases/evidence/${encodeURIComponent(evidenceId)}/verify-integrity`, { method: "POST", headers: { "X-Analyst-ID": "demo-analyst" } });
    const verification = await responseJson(response);
    showToast(verification.matches ? "Stored original re-hashed: SHA-256 matches the intake record." : "Hash mismatch found. Preserve the record and escalate immediately.", !verification.matches);
  } catch (error) {
    showToast(error.message || "Integrity verification failed.", true);
  }
}

function openUpload() { uploadModal.hidden = false; uploadModal.querySelector(".form-input").focus(); }
function closeUpload() { uploadModal.hidden = true; }
document.getElementById("openUpload").addEventListener("click", openUpload);
document.getElementById("alternateAction").addEventListener("click", openUpload);
document.getElementById("closeUpload").addEventListener("click", closeUpload);
async function createCaseAndUploadEvidence() {
  const caseReference = document.getElementById("caseReference").value.trim();
  const caseTitle = document.getElementById("caseTitle").value.trim();
  const file = document.getElementById("evidenceUpload").files[0];
  if (!caseReference || !caseTitle || !file) {
    showToast("Enter a case reference, case title, and an evidence file.", true);
    return;
  }

  uploadButton.disabled = true;
  uploadButton.textContent = "Creating secure record…";
  try {
    const caseResponse = await fetch(`${API_BASE}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Analyst-ID": "demo-analyst" },
      body: JSON.stringify({ reference: caseReference, title: caseTitle })
    });
    const caseRecord = await responseJson(caseResponse);
    const formData = new FormData();
    formData.append("file", file);
    const evidenceResponse = await fetch(`${API_BASE}/cases/${caseRecord.id}/evidence`, {
      method: "POST",
      headers: { "X-Analyst-ID": "demo-analyst" },
      body: formData
    });
    const evidence = await responseJson(evidenceResponse);
    closeUpload();
    const analysisModules = {
      image: { endpoint: "image", label: "Metadata and JPEG ELA" },
      video: { endpoint: "video", label: "CCTV frame-sequence review" },
      audio: { endpoint: "audio", label: "WAV waveform and spectral review" }
    };
    const selectedModule = analysisModules[evidence.media_type];
    if (selectedModule) {
      try {
        const analysisResponse = await fetch(`${API_BASE}/cases/evidence/${evidence.id}/analysis/${selectedModule.endpoint}`, {
          method: "POST",
          headers: { "X-Analyst-ID": "demo-analyst" }
        });
        const analysis = await responseJson(analysisResponse);
        showToast(`Evidence preserved. ${selectedModule.label} completed with ${analysis.findings.length} reviewable findings.`);
      } catch (analysisError) {
        showToast(`Evidence preserved with SHA-256 ${evidence.sha256.slice(0, 12)}… ${selectedModule.label} can be retried safely.`, true);
      }
    } else {
      showToast(`Evidence ${evidence.original_filename} preserved with SHA-256 ${evidence.sha256.slice(0, 12)}…`);
    }
    await loadDashboard();
  } catch (error) {
    showToast(error.message || "Evidence intake failed safely.", true);
  } finally {
    uploadButton.disabled = false;
    uploadButton.textContent = "Create record and analyse";
  }
}
uploadButton.addEventListener("click", createCaseAndUploadEvidence);
document.getElementById("evidenceUpload").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file && !document.getElementById("caseTitle").value.trim()) document.getElementById("caseTitle").value = `Evidence intake — ${file.name}`;
});
uploadModal.addEventListener("click", (event) => { if (event.target === uploadModal) closeUpload(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !uploadModal.hidden) closeUpload(); });
loadDashboard();
