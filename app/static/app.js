(function () {
  const API_BASE = '';
  let token = localStorage.getItem('openopt_token');
  let chartInstance = null;

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

  function showLogin() {
    show(document.getElementById('login-section'));
    hide(document.getElementById('dashboard-section'));
    document.getElementById('auth-actions').innerHTML = '';
  }

  function showDashboard() {
    hide(document.getElementById('login-section'));
    show(document.getElementById('dashboard-section'));
    document.getElementById('auth-actions').innerHTML = '<button type="button" id="logout-btn">Sign out</button>';
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

      const list = (arr, fmt) => arr.map(fmt).join('');
      document.getElementById('household-list').innerHTML = list(households, function (h) {
        return '<li><strong>' + escapeHtml(h.name) + '</strong> (id: ' + h.id + ')</li>';
      }) || '<li class="muted">No households</li>';

      document.getElementById('account-list').innerHTML = list(accounts, function (a) {
        const bal = (a.balance_cents / 100).toFixed(2);
        return '<li>' + escapeHtml(a.name) + ' – ' + a.institution_id + ' – $' + bal + '</li>';
      }) || '<li class="muted">No accounts</li>';

      document.getElementById('goal-list').innerHTML = list(goals, function (g) {
        const amt = (g.target_amount_cents / 100).toFixed(0);
        return '<li>' + escapeHtml(g.name) + ' – $' + amt + '</li>';
      }) || '<li class="muted">No goals</li>';
    } catch (err) {
      console.error(err);
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
        narrativeEl.textContent = data.detail || 'Request failed';
        show(resultEl);
        hide(loadingEl);
        return;
      }
      narrativeEl.textContent = data.response || '';
      show(resultEl);
      hide(loadingEl);

      const spec = data.chart_spec;
      if (spec && spec.type === 'before_after_interest' && spec.labels && spec.values_dollars) {
        show(chartContainer);
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(chartCanvas.getContext('2d'), {
          type: 'bar',
          data: {
            labels: spec.labels,
            datasets: [{
              label: 'Interest (1 year) $',
              data: spec.values_dollars,
              backgroundColor: ['#8b949e', '#e4a853'],
            }],
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true },
            },
          },
        });
      } else {
        hide(chartContainer);
      }
    } catch (err) {
      narrativeEl.textContent = err.message || 'Network error';
      show(resultEl);
      hide(loadingEl);
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
