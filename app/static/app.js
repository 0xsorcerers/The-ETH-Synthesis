const form = document.getElementById("report-form");
const statusNode = document.getElementById("status");
const summaryPanel = document.getElementById("summary");
const assumptionsPanel = document.getElementById("assumptions");
const reportPanel = document.getElementById("report");
const reportBody = document.getElementById("report-body");
const assumptionList = document.getElementById("assumption-list");
const exportButton = document.getElementById("export-button");

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
    statusNode.textContent = "Report ready. Review line items and fallback flags below.";
  } catch (error) {
    summaryPanel.classList.add("hidden");
    assumptionsPanel.classList.add("hidden");
    reportPanel.classList.add("hidden");
    exportButton.classList.add("hidden");
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

function renderSummary(summary) {
  document.getElementById("income-total").textContent = money.format(summary.total_taxable_income_usd);
  document.getElementById("gains-total").textContent = money.format(summary.total_capital_gains_usd);
  document.getElementById("losses-total").textContent = money.format(summary.total_capital_losses_usd);
  document.getElementById("fallback-total").textContent = String(summary.fallback_count);
  document.getElementById("summary-badge").textContent = `${summary.jurisdiction} ${summary.tax_year}`;
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
