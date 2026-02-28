(function () {
  const API_BASE = '';
  let token = localStorage.getItem('openopt_token');
  let chartInstance = null;
  let autoChartInstances = [];

  function headers() {
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  function show(el) {
    if (el) el.classList.remove('hidden');
  }
  function hide(el) {
    if (el) el.classList.add('hidden');
  }
  function formatCurrency(amount, fractionDigits) {
    return '$' + Number(amount || 0).toLocaleString(undefined, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    });
  }

  function showLogin() {
    show(document.getElementById('login-section'));
    hide(document.getElementById('dashboard-section'));
    document.getElementById('auth-actions').innerHTML = '';
  }

  function showDashboard() {
    hide(document.getElementById('login-section'));
    show(document.getElementById('dashboard-section'));
    document.getElementById('auth-actions').innerHTML = '<button type="button" id="logout-btn" class="btn btn-ghost">Sign out</button>';
    document.getElementById('logout-btn').addEventListener('click', logout);
    loadDashboard();
  }

  function logout() {
    token = null;
    localStorage.removeItem('openopt_token');
    showLogin();
  }

  document.getElementById('login-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    try {
      const r = await fetch(API_BASE + '/api/auth/login', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ email, password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        errEl.textContent = data.detail || 'Login failed';
        return;
      }
      token = data.access_token;
      localStorage.setItem('openopt_token', token);
      showDashboard();
    } catch (err) {
      errEl.textContent = err.message || 'Network error';
    }
  });

  async function loadDashboard() {
    try {
      const [householdsRes, accountsRes, goalsRes] = await Promise.all([
        fetch(API_BASE + '/api/households', { headers: headers() }),
        fetch(API_BASE + '/api/accounts', { headers: headers() }),
        fetch(API_BASE + '/api/goals', { headers: headers() }),
      ]);

      const households = householdsRes.ok ? await householdsRes.json() : [];
      const accounts = accountsRes.ok ? await accountsRes.json() : [];
      const goals = goalsRes.ok ? await goalsRes.json() : [];

      // Fetch members for each household so we show the full family
      const householdsWithMembers = await Promise.all(
        households.map(async function (h) {
          const membersRes = await fetch(API_BASE + '/api/households/' + h.id + '/members', { headers: headers() });
          const members = membersRes.ok ? await membersRes.json() : [];
          return { household: h, members: members };
        })
      );

      const list = (arr, fmt) => arr.map(fmt).join('');
      document.getElementById('household-list').innerHTML = list(householdsWithMembers, function (x) {
        const h = x.household;
        const members = x.members || [];
        const parents = members.filter(function (m) { return m.role === 'parent'; }).length;
        const children = members.filter(function (m) { return m.role === 'child'; }).length;
        const parts = [];
        if (parents) parts.push(parents + ' parent' + (parents > 1 ? 's' : ''));
        if (children) parts.push(children + ' child' + (children > 1 ? 'ren' : ''));
        const familyLabel = parts.length ? ' — ' + parts.join(', ') : '';
        return '<li><strong>' + escapeHtml(h.name) + '</strong>' + familyLabel + '</li>';
      }) || '<li class="muted">No households</li>';

      const totalCents = accounts.reduce(function (sum, a) { return sum + (a.balance_cents || 0); }, 0);
      const totalDollars = totalCents / 100;
      var heroEl = document.getElementById('hero-total');
      if (heroEl) heroEl.textContent = formatCurrency(totalDollars, 2);
      document.getElementById('account-summary').textContent =
        accounts.length + ' account' + (accounts.length !== 1 ? 's' : '') + ' across your household(s). Total: ' + formatCurrency(totalDollars, 2);

      // Build one table per household with one column per user (member)
      function memberLabels(members) {
        var sorted = members.slice().sort(function (a, b) {
          if (a.role !== b.role) return a.role === 'parent' ? -1 : 1;
          return (a.user_id || 0) - (b.user_id || 0);
        });
        var p = 0, c = 0;
        return sorted.map(function (m) {
          if (m.role === 'parent') { p++; return { key: 'u' + m.user_id, label: 'Parent ' + p }; }
          c++; return { key: 'u' + m.user_id, label: 'Child ' + c };
        });
      }

      function buildHouseholdTables() {
        var container = document.getElementById('accounts-tables');
        container.innerHTML = '';
        if (accounts.length === 0) {
          container.innerHTML = '<p class="muted">No accounts</p>';
          return;
        }
        householdsWithMembers.forEach(function (x) {
          var h = x.household;
          var members = x.members || [];
          var labels = memberLabels(members);
          var houseAccounts = accounts.filter(function (a) { return a.household_id === h.id; });
          if (houseAccounts.length === 0) return;

          var cols = ['Account', 'Institution'].concat(labels.map(function (l) { return l.label; })).concat(['Household', 'Balance', 'Cumulative']);
          var thead = '<thead><tr>' + cols.map(function (c) { return '<th>' + escapeHtml(c) + '</th>'; }).join('') + '</tr></thead>';
          var cumulativeCents = 0;
          var rows = houseAccounts.map(function (a) {
            var cents = a.balance_cents || 0;
            cumulativeCents += cents;
            var bal = cents / 100;
            var cum = cumulativeCents / 100;
            var ownerId = a.user_id;
            var cells = ['<td>' + escapeHtml(a.name) + '</td>', '<td>' + escapeHtml(a.institution_id) + '</td>'];
            labels.forEach(function (l) {
              var num = (ownerId && l.key === 'u' + ownerId) ? formatCurrency(bal, 2) : '';
              cells.push('<td class="num">' + (num || '–') + '</td>');
            });
            cells.push('<td class="num">' + (!ownerId ? formatCurrency(bal, 2) : '–') + '</td>');
            cells.push('<td class="num">' + formatCurrency(bal, 2) + '</td>');
            cells.push('<td class="num cumulative">' + formatCurrency(cum, 2) + '</td>');
            return '<tr>' + cells.join('') + '</tr>';
          });
          var houseTotal = houseAccounts.reduce(function (s, a) { return s + (a.balance_cents || 0); }, 0);
          var totalColspan = 2 + labels.length + 1;
          var foot = '<tfoot><tr class="total-row"><td colspan="' + totalColspan + '"><strong>Subtotal</strong></td><td class="num" colspan="2"><strong>' + formatCurrency(houseTotal / 100, 2) + '</strong></td></tr></tfoot>';
          var html = '<div class="household-accounts"><h3 class="household-accounts-title">' + escapeHtml(h.name) + '</h3><div class="accounts-table-wrap"><table class="accounts-table">' + thead + '<tbody>' + rows.join('') + '</tbody>' + foot + '</table></div></div>';
          container.insertAdjacentHTML('beforeend', html);
        });
      }
      buildHouseholdTables();

      document.getElementById('goal-list').innerHTML = list(goals, function (g) {
        const amt = g.target_amount_cents / 100;
        return '<li>' + escapeHtml(g.name) + ' – ' + formatCurrency(amt, 0) + '</li>';
      }) || '<li class="muted">No goals</li>';

      loadAutoRecommendations();
    } catch (err) {
      console.error(err);
    }
  }

  function createFillGradient(ctx, topColor, bottomColor) {
    const chart = ctx.chart;
    const area = chart.chartArea;
    if (!area) return bottomColor;
    const gradient = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradient.addColorStop(0, topColor);
    gradient.addColorStop(1, bottomColor);
    return gradient;
  }

  function radiusWithEndMarker(values, radius) {
    return values.map(function (_, i) {
      return i === values.length - 1 ? radius : 0;
    });
  }

  function renderChartMetrics(spec, metricsEl) {
    if (!metricsEl) return;
    var today = typeof spec.today_dollars === 'number' ? spec.today_dollars : (spec.series_current_dollars || [])[0];
    var improved = typeof spec.five_year_recommended_dollars === 'number'
      ? spec.five_year_recommended_dollars
      : (spec.series_recommended_dollars || [])[spec.series_recommended_dollars.length - 1];
    var current = typeof spec.five_year_current_dollars === 'number'
      ? spec.five_year_current_dollars
      : (spec.series_current_dollars || [])[spec.series_current_dollars.length - 1];
    if (typeof today !== 'number' || typeof improved !== 'number' || typeof current !== 'number') {
      metricsEl.innerHTML = '';
      return;
    }
    metricsEl.innerHTML = ''
      + '<div class="chart-metric">'
      + '<span class="chart-metric-label">Today</span>'
      + '<span class="chart-metric-value">$' + today.toLocaleString(undefined, { maximumFractionDigits: 0 }) + '</span>'
      + '</div>'
      + '<div class="chart-metric">'
      + '<span class="chart-metric-label">In 5 years</span>'
      + '<span class="chart-metric-value">$' + improved.toLocaleString(undefined, { maximumFractionDigits: 0 }) + '</span>'
      + '</div>'
      + '<div class="chart-metric">'
      + '<span class="chart-metric-label">Improvement</span>'
      + '<span class="chart-metric-value chart-metric-value-positive">+$' + (improved - current).toLocaleString(undefined, { maximumFractionDigits: 0 }) + '</span>'
      + '</div>';
  }

  function renderChartSpec(spec, chartCanvas, chartNoteEl, metricsEl) {
    if (!spec || !chartCanvas) return null;
    if (chartNoteEl) chartNoteEl.textContent = spec.rates_note || '';
    if (spec.type === 'five_year_projection' && spec.labels && spec.series_current_dollars && spec.series_recommended_dollars) {
      renderChartMetrics(spec, metricsEl);
      var wsPalette = {
        currentLine: '#86a24f',
        currentFillTop: 'rgba(181, 204, 126, 0.45)',
        currentFillBottom: 'rgba(181, 204, 126, 0.12)',
        improvedLine: '#556b2f',
        improvedFillTop: 'rgba(136, 162, 72, 0.42)',
        improvedFillBottom: 'rgba(136, 162, 72, 0.10)',
        axisText: '#4f4c46',
        grid: 'rgba(128, 129, 121, 0.35)',
      };
      return new Chart(chartCanvas.getContext('2d'), {
        plugins: [{
          id: 'chartAreaBackground',
          beforeDraw: function (chart) {
            var ctx = chart.ctx;
            var area = chart.chartArea;
            if (!area) return;
            ctx.save();
            ctx.fillStyle = '#f4f4ef';
            ctx.fillRect(area.left, area.top, area.right - area.left, area.bottom - area.top);
            ctx.restore();
          },
        }],
        type: 'line',
        data: {
          labels: spec.labels,
          datasets: [
            {
              label: 'Current path',
              data: spec.series_current_dollars,
              borderColor: wsPalette.currentLine,
              backgroundColor: function (ctx) {
                return createFillGradient(ctx, wsPalette.currentFillTop, wsPalette.currentFillBottom);
              },
              fill: true,
              tension: 0.22,
              borderWidth: 2,
              pointRadius: radiusWithEndMarker(spec.series_current_dollars, 3),
              pointBackgroundColor: wsPalette.currentLine,
              pointHoverRadius: 4,
            },
            {
              label: 'With strategies',
              data: spec.series_recommended_dollars,
              borderColor: wsPalette.improvedLine,
              backgroundColor: function (ctx) {
                return createFillGradient(ctx, wsPalette.improvedFillTop, wsPalette.improvedFillBottom);
              },
              fill: true,
              tension: 0.22,
              borderWidth: 2.2,
              pointRadius: radiusWithEndMarker(spec.series_recommended_dollars, 4),
              pointBackgroundColor: wsPalette.improvedLine,
              pointHoverRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              position: 'top',
              align: 'start',
              labels: { color: wsPalette.axisText, boxWidth: 14, boxHeight: 2, usePointStyle: true, pointStyle: 'line' },
            },
          },
          scales: {
            y: {
              display: true,
              grid: { display: true, color: wsPalette.grid, borderDash: [2, 5], drawTicks: false },
              border: { display: false },
              ticks: {
                color: wsPalette.axisText,
                maxTicksLimit: 6,
                callback: function (value) {
                  if (Math.abs(value) >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M';
                  if (Math.abs(value) >= 1000) return '$' + Math.round(value / 1000) + 'k';
                  return '$' + Math.round(value);
                },
              },
            },
            x: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: { color: wsPalette.axisText },
            },
          },
        },
      });
    }
    if (spec.type === 'before_after_interest' && spec.labels && spec.values_dollars) {
      return new Chart(chartCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: spec.labels,
          datasets: [{ label: 'Interest (1 year) $', data: spec.values_dollars, backgroundColor: ['#83a6a8', '#0d9488'] }],
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
      });
    }
    return null;
  }

  async function loadAutoRecommendations() {
    const loadingEl = document.getElementById('auto-recommendations-loading');
    const resultEl = document.getElementById('auto-recommendations-result');
    const listEl = document.getElementById('auto-recommendations-list');

    if (!loadingEl || !resultEl) return;
    show(loadingEl);
    hide(resultEl);
    autoChartInstances.forEach(function (chart) { chart.destroy(); });
    autoChartInstances = [];

    try {
      const r = await fetch(API_BASE + '/api/recommendations/auto', { headers: headers() });
      const data = await r.json().catch(function () { return {}; });
      hide(loadingEl);
      if (!r.ok) {
        if (listEl) listEl.innerHTML = '<p class="error-msg">' + escapeHtml(typeof data.detail === 'string' ? data.detail : 'Could not load recommendations.') + '</p>';
        show(resultEl);
        return;
      }

      var recs = data.recommendations || [];
      if (listEl) {
        if (recs.length > 0) {
          listEl.innerHTML = recs.map(function (rec, i) {
            var title = rec.title || ('Recommendation ' + (i + 1));
            var body = rec.response || '';
            var chartId = 'auto-recommendation-chart-' + i;
            var noteId = 'auto-recommendation-chart-note-' + i;
            var metricsId = 'auto-recommendation-chart-metrics-' + i;
            return ''
              + '<div class="recommendation-item">'
              + '<h3 class="recommendation-item-title">' + escapeHtml(title) + '</h3>'
              + '<p class="recommendation-item-body">' + escapeHtml(body).replace(/\n/g, '<br/>') + '</p>'
              + '<div class="recommendation-chart-container">'
              + '<div id="' + metricsId + '" class="chart-metrics"></div>'
              + '<div class="chart-canvas-wrap"><canvas id="' + chartId + '" height="180"></canvas></div>'
              + '<p id="' + noteId + '" class="chart-note"></p>'
              + '</div>'
              + '</div>';
          }).join('');
        } else {
          listEl.innerHTML = '<p class="muted">No recommendations generated.</p>';
        }
      }
      show(resultEl);
      recs.forEach(function (rec, i) {
        var spec = rec.chart_spec || data.chart_spec;
        var canvas = document.getElementById('auto-recommendation-chart-' + i);
        var noteEl = document.getElementById('auto-recommendation-chart-note-' + i);
        var metricsEl = document.getElementById('auto-recommendation-chart-metrics-' + i);
        if (!canvas || !spec) return;
        var chart = renderChartSpec(spec, canvas, noteEl, metricsEl);
        if (chart) autoChartInstances.push(chart);
      });
    } catch (err) {
      hide(loadingEl);
      if (listEl) listEl.innerHTML = '<p class="error-msg">' + escapeHtml(err.message || 'Network error') + '</p>';
      show(resultEl);
    }
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  document.getElementById('recommendation-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const question = document.getElementById('recommendation-question').value.trim();
    if (!question) return;
    const loadingEl = document.getElementById('recommendation-loading');
    const resultEl = document.getElementById('recommendation-result');
    const narrativeEl = document.getElementById('recommendation-narrative');
    const chartContainer = document.getElementById('recommendation-chart-container');
    const chartCanvas = document.getElementById('recommendation-chart');
    const chartMetrics = document.getElementById('recommendation-chart-metrics');
    const chartNote = document.getElementById('recommendation-chart-note');

    show(loadingEl);
    hide(resultEl);
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }

    try {
      const r = await fetch(API_BASE + '/api/recommendations', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ question, include_visualization: true }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        narrativeEl.textContent = typeof data.detail === 'string' ? data.detail : (data.detail && data.detail[0] ? data.detail[0].msg : 'Request failed');
        show(resultEl);
        hide(loadingEl);
        resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
      }
      narrativeEl.textContent = data.response || '';
      show(resultEl);
      hide(loadingEl);
      resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      const spec = data.chart_spec;
      if (chartNote) chartNote.textContent = '';
      if (chartMetrics) chartMetrics.innerHTML = '';
      if (spec && spec.type === 'five_year_projection' && spec.labels && spec.series_current_dollars && spec.series_recommended_dollars) {
        show(chartContainer);
        if (chartInstance) chartInstance.destroy();
        chartInstance = renderChartSpec(spec, chartCanvas, chartNote, chartMetrics);
      } else if (spec && spec.type === 'before_after_interest' && spec.labels && spec.values_dollars) {
        show(chartContainer);
        if (chartInstance) chartInstance.destroy();
        chartInstance = renderChartSpec(spec, chartCanvas, chartNote, chartMetrics);
      } else {
        hide(chartContainer);
      }
    } catch (err) {
      narrativeEl.textContent = err.message || 'Network error';
      show(resultEl);
      hide(loadingEl);
      resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });

  if (token) {
    fetch(API_BASE + '/api/households', { headers: headers() })
      .then(function (r) {
        if (r.ok) showDashboard();
        else showLogin();
      })
      .catch(function () { showLogin(); });
  } else {
    showLogin();
  }
})();
