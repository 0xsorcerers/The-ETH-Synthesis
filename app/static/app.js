const form = document.getElementById("report-form");
const statusNode = document.getElementById("status");
const summaryPanel = document.getElementById("summary");
const assumptionsPanel = document.getElementById("assumptions");
const reportPanel = document.getElementById("report");
const reportBody = document.getElementById("report-body");
const assumptionList = document.getElementById("assumption-list");
const exportButton = document.getElementById("export-button");
const partnerSignals = document.getElementById("partner-signals");
const agentPlanButton = document.getElementById("agent-plan-button");
const inspectButton = document.getElementById("inspect-button");
const previewButton = document.getElementById("preview-button");
const autonomyPlanPanel = document.getElementById("autonomy-plan");
const autonomyPlanBadge = document.getElementById("autonomy-plan-badge");
const autonomyPlanSummary = document.getElementById("autonomy-plan-summary");
const autonomyRationale = document.getElementById("autonomy-rationale");
const autonomyHandoffNotes = document.getElementById("autonomy-handoff-notes");
const autonomyNextSteps = document.getElementById("autonomy-next-steps");
const autonomyRecommendedAction = document.getElementById("autonomy-recommended-action");
const readinessPanel = document.getElementById("readiness");
const readinessBody = document.getElementById("readiness-body");
const readinessBadge = document.getElementById("readiness-badge");
const readinessColumns = document.getElementById("readiness-columns");
const readinessAgentNotes = document.getElementById("readiness-agent-notes");
const previewPanel = document.getElementById("preview");
const previewBody = document.getElementById("preview-body");
const bundleButton = document.getElementById("bundle-button");
const htmlButton = document.getElementById("html-button");
const bundlePanel = document.getElementById("bundle");
const bundleDetails = document.getElementById("bundle-details");
const publishButton = document.getElementById("publish-button");
const refreshHistoryButton = document.getElementById("refresh-history-button");
const historyList = document.getElementById("history-list");
const guideGrid = document.getElementById("guide-grid");
const manifestButton = document.getElementById("manifest-button");
const jurisdictionSelect = document.getElementById("jurisdiction-select");
const jurisdictionMultiSelect = document.getElementById("jurisdiction-multi-select");
const multiReportButton = document.getElementById("multi-report-button");
const multiSummaryPanel = document.getElementById("multi-summary");
const multiSummaryBody = document.getElementById("multi-summary-body");
const ruleTemplatesBody = document.getElementById("rule-templates-body");
const taxYearInput = document.querySelector('input[name="tax_year"]');
const heroGuide = document.getElementById("hero-guide");
const workflowList = document.getElementById("workflow-list");
const uiGuideList = document.getElementById("ui-guide-list");
const reportGuideList = document.getElementById("report-guide-list");
const autonomyNotes = document.getElementById("autonomy-notes");
const scalabilityNotes = document.getElementById("scalability-notes");

let agentManifestCache = null;

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

agentPlanButton.addEventListener("click", async () => {
  statusNode.textContent = "Building autonomy run plan...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/autonomy/plan-from-csv", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Autonomy plan failed.");
    }

    renderAutonomyPlan(payload);
    statusNode.textContent =
      payload.autonomy_status === "blocked"
        ? "Autonomy plan found blockers that must be repaired first."
        : payload.autonomy_status === "review"
          ? "Autonomy plan recommends a quick review before full analysis."
          : "Autonomy plan is clear to proceed.";
  } catch (error) {
    autonomyPlanPanel.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

inspectButton.addEventListener("click", async () => {
  statusNode.textContent = "Inspecting CSV readiness...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/ingestion/readiness-from-csv", {
      method: "POST",
      body: buildCsvOnlyPayload(formData),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "CSV readiness inspection failed.");
    }

    renderReadiness(payload);
    statusNode.textContent =
      payload.summary.readiness === "blocked"
        ? "CSV has blocking issues. Fix them before preview or report generation."
        : payload.summary.readiness === "needs_review"
          ? "CSV is usable but should be reviewed before report generation."
          : "CSV readiness passed.";
  } catch (error) {
    readinessPanel.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusNode.textContent = "Running jurisdiction-aware analysis...";

  const formData = new FormData(form);

  try {
    const response = await fetch("/reports/generate-from-csv", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Report generation failed.");
    }

    renderSummary(payload.summary);
    renderAssumptions(payload.assumptions);
    renderLineItems(payload.line_items);
    exportButton.classList.remove("hidden");
    htmlButton.classList.remove("hidden");
    bundleButton.classList.remove("hidden");
    statusNode.textContent = "Report ready. Review line items and fallback flags below.";
  } catch (error) {
    summaryPanel.classList.add("hidden");
    assumptionsPanel.classList.add("hidden");
    reportPanel.classList.add("hidden");
    exportButton.classList.add("hidden");
    htmlButton.classList.add("hidden");
    bundleButton.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

previewButton.addEventListener("click", async () => {
  statusNode.textContent = "Previewing normalization...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/normalize/preview-from-csv", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Normalization preview failed.");
    }

    previewBody.innerHTML = payload
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.tx_id)}</td>
            <td>${escapeHtml(item.event_type)}</td>
            <td>${Math.round(item.confidence * 100)}%</td>
            <td>${renderNormalizedFlow(item.normalized)}</td>
            <td>${escapeHtml(item.rationale)}</td>
          </tr>
        `,
      )
      .join("");
    previewPanel.classList.remove("hidden");
    statusNode.textContent = "Normalization preview ready.";
  } catch (error) {
    previewPanel.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

multiReportButton.addEventListener("click", async () => {
  statusNode.textContent = "Running multi-jurisdiction analysis...";
  const formData = new FormData(form);
  const jurisdictions = selectedJurisdictions();
  formData.set("jurisdictions", jurisdictions.join(","));

  try {
    const response = await fetch("/reports/generate-multi-from-csv", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Multi-jurisdiction analysis failed.");
    }
    renderMultiJurisdictionSummary(payload.comparison || []);
    statusNode.textContent = "Multi-jurisdiction analysis is ready.";
  } catch (error) {
    multiSummaryPanel.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

exportButton.addEventListener("click", async () => {
  statusNode.textContent = "Preparing Markdown export...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/reports/export-markdown-from-csv", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || "Markdown export failed.");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="(.+)"/)?.[1] || "skynet-report.md";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    statusNode.textContent = "Markdown report exported.";
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

htmlButton.addEventListener("click", async () => {
  statusNode.textContent = "Preparing HTML export...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/reports/export-html-from-csv", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || "HTML export failed.");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="(.+)"/)?.[1] || "skynet-report.html";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    statusNode.textContent = "HTML report exported.";
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

bundleButton.addEventListener("click", async () => {
  statusNode.textContent = "Saving artifact bundle...";
  const formData = new FormData(form);

  try {
    const response = await fetch("/artifacts/save-from-csv", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Artifact bundle save failed.");
    }

    bundleDetails.innerHTML = `
      <div>Bundle ID</div>
      <code>${escapeHtml(payload.bundle_id)}</code>
      <div>Directory</div>
      <code>${escapeHtml(payload.directory)}</code>
      <div>Report JSON</div>
      <code>${escapeHtml(payload.report_json)}</code>
      <div>Report Markdown</div>
      <code>${escapeHtml(payload.report_markdown)}</code>
      <div>Report HTML</div>
      <code>${escapeHtml(payload.report_html)}</code>
      <div>Normalization Preview</div>
      <code>${escapeHtml(payload.normalization_preview)}</code>
      <div>Collaboration Log Snapshot</div>
      <code>${escapeHtml(payload.collaboration_log)}</code>
    `;
    bundlePanel.classList.remove("hidden");
    await loadArtifactHistory();
    statusNode.textContent = "Artifact bundle saved.";
  } catch (error) {
    bundlePanel.classList.add("hidden");
    statusNode.textContent = error.message;
  }
});

publishButton.addEventListener("click", async () => {
  statusNode.textContent = "Publishing current work snapshot...";
  try {
    const response = await fetch("/publish", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Publish failed.");
    }

    bundleDetails.innerHTML = `
      <div>Publish ID</div>
      <code>${escapeHtml(payload.publish_id)}</code>
      <div>Publish Directory</div>
      <code>${escapeHtml(payload.directory)}</code>
      <div>Summary Markdown</div>
      <code>${escapeHtml(payload.summary_markdown)}</code>
      <div>Included Docs</div>
      <code>${escapeHtml((payload.included_docs || []).join("\n") || "none")}</code>
      <div>Included Artifacts</div>
      <code>${escapeHtml((payload.included_artifacts || []).join("\n") || "none")}</code>
    `;
    bundlePanel.classList.remove("hidden");
    statusNode.textContent = "Build snapshot published locally.";
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

refreshHistoryButton.addEventListener("click", async () => {
  await loadArtifactHistory();
});

manifestButton.addEventListener("click", async () => {
  statusNode.textContent = "Preparing agent manifest...";
  try {
    const manifest = await loadAgentManifest();
    await navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
    statusNode.textContent = "Agent manifest copied to clipboard.";
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

function renderSummary(summary) {
  document.getElementById("income-total").textContent = money.format(summary.total_taxable_income_usd);
  document.getElementById("gains-total").textContent = money.format(summary.total_capital_gains_usd);
  document.getElementById("losses-total").textContent = money.format(summary.total_capital_losses_usd);
  document.getElementById("fallback-total").textContent = String(summary.fallback_count);
  document.getElementById("summary-badge").textContent = `${summary.jurisdiction} ${summary.tax_year} · ${summary.period_label || "CSV date range"}`;
  statusNode.textContent = summary.tax_year_selection_note || statusNode.textContent;
  renderPartnerSignals(summary.partner_signals);
  summaryPanel.classList.remove("hidden");
}

function renderAutonomyPlan(plan) {
  autonomyPlanBadge.textContent = plan.autonomy_status.replaceAll("_", " ");
  autonomyPlanBadge.className = `badge readiness-${plan.autonomy_status === "review" ? "needs_review" : plan.autonomy_status}`;
  autonomyPlanSummary.textContent = plan.summary;
  document.getElementById("autonomy-total-transactions").textContent = String(plan.stats.total_transactions);
  document.getElementById("autonomy-warning-rows").textContent = String(plan.stats.warning_rows);
  document.getElementById("autonomy-low-confidence").textContent = String(plan.stats.low_confidence_count);
  document.getElementById("autonomy-fallback-risk").textContent = String(plan.stats.predicted_fallback_count);
  autonomyRationale.innerHTML = (plan.rationale || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  autonomyHandoffNotes.innerHTML = (plan.handoff_notes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  autonomyRecommendedAction.innerHTML = `
    <article class="guide-item">
      <div class="guide-item-top">
        <strong>${escapeHtml(plan.recommended_action)}</strong>
        <span class="signal-chip">${escapeHtml(plan.jurisdiction)} ${escapeHtml(plan.tax_year)}</span>
      </div>
      <p>${escapeHtml(plan.summary)}</p>
      <small>Use this action as the default branch for agent handoff.</small>
    </article>
  `;
  autonomyNextSteps.innerHTML = (plan.next_steps || [])
    .map(
      (step) => `
        <article class="guide-item">
          <div class="guide-item-top">
            <strong>${escapeHtml(step.label)}</strong>
            <span class="signal-chip ${step.status === "blocked" ? "is-missing" : ""}">${escapeHtml(step.status)}</span>
          </div>
          <p>${escapeHtml(step.detail)}</p>
          ${step.endpoint ? `<small>Endpoint: ${escapeHtml(step.endpoint)}</small>` : ""}
        </article>
      `,
    )
    .join("");
  autonomyPlanPanel.classList.remove("hidden");
}

function renderReadiness(report) {
  document.getElementById("readiness-total-rows").textContent = String(report.summary.total_rows);
  document.getElementById("readiness-valid-rows").textContent = String(report.summary.valid_rows);
  document.getElementById("readiness-warning-count").textContent = String(report.summary.warning_count);
  document.getElementById("readiness-error-count").textContent = String(report.summary.error_count);
  readinessBadge.textContent = report.summary.readiness.replaceAll("_", " ");
  readinessBadge.className = `badge readiness-${report.summary.readiness}`;

  readinessColumns.innerHTML = report.required_columns
    .map((column) => {
      const present = (report.present_columns || []).includes(column);
      return `<span class="signal-chip ${present ? "is-present" : "is-missing"}">${escapeHtml(column)}</span>`;
    })
    .join("");

  readinessAgentNotes.innerHTML = report.agent_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");

  if (!report.issues || report.issues.length === 0) {
    readinessBody.innerHTML = `
      <tr>
        <td><span class="flag success">ready</span></td>
        <td>-</td>
        <td>-</td>
        <td>No CSV issues detected.</td>
        <td>Proceed to normalization preview or full analysis.</td>
      </tr>
    `;
  } else {
    readinessBody.innerHTML = report.issues
      .map(
        (issue) => `
          <tr>
            <td><span class="flag ${issue.severity === "error" ? "danger" : issue.severity === "warning" ? "" : "success"}">${escapeHtml(issue.severity)}</span></td>
            <td>${issue.row_number ? escapeHtml(issue.row_number) : "-"}</td>
            <td>${issue.tx_id ? escapeHtml(issue.tx_id) : "-"}</td>
            <td>${escapeHtml(issue.message)}</td>
            <td>${escapeHtml(issue.recommendation)}</td>
          </tr>
        `,
      )
      .join("");
  }

  readinessPanel.classList.remove("hidden");
}

function renderAssumptions(assumptions) {
  assumptionList.innerHTML = assumptions.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  assumptionsPanel.classList.remove("hidden");
}

function renderLineItems(items) {
  reportBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.tx_id)}</td>
          <td>${renderFlow(item)}</td>
          <td>${escapeHtml(item.event_type)}</td>
          <td>${escapeHtml(item.tax_treatment)}</td>
          <td>${money.format(item.taxable_amount_usd)}</td>
          <td>${money.format(item.gain_or_loss_usd)}</td>
          <td>${Math.round(item.confidence * 100)}%</td>
          <td>
            ${item.fallback_applied ? '<span class="flag">fallback</span>' : '<span class="flag danger">rule matched</span>'}
            <small>${escapeHtml(item.explanation)}</small>
            ${renderCitations(item.citations)}
          </td>
        </tr>
      `,
    )
    .join("");
  reportPanel.classList.remove("hidden");
}

function renderFlow(item) {
  const parts = [];
  if (item.disposed_asset && item.disposed_quantity) {
    parts.push(`Out: ${escapeHtml(item.disposed_quantity)} ${escapeHtml(item.disposed_asset)}`);
  }
  if (item.acquired_asset && item.acquired_quantity) {
    parts.push(`In: ${escapeHtml(item.acquired_quantity)} ${escapeHtml(item.acquired_asset)}`);
  }
  if (parts.length === 0) {
    return escapeHtml(item.asset);
  }
  return parts.join("<br />");
}

function renderNormalizedFlow(normalized) {
  const parts = [];
  if (normalized.disposed_asset && normalized.disposed_quantity) {
    parts.push(`Out: ${escapeHtml(normalized.disposed_quantity)} ${escapeHtml(normalized.disposed_asset)}`);
  }
  if (normalized.acquired_asset && normalized.acquired_quantity) {
    parts.push(`In: ${escapeHtml(normalized.acquired_quantity)} ${escapeHtml(normalized.acquired_asset)}`);
  }
  if (parts.length === 0) {
    return "No material asset movement";
  }
  return parts.join("<br />");
}

function renderPartnerSignals(signals) {
  const entries = Object.entries(signals || {});
  if (entries.length === 0) {
    partnerSignals.innerHTML = '<span class="signal-chip">No partner metadata detected</span>';
    return;
  }
  partnerSignals.innerHTML = entries
    .map(([name, count]) => `<span class="signal-chip">${escapeHtml(name)}: ${escapeHtml(count)}</span>`)
    .join("");
}

function renderCitations(citations) {
  if (!citations || citations.length === 0) {
    return "";
  }
  return citations
    .map(
      (citation) =>
        `<small><a href="${escapeHtml(citation.url)}" target="_blank" rel="noreferrer">${escapeHtml(citation.authority)}: ${escapeHtml(citation.title)}</a></small>`,
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildCsvOnlyPayload(formData) {
  const payload = new FormData();
  const file = formData.get("file");
  if (file) {
    payload.append("file", file);
  }
  return payload;
}

async function loadArtifactHistory() {
  try {
    const response = await fetch("/artifacts");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to load artifact history.");
    }

    if (payload.length === 0) {
      historyList.innerHTML = '<span class="status">No saved bundles yet.</span>';
      return;
    }

    historyList.innerHTML = payload
      .map(
        (item) => `
          <div>Bundle ID</div>
          <code>${escapeHtml(item.bundle_id)}</code>
          <div>Directory</div>
          <code>${escapeHtml(item.directory)}</code>
          <div>Report HTML</div>
          <code>${escapeHtml(item.report_html)}</code>
          <div>Collaboration Log</div>
          <code>${escapeHtml(item.collaboration_log)}</code>
        `,
      )
      .join("");
  } catch (error) {
    historyList.innerHTML = `<span class="status">${escapeHtml(error.message)}</span>`;
  }
}

async function loadJurisdictions() {
  try {
    const response = await fetch("/jurisdictions");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to load jurisdictions.");
    }

    if (!Array.isArray(payload) || payload.length === 0) {
      jurisdictionSelect.innerHTML = '<option value="US">United States</option>';
      jurisdictionMultiSelect.innerHTML = '<option value="US">United States</option>';
      return;
    }

    jurisdictionSelect.innerHTML = payload
      .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.label)}</option>`)
      .join("");
    jurisdictionMultiSelect.innerHTML = payload
      .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.label)}</option>`)
      .join("");
    if (jurisdictionMultiSelect.options.length > 0) {
      jurisdictionMultiSelect.options[0].selected = true;
    }
  } catch (error) {
    jurisdictionSelect.innerHTML = '<option value="US">United States</option>';
    jurisdictionMultiSelect.innerHTML = '<option value="US">United States</option>';
    statusNode.textContent = error.message;
  }
}

function selectedJurisdictions() {
  const values = Array.from(jurisdictionMultiSelect.selectedOptions).map((option) => option.value);
  if (values.length > 0) {
    return values;
  }
  return [jurisdictionSelect.value];
}

function renderMultiJurisdictionSummary(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    multiSummaryPanel.classList.add("hidden");
    return;
  }
  multiSummaryBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.label)} (${escapeHtml(row.jurisdiction)})</td>
          <td>${money.format(row.taxable_income_usd || 0)}</td>
          <td>${money.format(row.capital_gains_usd || 0)}</td>
          <td>${money.format(row.capital_losses_usd || 0)}</td>
          <td>${escapeHtml(String(row.fallback_count ?? 0))}</td>
        </tr>
      `,
    )
    .join("");
  multiSummaryPanel.classList.remove("hidden");
}

async function loadRuleTemplates() {
  const jurisdictions = selectedJurisdictions();
  const taxYear = (taxYearInput?.value || "").trim();
  const yearParam = taxYear ? `&tax_year=${encodeURIComponent(taxYear)}` : "";
  try {
    const response = await fetch(
      `/rules/templates?jurisdictions=${encodeURIComponent(jurisdictions.join(","))}${yearParam}`,
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to load jurisdiction templates.");
    }

    ruleTemplatesBody.innerHTML = payload
      .map(
        (template) => `
          <article class="guide-item">
            <div class="guide-item-top">
              <strong>${escapeHtml(template.label)} (${escapeHtml(template.jurisdiction)})</strong>
              <span class="signal-chip">v${escapeHtml(template.version)}</span>
            </div>
            <p>Fallback: ${escapeHtml(template.fallback_mode)} — ${escapeHtml(template.fallback_description)}</p>
            <small>Events: ${escapeHtml(template.event_templates.map((item) => `${item.event_type}:${item.tax_treatment}`).join(", "))}</small>
          </article>
        `,
      )
      .join("");
  } catch (error) {
    ruleTemplatesBody.innerHTML = `<span class="status">${escapeHtml(error.message)}</span>`;
  }
}

async function loadAgentManifest() {
  if (agentManifestCache) {
    return agentManifestCache;
  }
  const response = await fetch("/agent/manifest");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to load agent manifest.");
  }
  agentManifestCache = payload;
  return payload;
}

async function loadGuideCards() {
  try {
    const manifest = await loadAgentManifest();
    guideGrid.innerHTML = manifest.workflow
      .map(
        (step, index) => `
          <article>
            <span>Step ${index + 1}</span>
            <p>${escapeHtml(step)}</p>
          </article>
        `,
      )
      .join("");
  } catch (error) {
    guideGrid.innerHTML = `<article><span>Unavailable</span><p>${escapeHtml(error.message)}</p></article>`;
  }
}

async function loadGuide() {
  try {
    const response = await fetch("/guide");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to load operator guide.");
    }

    heroGuide.innerHTML = `
      <div class="hero-guide-card">
        <span>Purpose</span>
        <strong>${escapeHtml(payload.purpose)}</strong>
      </div>
      <div class="hero-guide-card">
        <span>Workflow</span>
        <strong>${escapeHtml(payload.workflows.length)} guided steps</strong>
      </div>
      <div class="hero-guide-card">
        <span>Version</span>
        <strong>${escapeHtml(payload.version)}</strong>
      </div>
    `;

    workflowList.innerHTML = payload.workflows
      .map(
        (step) => `
          <article class="guide-card">
            <span>${escapeHtml(step.id)}</span>
            <h3>${escapeHtml(step.label)}</h3>
            <p>${escapeHtml(step.description)}</p>
            <small>Agent hint: ${escapeHtml(step.agent_hint)}</small>
          </article>
        `,
      )
      .join("");

    uiGuideList.innerHTML = payload.ui_elements.map(renderGuideItem).join("");
    reportGuideList.innerHTML = payload.report_elements.map(renderGuideItem).join("");
    autonomyNotes.innerHTML = payload.autonomous_usage_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
    scalabilityNotes.innerHTML = payload.scalability_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  } catch (error) {
    heroGuide.innerHTML = `<p class="status">${escapeHtml(error.message)}</p>`;
    workflowList.innerHTML = "";
    uiGuideList.innerHTML = "";
    reportGuideList.innerHTML = "";
    autonomyNotes.innerHTML = "";
    scalabilityNotes.innerHTML = "";
  }
}

function renderGuideItem(item) {
  const audience = (item.audience || []).join(" + ");
  return `
    <article class="guide-item">
      <div class="guide-item-top">
        <strong>${escapeHtml(item.label)}</strong>
        <span class="signal-chip">${escapeHtml(audience)}</span>
      </div>
      <p>${escapeHtml(item.summary)}</p>
      <small>${escapeHtml(item.operational_note)}</small>
    </article>
  `;
}

loadArtifactHistory();
loadJurisdictions();
loadGuideCards();
loadGuide();
loadRuleTemplates();
jurisdictionSelect.addEventListener("change", loadRuleTemplates);
jurisdictionMultiSelect.addEventListener("change", loadRuleTemplates);
taxYearInput?.addEventListener("change", loadRuleTemplates);
