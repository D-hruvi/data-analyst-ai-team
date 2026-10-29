/**
 * Data Analyst AI Team - Enterprise Engineering Workbench
 * Senior software developer design: Split-pane workbench, dense telemetry, zero fluff.
 */

(function () {
  "use strict";

  const state = {
    theme: localStorage.getItem("da_theme") || "dark",
    activeView: "workbench", // workbench | benchmark | rfc
    selectedMode: "team", // baseline1 | baseline2 | team
    isCompareMode: false,
    activeDataset: null,
    datasetPreview: null,
    isRunning: false,
    currentResult: null,
    benchmarkData: null,
    benchmarkFilter: {
      dataset: "all",
      kind: "all",
      outcome: "all",
      search: "",
    },
  };

  const $ = (id) => document.getElementById(id);
  const $$ = (sel) => document.querySelectorAll(sel);

  // Status mapping
  const STATUS_MAP = {
    ok: { label: "PASS: Answered", cls: "pass" },
    answered: { label: "PASS: Answered", cls: "pass" },
    cannot_answer: { label: "GUARDRAIL: Cannot Answer", cls: "warn" },
    not_sure: { label: "NOT SURE (Timeout/Limit)", cls: "warn" },
    error: { label: "FAIL: Execution Error", cls: "fail" },
    pass: { label: "PASS", cls: "pass" },
    fail: { label: "FAIL", cls: "fail" },
  };

  // =========================================================================
  // Theme Management
  // =========================================================================
  function initTheme() {
    if (state.theme !== "light") {
      state.theme = "dark";
    }
    applyTheme();

    $("themeToggleBtn").addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      localStorage.setItem("da_theme", state.theme);
      applyTheme();
    });
  }

  function applyTheme() {
    document.documentElement.setAttribute("data-theme", state.theme);
    $("themeToggleBtn").innerHTML = state.theme === "dark"
      ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`
      : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
  }

  // =========================================================================
  // View Navigation
  // =========================================================================
  function initNav() {
    $$(".nav-tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const view = btn.getAttribute("data-view");
        switchView(view);
      });
    });
  }

  function switchView(viewName) {
    state.activeView = viewName;
    $$(".nav-tab-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-view") === viewName);
    });
    $$(".view-section").forEach((s) => {
      s.classList.toggle("active", s.id === `view-${viewName}`);
    });

    if (viewName === "benchmark" && !state.benchmarkData) {
      loadBenchmarkSuite();
    }
  }

  // =========================================================================
  // Dataset Management & Schema Tree
  // =========================================================================
  async function initDatasets() {
    const select = $("datasetSelect");

    try {
      const res = await fetch("/api/sample-datasets");
      if (!res.ok) throw new Error("Could not fetch datasets");
      const data = await res.json();
      const datasets = data.datasets || [];

      select.innerHTML = "";
      datasets.forEach((ds) => {
        const opt = document.createElement("option");
        opt.value = ds.id;
        opt.textContent = `${ds.filename} (${ds.rows.toLocaleString()} rows)`;
        select.appendChild(opt);
      });

      const uploadOpt = document.createElement("option");
      uploadOpt.value = "__upload__";
      uploadOpt.textContent = "+ Upload custom CSV...";
      select.appendChild(uploadOpt);

      window._availableDatasets = datasets;

      if (datasets.length > 0) {
        loadDataset(datasets[0].id);
      }
    } catch (err) {
      console.error("Dataset init error:", err);
    }

    select.addEventListener("change", (e) => {
      if (e.target.value === "__upload__") {
        $("fileUploadInput").click();
      } else {
        loadDataset(e.target.value);
      }
    });

    $("fileUploadInput").addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        loadCustomCsv(e.target.files[0]);
      }
    });

    $("previewTableBtn").addEventListener("click", openDataPreviewModal);
  }

  async function loadDataset(datasetId) {
    const dsMeta = (window._availableDatasets || []).find((d) => d.id === datasetId);
    if (!dsMeta) return;

    try {
      const res = await fetch(`/api/sample-datasets/${datasetId}`);
      if (!res.ok) throw new Error("Failed to load CSV file");
      const csvText = await res.text();
      const file = new File([csvText], dsMeta.filename, { type: "text/csv" });

      state.activeDataset = {
        id: dsMeta.id,
        filename: dsMeta.filename,
        rows: dsMeta.rows,
        columns: dsMeta.columns,
        sample_questions: dsMeta.sample_questions || [],
        file: file,
      };

      parseAndRenderSchema(csvText);
      updatePresetDropdown(state.activeDataset.sample_questions);
    } catch (err) {
      showError("Dataset load failed: " + err.message);
    }
  }

  function loadCustomCsv(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      showError("Please select a .csv file");
      return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
      const csvText = e.target.result;
      const lines = csvText.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
      const rows = Math.max(0, lines.length - 1);

      state.activeDataset = {
        id: "custom",
        filename: file.name,
        rows: rows,
        columns: [],
        sample_questions: [
          "How many rows are in the dataset?",
          "Summarize the numerical columns.",
        ],
        file: file,
      };

      // Add option to select
      const select = $("datasetSelect");
      const opt = document.createElement("option");
      opt.value = "custom";
      opt.textContent = `${file.name} (${rows.toLocaleString()} rows)`;
      select.insertBefore(opt, select.firstChild);
      select.value = "custom";

      parseAndRenderSchema(csvText);
      updatePresetDropdown(state.activeDataset.sample_questions);
    };
    reader.readAsText(file);
  }

  function parseAndRenderSchema(csvText) {
    const lines = csvText.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) return;

    const splitLine = (l) => {
      const parts = [];
      let cur = "";
      let inQuotes = false;
      for (let i = 0; i < l.length; i++) {
        const c = l[i];
        if (c === '"') inQuotes = !inQuotes;
        else if (c === "," && !inQuotes) {
          parts.push(cur.trim().replace(/^"|"$/g, ""));
          cur = "";
        } else cur += c;
      }
      parts.push(cur.trim().replace(/^"|"$/g, ""));
      return parts;
    };

    const headers = splitLine(lines[0]);
    const sampleRows = lines.slice(1, 6).map(splitLine);

    // Infer basic types from sample rows
    const inferredTypes = headers.map((col, idx) => {
      const sampleVals = sampleRows.map((r) => r[idx]).filter((v) => v !== undefined && v !== "");
      if (sampleVals.length === 0) return "object";
      const isNum = sampleVals.every((v) => !isNaN(Number(v)));
      if (isNum) {
        const hasDot = sampleVals.some((v) => v.includes("."));
        return hasDot ? "float64" : "int64";
      }
      return "object";
    });

    state.datasetPreview = {
      headers: headers,
      types: inferredTypes,
      sampleRows: sampleRows,
    };

    const schemaBox = $("schemaTreeBox");
    schemaBox.innerHTML = "";

    headers.forEach((h, idx) => {
      const item = document.createElement("div");
      item.className = "schema-item";
      item.innerHTML = `
        <span class="col-name">${escapeHtml(h)}</span>
        <span class="col-type">${inferredTypes[idx]}</span>
      `;
      schemaBox.appendChild(item);
    });

    $("datasetMetaLabel").textContent = `${headers.length} columns · ${state.activeDataset.rows.toLocaleString()} rows`;
  }

  function updatePresetDropdown(questions) {
    const preset = $("queryPresetSelect");
    preset.innerHTML = '<option value="">Load query preset...</option>';

    if (!questions || questions.length === 0) return;

    questions.forEach((q) => {
      const opt = document.createElement("option");
      opt.value = q;
      opt.textContent = q;
      preset.appendChild(opt);
    });

    preset.onchange = (e) => {
      if (e.target.value) {
        $("queryInput").value = e.target.value;
      }
    };
  }

  function openDataPreviewModal() {
    if (!state.datasetPreview) return;
    const { headers, types, sampleRows } = state.datasetPreview;

    let html = `<div style="font-size:11px; font-family:var(--font-mono); margin-bottom:12px; color:var(--text-muted);">
      DATA PREVIEW (FIRST 5 ROWS) · ${state.activeDataset.filename}
    </div>`;

    html += `<div style="overflow-x:auto;"><table class="data-table"><thead><tr>`;
    headers.forEach((h, i) => {
      html += `<th>${escapeHtml(h)}<br><span style="font-size:9px; text-transform:none; font-weight:normal; color:var(--text-muted);">${types[i]}</span></th>`;
    });
    html += `</tr></thead><tbody>`;

    sampleRows.forEach((row) => {
      html += `<tr>`;
      headers.forEach((_, i) => {
        html += `<td>${escapeHtml(row[i] !== undefined ? row[i] : "")}</td>`;
      });
      html += `</tr>`;
    });

    html += `</tbody></table></div>`;

    openModal("Dataset Table Preview", html);
  }

  // =========================================================================
  // Execution Arm Controls
  // =========================================================================
  function initArmControls() {
    $$(".arm-radio-label").forEach((lbl) => {
      lbl.addEventListener("click", () => {
        const mode = lbl.getAttribute("data-mode");
        selectArm(mode);
      });
    });

    $("compareToggle").addEventListener("change", (e) => {
      state.isCompareMode = e.target.checked;
      $("btnExecute").textContent = state.isCompareMode ? "Run 3-Arm Arena" : "Execute Query";
    });

    $("btnExecute").addEventListener("click", runQuery);

    $("queryInput").addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (!state.isRunning) runQuery();
      }
    });

    // Subtabs in results
    $$(".res-subtab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const sub = tab.getAttribute("data-subtab");
        switchSubtab(sub);
      });
    });
  }

  function selectArm(mode) {
    state.selectedMode = mode;
    $$(".arm-radio-label").forEach((lbl) => {
      const match = lbl.getAttribute("data-mode") === mode;
      lbl.classList.toggle("selected", match);
      lbl.querySelector('input[type="radio"]').checked = match;
    });
  }

  function switchSubtab(subtabId) {
    $$(".res-subtab").forEach((t) => t.classList.toggle("active", t.getAttribute("data-subtab") === subtabId));
    $$(".res-panel-tab").forEach((p) => (p.style.display = p.id === `subpanel-${subtabId}` ? "block" : "none"));
  }

  // =========================================================================
  // Execution Logic (Single or 3-Arm Arena)
  // =========================================================================
  async function runQuery() {
    const question = $("queryInput").value.trim();
    if (!state.activeDataset || !state.activeDataset.file) {
      showError("Please select a dataset first.");
      return;
    }
    if (!question) {
      showError("Please enter a question to execute.");
      return;
    }

    clearError();
    setExecuting(true);

    if (state.isCompareMode) {
      await runArenaExecution(question);
    } else {
      await runSingleExecution(question);
    }

    setExecuting(false);
  }

  async function runSingleExecution(question) {
    $("singleResultHub").style.display = "none";
    $("arenaResultHub").style.display = "none";

    try {
      const result = await postAsk(state.activeDataset.file, question, state.selectedMode);
      renderSingleResult(result);
    } catch (err) {
      showError(err.message || "Execution failed.");
    }
  }

  async function runArenaExecution(question) {
    $("singleResultHub").style.display = "none";
    $("arenaResultHub").style.display = "block";

    renderArenaRunning();

    try {
      const [resB1, resB2, resTeam] = await Promise.all([
        postAsk(state.activeDataset.file, question, "baseline1").catch((e) => ({ error: e.message, status: "error" })),
        postAsk(state.activeDataset.file, question, "baseline2").catch((e) => ({ error: e.message, status: "error" })),
        postAsk(state.activeDataset.file, question, "team").catch((e) => ({ error: e.message, status: "error" })),
      ]);

      renderArenaResults(resB1, resB2, resTeam);
    } catch (err) {
      showError("Arena run failure: " + err.message);
    }
  }

  async function postAsk(file, question, mode) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("question", question);
    fd.append("mode", mode);

    const res = await fetch("/ask", { method: "POST", body: fd });
    const body = await res.json().catch(() => null);

    if (!res.ok) {
      throw new Error(body?.detail || `HTTP Error ${res.status}`);
    }

    return body;
  }

  function setExecuting(executing) {
    state.isRunning = executing;
    $("btnExecute").disabled = executing;
    $("btnExecute").textContent = executing ? "Executing..." : state.isCompareMode ? "Run 3-Arm Arena" : "Execute Query";
    $("executingStatusIndicator").style.display = executing ? "inline-flex" : "none";
  }

  function showError(msg) {
    $("errorBanner").style.display = "block";
    $("errorBannerText").textContent = msg;
  }

  function clearError() {
    $("errorBanner").style.display = "none";
  }

  // =========================================================================
  // Render Single Results
  // =========================================================================
  function renderSingleResult(res) {
    state.currentResult = res;
    $("singleResultHub").style.display = "block";
    $("arenaResultHub").style.display = "none";

    // Status Badge
    const st = STATUS_MAP[res.status] || { label: res.status || "UNKNOWN", cls: "neutral" };
    $("singleStatusBadge").textContent = st.label;
    $("singleStatusBadge").className = `badge-status ${st.cls}`;

    const modeNames = {
      baseline1: "Baseline 1 (Single Agent, 1 attempt)",
      baseline2: "Baseline 2 (Single Agent, 3 attempts)",
      baseline3: "Baseline 2 (Single Agent, 3 attempts)",
      team: "Multi-Agent Team (4 Agents)",
    };
    $("singleModeLabel").textContent = modeNames[res.mode] || res.mode;

    // Answer text
    const text = res.answer || res.error || "No answer generated.";
    $("singleAnswerText").textContent = text;

    // Telemetry
    const s = res.stats || {};
    $("telemetryLatency").textContent = typeof s.seconds === "number" ? `${s.seconds.toFixed(2)}s` : "-";
    $("telemetryCalls").textContent = s.llm_calls !== undefined ? s.llm_calls : "-";
    $("telemetryTokens").textContent = s.total_tokens !== undefined ? s.total_tokens.toLocaleString() : "-";
    $("telemetryTokensDetail").textContent = s.input_tokens && s.output_tokens ? `${s.input_tokens} in / ${s.output_tokens} out` : "";
    $("telemetryCost").textContent = typeof s.cost_usd === "number" ? `$${s.cost_usd.toFixed(5)}` : "-";
    $("telemetryAttempts").textContent = res.attempts ? `${res.attempts}` : "1";

    // Code
    $("singleCodeBlock").textContent = res.code || "# No code produced";
    $("btnCopyCode").onclick = () => {
      navigator.clipboard.writeText(res.code || "").then(() => {
        $("btnCopyCode").textContent = "Copied!";
        setTimeout(() => ($("btnCopyCode").textContent = "Copy Script"), 1500);
      });
    };

    // Chart
    const plotTab = $('[data-subtab="plot"]');
    if (res.chart_url) {
      plotTab.style.display = "inline-block";
      $("singlePlotImg").src = res.chart_url;
      $("singlePlotDownload").href = res.chart_url;
    } else {
      plotTab.style.display = "none";
      $("singlePlotImg").removeAttribute("src");
    }

    // Trace
    const tracePanel = $("singleTracePanel");
    tracePanel.innerHTML = "";
    if (res.mode === "team" && res.plan) {
      tracePanel.innerHTML = `
        <div style="margin-bottom:12px;">
          <div style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">1. Planner Output</div>
          <pre class="code-pre" style="margin-top:4px;">${escapeHtml(res.plan)}</pre>
        </div>
        <div style="margin-bottom:12px;">
          <div style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">2. Coder Execution</div>
          <pre class="code-pre" style="margin-top:4px;">${escapeHtml(res.code || "(no code)")}</pre>
        </div>
        <div>
          <div style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">3. Explainer Synthesis</div>
          <div style="margin-top:4px; font-size:12px; color:var(--text-primary); padding:10px; background:var(--bg-canvas); border:1px solid var(--border); border-radius:var(--radius-sm);">${escapeHtml(res.answer || "(empty)")}</div>
        </div>
      `;
    } else {
      tracePanel.innerHTML = `<div style="color:var(--text-muted); font-size:12px;">Direct single-agent execution in Docker sandbox (attempts: ${res.attempts || 1}).</div>`;
    }

    switchSubtab("answer");
  }

  // =========================================================================
  // Render Arena Results (3 Arms)
  // =========================================================================
  function renderArenaRunning() {
    const arms = [
      { id: "b1", title: "Baseline 1 (1 shot)" },
      { id: "b2", title: "Baseline 2 (3 attempts)" },
      { id: "team", title: "Multi-Agent Team" },
    ];

    $("arenaGridContainer").innerHTML = arms
      .map(
        (a) => `
      <div class="arena-arm-col" id="col-${a.id}">
        <div class="arena-col-top">
          <span class="arena-col-name">${a.title}</span>
          <span class="badge-status neutral">RUNNING...</span>
        </div>
        <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 11px;">
          Running in Docker sandbox...
        </div>
      </div>
    `
      )
      .join("");
  }

  function renderArenaResults(b1, b2, team) {
    const arms = [
      { id: "b1", title: "Baseline 1 (1 attempt)", res: b1 },
      { id: "b2", title: "Baseline 2 (3 attempts)", res: b2 },
      { id: "team", title: "Multi-Agent Team", res: team },
    ];

    // Ratio telemetry calculation
    const c1 = b1.stats?.cost_usd || 0;
    const cTeam = team.stats?.cost_usd || 0;
    const costMult = c1 > 0 ? (cTeam / c1).toFixed(1) : "-";

    const t1 = b1.stats?.total_tokens || 0;
    const tTeam = team.stats?.total_tokens || 0;
    const tokenMult = t1 > 0 ? (tTeam / t1).toFixed(1) : "-";

    $("arenaSummaryMetrics").innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; font-size:12px; padding:10px 14px; background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:14px;">
        <span>Multi-Agent vs Single Agent Telemetry: Multi-Agent Team used <b>${tokenMult}x tokens</b> and cost <b>${costMult}x as much</b>.</span>
        <span style="font-family:var(--font-mono); color:var(--text-muted); font-size:11px;">
          B1: ${b1.stats?.seconds?.toFixed(2) || "-"}s · B2: ${b2.stats?.seconds?.toFixed(2) || "-"}s · Team: ${team.stats?.seconds?.toFixed(2) || "-"}s
        </span>
      </div>
    `;

    $("arenaGridContainer").innerHTML = arms
      .map(({ id, title, res }) => {
        const st = STATUS_MAP[res.status] || { label: res.status || "UNKNOWN", cls: "neutral" };
        const s = res.stats || {};
        const chartHtml = res.chart_url
          ? `<div style="text-align:center; padding:8px; border-bottom:1px solid var(--border); background:#fff;"><img src="${res.chart_url}" style="max-width:100%; max-height:180px;" alt="plot"></div>`
          : "";

        return `
        <div class="arena-arm-col">
          <div class="arena-col-top">
            <span class="arena-col-name">${title}</span>
            <span class="badge-status ${st.cls}">${st.label}</span>
          </div>
          <div class="arena-col-metrics">
            <span>Latency: ${typeof s.seconds === "number" ? s.seconds.toFixed(2) + "s" : "-"}</span>
            <span>Tokens: ${s.total_tokens ? s.total_tokens.toLocaleString() : "-"}</span>
            <span>Cost: $${typeof s.cost_usd === "number" ? s.cost_usd.toFixed(5) : "-"}</span>
            <span>Attempts: ${res.attempts || 1}</span>
          </div>
          <div class="arena-col-answer">
            ${escapeHtml(res.answer || res.error || "No answer generated.")}
          </div>
          ${chartHtml}
          <div class="code-container" style="margin:0; border:none; border-top:1px solid var(--border);">
            <div class="code-top">
              <span>Python Script</span>
              <button class="btn-copy" onclick="navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(res.code || "")}'))">Copy</button>
            </div>
            <pre class="code-pre" style="max-height:160px;"><code>${escapeHtml(res.code || "# No code")}</code></pre>
          </div>
        </div>
      `;
      })
      .join("");
  }

  // =========================================================================
  // VIEW 2: Benchmark Suite (50 Questions Matrix)
  // =========================================================================
  async function loadBenchmarkSuite() {
    try {
      const res = await fetch("/api/benchmark");
      if (!res.ok) throw new Error("Could not load benchmark data");
      const data = await res.json();
      state.benchmarkData = data;

      renderBenchmarkSummaryTable(data.summary);
      renderBenchmarkTakeaways(data.takeaways);
      initBenchmarkFilters();
      renderBenchmarkMatrixTable();
    } catch (err) {
      console.error("Benchmark error:", err);
    }
  }

  function renderBenchmarkSummaryTable(summary) {
    const arms = [
      { key: "baseline1", name: "Baseline 1 (Single Agent, 1 attempt)", highlight: false },
      { key: "baseline3", name: "Baseline 2 (Single Agent, 3 attempts)", highlight: true },
      { key: "team", name: "Multi-Agent Team (4 Agents)", highlight: false },
    ];

    const tbody = $("benchmarkSummaryTbody");
    tbody.innerHTML = "";

    arms.forEach(({ key, name, highlight }) => {
      const s = summary[key] || {};
      const tr = document.createElement("tr");
      if (highlight) tr.className = "table-row-highlight";

      tr.innerHTML = `
        <td style="font-weight:600; color:var(--text-primary);">${name} ${highlight ? '<span class="badge-status pass" style="font-size:9px; padding:1px 5px; margin-left:6px;">WINNER</span>' : ''}</td>
        <td style="font-family:var(--font-mono); font-weight:700;">${s.accuracy_pct || 0}%</td>
        <td style="font-family:var(--font-mono);">${s.passed || 0} / ${s.total || 0}</td>
        <td style="font-family:var(--font-mono);">${(s.mean_tokens || 0).toLocaleString()}</td>
        <td style="font-family:var(--font-mono);">${(s.mean_seconds || 0).toFixed(2)}s</td>
        <td style="font-family:var(--font-mono);">$${(s.total_cost_usd || 0).toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">$${(s.mean_cost_usd || 0).toFixed(5)}</td>
        <td style="font-family:var(--font-mono);">${s.total_retries || 0}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderBenchmarkTakeaways(takeaways) {
    const strip = $("benchmarkTakeawaysStrip");
    strip.innerHTML = "";
    if (!takeaways) return;

    takeaways.forEach((t) => {
      const box = document.createElement("div");
      box.className = "takeaway-box";
      box.innerHTML = `
        <div class="takeaway-title">
          <span>${escapeHtml(t.title)}</span>
          <span class="badge-status neutral" style="font-size:9px;">${escapeHtml(t.highlight)}</span>
        </div>
        <div class="takeaway-text">${escapeHtml(t.body)}</div>
      `;
      strip.appendChild(box);
    });
  }

  function initBenchmarkFilters() {
    $("filterDataset").onchange = (e) => {
      state.benchmarkFilter.dataset = e.target.value;
      renderBenchmarkMatrixTable();
    };
    $("filterKind").onchange = (e) => {
      state.benchmarkFilter.kind = e.target.value;
      renderBenchmarkMatrixTable();
    };
    $("filterOutcome").onchange = (e) => {
      state.benchmarkFilter.outcome = e.target.value;
      renderBenchmarkMatrixTable();
    };
    $("filterSearch").oninput = (e) => {
      state.benchmarkFilter.search = e.target.value.toLowerCase().trim();
      renderBenchmarkMatrixTable();
    };
  }

  function renderBenchmarkMatrixTable() {
    if (!state.benchmarkData || !state.benchmarkData.questions) return;
    const questions = state.benchmarkData.questions;

    const filtered = questions.filter((q) => {
      if (state.benchmarkFilter.dataset !== "all" && q.dataset !== state.benchmarkFilter.dataset) return false;
      if (state.benchmarkFilter.kind !== "all" && q.kind !== state.benchmarkFilter.kind) return false;
      if (state.benchmarkFilter.outcome === "failures") {
        const b1P = q.arms?.baseline1?.verdict === "pass";
        const b2P = q.arms?.baseline3?.verdict === "pass";
        const teamP = q.arms?.team?.verdict === "pass";
        if (b1P && b2P && teamP) return false;
      } else if (state.benchmarkFilter.outcome === "team_fail") {
        if (q.arms?.team?.verdict === "pass") return false;
      }
      if (state.benchmarkFilter.search) {
        const haystack = `${q.id} ${q.question} ${q.dataset} ${q.kind}`.toLowerCase();
        if (!haystack.includes(state.benchmarkFilter.search)) return false;
      }
      return true;
    });

    $("matrixRowCount").textContent = `Showing ${filtered.length} of ${questions.length} questions`;

    const tbody = $("benchmarkMatrixTbody");
    tbody.innerHTML = "";

    filtered.forEach((q) => {
      const b1 = q.arms?.baseline1 || {};
      const b2 = q.arms?.baseline3 || {};
      const team = q.arms?.team || {};

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="col-qid">${escapeHtml(q.id)}</td>
        <td><span class="badge-status neutral" style="font-size:10px;">${escapeHtml(q.dataset)}</span></td>
        <td><span class="badge-status neutral" style="font-size:10px;">${escapeHtml(q.kind)}</span></td>
        <td style="max-width:380px;">
          <div>${escapeHtml(q.question)}</div>
          ${q.insight ? `<div style="font-size:10px; color:var(--status-warn-text); margin-top:2px;">Notice: ${escapeHtml(q.insight)}</div>` : ""}
        </td>
        <td><span class="badge-status ${b1.verdict === "pass" ? "pass" : "fail"}">${b1.verdict || "-"}</span></td>
        <td><span class="badge-status ${b2.verdict === "pass" ? "pass" : "fail"}">${b2.verdict || "-"}</span></td>
        <td><span class="badge-status ${team.verdict === "pass" ? "pass" : "fail"}">${team.verdict || "-"}</span></td>
        <td><button class="btn-copy">Inspect</button></td>
      `;

      tr.onclick = () => openQuestionModal(q);
      tbody.appendChild(tr);
    });
  }

  function openQuestionModal(q) {
    const b1 = q.arms?.baseline1 || {};
    const b2 = q.arms?.baseline3 || {};
    const team = q.arms?.team || {};

    const exp = q.expected ? (q.expected.value !== undefined ? String(q.expected.value) : JSON.stringify(q.expected)) : "-";

    const content = `
      <div style="padding:10px 14px; background:var(--bg-canvas); border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:14px;">
        <div style="font-size:13px; font-weight:600; color:var(--text-primary); margin-bottom:4px;">${escapeHtml(q.question)}</div>
        <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); display:flex; gap:16px; flex-wrap:wrap;">
          <span>ID: <b>${escapeHtml(q.id)}</b></span>
          <span>DATASET: <b>${escapeHtml(q.dataset)}.csv</b></span>
          <span>KIND: <b>${escapeHtml(q.kind)}</b></span>
          <span>GROUND TRUTH: <b>${escapeHtml(exp)}</b></span>
        </div>
        ${q.insight ? `<div style="font-size:11px; color:var(--status-warn-text); margin-top:6px; padding-top:6px; border-top:1px solid var(--border);">Investigation Note: ${escapeHtml(q.insight)}</div>` : ""}
      </div>

      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:12px;">
        <!-- B1 -->
        <div style="border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px; background:var(--bg-canvas);">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:600; font-size:11px;">Baseline 1 (1 shot)</span>
            <span class="badge-status ${b1.verdict === "pass" ? "pass" : "fail"}">${b1.verdict}</span>
          </div>
          <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted); margin-bottom:6px;">
            Tokens: ${b1.tokens || 0} · Cost: $${(b1.cost_usd || 0).toFixed(5)}
          </div>
          <div style="font-size:11px; padding:6px 8px; background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-xs); margin-bottom:8px; min-height:40px;">
            ${escapeHtml(b1.answer || b1.error || "(empty)")}
          </div>
          <pre class="code-pre" style="font-size:10px; max-height:140px;"><code>${escapeHtml(b1.code || "# No code")}</code></pre>
        </div>

        <!-- B2 -->
        <div style="border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px; background:var(--bg-canvas);">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:600; font-size:11px;">Baseline 2 (3 attempts)</span>
            <span class="badge-status ${b2.verdict === "pass" ? "pass" : "fail"}">${b2.verdict}</span>
          </div>
          <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted); margin-bottom:6px;">
            Tokens: ${b2.tokens || 0} · Cost: $${(b2.cost_usd || 0).toFixed(5)} · Retries: ${b2.retries || 0}
          </div>
          <div style="font-size:11px; padding:6px 8px; background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-xs); margin-bottom:8px; min-height:40px;">
            ${escapeHtml(b2.answer || b2.error || "(empty)")}
          </div>
          <pre class="code-pre" style="font-size:10px; max-height:140px;"><code>${escapeHtml(b2.code || "# No code")}</code></pre>
        </div>

        <!-- Team -->
        <div style="border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px; background:var(--bg-canvas);">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:600; font-size:11px;">Multi-Agent Team</span>
            <span class="badge-status ${team.verdict === "pass" ? "pass" : "fail"}">${team.verdict}</span>
          </div>
          <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted); margin-bottom:6px;">
            Tokens: ${team.tokens || 0} · Cost: $${(team.cost_usd || 0).toFixed(5)} · Calls: ${team.llm_calls || 4}
          </div>
          <div style="font-size:11px; padding:6px 8px; background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-xs); margin-bottom:8px; min-height:40px;">
            ${escapeHtml(team.answer || team.error || "(empty)")}
          </div>
          <pre class="code-pre" style="font-size:10px; max-height:140px;"><code>${escapeHtml(team.code || "# No code")}</code></pre>
        </div>
      </div>
    `;

    openModal(`Inspection: ${q.id}`, content);
  }

  // =========================================================================
  // Modal Utilities
  // =========================================================================
  function openModal(title, bodyHtml) {
    $("modalTitle").textContent = title;
    $("modalContent").innerHTML = bodyHtml;
    $("modalOverlay").classList.add("active");
  }

  function closeModal() {
    $("modalOverlay").classList.remove("active");
  }

  function initModal() {
    $("modalCloseBtn").onclick = closeModal;
    $("modalOverlay").onclick = (e) => {
      if (e.target === $("modalOverlay")) closeModal();
    };
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initialization
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initNav();
    initDatasets();
    initArmControls();
    initModal();
  });
})();
