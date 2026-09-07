"""
Frontend HTML for the AI-Based Fake Identity & Document Screening System.
Kept in its own file so main.py stays focused on API logic.
"""

UPLOAD_PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Document Screening System | Ministry of Home Affairs</title>
<style>
    :root {
        --navy: #0B3D5C;
        --navy-dark: #072A40;
        --saffron: #FF9933;
        --green: #138808;
        --amber: #B45309;
        --red: #B91C1C;
        --paper: #F7F5F0;
        --ink: #1F2937;
        --ink-soft: #5B6472;
        --line: #DDD8CC;
        --card: #FFFFFF;
    }
    * { box-sizing: border-box; }
    body {
        margin: 0;
        font-family: 'Segoe UI', 'Noto Sans', Arial, sans-serif;
        background: var(--paper);
        color: var(--ink);
    }
    h1, h2, h3 { font-family: Georgia, 'Noto Serif', 'Times New Roman', serif; margin: 0; }

    /* ---------- Header / masthead ---------- */
    .masthead {
        background: var(--navy);
        color: #fff;
        padding: 14px 24px;
    }
    .masthead-inner {
        max-width: 1080px; margin: 0 auto;
        display: flex; align-items: center; gap: 14px;
    }
    .emblem {
        width: 42px; height: 42px; border-radius: 50%;
        background: #fff; color: var(--navy);
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 15px; flex-shrink: 0;
        font-family: Georgia, serif;
    }
    .masthead-text .en { font-size: 15px; font-weight: 600; letter-spacing: 0.2px; }
    .masthead-text .dept { font-size: 12px; color: #C9D9E4; margin-top: 1px; }

    .tricolor-rule { height: 4px; display: flex; }
    .tricolor-rule span { flex: 1; }
    .tricolor-rule .s1 { background: var(--saffron); }
    .tricolor-rule .s2 { background: #ffffff; }
    .tricolor-rule .s3 { background: var(--green); }

    /* ---------- Hero ---------- */
    .hero {
        max-width: 1080px; margin: 0 auto; padding: 34px 24px 20px;
    }
    .hero h1 { font-size: 27px; color: var(--navy-dark); line-height: 1.3; }
    .hero p.sub { color: var(--ink-soft); font-size: 14.5px; margin-top: 8px; max-width: 640px; line-height: 1.5; }
    .hero .ref { font-size: 12px; color: var(--ink-soft); margin-top: 10px; }

    .stats-row { display: flex; gap: 14px; margin-top: 20px; flex-wrap: wrap; }
    .stat-box {
        background: var(--card); border: 1px solid var(--line); border-left: 3px solid var(--saffron);
        padding: 10px 16px; min-width: 130px;
    }
    .stat-box .num { font-size: 22px; font-weight: 700; color: var(--navy-dark); font-family: Georgia, serif; }
    .stat-box .lbl { font-size: 11.5px; color: var(--ink-soft); margin-top: 2px; }

    /* ---------- Layout ---------- */
    .container { max-width: 1080px; margin: 0 auto; padding: 10px 24px 60px; }
    .card {
        background: var(--card); border: 1px solid var(--line);
        padding: 22px 24px; margin-top: 20px;
    }
    .card-title {
        font-size: 15px; font-weight: 700; color: var(--navy-dark);
        border-bottom: 2px solid var(--saffron); padding-bottom: 8px; margin-bottom: 16px;
        display: flex; justify-content: space-between; align-items: center;
    }

    /* ---------- Tabs ---------- */
    .tabs { display: flex; gap: 4px; margin-top: 24px; border-bottom: 1px solid var(--line); }
    .tab-btn {
        padding: 10px 18px; font-size: 13.5px; font-weight: 600; cursor: pointer;
        background: none; border: none; color: var(--ink-soft);
        border-bottom: 2px solid transparent; margin-bottom: -1px;
    }
    .tab-btn.active { color: var(--navy-dark); border-bottom-color: var(--saffron); }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    /* ---------- Form ---------- */
    label { display: block; font-size: 13px; font-weight: 600; color: var(--ink); margin-top: 14px; }
    label:first-child { margin-top: 0; }
    label .opt { font-weight: 400; color: var(--ink-soft); }
    input[type=file] {
        margin-top: 6px; font-size: 13px; width: 100%;
        padding: 8px; border: 1px dashed var(--line); background: #FBFAF7;
    }
    .btn {
        margin-top: 20px; padding: 11px 24px; font-size: 14px; font-weight: 600;
        cursor: pointer; background: var(--navy); color: white; border: none;
    }
    .btn:hover { background: var(--navy-dark); }
    .btn:disabled { background: #9AAAB6; cursor: not-allowed; }
    .btn.secondary { background: #fff; color: var(--navy); border: 1.5px solid var(--navy); }
    .btn.secondary:hover { background: #EEF3F6; }

    #status, #batchStatus { font-size: 13px; color: var(--ink-soft); margin-top: 12px; }

    /* ---------- Results ---------- */
    #resultsPanel { display: none; }

    .verdict-banner {
        display: flex; flex-wrap: wrap; align-items: center; gap: 24px;
        padding: 20px 22px; color: white;
    }
    .verdict-banner.genuine { background: var(--green); }
    .verdict-banner.review { background: var(--amber); }
    .verdict-banner.fake { background: var(--red); }
    .verdict-left .v-label { font-size: 11px; letter-spacing: 0.03em; opacity: 0.85; }
    .verdict-left .v-title { font-size: 21px; font-weight: 700; font-family: Georgia, serif; }
    .verdict-report-id { font-size: 11px; opacity: 0.85; margin-top: 4px; }

    .gauge-wrap { display: flex; align-items: center; gap: 10px; margin-left: auto; }
    .gauge-num { font-size: 26px; font-weight: 700; font-family: Georgia, serif; }
    .gauge-lbl { font-size: 10.5px; opacity: 0.85; }

    .section-heading {
        font-size: 13.5px; font-weight: 700; color: var(--navy-dark);
        margin: 22px 0 10px 0; text-transform: uppercase; letter-spacing: 0.04em;
    }

    .ela-img-wrap { text-align: center; }
    .ela-img-wrap img {
        max-width: 100%; border: 1px solid var(--line); background: #111;
    }
    .ela-caption { font-size: 12px; color: var(--ink-soft); margin-top: 8px; }

    .flag-card {
        background: #FBFAF7; border: 1px solid var(--line); border-left: 4px solid #ccc;
        padding: 12px 14px; margin-bottom: 8px;
    }
    .flag-card.high   { border-left-color: var(--red); }
    .flag-card.medium { border-left-color: var(--amber); }
    .flag-card.low    { border-left-color: #6b7280; }
    .flag-top { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
    .flag-code { font-weight: 700; font-size: 13px; }
    .flag-badge {
        font-size: 10px; font-weight: 700; text-transform: uppercase;
        padding: 2px 8px; color: white; white-space: nowrap;
    }
    .flag-badge.high   { background: var(--red); }
    .flag-badge.medium { background: var(--amber); }
    .flag-badge.low    { background: #6b7280; }
    .flag-desc { font-size: 13px; color: #333; margin-top: 6px; line-height: 1.45; }
    .flag-source { font-size: 11px; color: var(--ink-soft); margin-top: 6px; }
    .no-flags { font-size: 13px; color: var(--ink-soft); font-style: italic; }

    .fields-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .fields-table td { padding: 7px 10px; border-bottom: 1px solid var(--line); }
    .fields-table td:first-child { font-weight: 600; color: var(--ink-soft); width: 38%; }

    .module-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .module-box { background: #FBFAF7; border: 1px solid var(--line); padding: 10px 12px; font-size: 13px; }
    .module-box .m-name { font-weight: 600; margin-bottom: 4px; }
    .module-box .m-score { font-size: 12px; color: var(--ink-soft); }
    .module-box .m-skip { font-size: 12px; color: #999; font-style: italic; }

    /* ---------- Audit trail ---------- */
    table.audit-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    table.audit-table th {
        text-align: left; padding: 8px 10px; background: #F0EDE4; color: var(--ink-soft);
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600;
    }
    table.audit-table td { padding: 8px 10px; border-bottom: 1px solid var(--line); }
    .badge-pill {
        display: inline-block; padding: 2px 9px; font-size: 11px; font-weight: 600; color: white;
    }
    .badge-pill.genuine { background: var(--green); }
    .badge-pill.review { background: var(--amber); }
    .badge-pill.fake { background: var(--red); }
    #auditEmpty { font-size: 13px; color: var(--ink-soft); font-style: italic; padding: 10px 0; }

    /* ---------- Batch ---------- */
    .batch-summary-row { display: flex; gap: 14px; margin: 16px 0; flex-wrap: wrap; }
    .batch-summary-box { flex: 1; min-width: 130px; padding: 12px 16px; color: #fff; }
    .batch-summary-box.genuine { background: var(--green); }
    .batch-summary-box.review { background: var(--amber); }
    .batch-summary-box.fake { background: var(--red); }
    .batch-summary-box .n { font-size: 24px; font-weight: 700; font-family: Georgia, serif; }
    .batch-summary-box .l { font-size: 11.5px; opacity: 0.9; }

    .batch-item {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 12px; border: 1px solid var(--line); margin-bottom: 6px; font-size: 13px;
    }

    footer {
        text-align: center; font-size: 11.5px; color: var(--ink-soft);
        padding: 20px; border-top: 1px solid var(--line); margin-top: 30px;
    }

    @media (max-width: 640px) {
        .module-grid { grid-template-columns: 1fr; }
        .verdict-banner { flex-direction: column; align-items: flex-start; }
        .gauge-wrap { margin-left: 0; }
    }
</style>
</head>
<body>

<div class="masthead">
    <div class="masthead-inner">
        <div class="emblem">GoI</div>
        <div class="masthead-text">
            <div class="en">Government of India &middot; Ministry of Home Affairs</div>
            <div class="dept">Sashastra Seema Bal (SSB), Police II Division</div>
        </div>
    </div>
</div>
<div class="tricolor-rule"><span class="s1"></span><span class="s2"></span><span class="s3"></span></div>

<div class="hero">
    <h1>AI-Based Fake Identity &amp; Document Screening System</h1>
    <p class="sub">Automated verification of identity and travel documents — detecting tampering,
        validating extracted data, and generating an explainable risk assessment to support faster,
        more consistent screening decisions at checkpoints.</p>
    <p class="ref">Problem Statement Reference: SIH26188</p>

    <div class="stats-row">
        <div class="stat-box"><div class="num" id="statTotal">0</div><div class="lbl">Documents Screened</div></div>
        <div class="stat-box"><div class="num" id="statGenuine">0</div><div class="lbl">Likely Genuine</div></div>
        <div class="stat-box"><div class="num" id="statReview">0</div><div class="lbl">Needs Review</div></div>
        <div class="stat-box"><div class="num" id="statFake">0</div><div class="lbl">Likely Fake</div></div>
    </div>
</div>

<div class="container">

    <div class="tabs">
        <button class="tab-btn active" data-tab="single">Single Document Screening</button>
        <button class="tab-btn" data-tab="batch">Batch / Checkpoint Mode</button>
        <button class="tab-btn" data-tab="audit">Digital Audit Trail</button>
    </div>

    <!-- ===================== SINGLE SCREENING ===================== -->
    <div class="tab-panel active" id="panel-single">
        <div class="card">
            <div class="card-title">Screen a Document</div>
            <form id="uploadForm">
                <label>Document image <span class="opt">(required)</span></label>
                <input type="file" name="document" id="document" accept="image/*" required>

                <label>Selfie image <span class="opt">(optional — enables face verification)</span></label>
                <input type="file" name="selfie" id="selfie" accept="image/*">

                <label>Stamp crop image <span class="opt">(optional — enables stamp forgery check)</span></label>
                <input type="file" name="stamp_crop" id="stamp_crop" accept="image/*">

                <button type="submit" class="btn" id="submitBtn">Screen Document</button>
            </form>
            <p id="status"></p>
        </div>

        <div id="resultsPanel">
            <div class="card" style="padding:0; overflow:hidden;">
                <div id="verdictBanner" class="verdict-banner">
                    <div class="verdict-left">
                        <div class="v-label">SCREENING VERDICT</div>
                        <div class="v-title" id="verdictTitle">—</div>
                        <div class="verdict-report-id" id="reportIdLine"></div>
                    </div>
                    <div class="gauge-wrap">
                        <svg width="72" height="72" viewBox="0 0 72 72">
                            <circle cx="36" cy="36" r="30" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="7"/>
                            <circle id="gaugeArc" cx="36" cy="36" r="30" fill="none" stroke="white" stroke-width="7"
                                    stroke-dasharray="188.5" stroke-dashoffset="188.5" stroke-linecap="round"
                                    transform="rotate(-90 36 36)"/>
                        </svg>
                        <div>
                            <div class="gauge-num" id="trustScoreValue">—</div>
                            <div class="gauge-lbl">TRUST SCORE</div>
                        </div>
                    </div>
                </div>

                <div style="padding: 20px 24px 24px;">
                    <button class="btn secondary" id="downloadPdfBtn" style="margin-top:0;">Download PDF Report</button>

                    <div id="elaSection" style="display:none;">
                        <div class="section-heading">Tampering Visualization (Error Level Analysis)</div>
                        <div class="ela-img-wrap">
                            <img id="elaImage" src="" alt="ELA heatmap">
                            <p class="ela-caption">Brighter, patchy regions indicate areas with a compression signature
                                different from the rest of the document — a common sign of a pasted or edited region.</p>
                        </div>
                    </div>

                    <div class="section-heading">Top Reasons</div>
                    <div id="topReasons"></div>

                    <div class="section-heading">Extracted Document Fields</div>
                    <table class="fields-table" id="fieldsTable"></table>

                    <div class="section-heading">Module Breakdown</div>
                    <div class="module-grid" id="moduleGrid"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- ===================== BATCH SCREENING ===================== -->
    <div class="tab-panel" id="panel-batch">
        <div class="card">
            <div class="card-title">Batch / Checkpoint Simulation</div>
            <p style="font-size:13px; color:var(--ink-soft); margin-top:-6px;">
                Upload multiple documents at once to simulate a checkpoint processing a queue of travelers.
            </p>
            <form id="batchForm">
                <label>Document images <span class="opt">(select multiple)</span></label>
                <input type="file" name="documents" id="batchDocuments" accept="image/*" multiple required>
                <button type="submit" class="btn" id="batchSubmitBtn">Screen Batch</button>
            </form>
            <p id="batchStatus"></p>
        </div>

        <div class="card" id="batchResultsCard" style="display:none;">
            <div class="card-title">Batch Results</div>
            <div class="batch-summary-row" id="batchSummaryRow"></div>
            <div id="batchItemsList"></div>
        </div>
    </div>

    <!-- ===================== AUDIT TRAIL ===================== -->
    <div class="tab-panel" id="panel-audit">
        <div class="card">
            <div class="card-title">
                Digital Audit Trail
                <button class="btn secondary" style="margin-top:0; padding:6px 14px; font-size:12px;" id="refreshAuditBtn">Refresh</button>
            </div>
            <p style="font-size:13px; color:var(--ink-soft); margin-top:-6px;">
                A running record of every document screened in this session — supporting traceability for
                investigations and intelligence analysis. (In-memory for this prototype; a production deployment
                would persist this to a secure, access-controlled database.)
            </p>
            <div id="auditEmpty" style="display:none;">No documents have been screened yet.</div>
            <table class="audit-table" id="auditTable" style="display:none;">
                <thead>
                    <tr><th>Time</th><th>Report ID</th><th>Filename</th><th>Verdict</th><th>Trust Score</th><th></th></tr>
                </thead>
                <tbody id="auditTableBody"></tbody>
            </table>
        </div>
    </div>

</div>

<footer>
    AI-Based Fake Identity &amp; Document Screening System — Hackathon Prototype (SIH26188).
    Screening results are AI-assisted findings for human review, not automated approval or rejection decisions.
</footer>

<script>
    const MODULE_LABELS = {
        module_2_document_validation: "Document Validation",
        module_3_tampering_detection: "Tampering Detection",
        module_4_face_verification: "Face Verification",
    };

    function verdictInfo(verdict) {
        if (verdict === "Likely Genuine") return { cls: "genuine", pill: "genuine" };
        if (verdict === "Needs Manual Review") return { cls: "review", pill: "review" };
        return { cls: "fake", pill: "fake" };
    }

    function renderFlag(flag) {
        const sev = (flag.severity || "low").toLowerCase();
        const div = document.createElement("div");
        div.className = "flag-card " + sev;
        div.innerHTML = `
            <div class="flag-top">
                <span class="flag-code">${flag.code || "FLAG"}</span>
                <span class="flag-badge ${sev}">${sev}</span>
            </div>
            <div class="flag-desc">${flag.description || ""}</div>
            <div class="flag-source">Source: ${flag.source_module || "unknown"}</div>
        `;
        return div;
    }

    function renderModuleBox(label, mod) {
        const box = document.createElement("div");
        box.className = "module-box";
        if (!mod || mod.evaluated === false) {
            box.innerHTML = `<div class="m-name">${label}</div><div class="m-skip">Not evaluated (optional input not provided)</div>`;
        } else {
            const score = (mod.risk_score !== undefined && mod.risk_score !== null) ? mod.risk_score : "N/A";
            let extra = "";
            if (mod.match_confidence !== undefined && mod.match_confidence !== null) {
                extra = ` &middot; match confidence: ${mod.match_confidence}%`;
            }
            box.innerHTML = `<div class="m-name">${label}</div><div class="m-score">Risk score: ${score}${extra}</div>`;
        }
        return box;
    }

    function setGauge(trustScore) {
        const circumference = 188.5; // 2 * pi * r(30)
        const clamped = Math.max(0, Math.min(100, trustScore || 0));
        const offset = circumference - (clamped / 100) * circumference;
        document.getElementById('gaugeArc').style.strokeDashoffset = offset;
    }

    // ---------- Single document screening ----------
    let lastReportId = null;

    document.getElementById('uploadForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const statusEl = document.getElementById('status');
        const resultsPanel = document.getElementById('resultsPanel');
        const submitBtn = document.getElementById('submitBtn');

        resultsPanel.style.display = 'none';
        statusEl.textContent = 'Processing... this can take a few seconds.';
        submitBtn.disabled = true;

        const formData = new FormData();
        const docFile = document.getElementById('document').files[0];
        const selfieFile = document.getElementById('selfie').files[0];
        const stampFile = document.getElementById('stamp_crop').files[0];

        formData.append('document', docFile);
        if (selfieFile) formData.append('selfie', selfieFile);
        if (stampFile) formData.append('stamp_crop', stampFile);

        try {
            const response = await fetch('/screen-document', { method: 'POST', body: formData });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Server returned ${response.status}: ${errText}`);
            }
            const data = await response.json();
            statusEl.textContent = 'Done.';
            renderSingleResult(data);
            refreshAuditTrail();
        } catch (err) {
            statusEl.textContent = 'Error: ' + err.message;
        } finally {
            submitBtn.disabled = false;
        }
    });

    function renderSingleResult(data) {
        const info = verdictInfo(data.verdict);
        lastReportId = data.report_id;

        document.getElementById('verdictBanner').className = 'verdict-banner ' + info.cls;
        document.getElementById('verdictTitle').textContent = data.verdict || 'Unknown';
        document.getElementById('reportIdLine').textContent = 'Report ID: ' + (data.report_id || '—');
        document.getElementById('trustScoreValue').textContent = (data.final_trust_score ?? '—');
        setGauge(data.final_trust_score);

        const elaSection = document.getElementById('elaSection');
        if (data.ela_heatmap_base64) {
            document.getElementById('elaImage').src = 'data:image/jpeg;base64,' + data.ela_heatmap_base64;
            elaSection.style.display = 'block';
        } else {
            elaSection.style.display = 'none';
        }

        const topReasonsEl = document.getElementById('topReasons');
        topReasonsEl.innerHTML = '';
        if (data.top_reasons && data.top_reasons.length > 0) {
            data.top_reasons.forEach(flag => topReasonsEl.appendChild(renderFlag(flag)));
        } else {
            topReasonsEl.innerHTML = '<div class="no-flags">No issues flagged by any module.</div>';
        }

        const fieldsTable = document.getElementById('fieldsTable');
        fieldsTable.innerHTML = '';
        const ocrModule = (data.modules && data.modules.module_1_ocr_extraction) || {};
        const fields = ocrModule.extracted_fields || {};
        const fieldKeys = Object.keys(fields);
        if (fieldKeys.length === 0) {
            fieldsTable.innerHTML = '<tr><td colspan="2" style="font-style:italic;color:#888;">No fields could be extracted.</td></tr>';
        } else {
            fieldKeys.forEach(key => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${key.replace(/_/g, ' ')}</td><td>${fields[key]}</td>`;
                fieldsTable.appendChild(row);
            });
        }

        const moduleGrid = document.getElementById('moduleGrid');
        moduleGrid.innerHTML = '';
        const modules = data.modules || {};
        Object.keys(MODULE_LABELS).forEach(key => {
            moduleGrid.appendChild(renderModuleBox(MODULE_LABELS[key], modules[key]));
        });

        document.getElementById('resultsPanel').style.display = 'block';
    }

    document.getElementById('downloadPdfBtn').addEventListener('click', function() {
        if (!lastReportId) return;
        window.open('/generate-report/' + lastReportId, '_blank');
    });

    // ---------- Tabs ----------
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
            if (btn.dataset.tab === 'audit') refreshAuditTrail();
        });
    });

    // ---------- Batch screening ----------
    document.getElementById('batchForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const statusEl = document.getElementById('batchStatus');
        const submitBtn = document.getElementById('batchSubmitBtn');
        const files = document.getElementById('batchDocuments').files;

        if (files.length === 0) return;

        statusEl.textContent = `Processing ${files.length} document(s)... this can take a while.`;
        submitBtn.disabled = true;
        document.getElementById('batchResultsCard').style.display = 'none';

        const formData = new FormData();
        for (const file of files) formData.append('documents', file);

        try {
            const response = await fetch('/screen-batch', { method: 'POST', body: formData });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Server returned ${response.status}: ${errText}`);
            }
            const data = await response.json();
            statusEl.textContent = `Done — ${data.total} document(s) screened.`;
            renderBatchResult(data);
            refreshAuditTrail();
        } catch (err) {
            statusEl.textContent = 'Error: ' + err.message;
        } finally {
            submitBtn.disabled = false;
        }
    });

    function renderBatchResult(data) {
        const summaryRow = document.getElementById('batchSummaryRow');
        summaryRow.innerHTML = '';
        const labels = {
            "Likely Genuine": ["genuine", "Likely Genuine"],
            "Needs Manual Review": ["review", "Needs Review"],
            "Likely Fake": ["fake", "Likely Fake"],
        };
        Object.keys(labels).forEach(key => {
            const [cls, label] = labels[key];
            const box = document.createElement('div');
            box.className = 'batch-summary-box ' + cls;
            box.innerHTML = `<div class="n">${data.summary[key] || 0}</div><div class="l">${label}</div>`;
            summaryRow.appendChild(box);
        });

        const itemsList = document.getElementById('batchItemsList');
        itemsList.innerHTML = '';
        data.results.forEach(item => {
            const info = verdictInfo(item.verdict);
            const row = document.createElement('div');
            row.className = 'batch-item';
            row.innerHTML = `
                <span>${item.filename}</span>
                <span class="badge-pill ${info.pill}">${item.verdict}</span>
                <span>Trust: ${item.trust_score}%</span>
                <a href="/generate-report/${item.report_id}" target="_blank" style="font-size:12px;">PDF</a>
            `;
            row.style.display = 'flex';
            row.style.justifyContent = 'space-between';
            row.style.alignItems = 'center';
            row.style.gap = '10px';
            itemsList.appendChild(row);
        });

        document.getElementById('batchResultsCard').style.display = 'block';
    }

    // ---------- Audit trail ----------
    async function refreshAuditTrail() {
        try {
            const response = await fetch('/audit-trail?limit=50');
            const data = await response.json();
            const entries = data.entries || [];

            document.getElementById('statTotal').textContent = data.count || 0;
            document.getElementById('statGenuine').textContent = entries.filter(e => e.verdict === 'Likely Genuine').length;
            document.getElementById('statReview').textContent = entries.filter(e => e.verdict === 'Needs Manual Review').length;
            document.getElementById('statFake').textContent = entries.filter(e => e.verdict === 'Likely Fake').length;

            const tableBody = document.getElementById('auditTableBody');
            const table = document.getElementById('auditTable');
            const empty = document.getElementById('auditEmpty');

            if (entries.length === 0) {
                table.style.display = 'none';
                empty.style.display = 'block';
                return;
            }
            empty.style.display = 'none';
            table.style.display = 'table';
            tableBody.innerHTML = '';

            entries.forEach(entry => {
                const info = verdictInfo(entry.verdict);
                const row = document.createElement('tr');
                const time = new Date(entry.timestamp).toLocaleString();
                row.innerHTML = `
                    <td>${time}</td>
                    <td>${entry.report_id}</td>
                    <td>${entry.filename}</td>
                    <td><span class="badge-pill ${info.pill}">${entry.verdict}</span></td>
                    <td>${entry.trust_score}%</td>
                    <td><a href="/generate-report/${entry.report_id}" target="_blank">PDF</a></td>
                `;
                tableBody.appendChild(row);
            });
        } catch (err) {
            console.error('Failed to load audit trail:', err);
        }
    }

    document.getElementById('refreshAuditBtn').addEventListener('click', refreshAuditTrail);

    // Load audit trail + stats on first page load
    refreshAuditTrail();
</script>
</body>
</html>
"""
