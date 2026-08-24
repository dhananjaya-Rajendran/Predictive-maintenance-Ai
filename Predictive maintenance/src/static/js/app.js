/**
 * AutoPredict AI - Main Web Application State & Dashboard Logic
 */

let currentShopFilter = "ALL";
let currentMachineDetailId = null;
let telemetryChartInstance = null;
let fftChartInstance = null;
let pollingInterval = null;

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  telemetryChartInstance = new TelemetryChart("telemetryChartCanvas");
  fftChartInstance = new FFTChart("fftChartCanvas");

  fetchDashboardSummary();
  fetchMachineList();

  // Setup tab filter listeners
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      e.target.classList.add("active");
      currentShopFilter = e.target.getAttribute("data-shop");
      fetchMachineList();
    });
  });

  // Setup Live Telemetry Polling (every 4 seconds)
  pollingInterval = setInterval(() => {
    fetchDashboardSummary();
    fetchMachineList();
    if (currentMachineDetailId) {
      fetchMachineHealth(currentMachineDetailId);
    }
  }, 4000);
});

async function fetchDashboardSummary() {
  try {
    const res = await fetch("/api/v1/dashboard/summary");
    const data = await res.json();

    document.getElementById("plantHealthVal").innerText = data.overall_plant_health_index.toFixed(1);
    document.getElementById("activeCriticalVal").innerText = `${data.risk_breakdown.CRITICAL} Assets`;
    document.getElementById("downtimeAvoidedVal").innerText = `${data.downtime_avoided_hours_mtd}h`;
    document.getElementById("costSavedVal").innerText = `$${(data.estimated_cost_saved_usd / 1000000).toFixed(2)}M`;
    document.getElementById("accuracyVal").innerText = `${data.prediction_accuracy_percentage}%`;

    document.getElementById("pillCritCount").innerText = data.risk_breakdown.CRITICAL;
    document.getElementById("pillWarnCount").innerText = data.risk_breakdown.WARNING;
    document.getElementById("pillWatchCount").innerText = data.risk_breakdown.WATCH;
    document.getElementById("pillHealthyCount").innerText = data.risk_breakdown.HEALTHY;
  } catch (err) {
    console.error("Error fetching summary:", err);
  }
}

async function fetchMachineList() {
  try {
    const url = currentShopFilter === "ALL" ? "/api/v1/machines" : `/api/v1/machines?shop=${currentShopFilter}`;
    const res = await fetch(url);
    const machines = await res.json();

    const tbody = document.getElementById("riskTableBody");
    tbody.innerHTML = "";

    machines.forEach((m) => {
      const tr = document.createElement("tr");
      tr.onclick = () => openMachineDetail(m.machine_id);

      const riskPillClass = `pill-${m.risk_tier.toLowerCase()}`;
      const probPercent = (m.failure_probability * 100).toFixed(1);

      tr.innerHTML = `
        <td>
          <div class="asset-cell">
            <span class="asset-tag">${m.asset_tag}</span>
            <span class="asset-name">${m.name}</span>
          </div>
        </td>
        <td><strong>${m.shop}</strong></td>
        <td><span class="horizon-badge">${m.criticality.replace("TIER_", "T")}</span></td>
        <td><span class="pill ${riskPillClass}">${m.risk_tier}</span></td>
        <td class="prob-cell">${probPercent}%</td>
        <td><span class="horizon-badge">${m.predicted_horizon_hours} Hours</span></td>
        <td>
          <button class="btn btn-primary" style="padding:4px 8px; font-size:11px;" onclick="event.stopPropagation(); openCopilotForAsset('${m.machine_id}')">
            AI Diagnosis
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error fetching machines:", err);
  }
}

async function openMachineDetail(machineId) {
  currentMachineDetailId = machineId;
  const modal = document.getElementById("machineModal");
  modal.classList.add("active");

  await fetchMachineHealth(machineId);
}

function closeMachineDetail() {
  currentMachineDetailId = null;
  document.getElementById("machineModal").classList.remove("active");
}

async function fetchMachineHealth(machineId) {
  try {
    const [healthRes, teleRes, fftRes] = await Promise.all([
      fetch(`/api/v1/machines/${machineId}/health`),
      fetch(`/api/v1/machines/${machineId}/telemetry`),
      fetch(`/api/v1/machines/${machineId}/fft`)
    ]);

    const health = await healthRes.json();
    const tele = await teleRes.json();
    const fft = await fftRes.json();

    document.getElementById("modalAssetTag").innerText = health.asset_tag;
    document.getElementById("modalMachineName").innerText = health.name;
    document.getElementById("modalShop").innerText = `${health.shop} • ${health.criticality}`;
    document.getElementById("modalRiskTier").innerText = health.risk_tier;
    document.getElementById("modalRiskTier").className = `pill pill-${health.risk_tier.toLowerCase()}`;

    document.getElementById("detailFailProb").innerText = `${(health.prediction.failure_probability * 100).toFixed(1)}%`;
    document.getElementById("detailHorizon").innerText = `${health.prediction.predicted_horizon_hours} Hours`;
    document.getElementById("detailConfidence").innerText = `${(health.prediction.confidence_score * 100).toFixed(0)}%`;

    // Render SHAP attribution list
    const shapContainer = document.getElementById("shapList");
    shapContainer.innerHTML = "";

    health.prediction.top_contributing_features.forEach((feat) => {
      const item = document.createElement("div");
      item.className = "shap-item";
      item.innerHTML = `
        <div class="shap-meta">
          <span><strong>${feat.feature_name}</strong> (${feat.current_value} ${feat.unit})</span>
          <span style="color:#38bdf8; font-weight:700;">+${feat.shap_importance_percent}%</span>
        </div>
        <div class="shap-bar-bg">
          <div class="shap-bar-fill" style="width: ${feat.shap_importance_percent}%;"></div>
        </div>
        <div style="font-size:11px; color:#94a3b8;">${feat.diagnostic_note}</div>
      `;
      shapContainer.appendChild(item);
    });

    // Render Telemetry & FFT charts
    if (tele.vibration_rms && tele.vibration_rms.length > 0) {
      telemetryChartInstance.setData(
        tele.timestamps,
        tele.vibration_rms,
        "mm/s RMS",
        4.5,
        7.1
      );
    }

    if (fft.frequencies_hz && fft.frequencies_hz.length > 0) {
      const bpfiMarker = fft.bearing_kinematic_markers ? fft.bearing_kinematic_markers.bpfi_inner_race_hz : 248.5;
      fftChartInstance.setSpectrum(fft.frequencies_hz, fft.amplitudes, bpfiMarker);
    }
  } catch (err) {
    console.error("Error fetching machine detail:", err);
  }
}

function openCopilotForAsset(machineId) {
  AGENT_CHAT.setContext(machineId);
}

async function injectFaultFromModal(failureMode) {
  if (!currentMachineDetailId) return;
  try {
    await fetch("/api/v1/simulator/inject_anomaly", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        machine_id: currentMachineDetailId,
        failure_mode: failureMode,
        severity: 0.85,
        rate_per_hour: 0.015
      })
    });
    alert(`Fault '${failureMode}' injected into ${currentMachineDetailId}. Watch the 24-72h failure horizon compute in real time.`);
    fetchMachineHealth(currentMachineDetailId);
    fetchMachineList();
  } catch (err) {
    alert("Error injecting fault.");
  }
}

async function clearFaultFromModal() {
  if (!currentMachineDetailId) return;
  try {
    await fetch(`/api/v1/simulator/clear_fault/${currentMachineDetailId}`, { method: "POST" });
    alert(`Machine ${currentMachineDetailId} reset to nominal healthy baseline.`);
    fetchMachineHealth(currentMachineDetailId);
    fetchMachineList();
  } catch (err) {
    alert("Error clearing fault.");
  }
}
