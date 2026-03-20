const form = document.getElementById("report-form");
const statusNode = document.getElementById("status");
const summaryPanel = document.getElementById("summary");
const assumptionsPanel = document.getElementById("assumptions");
const reportPanel = document.getElementById("report");
const reportBody = document.getElementById("report-body");
const assumptionList = document.getElementById("assumption-list");
const exportButton = document.getElementById("export-button");
const partnerSignals = document.getElementById("partner-signals");
const previewButton = document.getElementById("preview-button");
const previewPanel = document.getElementById("preview");
const previewBody = document.getElementById("preview-body");
const bundleButton = document.getElementById("bundle-button");
const bundlePanel = document.getElementById("bundle");
const bundleDetails = document.getElementById("bundle-details");
const refreshHistoryButton = document.getElementById("refresh-history-button");
const historyList = document.getElementById("history-list");

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
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
    bundleButton.classList.remove("hidden");
    statusNode.textContent = "Report ready. Review line items and fallback flags below.";
  } catch (error) {
    summaryPanel.classList.add("hidden");
    assumptionsPanel.classList.add("hidden");
    reportPanel.classList.add("hidden");
    exportButton.classList.add("hidden");
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

refreshHistoryButton.addEventListener("click", async () => {
  await loadArtifactHistory();
});

function renderSummary(summary) {
  document.getElementById("income-total").textContent = money.format(summary.total_taxable_income_usd);
  document.getElementById("gains-total").textContent = money.format(summary.total_capital_gains_usd);
  document.getElementById("losses-total").textContent = money.format(summary.total_capital_losses_usd);
  document.getElementById("fallback-total").textContent = String(summary.fallback_count);
  document.getElementById("summary-badge").textContent = `${summary.jurisdiction} ${summary.tax_year}`;
  renderPartnerSignals(summary.partner_signals);
  summaryPanel.classList.remove("hidden");
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
          <div>Collaboration Log</div>
          <code>${escapeHtml(item.collaboration_log)}</code>
        `,
      )
      .join("");
  } catch (error) {
    historyList.innerHTML = `<span class="status">${escapeHtml(error.message)}</span>`;
  }
}

loadArtifactHistory();
