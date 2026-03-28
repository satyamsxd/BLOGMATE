/**
 * Blogmate — Frontend Application
 * Handles multi-view navigation, real-time SSE streaming, and data rendering.
 */

// ── State ────────────────────────────────────────────────────────────────
let currentResult = null;
let pipelineStartTime = null;
let pipelineTimerInterval = null;

// ── Init ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetchProviderStatus();
  loadHistory();
  
  // Set initial view
  const hash = window.location.hash.replace('#', '') || 'dashboard';
  setTimeout(() => switchView(hash), 50);

  // Enter key support
  const input = document.getElementById('keyword-input');
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') startGeneration();
    });
  }
});

// ── View Management ──────────────────────────────────────────────────────
function switchView(viewId) {
  // Update URL hash without scroll
  history.replaceState(null, null, `#${viewId}`);

  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  
  // Show target view
  const targetView = document.getElementById(`view-${viewId}`);
  if (targetView) targetView.classList.add('active');

  // Update Navigation Active States
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === viewId);
  });
  document.querySelectorAll('.navbar-tabs .navbar-tab').forEach(el => {
    el.classList.toggle('active', el.dataset.view === viewId);
  });

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
  
  // Conditionally show/hide the top navbar generate button
  const navBtn = document.getElementById('navbar-generate-btn');
  if (navBtn) {
    navBtn.style.display = viewId === 'blog-generation' ? 'none' : 'block';
  }
}

// ── Pipeline Progress ────────────────────────────────────────────────────
function showProgress() {
  document.getElementById('pipeline-progress').classList.add('active');
  document.getElementById('blog-output').classList.remove('visible');
  document.getElementById('error-banner').classList.remove('visible');
  
  // Show generating states on empty placeholders
  document.getElementById('seo-empty-state').classList.add('hidden');
  document.getElementById('seo-content').classList.add('hidden');
  document.getElementById('serp-empty-state').classList.add('hidden');
  document.getElementById('serp-content').classList.add('hidden');
  
  document.querySelectorAll('.stage-item').forEach(s => {
    s.classList.remove('active', 'done');
    const num = s.dataset.stage;
    s.querySelector('.stage-num').textContent = num;
  });
  document.querySelectorAll('.stage-time').forEach(t => t.textContent = '');

  // Start timer
  pipelineStartTime = performance.now();
  document.getElementById('pipeline-timer').textContent = '0.0s';
  pipelineTimerInterval = setInterval(() => {
    const elapsed = ((performance.now() - pipelineStartTime) / 1000).toFixed(1);
    document.getElementById('pipeline-timer').textContent = elapsed + 's';
  }, 100);
}

function markStageStart(stageNum) {
  const item = document.querySelector(`.stage-item[data-stage="${stageNum}"]`);
  if (item) {
    item.classList.add('active');
    item.classList.remove('done');
  }
}

function markStageComplete(stageNum, duration) {
  const item = document.querySelector(`.stage-item[data-stage="${stageNum}"]`);
  if (item) {
    item.classList.remove('active');
    item.classList.add('done');
    item.querySelector('.stage-num').textContent = '✓';
    const timeEl = item.querySelector('.stage-time');
    if (timeEl && duration) timeEl.textContent = duration.toFixed(1) + 's';
  }
}

function completeAllStages() {
  document.querySelectorAll('.stage-item').forEach(s => {
    s.classList.remove('active');
    s.classList.add('done');
    s.querySelector('.stage-num').textContent = '✓';
  });
  if (pipelineTimerInterval) {
    clearInterval(pipelineTimerInterval);
    pipelineTimerInterval = null;
  }
}

function showError(msg) {
  const banner = document.getElementById('error-banner');
  document.getElementById('error-text').textContent = msg;
  banner.classList.add('visible');
  if (pipelineTimerInterval) {
    clearInterval(pipelineTimerInterval);
    pipelineTimerInterval = null;
  }
}

// ── Generation (SSE Streaming) ───────────────────────────────────────────
async function startGeneration() {
  const input = document.getElementById('keyword-input');
  const btn = document.getElementById('generate-btn');
  const keyword = input.value.trim();

  if (!keyword) {
    input.focus();
    input.style.borderColor = 'var(--brand-red)';
    setTimeout(() => input.style.borderColor = '', 1000);
    return;
  }

  btn.disabled = true;
  btn.querySelector('.btn-text').innerHTML = '<span class="spinner"></span> Generating...';
  
  // Ensure we are on generation view
  switchView('blog-generation');
  showProgress();

  try {
    const response = await fetch('/api/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || 'Generation failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            handleSSEEvent(event);
          } catch (e) { /* ignore parse errors for chunked frames */ }
        }
      }
    }

    if (buffer.startsWith('data: ')) {
      try { handleSSEEvent(JSON.parse(buffer.slice(6))); } catch (e) {}
    }

  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-3px;margin-right:6px;"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 
      Generate Blog`;
  }
}

function handleSSEEvent(event) {
  if (event.type === 'stage_start') {
    markStageStart(event.stage_number);
  } else if (event.type === 'stage_complete') {
    markStageComplete(event.stage_number, event.duration);
  } else if (event.type === 'done') {
    completeAllStages();
    currentResult = event.result;

    setTimeout(() => {
      renderResults(currentResult);
      document.getElementById('blog-output').classList.add('visible');
      document.getElementById('seo-content').classList.remove('hidden');
      document.getElementById('serp-content').classList.remove('hidden');
      
      const badge = document.getElementById('analysis-badge');
      if (badge) badge.classList.remove('hidden');

      saveHistory(currentResult);
      fetchProviderStatus();
      updateDashboardStats(); // refresh overview tab
      
      showToast('Generation complete!');
    }, 400);

  } else if (event.type === 'error') {
    showError(event.error);
  }
}

// ── Render Results ───────────────────────────────────────────────────────
function renderResults(r) {
  renderMetaBar(r);
  renderBlog(r);
  renderSEO(r);
  renderSERPGaps(r);
  renderLinks(r);
  renderSnippet(r);
  renderStrategy(r);
}

function renderMetaBar(r) {
  const timing = r.pipeline_timing || {};
  document.getElementById('total-time').textContent = (timing.total || 0).toFixed(1) + 's total';
  document.getElementById('total-words').textContent = (r.blog_content || {}).total_word_count + ' words';
  fetch('/api/providers/active')
    .then(res => res.json())
    .then(data => { document.getElementById('provider-used').textContent = (data.active || []).join(' → ') || 'multi-provider'; })
    .catch(() => { document.getElementById('provider-used').textContent = 'multi-provider'; });
}

function renderBlog(r) {
  const blog = r.blog_content || {};
  const strategy = r.content_strategy || {};
  document.getElementById('blog-meta-preview').innerHTML = `
    <div class="meta-title">${esc(strategy.seo_title || '')}</div>
    <div class="meta-url">yourdomain.com › blog › ${esc(r.keyword || '')}</div>
    <div class="meta-desc">${esc(strategy.meta_description || '')}</div>`;
  
  const wc = blog.total_word_count || 0;
  const sc = (blog.sections || []).length;
  document.getElementById('blog-stats-bar').innerHTML = `
    <span>📝 <strong>${wc}</strong> words</span>
    <span>📑 <strong>${sc}</strong> sections</span>
    <span>⏱️ <strong>${Math.ceil(wc / 230)}</strong> min read</span>`;
    
  // Using marked.js if available
  if (typeof marked !== 'undefined') {
    document.getElementById('blog-rendered').innerHTML = marked.parse(blog.full_markdown || '');
  } else {
    document.getElementById('blog-rendered').textContent = blog.full_markdown;
  }
}

/* ── SEO Dashboard (Aether UI) ── */
function renderSEO(r) {
  const seo = r.seo_analysis || {};
  const scoreData = seo.seo_score || {};
  const readability = seo.readability || {};
  const naturalness = seo.naturalness || {};
  const density = seo.keyword_density || {};

  // Readability Card
  const fScore = readability.flesch_score || 0;
  document.getElementById('flesch-score-big').textContent = fScore;
  document.getElementById('flesch-grade').textContent = readability.flesch_grade || 'N/A';
  let fColor = fScore >= 60 ? '#10b981' : (fScore >= 40 ? '#f59e0b' : '#ef4444');
  document.getElementById('flesch-score-big').style.color = fColor;
  document.getElementById('flesch-grade').style.color = fColor;
  
  document.getElementById('avg-sentence-len').textContent = readability.avg_sentence_length || 0;
  document.getElementById('total-words-stat').textContent = readability.total_words || 0;
  document.getElementById('total-sentences-stat').textContent = readability.total_sentences || 0;

  // Keyword Density Table
  let dHtml = '';
  // Primary
  const pDen = density.primary_density || 0;
  const pCol = densityColor(pDen);
  dHtml += `<tr>
    <td><span class="kw-primary-icon">★</span> <strong>${esc(density.primary_keyword)}</strong></td>
    <td>${pDen}%</td>
    <td><div class="density-bar-bg"><div class="density-bar-fill" style="width:${Math.min(pDen*30, 100)}%;background:${pCol}"></div></div></td>
    <td>${(r.blog_content || {}).total_keyword_mentions || 0}</td>
  </tr>`;
  
  // Secondary
  Object.entries(density.secondary_keywords || {}).forEach(([kw, d]) => {
    let hits = Math.round(d * ((readability.total_words || 1000)/100)); // rough approx
    dHtml += `<tr>
      <td><span class="kw-secondary-icon">#</span> ${esc(kw)}</td>
      <td>${d}%</td>
      <td><div class="density-bar-bg"><div class="density-bar-fill" style="width:${Math.min(d*30, 100)}%;background:${densityColor(d)}"></div></div></td>
      <td>${hits}</td>
    </tr>`;
  });
  document.getElementById('density-tbody').innerHTML = dHtml;

  // Warnings
  let wHtml = '';
  (density.warnings || []).forEach(w => { wHtml += `<div class="density-warning-flag">⚠️ ${esc(w)}</div>`;});
  document.getElementById('density-warnings').innerHTML = wHtml;

  // Naturalness circular gauge
  const natScore = naturalness.score || 0;
  document.getElementById('naturalness-score-big').textContent = natScore;
  const natColor = scoreColor(natScore);
  
  // SVG Stroke offset calculation
  const circumference = 2 * Math.PI * 58;
  const offset = circumference - (natScore / 100) * circumference;
  const ring = document.getElementById('naturalness-ring');
  ring.style.strokeDasharray = `${circumference} ${circumference}`;
  ring.style.strokeDashoffset = circumference; // start empty
  ring.style.stroke = natColor;
  
  // Animate
  setTimeout(() => { ring.style.strokeDashoffset = offset; }, 100);

  document.getElementById('naturalness-text').textContent = naturalness.assessment || '';
  
  // Naturalness Badges + Metrics Strip
  const signals = naturalness.signals || {};
  let badges = '';
  let stripHtml = '';
  
  if (Object.keys(signals).length === 0) {
    badges = '<span class="nat-badge pass">Optimized for Discover</span> <span class="nat-badge pass">High Authority Signal</span>';
  } else {
    // Badges from signals
    Object.entries(signals).forEach(([key, val]) => {
      const isGood = val.score >= 70;
      badges += `<span class="nat-badge ${isGood?'pass':''}">${formatKey(key)}: ${val.score}</span> `;
      
      const pColor = scoreColor(val.score);
      stripHtml += `
        <div class="metric-line">
          <div class="metric-header"><span class="label">${formatKey(key)}</span> <span style="color:${pColor}">${val.score >= 80 ? 'Optimal' : (val.score >= 60 ? 'Good' : 'Needs Work')}</span></div>
          <div class="metric-bar-bg"><div class="metric-bar-line" style="width:${val.score}%;background:${pColor}"></div></div>
        </div>
      `;
    });
  }
  
  document.getElementById('naturalness-badges').innerHTML = badges || '<span class="nat-badge pass">Natural phrasing</span>';
  document.getElementById('metrics-strip').innerHTML = stripHtml;

  // Flags detail mapping
  let flexDetails = '';
  if ((naturalness.ai_cliche_phrases || []).length) flexDetails += `<h4>AI Phrases</h4>` + naturalness.ai_cliche_phrases.map(f => `<div class="flag-item"><span class="flag-phrase">"${esc(f.phrase)}"</span> <span class="flag-count">×${f.count}</span></div>`).join('');
  if ((naturalness.repetition_flags || []).length) flexDetails += `<h4>Repetition</h4>` + naturalness.repetition_flags.map(f => `<div class="flag-item"><span class="flag-phrase">"${esc(f.phrase)}"</span> <span class="flag-count">×${f.count}</span></div>`).join('');
  document.getElementById('naturalness-details').innerHTML = flexDetails || '<p style="color:var(--brand-green);">✅ Clean. No AI clichés or repetition patterns detected.</p>';

  // Old SEO Scores Dashboard
  const scores = [
    { label: 'Overall SEO', value: scoreData.total_score || 0, max: 100, color: scoreColor(scoreData.total_score || 0) },
    { label: 'Readability', value: readability.flesch_score || 0, max: 100, color: readabilityColor(readability.flesch_score || 0) },
    { label: 'Naturalness', value: naturalness.score || 0, max: 100, color: scoreColor(naturalness.score || 0) }
  ];

  document.getElementById('seo-scores').innerHTML = scores.map(s => {
    const c = 2 * Math.PI * 36;
    return `
      <div class="score-card">
        <div class="score-ring">
          <svg viewBox="0 0 80 80">
            <circle class="bg" cx="40" cy="40" r="36" fill="none" stroke-width="6"/>
            <circle class="fill" cx="40" cy="40" r="36" fill="none" stroke-width="6" stroke="${s.color}" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c - (s.value/s.max)*c}"/>
          </svg>
          <div class="score-value" style="color:${s.color}">${s.value}</div>
        </div>
        <div class="score-card-label">${s.label}</div>
      </div>`;
  }).join('');

  const breakdown = scoreData.breakdown || {};
  document.getElementById('seo-breakdown').innerHTML = Object.entries(breakdown).map(([key, cat]) => {
    const pct = Math.round((cat.score / cat.max) * 100);
    const col = scoreColor(pct);
    return `
      <div class="breakdown-item">
        <div class="breakdown-header"><span>${formatKey(key)}</span><span style="color:${col}">${cat.score}/${cat.max}</span></div>
        <div class="breakdown-bar"><div class="breakdown-fill" style="width:${pct}%;background:${col}"></div></div>
        <ul class="breakdown-details">${(cat.details || []).map(d => `<li>${esc(d)}</li>`).join('')}</ul>
      </div>`;
  }).join('');
}

function renderSERPGaps(r) {
  const serp = r.serp_analysis || {};
  document.getElementById('gap-summary').textContent = serp.gap_report_summary || '';
  document.getElementById('gap-grid').innerHTML = (serp.content_gaps || []).map(g => {
    const sev = (g.severity || 'medium').toLowerCase();
    return `
      <div class="gap-card severity-${sev}">
        <div class="gap-title">${esc(g.gap || '')}</div>
        <div class="gap-type">${esc(g.gap_type || sev)} • ${sev} severity</div>
        <div class="gap-opportunity">${esc(g.opportunity || '')}</div>
      </div>`;
  }).join('');
}

function renderLinks(r) {
  const links = (r.internal_links || {}).suggestions || [];
  document.getElementById('links-list').innerHTML = links.length ? links.map(l => `
    <div class="link-suggestion">
      <div class="link-anchor">${esc(l.anchor_text || '')}</div>
      <div class="link-url">→ ${esc(l.url || '')} (${esc(l.page_title || '')})</div>
      <div class="link-reason">${esc(l.reasoning || '')}</div>
      <div class="link-badge">${esc(l.placement_type || 'reference')}</div>
    </div>`).join('') : '<p class="empty-state-text">No linking suggestions generated.</p>';
}

function renderStrategy(r) {
  const justify = r.strategy_justification || {};
  document.getElementById('rank-reasons').innerHTML = (justify.why_this_can_rank || []).map(s => `<li>${esc(s)}</li>`).join('');
  document.getElementById('competitive-advantages').innerHTML = (justify.competitive_advantages || []).map(s => `<li>${esc(s)}</li>`).join('');

  let outlineHtml = '';
  ((r.content_strategy || {}).outline || []).forEach(item => {
    const cls = item.level.toLowerCase();
    outlineHtml += `<div class="outline-node ${cls}">
      <div class="outline-node-content"><strong>${esc(item.level)}</strong> ${esc(item.heading || '')}</div>
      <div>${(item.target_keywords||[]).map(k => `<span class="outline-tag">${esc(k)}</span>`).join('')}
      ${item.geo_format && item.geo_format !== 'paragraph' ? `<span class="outline-tag" style="color:var(--brand-green);border-color:var(--brand-green)">geo: ${esc(item.geo_format)}</span>` : ''}</div>
    </div>`;
  });
  document.getElementById('outline-map').innerHTML = outlineHtml;

  const timing = r.pipeline_timing || {};
  document.getElementById('timing-breakdown').innerHTML = `<div style="font-size:2rem;color:var(--brand-cyan);font-weight:700;font-family:var(--font-mono);margin-bottom:1rem">${(timing.total||0).toFixed(1)}s total build time</div>` + 
    Object.entries(timing).filter(([k]) => k!=='total').map(([k,v]) => `<div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid var(--border-subtle);font-size:0.9rem"><span style="color:var(--text-secondary)">${formatKey(k)}</span><span style="font-family:var(--font-mono)">${v.toFixed(1)}s</span></div>`).join('');
}

function renderSnippet(r) {
  const snip = (r.seo_analysis || {}).snippet_readiness || {};
  document.getElementById('snippet-score-area').innerHTML = `<div style="font-size:3rem;font-weight:800;color:${scoreColor(snip.score||0)}">${snip.score||0}%</div><div style="color:var(--text-secondary)">${snip.elements_present||0} of 5 Elements</div>`;
  const checks = [
    { L: 'Clear Definitions', P: snip.has_definitions }, { L: 'Bullet/Number Lists', P: snip.has_lists },
    { L: 'Comparison Tables', P: snip.has_tables }, { L: 'Q&A Headers', P: snip.has_qa }, { L: 'Structured H2/H3', P: snip.has_headings }
  ];
  document.getElementById('snippet-checklist').innerHTML = checks.map(c => `<li class="checklist-item"><div class="check-icon ${c.P?'pass':'fail'}">${c.P?'✓':'✗'}</div><span class="check-label">${c.L}</span></li>`).join('');
}

// ── Dashboard Overview Data ──────────────────────────────────────────────
function updateDashboardStats() {
  const history = JSON.parse(localStorage.getItem('blogy_history') || '[]');
  document.getElementById('dash-total-gen').textContent = history.length;
  
  if (history.length) {
    const avgSeo = Math.round(history.reduce((acc, h) => acc + h.seo_score, 0) / history.length);
    document.getElementById('dash-avg-seo').textContent = avgSeo;
    const totWords = history.reduce((acc, h) => acc + h.word_count, 0);
    // abbreviate
    document.getElementById('dash-total-words').textContent = totWords > 1000 ? (totWords/1000).toFixed(1) + 'k' : totWords;
  }
}

// ── Export / History / Utils ─────────────────────────────────────────────
function copyMarkdown() {
  if (currentResult) {
    navigator.clipboard.writeText(currentResult.blog_content.full_markdown || '');
    showToast('Markdown Copied!');
  }
}

function copyHTML() {
  if (currentResult) {
    navigator.clipboard.writeText(document.getElementById('blog-rendered').innerHTML);
    showToast('HTML Copied!');
  }
}

function downloadMD() {
  if (currentResult) {
    const md = currentResult.blog_content.full_markdown;
    const kw = (currentResult.keyword||'blog').replace(/\s+/g, '-');
    const b = new Blob([md], {type: 'text/markdown'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(b); a.download = `${kw}.md`; a.click();
    showToast(`Downloaded ${kw}.md`);
  }
}

function toggleHistory() {
  document.getElementById('history-drawer').classList.toggle('open');
  document.getElementById('history-overlay').classList.toggle('open');
}

function saveHistory(res) {
  const h = JSON.parse(localStorage.getItem('blogy_history') || '[]');
  h.unshift({ keyword: res.keyword, seo_score: res.seo_analysis?.seo_score?.total_score||0, word_count: res.blog_content?.total_word_count||0, timing: res.pipeline_timing?.total||0, timestamp: Date.now() });
  if (h.length > 20) h.length = 20;
  localStorage.setItem('blogy_history', JSON.stringify(h));
  renderHistory(h);
}

function loadHistory() {
  const h = JSON.parse(localStorage.getItem('blogy_history') || '[]');
  renderHistory(h);
  updateDashboardStats();
}

function renderHistory(h) {
  const b = document.getElementById('history-badge');
  if(b) { b.textContent = h.length; b.style.display = h.length ? 'block' : 'none'; }
  
  const html = h.length ? h.map(i => `
    <div class="history-item" onclick="document.getElementById('keyword-input').value='${escAttr(i.keyword)}'; switchView('blog-generation'); document.getElementById('sidebar').classList.remove('open'); toggleHistory();">
      <div class="history-keyword">${esc(i.keyword)}</div>
      <div class="history-meta"><span>🏆 ${i.seo_score}/100</span><span>📝 ${i.word_count} words</span></div>
    </div>`).join('') : '<p class="empty-state-text">No generations yet.</p>';
    
  // update sidebar drawer
  const hd = document.getElementById('history-list');
  if(hd) hd.innerHTML = html;
  
  // update dashboard preview map
  const dh = document.getElementById('dashboard-history');
  if(dh) dh.innerHTML = html.replace(/history-item/g, 'history-item dash-variant');
}

function fetchProviderStatus() {
  fetch('/api/providers/health').then(r=>r.json()).then(d => {
    const act = d.active || [];
    const pro = d.providers || [];
    const dot = document.querySelector('.provider-dot');
    const txt = document.querySelector('.provider-text');
    
    if (document.getElementById('dash-providers')) {
      document.getElementById('dash-providers').textContent = act.length;
    }

    if (!act.length) { dot.className = 'provider-dot offline'; txt.textContent = 'Offline'; return; }
    
    const un = pro.filter(p => !p.healthy).length;
    dot.className = un ? 'provider-dot warning' : 'provider-dot online';
    txt.textContent = act.length + ' Active';
    
    // Settings tab sync
    const st = document.getElementById('settings-provider-health');
    if (st) {
      st.innerHTML = pro.map(p => `
        <div class="provider-health-item">
          <div><span class="ph-name">${p.name.toUpperCase()}</span> <span class="ph-status ${p.healthy?'healthy':'sick'}">${p.healthy?'ONLINE':'ERROR'}</span></div>
          <div class="ph-metrics">Reqs: ${p.requests_handled} | Fails: ${p.errors_encountered} | Avg: ${p.avg_response_time_ms}ms</div>
        </div>`).join('');
    }
  }).catch(() => {});
}

function showToast(m) {
  const t = document.getElementById('toast');
  t.textContent = m; t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), 3000);
}

// Helpers
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function escAttr(s) { return esc(s).replace(/'/g,'&#39;').replace(/"/g,'&quot;'); }
function formatKey(k) { return k.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase()); }
function scoreColor(v) { return v>=80 ? '#10b981' : (v>=60 ? '#f59e0b' : '#ef4444'); }
function readabilityColor(v) { return v>=60 ? '#10b981' : (v>=40 ? '#f59e0b' : '#ef4444'); }
function densityColor(d) { return (d>=1.0 && d<=2.5) ? '#10b981' : ((d>=0.5 && d<=3.5) ? '#f59e0b' : '#ef4444'); }
