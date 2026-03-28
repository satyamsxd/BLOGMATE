/**
 * Blogy — Frontend Application
 * Real SSE streaming, export, history, particles, animated counters.
 */

// ── State ────────────────────────────────────────────────────────────────
let currentResult = null;
let pipelineStartTime = null;
let pipelineTimerInterval = null;

// ── Init ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  fetchProviderStatus();
  loadHistory();
});

// ── Tab Management ───────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(`panel-${tabId}`).classList.add('active');
}

// ── Pipeline Progress ────────────────────────────────────────────────────
function showProgress() {
  document.getElementById('pipeline-progress').classList.add('active');
  document.getElementById('output-section').classList.remove('visible');
  document.getElementById('error-banner').classList.remove('visible');
  document.querySelectorAll('.stage-item').forEach(s => {
    s.classList.remove('active', 'done');
    const num = s.dataset.stage;
    s.querySelector('.stage-num').textContent = num;
  });
  document.querySelectorAll('.stage-time').forEach(t => t.textContent = '');
  document.querySelectorAll('.stage-connector').forEach(c => {
    c.style.background = 'var(--border-subtle)';
  });

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
    if (timeEl && duration) {
      timeEl.textContent = duration.toFixed(1) + 's';
    }
  }
  // Animate the connector after this stage
  const connectors = document.querySelectorAll('.stage-connector');
  if (stageNum - 1 < connectors.length) {
    connectors[stageNum - 1].style.background = 'var(--accent-green)';
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
    input.style.borderColor = 'var(--accent-red)';
    setTimeout(() => input.style.borderColor = '', 1000);
    return;
  }

  btn.disabled = true;
  btn.querySelector('.btn-text').innerHTML = '<span class="spinner"></span> Generating...';
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
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            handleSSEEvent(event);
          } catch (e) {
            // skip unparseable
          }
        }
      }
    }

    // Process any remaining buffer
    if (buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6));
        handleSSEEvent(event);
      } catch (e) {
        // skip
      }
    }

  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -3px; margin-right: 6px;">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
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
      document.getElementById('output-section').classList.add('visible');
      saveHistory(currentResult);
      fetchProviderStatus();
    }, 400);

  } else if (event.type === 'error') {
    showError(event.error);
  }
}

// ── Enter key support ────────────────────────────────────────────────────
document.getElementById('keyword-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') startGeneration();
});

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

// ── Render: Meta Bar ─────────────────────────────────────────────────────
function renderMetaBar(r) {
  const timing = r.pipeline_timing || {};
  document.getElementById('total-time').textContent = (timing.total || 0).toFixed(1) + 's total';
  document.getElementById('total-words').textContent = (r.blog_content || {}).total_word_count + ' words';

  // Get active providers
  fetch('/api/providers/active')
    .then(res => res.json())
    .then(data => {
      document.getElementById('provider-used').textContent = (data.active || []).join(' → ') || 'unknown';
    })
    .catch(() => {
      document.getElementById('provider-used').textContent = 'multi-provider';
    });
}

// ── Render: Blog ─────────────────────────────────────────────────────────
function renderBlog(r) {
  const blog = r.blog_content || {};
  const strategy = r.content_strategy || {};
  const md = blog.full_markdown || '';

  document.getElementById('blog-meta-preview').innerHTML = `
    <div class="meta-preview">
      <div class="meta-title">${esc(strategy.seo_title || '')}</div>
      <div class="meta-url">yourdomain.com › blog › ${esc(r.keyword || '')}</div>
      <div class="meta-desc">${esc(strategy.meta_description || '')}</div>
    </div>`;

  const wc = blog.total_word_count || 0;
  const sc = (blog.sections || []).length;
  document.getElementById('blog-stats-bar').innerHTML = `
    <div class="blog-stats">
      <span>📝 <span class="stat-value">${wc}</span> words</span>
      <span>📑 <span class="stat-value">${sc}</span> sections</span>
      <span>⏱️ <span class="stat-value">${Math.ceil(wc / 230)}</span> min read</span>
    </div>`;

  document.getElementById('blog-rendered').innerHTML = marked.parse(md);
}

// ── Render: SEO ──────────────────────────────────────────────────────────
function renderSEO(r) {
  const seo = r.seo_analysis || {};
  const scoreData = seo.seo_score || {};
  const readability = seo.readability || {};
  const naturalness = seo.naturalness || {};
  const density = seo.keyword_density || {};

  const scores = [
    { label: 'SEO Score', value: scoreData.total_score || 0, max: 100, color: scoreColor(scoreData.total_score || 0) },
    { label: 'Readability', value: readability.flesch_score || 0, max: 100, color: readabilityColor(readability.flesch_score || 0) },
    { label: 'Naturalness', value: naturalness.score || 0, max: 100, color: scoreColor(naturalness.score || 0) },
    { label: 'Snippet Ready', value: (seo.snippet_readiness || {}).score || 0, max: 100, color: scoreColor((seo.snippet_readiness || {}).score || 0) },
  ];

  document.getElementById('seo-scores').innerHTML = scores.map(s => {
    const circumference = 2 * Math.PI * 42;
    return `
      <div class="score-card">
        <div class="score-ring">
          <svg viewBox="0 0 100 100">
            <circle class="bg" cx="50" cy="50" r="42" fill="none" stroke-width="5"/>
            <circle class="fill" cx="50" cy="50" r="42" fill="none" stroke-width="5"
              stroke="${s.color}" stroke-linecap="round"
              stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"
              data-target-offset="${circumference - (s.value / s.max) * circumference}"/>
          </svg>
          <div class="score-value" style="color:${s.color}" data-target="${s.value}">0</div>
        </div>
        <div class="score-label">${s.label}</div>
      </div>`;
  }).join('');

  // Animate score rings after render
  requestAnimationFrame(() => {
    setTimeout(() => {
      document.querySelectorAll('.score-ring .fill').forEach(circle => {
        circle.style.strokeDashoffset = circle.dataset.targetOffset;
      });
      document.querySelectorAll('.score-ring .score-value').forEach(el => {
        animateCounter(el, 0, parseInt(el.dataset.target), 1400);
      });
    }, 100);
  });

  // SEO Breakdown
  const breakdown = scoreData.breakdown || {};
  document.getElementById('seo-breakdown').innerHTML = Object.entries(breakdown).map(([key, cat]) => {
    const pct = Math.round((cat.score / cat.max) * 100);
    const color = scoreColor(pct);
    return `
      <div class="breakdown-item">
        <div class="breakdown-header">
          <span class="breakdown-name">${formatKey(key)}</span>
          <span class="breakdown-score" style="color:${color}">${cat.score}/${cat.max}</span>
        </div>
        <div class="breakdown-bar">
          <div class="breakdown-fill" style="width:${pct}%;background:${color}"></div>
        </div>
        <ul class="breakdown-details">
          ${(cat.details || []).map(d => `<li>${esc(d)}</li>`).join('')}
        </ul>
      </div>`;
  }).join('');

  // Readability
  document.getElementById('readability-info').innerHTML = `
    <div class="score-dashboard" style="margin-bottom:0">
      <div class="score-card">
        <div style="font-size:2.2rem;font-weight:800;color:${scoreColor(readability.flesch_score || 0)};margin-bottom:0.4rem">${readability.flesch_score || 0}</div>
        <div class="score-label">Flesch Score — ${readability.flesch_grade || 'N/A'}</div>
      </div>
      <div class="score-card">
        <div style="font-size:2.2rem;font-weight:800;color:var(--accent-cyan);margin-bottom:0.4rem">${readability.avg_sentence_length || 0}</div>
        <div class="score-label">Avg Sentence Length</div>
      </div>
      <div class="score-card">
        <div style="font-size:2.2rem;font-weight:800;color:var(--accent-purple);margin-bottom:0.4rem">${readability.total_words || 0}</div>
        <div class="score-label">Total Words</div>
      </div>
      <div class="score-card">
        <div style="font-size:2.2rem;font-weight:800;color:var(--accent-amber);margin-bottom:0.4rem">${readability.total_sentences || 0}</div>
        <div class="score-label">Total Sentences</div>
      </div>
    </div>`;

  // Keyword Density
  let densityHtml = `
    <table class="density-table">
      <thead><tr><th>Keyword</th><th>Density</th><th>Visual</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>${esc(density.primary_keyword || '')}</strong> (primary)</td>
          <td>${density.primary_density || 0}%</td>
          <td><div class="density-bar-container"><div class="density-bar" style="width:${Math.min((density.primary_density || 0) * 30, 100)}%;background:${densityColor(density.primary_density || 0)}"></div></div></td>
        </tr>`;
  Object.entries(density.secondary_keywords || {}).forEach(([kw, d]) => {
    densityHtml += `
        <tr>
          <td>${esc(kw)}</td>
          <td>${d}%</td>
          <td><div class="density-bar-container"><div class="density-bar" style="width:${Math.min(d * 30, 100)}%;background:${densityColor(d)}"></div></div></td>
        </tr>`;
  });
  densityHtml += '</tbody></table>';
  (density.warnings || []).forEach(w => {
    densityHtml += `<div class="density-warning">⚠️ ${esc(w)}</div>`;
  });
  document.getElementById('keyword-density').innerHTML = densityHtml;

  // Naturalness
  let natHtml = `
    <div style="font-size:1.4rem;font-weight:800;color:${scoreColor(naturalness.score || 0)};margin-bottom:0.2rem">${naturalness.score || 0}/100</div>
    <p style="color:var(--text-secondary);margin-bottom:1rem;font-size:0.88rem">${esc(naturalness.assessment || '')}</p>`;

  // Writing quality signals
  const signals = naturalness.signals || {};
  if (Object.keys(signals).length > 0) {
    natHtml += `<div class="naturalness-section"><h4>📊 Writing Quality Signals</h4>
      <div class="score-dashboard" style="margin-bottom:0.5rem">`;
    const signalEntries = [
      { key: 'sentence_variance', label: 'Sentence Variety', icon: '📏' },
      { key: 'vocabulary_diversity', label: 'Vocabulary Richness', icon: '📚' },
      { key: 'opener_variety', label: 'Opener Variety', icon: '🔤' },
      { key: 'passive_voice', label: 'Active Voice', icon: '💬' },
      { key: 'paragraph_quality', label: 'Paragraph Flow', icon: '¶' },
    ];
    for (const s of signalEntries) {
      const sig = signals[s.key] || {};
      const sigScore = sig.score || 0;
      natHtml += `
        <div class="score-card" style="padding:0.85rem">
          <div style="font-size:1.5rem;font-weight:800;color:${scoreColor(sigScore)};margin-bottom:0.25rem">${sigScore}</div>
          <div class="score-label" style="font-size:0.7rem">${s.icon} ${s.label}</div>
          <div style="font-size:0.65rem;color:var(--text-dim);margin-top:0.3rem">${esc(sig.detail || '')}</div>
        </div>`;
    }
    natHtml += `</div></div>`;
  }

  if ((naturalness.ai_cliche_phrases || []).length > 0) {
    natHtml += `<div class="naturalness-section"><h4>🚩 AI Cliché Phrases Detected</h4>`;
    natHtml += (naturalness.ai_cliche_phrases || []).map(f => `
      <div class="flag-item"><span class="flag-phrase">"${esc(f.phrase)}"</span><span class="flag-count">×${f.count}</span></div>`).join('');
    natHtml += '</div>';
  }
  if ((naturalness.repetition_flags || []).length > 0) {
    natHtml += `<div class="naturalness-section"><h4>🔁 Repetitive Patterns</h4>`;
    natHtml += (naturalness.repetition_flags || []).map(f => `
      <div class="flag-item"><span class="flag-phrase">"${esc(f.phrase)}"</span><span class="flag-count">×${f.count}</span></div>`).join('');
    natHtml += '</div>';
  }
  if ((naturalness.transition_overuse || []).length > 0) {
    natHtml += `<div class="naturalness-section"><h4>🔄 Overused Transitions</h4>`;
    natHtml += (naturalness.transition_overuse || []).map(f => `
      <div class="flag-item"><span class="flag-phrase">"${esc(f.word)}"</span><span class="flag-count">×${f.count}</span></div>`).join('');
    natHtml += '</div>';
  }
  if (!(naturalness.ai_cliche_phrases || []).length && !(naturalness.repetition_flags || []).length && !(naturalness.transition_overuse || []).length) {
    natHtml += '<p style="color:var(--accent-green)">✅ No AI clichés or repetitive patterns detected.</p>';
  }
  document.getElementById('naturalness-info').innerHTML = natHtml;
}

// ── Render: SERP Gaps ────────────────────────────────────────────────────
function renderSERPGaps(r) {
  const serp = r.serp_analysis || {};
  const gaps = serp.content_gaps || [];

  document.getElementById('gap-summary').textContent = serp.gap_report_summary || '';

  document.getElementById('gap-grid').innerHTML = gaps.map(g => {
    const severity = (g.severity || 'medium').toLowerCase();
    return `
      <div class="gap-card severity-${severity}">
        <div class="gap-title">${esc(g.gap || '')}</div>
        <span class="gap-type">${esc(g.gap_type || severity)} — ${severity} severity</span>
        <div class="gap-opportunity">${esc(g.opportunity || '')}</div>
      </div>`;
  }).join('');
}

// ── Render: Internal Links ───────────────────────────────────────────────
function renderLinks(r) {
  const links = (r.internal_links || {}).suggestions || [];

  document.getElementById('links-list').innerHTML = links.length === 0
    ? '<p class="empty-state">No internal linking suggestions generated.</p>'
    : links.map(l => `
      <div class="link-suggestion">
        <div class="link-anchor">"${esc(l.anchor_text || '')}"</div>
        <div class="link-url">→ ${esc(l.url || '')} (${esc(l.page_title || '')})</div>
        <div class="link-reason">${esc(l.reasoning || '')}</div>
        <span class="link-badge">${esc(l.placement_type || 'reference')}</span>
      </div>`).join('');
}

// ── Render: Snippet Readiness ────────────────────────────────────────────
function renderSnippet(r) {
  const snippet = (r.seo_analysis || {}).snippet_readiness || {};

  document.getElementById('snippet-score-area').innerHTML = `
    <div style="text-align:center;margin-bottom:1.25rem">
      <div style="font-size:2.5rem;font-weight:800;color:${scoreColor(snippet.score || 0)}">${snippet.score || 0}%</div>
      <div style="color:var(--text-secondary);font-size:0.85rem">${snippet.elements_present || 0} of ${snippet.elements_total || 5} snippet elements present</div>
    </div>`;

  const checks = [
    { label: 'Clear Definitions (extractable by AI)', pass: snippet.has_definitions },
    { label: 'Bullet / Numbered Lists', pass: snippet.has_lists },
    { label: 'Comparison Tables', pass: snippet.has_tables },
    { label: 'Q&A / FAQ Sections', pass: snippet.has_qa },
    { label: 'Structured Headings (H1/H2/H3)', pass: snippet.has_headings },
  ];

  document.getElementById('snippet-checklist').innerHTML = checks.map(c => `
    <li class="checklist-item">
      <span class="check-icon ${c.pass ? 'pass' : 'fail'}">${c.pass ? '✓' : '✗'}</span>
      <span class="check-label">${c.label}</span>
    </li>`).join('');
}

// ── Render: Strategy ─────────────────────────────────────────────────────
function renderStrategy(r) {
  const justification = r.strategy_justification || {};

  document.getElementById('rank-reasons').innerHTML =
    (justification.why_this_can_rank || []).map(s => `<li>${esc(s)}</li>`).join('');

  document.getElementById('competitive-advantages').innerHTML =
    (justification.competitive_advantages || []).map(s => `<li>${esc(s)}</li>`).join('');

  // Outline map
  const outline = (r.content_strategy || {}).outline || [];
  let outlineHtml = '<div style="font-size:0.88rem">';
  outline.forEach(item => {
    const indent = item.level === 'H1' ? 0 : item.level === 'H2' ? 1 : 2;
    const kws = item.target_keywords || [];
    const borderColors = ['var(--accent-cyan)', 'var(--accent-blue)', 'var(--accent-purple)'];
    outlineHtml += `
      <div style="padding:0.55rem 0.75rem;margin-left:${indent * 1.5}rem;margin-bottom:0.3rem;background:var(--bg-glass);border-radius:var(--radius-sm);border-left:3px solid ${borderColors[indent]}">
        <strong style="color:var(--text-primary)">${esc(item.level)}</strong> ${esc(item.heading || '')}
        ${kws.length ? `<div style="margin-top:0.25rem">${kws.map(k => `<span style="display:inline-block;font-size:0.68rem;padding:0.08rem 0.45rem;margin:0.08rem;background:rgba(99,102,241,0.12);color:var(--accent-blue);border-radius:3px">${esc(k)}</span>`).join('')}</div>` : ''}
        ${item.geo_format && item.geo_format !== 'paragraph' ? `<span style="display:inline-block;font-size:0.62rem;padding:0.08rem 0.35rem;margin-top:0.25rem;background:rgba(52,211,153,0.12);color:var(--accent-green);border-radius:3px">GEO: ${esc(item.geo_format)}</span>` : ''}
      </div>`;
  });
  outlineHtml += '</div>';
  document.getElementById('outline-map').innerHTML = outlineHtml;

  // Timing breakdown
  const timing = r.pipeline_timing || {};
  const timingEntries = Object.entries(timing).filter(([k]) => k !== 'total');
  let timingHtml = `
    <div style="text-align:center;margin-bottom:1rem">
      <div style="font-size:2rem;font-weight:800;color:var(--accent-cyan);font-family:var(--font-mono)">${(timing.total || 0).toFixed(1)}s</div>
      <div style="font-size:0.8rem;color:var(--text-muted)">Total Pipeline Time</div>
    </div>
    <div class="timing-grid">`;
  timingEntries.forEach(([key, val]) => {
    timingHtml += `
      <div class="timing-item">
        <div class="timing-value">${val.toFixed(1)}s</div>
        <div class="timing-label">${formatKey(key)}</div>
      </div>`;
  });
  timingHtml += '</div>';
  document.getElementById('timing-breakdown').innerHTML = timingHtml;
}

// ── Export Functions ──────────────────────────────────────────────────────
function copyMarkdown() {
  if (!currentResult) return;
  const md = (currentResult.blog_content || {}).full_markdown || '';
  navigator.clipboard.writeText(md).then(() => showToast('✓ Markdown copied to clipboard'));
}

function copyHTML() {
  if (!currentResult) return;
  const html = document.getElementById('blog-rendered').innerHTML;
  navigator.clipboard.writeText(html).then(() => showToast('✓ HTML copied to clipboard'));
}

function downloadMD() {
  if (!currentResult) return;
  const md = (currentResult.blog_content || {}).full_markdown || '';
  const keyword = (currentResult.keyword || 'blog').replace(/\s+/g, '-').toLowerCase();
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${keyword}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('✓ Downloaded ' + keyword + '.md');
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), 2500);
}

// ── History ──────────────────────────────────────────────────────────────
function toggleHistory() {
  document.getElementById('history-drawer').classList.toggle('open');
  document.getElementById('history-overlay').classList.toggle('open');
}

function saveHistory(result) {
  const history = JSON.parse(localStorage.getItem('blogy_history') || '[]');
  history.unshift({
    keyword: result.keyword,
    seo_score: (result.seo_analysis || {}).seo_score?.total_score || 0,
    word_count: (result.blog_content || {}).total_word_count || 0,
    timing: (result.pipeline_timing || {}).total || 0,
    timestamp: Date.now(),
  });
  // Keep last 20
  if (history.length > 20) history.length = 20;
  localStorage.setItem('blogy_history', JSON.stringify(history));
  renderHistory(history);
}

function loadHistory() {
  const history = JSON.parse(localStorage.getItem('blogy_history') || '[]');
  renderHistory(history);
}

function renderHistory(history) {
  const badge = document.getElementById('history-badge');
  if (history.length > 0) {
    badge.textContent = history.length;
    badge.classList.add('visible');
  } else {
    badge.classList.remove('visible');
  }

  const listEl = document.getElementById('history-list');
  if (history.length === 0) {
    listEl.innerHTML = '<p class="empty-state">No generations yet. Enter a keyword to get started.</p>';
    return;
  }

  listEl.innerHTML = history.map(h => {
    const timeAgo = getTimeAgo(h.timestamp);
    return `
      <div class="history-item" onclick="document.getElementById('keyword-input').value='${escAttr(h.keyword)}'; toggleHistory();">
        <div class="history-keyword">${esc(h.keyword)}</div>
        <div class="history-meta">
          <span>📊 ${h.seo_score}/100</span>
          <span>📝 ${h.word_count} words</span>
          <span>⏱️ ${(h.timing || 0).toFixed(1)}s</span>
          <span>🕐 ${timeAgo}</span>
        </div>
      </div>`;
  }).join('');
}

function getTimeAgo(ts) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  return days + 'd ago';
}

// ── Provider Status ──────────────────────────────────────────────────────
function fetchProviderStatus() {
  fetch('/api/providers/health')
    .then(res => res.json())
    .then(data => {
      const active = data.active || [];
      const providers = data.providers || [];
      const dot = document.querySelector('.provider-dot');
      const text = document.querySelector('.provider-text');

      const hasOllama = active.includes('ollama');

      if (active.length === 0) {
        dot.className = 'provider-dot offline';
        text.textContent = 'No providers';
      } else {
        const unhealthy = providers.filter(p => !p.healthy).length;
        const rateLimited = providers.filter(p => p.rate_limited).length;
        if (unhealthy > 0 || rateLimited > 0) {
          dot.className = 'provider-dot warning';
        } else {
          dot.className = 'provider-dot online';
        }
        if (hasOllama) {
          text.textContent = '∞ Ollama + ' + (active.length - 1) + ' cloud';
        } else {
          text.textContent = active.length + ' provider' + (active.length > 1 ? 's' : '') + ' active';
        }
      }

      // Show Ollama setup banner if not using local AI
      const existingBanner = document.getElementById('ollama-banner');
      if (!hasOllama && !existingBanner) {
        const banner = document.createElement('div');
        banner.id = 'ollama-banner';
        banner.style.cssText = `
          background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(6,182,212,0.08));
          border: 1px solid rgba(99,102,241,0.2);
          border-radius: 12px;
          padding: 0.85rem 1.25rem;
          margin-bottom: 1rem;
          font-size: 0.82rem;
          color: var(--text-secondary);
          display: flex;
          align-items: center;
          gap: 0.75rem;
          cursor: pointer;
          transition: all 0.3s ease;
        `;
        banner.innerHTML = `
          <span style="font-size:1.2rem">🦙</span>
          <span><strong style="color:var(--accent-cyan)">Want unlimited blogs?</strong> Install <a href="https://ollama.com/download" target="_blank" style="color:var(--accent-purple);text-decoration:underline">Ollama</a> and run <code style="background:rgba(255,255,255,0.06);padding:0.15rem 0.4rem;border-radius:4px;font-size:0.78rem">ollama pull llama3.1:8b</code> — then restart this app. Zero API limits, runs 100% locally.</span>
          <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:1rem;margin-left:auto">×</button>
        `;
        const container = document.querySelector('.app-container');
        const header = document.querySelector('.app-header');
        if (container && header) {
          header.after(banner);
        }
      } else if (hasOllama && existingBanner) {
        existingBanner.remove();
      }
    })
    .catch(() => {
      document.querySelector('.provider-dot').className = 'provider-dot offline';
      document.querySelector('.provider-text').textContent = 'Offline';
    });
}

// ── Animated Counter ─────────────────────────────────────────────────────
function animateCounter(el, from, to, duration) {
  const start = performance.now();
  function update(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(from + (to - from) * eased);
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

// ── Particle System ──────────────────────────────────────────────────────
function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width, height;
  const particles = [];
  const PARTICLE_COUNT = 50;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  resize();
  window.addEventListener('resize', resize);

  // Create particles
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 0.5,
      alpha: Math.random() * 0.3 + 0.05,
      color: Math.random() > 0.5
        ? `rgba(99, 102, 241, ${Math.random() * 0.3 + 0.05})`
        : `rgba(56, 189, 248, ${Math.random() * 0.3 + 0.05})`,
    });
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);

    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.fill();
    });

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 150) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(99, 102, 241, ${0.03 * (1 - dist / 150)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(animate);
  }

  animate();
}

// ── Helpers ──────────────────────────────────────────────────────────────
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function scoreColor(v) {
  if (v >= 80) return '#34d399';
  if (v >= 60) return '#fbbf24';
  if (v >= 40) return '#fb923c';
  return '#f87171';
}

function readabilityColor(v) {
  // Flesch Reading Ease: 60+ is good for blogs, 40-60 is moderate
  if (v >= 60) return '#34d399';
  if (v >= 40) return '#fbbf24';
  if (v >= 25) return '#fb923c';
  return '#f87171';
}

function escAttr(s) {
  // Escape for use inside HTML attribute single-quoted strings
  return esc(s).replace(/'/g, '&#39;').replace(/\\/g, '&#92;');
}

function densityColor(d) {
  if (d >= 1.0 && d <= 2.0) return '#34d399';
  if (d >= 0.5 && d <= 2.5) return '#fbbf24';
  return '#f87171';
}

function formatKey(k) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}
