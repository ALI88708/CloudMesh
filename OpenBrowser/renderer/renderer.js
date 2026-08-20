// OpenBrowser v1.0.0 - Main Renderer
let currentTabId = 0;
let tabCounter = 1;
let tabs = [{ id: 0, title: 'تبويب جديد', url: '', navHistory: [], navIndex: -1, zoom: 1 }];
let closedTabs = []; // تخزين آخر تابات مسكرة عشان نقدر نرجعها (Ctrl+Shift+T)
let stats = {};
let settings = {};
let bookmarks = [];
let startTime = Date.now();

// ========== INIT ==========
async function init() {
  settings = await window.openBrowser.getSettings();
  stats = await window.openBrowser.getStats();
  bookmarks = JSON.parse(localStorage.getItem('ob-bookmarks') || '[]');
  applyTheme(settings.theme || 'amoled');
  if (settings.fontSize) document.body.style.fontSize = settings.fontSize + 'px';
  initLang();
  setupEventListeners();
  startTimer();
}

// ========== THEME ==========
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  settings.theme = theme;
  document.querySelectorAll('.theme-card').forEach(c => c.classList.toggle('active', c.dataset.theme === theme));
  window.openBrowser.saveSettings(settings);
}

// ========== INTERNAL PAGES ==========
const INTERNAL_PAGES = {
  'settings': renderSettingsPage,
  'history': renderHistoryPage,
  'about': renderAboutPage,
  'help': renderHelpPage,
  'bookmarks': renderBookmarksPage,
  'new-tab': null,
  'game-v1': null,
  'game-v2': null
};

function isInternalPage(url) {
  return url && url.startsWith('openbrowser://');
}

function getInternalPageId(url) {
  return url.replace('openbrowser://', '');
}

function renderSettingsPage() {
  return `
  <div class="internal-page settings-page">
    <div class="ip-header">
      <div class="ip-icon">⚙</div>
      <h1>الإعدادات</h1>
      <p class="ip-sub">خصّص تجربتك مع OpenBrowser</p>
    </div>
    <div class="ip-content">
      <div class="settings-grid">
        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🎨</span><h3>الثيمات</h3></div>
          <div class="theme-grid-internal" id="ip-theme-grid">
            <div class="theme-option ${settings.theme === 'amoled' ? 'active' : ''}" data-theme="amoled">
              <div class="to-preview amoled-preview"></div>
              <span>AMOLED Dark</span>
            </div>
            <div class="theme-option ${settings.theme === 'dark' ? 'active' : ''}" data-theme="dark">
              <div class="to-preview dark-preview"></div>
              <span>Dark</span>
            </div>
            <div class="theme-option ${settings.theme === 'midnight' ? 'active' : ''}" data-theme="midnight">
              <div class="to-preview midnight-preview"></div>
              <span>Midnight Blue</span>
            </div>
            <div class="theme-option ${settings.theme === 'nord' ? 'active' : ''}" data-theme="nord">
              <div class="to-preview nord-preview"></div>
              <span>Nord</span>
            </div>
            <div class="theme-option ${settings.theme === 'light' ? 'active' : ''}" data-theme="light">
              <div class="to-preview light-preview"></div>
              <span>Light</span>
            </div>
          </div>
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🏠</span><h3>الصفحة الرئيسية</h3></div>
          <input type="text" class="ip-input" id="ip-homepage" value="${settings.homepage || ''}" placeholder="اتركه فارغاً للصفحة الجديدة">
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🔍</span><h3>محرك البحث الافتراضي</h3></div>
          <div class="radio-group" id="ip-search-engine">
            <label class="radio-option ${settings.searchEngine === 'google' || !settings.searchEngine ? 'active' : ''}" data-value="google">
              <span class="radio-dot"></span>
              <span>Google</span>
            </label>
            <label class="radio-option ${settings.searchEngine === 'bing' ? 'active' : ''}" data-value="bing">
              <span class="radio-dot"></span>
              <span>Bing</span>
            </label>
            <label class="radio-option ${settings.searchEngine === 'duckduckgo' ? 'active' : ''}" data-value="duckduckgo">
              <span class="radio-dot"></span>
              <span>DuckDuckGo</span>
            </label>
            <label class="radio-option ${settings.searchEngine === 'brave' ? 'active' : ''}" data-value="brave">
              <span class="radio-dot"></span>
              <span>Brave Search</span>
            </label>
          </div>
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">📝</span><h3>حجم الخط</h3></div>
          <div class="font-control">
            <button class="fc-btn" id="ip-font-dec">−</button>
            <span class="fc-value" id="ip-font-val">${settings.fontSize || 14}px</span>
            <button class="fc-btn" id="ip-font-inc">+</button>
          </div>
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">✨</span><h3>المميزات</h3></div>
          <label class="switch-row">
            <span>الweet Animations</span>
            <input type="checkbox" id="ip-animations" ${settings.enableAnimations !== false ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
          <label class="switch-row">
            <span>شريط الإشارات المرجعية</span>
            <input type="checkbox" id="ip-bookmarks" ${settings.showBookmarksBar !== false ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🛡</span><h3>الخصوصية والأمان</h3></div>
          <label class="switch-row">
            <span>حجب الإعلانات (Ad Blocker)</span>
            <input type="checkbox" id="ip-adblocker" ${settings.adBlocker !== false ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
          <label class="switch-row">
            <span>حجب المتتبعات (Tracker Blocker)</span>
            <input type="checkbox" id="ip-trackerblocker" ${settings.trackerBlocker !== false ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
          <label class="switch-row">
            <span>حماية البصمة (Fingerprint Protection)</span>
            <input type="checkbox" id="ip-fingerprint" ${settings.fingerprintProtection !== false ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
          <div class="privacy-stats" id="privacy-stats-box">
            <div class="ps-row"><span>الإعلانات المحجوبة:</span><strong id="ps-ads">0</strong></div>
            <div class="ps-row"><span>المتتبعات المحجوبة:</span><strong id="ps-trackers">0</strong></div>
          </div>
        </div>

        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">ℹ️</span><h3>حول OpenBrowser</h3></div>
          <div class="about-block">
            <p><strong>OpenBrowser</strong> v1.0.0</p>
            <p>متصفح خفيف وسريع مبني بـ Electron + Lightpanda Engine</p>
            <p>يحتاج فقط 153 MB RAM بدل 2 GB مثل Chrome</p>
            <div class="about-links">
              <span class="about-link" data-url="openbrowser://game-v1">🐍 لعبة Snake</span>
              <span class="about-link" data-url="openbrowser://history">📋 سجل الزيارات</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>`;
}

function renderHistoryPage() {
  const hist = (stats.visitHistory || []).map((url, i) => {
    const domain = url.replace(/https?:\/\//, '').split('/')[0];
    return `<div class="history-row" data-url="${url}">
      <span class="hr-num">${i + 1}</span>
      <span class="hr-url">${url}</span>
      <span class="hr-domain">${domain}</span>
    </div>`;
  }).join('');

  return `
  <div class="internal-page history-page">
    <div class="ip-header">
      <div class="ip-icon">📋</div>
      <h1>سجل الزيارات</h1>
      <p class="ip-sub">${(stats.visitHistory || []).length} صفحة في السجل</p>
    </div>
    <div class="ip-content">
      <div class="history-controls">
        <input type="text" class="ip-input" id="history-search" placeholder="بحث في السجل...">
        <button class="ip-btn danger" id="clear-history">مسح السجل</button>
      </div>
      <div class="history-list-internal" id="history-list">
        ${hist || '<div class="empty-state">لا يوجد سجل بعد</div>'}
      </div>
    </div>
  </div>`;
}

function renderAboutPage() {
  return `
  <div class="internal-page about-page">
    <div class="ip-header">
      <img class="ip-header-logo" src="logo.png" alt="OpenBrowser">
      <h1>OpenBrowser</h1>
      <p class="ip-sub">v1.0.0 - First Release</p>
    </div>
    <div class="ip-content">
      <div class="about-center">
        <img class="about-logo-big" src="logo.png" alt="OpenBrowser Logo">
        <h2>OpenBrowser</h2>
        <p class="about-tagline">Lightweight • Fast • Private • AI-Ready</p>
        <div class="about-features">
          <div class="af-item"><span>⚡</span><span>خفيف - 153 MB فقط</span></div>
          <div class="af-item"><span>🎨</span><span>5 ثيمات مخصصة</span></div>
          <div class="af-item"><span>🐍</span><span>ألعاب مخفية</span></div>
          <div class="af-item"><span>📊</span><span>إحصائيات مفصلة</span></div>
        </div>
        <p class="about-easter">💡 جرب: openbrowser://game-v1</p>
      </div>
    </div>
  </div>`;
}

// ========== NAVIGATION ==========
function navigateTo(url, tabId, isBackForward) {
  tabId = tabId || currentTabId;
  const tab = tabs.find(t => t.id === tabId);
  if (!tab) return;

  // Clean up game if leaving game page
  if (tab.url === 'openbrowser://game-v1' && url !== 'openbrowser://game-v1') {
    if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
    if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }
  }

  // Internal pages
  if (isInternalPage(url)) {
    const pageId = getInternalPageId(url);

    // new-tab = render NTP
    if (pageId === 'new-tab') {
      tab.url = '';
      tab.title = 'تبويب جديد';
      updateTabTitle(tabId, tab.title);
      document.getElementById('url-input').value = '';
      updateAddressIcon('');
      const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`);
      if (wrapper) wrapper.innerHTML = createNTP(tabId);
      return;
    }

    tab.url = url;
    tab.title = getInternalPageTitle(url);
    updateTabTitle(tabId, tab.title);
    document.getElementById('url-input').value = url;
    updateAddressIcon(url);

    if (pageId === 'game-v1') {
      stats.gamesPlayed = (stats.gamesPlayed || 0) + 1;
      window.openBrowser.saveStats(stats);
      renderGamePage(tabId);
    } else if (pageId === 'game-v2') {
      stats.gamesPlayed = (stats.gamesPlayed || 0) + 1;
      window.openBrowser.saveStats(stats);
      renderGamePageV2(tabId);
    } else {
      renderInternalPage(url, tabId);
    }

    // Add to nav history
    if (!isBackForward) {
      if (!tab.navHistory) tab.navHistory = [];
      if (!tab.navIndex) tab.navIndex = -1;
      tab.navHistory = tab.navHistory.slice(0, tab.navIndex + 1);
      tab.navHistory.push(url);
      tab.navIndex = tab.navHistory.length - 1;
    }
    updateNavButtons(tabId);
    return;
  }

  // Add protocol if missing
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    if (url.includes('.') && !url.includes(' ')) {
      url = 'https://' + url;
    } else {
      const engine = settings.searchEngine || 'google';
      const engines = {
        google: 'https://www.google.com/search?q=',
        bing: 'https://www.bing.com/search?q=',
        duckduckgo: 'https://duckduckgo.com/?q=',
        brave: 'https://search.brave.com/search?q='
      };
      url = (engines[engine] || engines.google) + encodeURIComponent(url);
    }
  }

  tab.url = url;
  tab.title = url.replace(/https?:\/\//, '').split('/')[0];
  updateTabTitle(tabId, tab.title);
  document.getElementById('url-input').value = url;
  updateAddressIcon(url);
  renderWebview(url, tabId);

  // Add to nav history
  if (!isBackForward) {
    if (!tab.navHistory) tab.navHistory = [];
    if (!tab.navIndex) tab.navIndex = -1;
    tab.navHistory = tab.navHistory.slice(0, tab.navIndex + 1);
    tab.navHistory.push(url);
    tab.navIndex = tab.navHistory.length - 1;
  }
  updateNavButtons(tabId);

  // Stats
  stats.pagesVisited = (stats.pagesVisited || 0) + 1;
  stats.lastVisit = new Date().toISOString();
  if (!stats.visitHistory) stats.visitHistory = [];
  stats.visitHistory.unshift(url);
  if (stats.visitHistory.length > 100) stats.visitHistory.pop();
  window.openBrowser.saveStats(stats);
  updateStats();
}

function renderInternalPage(url, tabId) {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`);
  if (!wrapper) return;
  const renderer = INTERNAL_PAGES[getInternalPageId(url)];
  if (renderer) {
    wrapper.innerHTML = renderer();
    setupInternalPageEvents(url, tabId);
  }
}

function renderWebview(url, tabId) {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`);
  if (!wrapper) return;
  wrapper.innerHTML = '';
  const wv = document.createElement('webview');
  wv.src = url;
  wv.preload = window.openBrowser.privacyPreloadPath;
  wv.style.width = '100%';
  wv.style.height = '100%';
  wv.style.border = 'none';
  wv.addEventListener('did-navigate', (e) => {
    tab.url = e.url;
    document.getElementById('url-input').value = e.url;
    updateAddressIcon(e.url);
    updateTabTitle(tabId, e.url.replace(/https?:\/\//, '').split('/')[0]);
  });
  wv.addEventListener('page-title-updated', (e) => updateTabTitle(tabId, e.title));
  wv.addEventListener('found-in-page', (e) => {
    const r = e.result;
    if (!r || !r.matches) return;
    const countEl = document.getElementById('find-count');
    if (countEl) countEl.textContent = `${r.activeMatchOrdinal}/${r.matches}`;
  });
  wv.addEventListener('did-start-loading', () => {});
  wv.addEventListener('did-stop-loading', () => {
    // Inject fingerprint protection into every webview page load
    wv.executeJavaScript(
      '(function(){' +
        'Object.defineProperty(navigator,"plugins",{get:function(){return{0:{name:"PDF Viewer"},length:5,item:function(i){return this[i]},namedItem:function(){return null},refresh:function(){}}}});' +
        'Object.defineProperty(navigator,"languages",{get:function(){return["en-US","en"]}});' +
        'Object.defineProperty(navigator,"hardwareConcurrency",{get:function(){return 8}});' +
        'Object.defineProperty(navigator,"deviceMemory",{get:function(){return 8}});' +
        'Object.defineProperty(navigator,"maxTouchPoints",{get:function(){return 0}});' +
        'Object.defineProperty(navigator,"webdriver",{get:function(){return false}});' +
        'var oTD=HTMLCanvasElement.prototype.toDataURL;' +
        'HTMLCanvasElement.prototype.toDataURL=function(t){if(t==="image/webp")return oTD.apply(this,arguments);var c=this.getContext("2d");if(c){var d;try{d=c.getImageData(0,0,Math.min(this.width,16),Math.min(this.height,16));}catch(e){return oTD.apply(this,arguments);}for(var i=0;i<d.data.length;i+=4){d.data[i]=d.data[i]^((i%7)<1?1:0);d.data[i+1]=d.data[i+1]^((i%11)<1?1:0);d.data[i+2]=d.data[i+2]^((i%13)<1?1:0);}c.putImageData(d,0,0);}return oTD.apply(this,arguments);};' +
        'var oTB=HTMLCanvasElement.prototype.toBlob;if(oTB){HTMLCanvasElement.prototype.toBlob=function(cb,type,q){var c=this.getContext("2d");if(c){var d;try{d=c.getImageData(0,0,Math.min(this.width,16),Math.min(this.height,16));}catch(e){return oTB.apply(this,arguments);}for(var i=0;i<d.data.length;i+=4){d.data[i]=d.data[i]^((i%7)<1?1:0);d.data[i+1]=d.data[i+1]^((i%11)<1?1:0);d.data[i+2]=d.data[i+2]^((i%13)<1?1:0);}c.putImageData(d,0,0);}return oTB.apply(this,arguments);};}' +
        'var oGP=WebGLRenderingContext.prototype.getParameter;WebGLRenderingContext.prototype.getParameter=function(p){if(p===37445)return"Inc.";if(p===37446)return"Iris OpenGL Engine";return oGP.apply(this,arguments);};' +
        'var oMT=CanvasRenderingContext2D.prototype.measureText;CanvasRenderingContext2D.prototype.measureText=function(){var r=oMT.apply(this,arguments);var w=r.width;Object.defineProperty(r,"width",{get:function(){return w+Math.random()*0.001}});return r};' +
        'var oGC=AudioBuffer.prototype.getChannelData;AudioBuffer.prototype.getChannelData=function(ch){var d=oGC.apply(this,arguments);for(var i=0;i<Math.min(d.length,10);i++){d[i]=d[i]+Math.random()*0.0000001;}return d};' +
      '})();'
    ).catch(function(){});
  });
  wrapper.appendChild(wv);
}

function setupInternalPageEvents(url, tabId) {
  const pageId = getInternalPageId(url);

  if (pageId === 'settings') {
    // Theme
    document.getElementById('ip-theme-grid')?.addEventListener('click', (e) => {
      const opt = e.target.closest('.theme-option');
      if (opt) {
        applyTheme(opt.dataset.theme);
        document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
      }
    });
    // Homepage
    document.getElementById('ip-homepage')?.addEventListener('change', (e) => {
      settings.homepage = e.target.value;
      window.openBrowser.saveSettings(settings);
    });
    // Search engine
    document.getElementById('ip-search-engine')?.addEventListener('click', (e) => {
      const opt = e.target.closest('.radio-option');
      if (opt) {
        settings.searchEngine = opt.dataset.value;
        window.openBrowser.saveSettings(settings);
        document.querySelectorAll('#ip-search-engine .radio-option').forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
      }
    });
    // Font size
    document.getElementById('ip-font-inc')?.addEventListener('click', () => {
      settings.fontSize = Math.min(24, (settings.fontSize || 14) + 2);
      document.getElementById('ip-font-val').textContent = settings.fontSize + 'px';
      document.body.style.fontSize = settings.fontSize + 'px';
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-font-dec')?.addEventListener('click', () => {
      settings.fontSize = Math.max(10, (settings.fontSize || 14) - 2);
      document.getElementById('ip-font-val').textContent = settings.fontSize + 'px';
      document.body.style.fontSize = settings.fontSize + 'px';
      window.openBrowser.saveSettings(settings);
    });
    // Toggles
    document.getElementById('ip-animations')?.addEventListener('change', (e) => {
      settings.enableAnimations = e.target.checked;
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-bookmarks')?.addEventListener('change', (e) => {
      settings.showBookmarksBar = e.target.checked;
      window.openBrowser.saveSettings(settings);
    });
    // Privacy toggles
    document.getElementById('ip-adblocker')?.addEventListener('change', (e) => {
      settings.adBlocker = e.target.checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleAdBlocker(e.target.checked);
    });
    document.getElementById('ip-trackerblocker')?.addEventListener('change', (e) => {
      settings.trackerBlocker = e.target.checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleTrackerBlocker(e.target.checked);
    });
    document.getElementById('ip-fingerprint')?.addEventListener('change', (e) => {
      settings.fingerprintProtection = e.target.checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleFingerprintProtection(e.target.checked);
    });
    // Load privacy stats
    window.openBrowser.getPrivacyStats().then(function(ps) {
      var ae = document.getElementById('ps-ads'); if (ae) ae.textContent = ps.adsBlocked;
      var te = document.getElementById('ps-trackers'); if (te) te.textContent = ps.trackersBlocked;
    });
    // Links
    document.querySelectorAll('.about-link').forEach(link => {
      link.addEventListener('click', () => navigateTo(link.dataset.url));
    });
  }

  if (pageId === 'history') {
    document.getElementById('history-search')?.addEventListener('input', function(e) {
      var q = e.target.value.toLowerCase();
      document.querySelectorAll('.history-row').forEach(function(row) {
        row.style.display = row.dataset.url.toLowerCase().includes(q) ? '' : 'none';
      });
    });
    document.querySelectorAll('.history-row').forEach(function(row) {
      row.addEventListener('click', function() { navigateTo(row.dataset.url); });
    });
    document.getElementById('clear-history')?.addEventListener('click', function() {
      stats.visitHistory = [];
      window.openBrowser.saveStats(stats);
      var list = document.getElementById('history-list');
      if (list) list.innerHTML = '<div class="empty-state">' + t('noHistory') + '</div>';
    });
  }

  if (pageId === 'help') {
    document.querySelectorAll('.help-row').forEach(function(row) {
      row.addEventListener('click', function() { navigateTo(row.dataset.url); });
      row.style.cursor = 'pointer';
    });
  }

  if (pageId === 'bookmarks') {
    document.querySelectorAll('.bm-remove').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        removeBookmark(btn.dataset.rm);
        navigateTo('openbrowser://bookmarks');
      });
    });
    document.querySelectorAll('#bookmarks-list .history-row').forEach(function(row) {
      row.addEventListener('click', function() { navigateTo(row.dataset.url); });
    });
  }
}

function getInternalPageTitle(url) {
  var id = getInternalPageId(url);
  var map = {
    'settings': currentLang === 'en' ? 'Settings' : '⚙ الإعدادات',
    'history': currentLang === 'en' ? 'History' : '📋 السجل',
    'about': currentLang === 'en' ? 'About' : 'ℹ حول',
    'help': currentLang === 'en' ? 'Help' : '❓ المساعدة',
    'bookmarks': currentLang === 'en' ? 'Bookmarks' : '⭐ الإشارات',
    'new-tab': currentLang === 'en' ? 'New Tab' : 'تبويب جديد',
    'game-v1': '🐍 Snake Game',
    'game-v2': '💎 Tetris'
  };
  return map[id] || url;
}

function updateNavButtons(tabId) {
  const tab = tabs.find(t => t.id === tabId);
  if (!tab) return;
  const backBtn = document.getElementById('btn-back');
  const fwdBtn = document.getElementById('btn-forward');
  if (backBtn) backBtn.style.opacity = (tab.navIndex > 0) ? '1' : '0.3';
  if (fwdBtn) fwdBtn.style.opacity = (tab.navIndex < (tab.navHistory || []).length - 1) ? '1' : '0.3';
}

function goBack() {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab || !tab.navHistory || tab.navIndex <= 0) return;
  tab.navIndex--;
  const url = tab.navHistory[tab.navIndex];
  navigateTo(url, currentTabId, true);
}

function goForward() {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab || !tab.navHistory || tab.navIndex >= tab.navHistory.length - 1) return;
  tab.navIndex++;
  const url = tab.navHistory[tab.navIndex];
  navigateTo(url, currentTabId, true);
}

function updateTabTitle(id, title) {
  const tab = tabs.find(t => t.id === id);
  if (tab) tab.title = title;
  const tabEl = document.querySelector(`.tab[data-tab-id="${id}"] .tab-title`);
  if (tabEl) tabEl.textContent = title;
}

function updateAddressIcon(url) {
  const icon = document.getElementById('address-icon');
  if (!url) { icon.textContent = '🔍'; return; }
  if (url.startsWith('https://')) icon.textContent = '🔒';
  else if (url.startsWith('http://')) icon.textContent = '⚠️';
  else if (url.startsWith('openbrowser://')) icon.textContent = '⚡';
  else icon.textContent = '🌐';
}

// ========== TABS ==========
function createTab(url) {
  const id = tabCounter++;
  tabs.push({ id, title: 'تبويب جديد', url: '', navHistory: [], navIndex: -1, zoom: 1 });

  const tabEl = document.createElement('div');
  tabEl.className = 'tab';
  tabEl.dataset.tabId = id;
  tabEl.innerHTML = `<span class="tab-title">تبويب جديد</span><button class="tab-close" data-close="${id}">×</button>`;
  document.getElementById('tabs-container').appendChild(tabEl);

  const wrapper = document.createElement('div');
  wrapper.className = 'webview-wrapper';
  wrapper.dataset.tabId = id;
  wrapper.innerHTML = createNTP(id);
  document.getElementById('content-area').appendChild(wrapper);

  switchTab(id);
  stats.tabsOpened = (stats.tabsOpened || 0) + 1;
  window.openBrowser.saveStats(stats);
  if (url) navigateTo(url, id);
}

function switchTab(id) {
  currentTabId = id;
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.toggle('active', parseInt(t.dataset.tabId) === id); });
  document.querySelectorAll('.webview-wrapper').forEach(function(w) { w.classList.toggle('active', parseInt(w.dataset.tabId) === id); });
  var tab = tabs.find(function(t) { return t.id === id; });
  if (tab) {
    document.getElementById('url-input').value = tab.url || '';
    updateAddressIcon(tab.url);
  }
  updateNavButtons(id);
  updateBookmarkButton();

  // كل تاب يحتفظ بمستوى الزوم الخاص فيه لما نرجعله
  const wv = document.querySelector(`.webview-wrapper[data-tab-id="${id}"] webview`);
  if (wv && tab) {
    const applyZoom = () => wv.setZoomFactor(tab.zoom || 1);
    if (wv.getWebContentsId) { try { applyZoom(); } catch (e) {} }
    else wv.addEventListener('dom-ready', applyZoom, { once: true });
  }
}

function setZoom(action) {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab) return;
  if (action === 'in') tab.zoom = Math.min(3, +(( tab.zoom || 1) + 0.1).toFixed(2));
  else if (action === 'out') tab.zoom = Math.max(0.3, +((tab.zoom || 1) - 0.1).toFixed(2));
  else tab.zoom = 1; // reset
  const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`);
  if (wv) wv.setZoomFactor(tab.zoom);
}

function closeTab(id) {
  if (tabs.length === 1) return;
  const idx = tabs.findIndex(t => t.id === id);
  const closedTab = tabs[idx];
  // نخزن الرابط والعنوان عشان لو المستخدم يريد يرجع التاب (Ctrl+Shift+T)
  if (closedTab && closedTab.url) {
    closedTabs.push({ url: closedTab.url, title: closedTab.title });
    if (closedTabs.length > 15) closedTabs.shift(); // ما نخزن أكثر من 15
  }
  tabs.splice(idx, 1);
  document.querySelector(`.tab[data-tab-id="${id}"]`)?.remove();
  document.querySelector(`.webview-wrapper[data-tab-id="${id}"]`)?.remove();
  if (currentTabId === id) {
    switchTab(tabs[Math.min(idx, tabs.length - 1)].id);
  }
}

function reopenClosedTab() {
  const last = closedTabs.pop();
  if (last) createTab(last.url);
}

function cycleTab(direction) {
  if (tabs.length < 2) return;
  const idx = tabs.findIndex(t => t.id === currentTabId);
  // % بالسالب ما يشتغل زين بجافاسكربت، فنضيف tabs.length قبل القسمة
  const nextIdx = (idx + direction + tabs.length) % tabs.length;
  switchTab(tabs[nextIdx].id);
}

function createNTP(tabId) {
  const isEn = currentLang === 'en';
  return `<div class="new-tab-page" id="ntp-${tabId}">
    <div class="ntp-content">
      <img class="ntp-logo-img" src="logo.png" alt="OpenBrowser">
      <div class="ntp-search"><input type="text" class="ntp-search-input" placeholder="${t('search')}"></div>
      <div class="ntp-shortcuts">
        <div class="shortcut" data-url="https://google.com"><div class="shortcut-icon">G</div><span>Google</span></div>
        <div class="shortcut" data-url="https://youtube.com"><div class="shortcut-icon">Y</div><span>YouTube</span></div>
        <div class="shortcut" data-url="https://github.com"><div class="shortcut-icon">H</div><span>GitHub</span></div>
        <div class="shortcut" data-url="openbrowser://settings"><div class="shortcut-icon">⚙</div><span>${t('settings')}</span></div>
        <div class="shortcut" data-url="openbrowser://bookmarks"><div class="shortcut-icon">⭐</div><span>${isEn ? 'Bookmarks' : 'الإشارات'}</span></div>
        <div class="shortcut" data-url="openbrowser://history"><div class="shortcut-icon">📋</div><span>${t('history')}</span></div>
        <div class="shortcut" data-url="openbrowser://game-v1"><div class="shortcut-icon">🐍</div><span>Snake</span></div>
        <div class="shortcut" data-url="openbrowser://game-v2"><div class="shortcut-icon">💎</div><span>Tetris</span></div>
        <div class="shortcut" data-url="openbrowser://help"><div class="shortcut-icon">❓</div><span>${isEn ? 'Help' : 'مساعدة'}</span></div>
      </div>
      <div class="ntp-footer"><span>v1.0.0 • ${isEn ? 'Lightweight • Fast • AI-Ready' : 'خفيف • سريع • جاهز للذكاء الاصطناعي'}</span></div>
    </div>
  </div>`;
}

// ========== HELP PAGE ==========
function renderHelpPage() {
  const isEn = currentLang === 'en';
  const pages = [
    { url: 'openbrowser://settings', icon: '⚙', title: isEn ? 'Settings' : 'الإعدادات', desc: isEn ? 'Customize themes, search engine, font size' : 'تخصيص الثيمات ومحرك البحث وحجم الخط' },
    { url: 'openbrowser://history', icon: '📋', title: isEn ? 'History' : 'السجل', desc: isEn ? 'View your browsing history' : 'عرض سجل التصفح' },
    { url: 'openbrowser://bookmarks', icon: '⭐', title: isEn ? 'Bookmarks' : 'الإشارات', desc: isEn ? 'Manage saved bookmarks' : 'إدارة الإشارات المحفوظة' },
    { url: 'openbrowser://help', icon: '❓', title: isEn ? 'Help' : 'المساعدة', desc: isEn ? 'Show help page' : 'عرض صفحة المساعدة' },
    { url: 'openbrowser://about', icon: 'ℹ', title: isEn ? 'About' : 'حول', desc: isEn ? 'About OpenBrowser' : 'حول المتصفح' },
    { url: 'openbrowser://game-v1', icon: '🐍', title: 'Snake', desc: isEn ? 'Classic snake game' : 'لعبة الثعبان' },
    { url: 'openbrowser://game-v2', icon: '💎', title: 'Tetris', desc: isEn ? 'Block puzzle game' : 'لعبة ترتيب المربعات' }
  ];
  const shortcuts = [
    { keys: 'Ctrl+T', desc: isEn ? 'New Tab' : 'تبويب جديد' },
    { keys: 'Ctrl+W', desc: isEn ? 'Close Tab' : 'إغلاق تبويب' },
    { keys: 'Ctrl+L', desc: isEn ? 'Address Bar' : 'شريط العناوين' },
    { keys: 'F5', desc: isEn ? 'Reload' : 'تحديث' },
    { keys: 'Alt+Left', desc: isEn ? 'Back' : 'رجوع' },
    { keys: 'Alt+Right', desc: isEn ? 'Forward' : 'أمام' }
  ];
  const pagesHtml = pages.map(p => '<div class="help-row" data-url="' + p.url + '"><span class="help-icon">' + p.icon + '</span><div class="help-info"><span class="help-title">' + p.title + '</span><span class="help-desc">' + p.desc + '</span></div><span class="help-url">' + p.url + '</span></div>').join('');
  const shortcutsHtml = shortcuts.map(s => '<div class="shortcut-row"><kbd>' + s.keys + '</kbd><span>' + s.desc + '</span></div>').join('');
  return '<div class="internal-page help-page"><div class="ip-header"><div class="ip-icon">❓</div><h1>' + (isEn ? 'Help & Commands' : 'المساعدة والأوامر') + '</h1><p class="ip-sub">' + (isEn ? 'All available pages and shortcuts' : 'جميع الصفحات والاختصارات') + '</p></div><div class="ip-content"><div class="settings-card"><div class="sc-header"><span class="sc-icon">📄</span><h3>' + (isEn ? 'Internal Pages' : 'الصفحات الداخلية') + '</h3></div><div class="help-list">' + pagesHtml + '</div></div><div class="settings-card"><div class="sc-header"><span class="sc-icon">⌨</span><h3>' + (isEn ? 'Shortcuts' : 'الاختصارات') + '</h3></div><div class="shortcuts-list">' + shortcutsHtml + '</div></div></div></div>';
}

// ========== BOOKMARKS ==========
function saveBookmarks() { localStorage.setItem('ob-bookmarks', JSON.stringify(bookmarks)); }
function addBookmark(url, title) {
  if (!url || bookmarks.find(function(b) { return b.url === url; })) return;
  bookmarks.unshift({ url: url, title: title || url, date: new Date().toISOString() });
  saveBookmarks(); updateBookmarkButton();
}
function removeBookmark(url) {
  bookmarks = bookmarks.filter(function(b) { return b.url !== url; });
  saveBookmarks(); updateBookmarkButton();
}
function isBookmarked(url) { return bookmarks.some(function(b) { return b.url === url; }); }
function updateBookmarkButton() {
  var btn = document.getElementById('btn-bookmark');
  if (!btn) return;
  var tab = tabs.find(function(t) { return t.id === currentTabId; });
  var url = tab ? tab.url : '';
  var bm = isBookmarked(url);
  btn.classList.toggle('active', bm);
  btn.innerHTML = bm
    ? '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 2h10v12l-5-3-5 3V2z" fill="currentColor"/></svg>'
    : '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 2h10v12l-5-3-5 3V2z" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
}
function renderBookmarksPage() {
  var isEn = currentLang === 'en';
  var list = bookmarks.map(function(b, i) {
    return '<div class="history-row" data-url="' + b.url + '"><span class="hr-num">' + (i+1) + '</span><span class="hr-url">' + b.title + '</span><button class="bm-remove" data-rm="' + b.url + '">×</button></div>';
  }).join('');
  return '<div class="internal-page bookmarks-page"><div class="ip-header"><div class="ip-icon">⭐</div><h1>' + (isEn ? 'Bookmarks' : 'الإشارات المرجعية') + '</h1><p class="ip-sub">' + bookmarks.length + ' ' + (isEn ? 'saved' : 'محفوظة') + '</p></div><div class="ip-content"><div class="history-list-internal" id="bookmarks-list">' + (list || '<div class="empty-state">' + (isEn ? 'No bookmarks' : 'لا يوجد إشارات') + '</div>') + '</div></div></div>';
}

// ========== GAME EASTER EGG ==========
function renderGamePage(tabId) {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`);
  if (!wrapper) return;

  // Cleanup old game
  if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
  if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }

  wrapper.innerHTML = `
  <div class="game-page">
    <div class="game-header-bar">
      <span class="game-title">🐍 Snake Game</span>
      <span class="game-badge">Easter Egg v1</span>
    </div>
    <div class="game-info-bar">
      <span>النقاط: <strong id="game-score">0</strong></span>
      <span>الأعلى: <strong id="game-hs">${parseInt(localStorage.getItem('snake-hs') || '0')}</strong></span>
    </div>
    <canvas id="game-canvas" width="400" height="400" tabindex="0"></canvas>
    <div class="game-controls-info">
      <p>الأسهم أو WASD للتحكم</p>
      <button class="game-start-btn" id="game-start-btn">▶ ابدأ اللعب</button>
    </div>
  </div>`;

  initSnakeGame();
}

function initSnakeGame() {
  const canvas = document.getElementById('game-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const grid = 20;
  const cells = canvas.width / grid;
  let snake, food, dir, nextDir, score, running;

  function reset() {
    snake = [{ x: 10, y: 10 }];
    dir = { x: 1, y: 0 };
    nextDir = { x: 1, y: 0 };
    score = 0;
    running = false;
    const se = document.getElementById('game-score');
    if (se) se.textContent = '0';
    placeFood();
    draw();
  }

  function placeFood() {
    food = { x: Math.floor(Math.random() * cells), y: Math.floor(Math.random() * cells) };
    for (const s of snake) {
      if (s.x === food.x && s.y === food.y) return placeFood();
    }
  }

  function draw() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#111';
    for (let i = 0; i <= cells; i++) {
      ctx.beginPath(); ctx.moveTo(i * grid, 0); ctx.lineTo(i * grid, canvas.height); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, i * grid); ctx.lineTo(canvas.width, i * grid); ctx.stroke();
    }
    snake.forEach((s, i) => {
      const b = 1 - (i / snake.length) * 0.5;
      ctx.fillStyle = `rgba(0, 212, 255, ${b})`;
      ctx.shadowColor = '#00d4ff';
      ctx.shadowBlur = i === 0 ? 12 : 4;
      ctx.beginPath();
      ctx.roundRect(s.x * grid + 1, s.y * grid + 1, grid - 2, grid - 2, 4);
      ctx.fill();
      ctx.shadowBlur = 0;
    });
    ctx.fillStyle = '#ff4444';
    ctx.shadowColor = '#ff4444';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(food.x * grid + grid / 2, food.y * grid + grid / 2, grid / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  function update() {
    dir = { ...nextDir };
    const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };
    if (head.x < 0 || head.x >= cells || head.y < 0 || head.y >= cells) return gameOver();
    for (const s of snake) { if (s.x === head.x && s.y === head.y) return gameOver(); }
    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) {
      score += 10;
      const se = document.getElementById('game-score');
      if (se) se.textContent = score;
      placeFood();
    } else {
      snake.pop();
    }
  }

  function gameOver() {
    running = false;
    if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
    const hs = parseInt(localStorage.getItem('snake-hs') || '0');
    if (score > hs) {
      localStorage.setItem('snake-hs', score.toString());
      const hse = document.getElementById('game-hs');
      if (hse) hse.textContent = score;
    }
    ctx.fillStyle = 'rgba(0,0,0,0.75)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ff4444';
    ctx.font = 'bold 36px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Game Over!', canvas.width / 2, canvas.height / 2 - 10);
    ctx.fillStyle = '#00d4ff';
    ctx.font = '20px Inter';
    ctx.fillText('Score: ' + score, canvas.width / 2, canvas.height / 2 + 20);
    ctx.fillStyle = '#666';
    ctx.font = '14px Inter';
    ctx.fillText('اضغط ابدأ للعب مرة ثانية', canvas.width / 2, canvas.height / 2 + 50);
  }

  function startGame() {
    reset();
    running = true;
    canvas.focus();
    if (window._gameInterval) clearInterval(window._gameInterval);
    window._gameInterval = setInterval(() => { if (running) { update(); draw(); } }, 120);
  }

  // Remove old handler
  if (window._gameKeyHandler) document.removeEventListener('keydown', window._gameKeyHandler);

  // KEY HANDLER
  window._gameKeyHandler = (e) => {
    if (!running) return;
    const key = e.key;
    if (key === 'ArrowUp' && dir.y !== 1) { nextDir = { x: 0, y: -1 }; e.preventDefault(); }
    else if (key === 'ArrowDown' && dir.y !== -1) { nextDir = { x: 0, y: 1 }; e.preventDefault(); }
    else if (key === 'ArrowLeft' && dir.x !== 1) { nextDir = { x: -1, y: 0 }; e.preventDefault(); }
    else if (key === 'ArrowRight' && dir.x !== -1) { nextDir = { x: 1, y: 0 }; e.preventDefault(); }
    else if (key === 'w' || key === 'W') { if (dir.y !== 1) { nextDir = { x: 0, y: -1 }; e.preventDefault(); } }
    else if (key === 's' || key === 'S') { if (dir.y !== -1) { nextDir = { x: 0, y: 1 }; e.preventDefault(); } }
    else if (key === 'a' || key === 'A') { if (dir.x !== 1) { nextDir = { x: -1, y: 0 }; e.preventDefault(); } }
    else if (key === 'd' || key === 'D') { if (dir.x !== -1) { nextDir = { x: 1, y: 0 }; e.preventDefault(); } }
  };
  document.addEventListener('keydown', window._gameKeyHandler);

  document.getElementById('game-start-btn').onclick = startGame;
  canvas.focus();
  reset();
}

// ========== GAME V2 - TETRIS ==========
function renderGamePageV2(tabId) {
  var wrapper = document.querySelector('.webview-wrapper[data-tab-id="' + tabId + '"]');
  if (!wrapper) return;
  if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
  if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }
  var isEn = currentLang === 'en';
  wrapper.innerHTML = '<div class="game-page"><div class="game-header-bar"><span class="game-title">💎 Tetris</span><span class="game-badge">Easter Egg v1</span></div><div class="game-info-bar"><span>' + (isEn ? 'Score' : 'النقاط') + ': <strong id="tet-score">0</strong></span><span>' + (isEn ? 'Lines' : 'الخطوط') + ': <strong id="tet-lines">0</strong></span></div><canvas id="tet-canvas" width="300" height="600"></canvas><div class="game-controls-info"><p>' + (isEn ? 'Arrow keys to move/rotate, Down to drop' : 'الأسهم للتحريك، السفل للإسقاط') + '</p><button class="game-start-btn" id="tet-start">' + (isEn ? '▶ Start' : '▶ ابدأ') + '</button></div></div>';
  initTetrisGame();
}

function initTetrisGame() {
  var canvas = document.getElementById('tet-canvas');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var COLS = 10, ROWS = 20, SIZE = 30;
  var board = [], piece, nextPiece, score = 0, lines = 0, running = false;
  var PIECES = [
    { shape: [[1,1,1,1]], color: '#00d4ff' },
    { shape: [[1,1],[1,1]], color: '#ffaa00' },
    { shape: [[0,1,0],[1,1,1]], color: '#aa55ff' },
    { shape: [[1,0,0],[1,1,1]], color: '#00ff88' },
    { shape: [[0,0,1],[1,1,1]], color: '#ff4444' },
    { shape: [[0,1,1],[1,1,0]], color: '#ff6699' },
    { shape: [[1,1,0],[0,1,1]], color: '#ffff00' }
  ];

  function resetBoard() { board = []; for (var r = 0; r < ROWS; r++) board.push(new Array(COLS).fill(0)); }
  function newPiece() {
    var p = PIECES[Math.floor(Math.random() * PIECES.length)];
    return { shape: p.shape.map(function(r) { return r.slice(); }), color: p.color, x: 3, y: 0 };
  }
  function valid(p, dx, dy) {
    for (var r = 0; r < p.shape.length; r++)
      for (var c = 0; c < p.shape[r].length; c++)
        if (p.shape[r][c]) {
          var nx = p.x + c + dx, ny = p.y + r + dy;
          if (nx < 0 || nx >= COLS || ny >= ROWS) return false;
          if (ny >= 0 && board[ny][nx]) return false;
        }
    return true;
  }
  function lock() {
    for (var r = 0; r < piece.shape.length; r++)
      for (var c = 0; c < piece.shape[r].length; c++)
        if (piece.shape[r][c] && piece.y + r >= 0) board[piece.y + r][piece.x + c] = piece.color;
  }
  function clearLines() {
    var cleared = 0;
    for (var r = ROWS - 1; r >= 0; r--) {
      if (board[r].every(function(c) { return c !== 0; })) {
        board.splice(r, 1);
        board.unshift(new Array(COLS).fill(0));
        cleared++; r++;
      }
    }
    if (cleared > 0) {
      lines += cleared;
      score += cleared * 10 * cleared;
      var se = document.getElementById('tet-score'); if (se) se.textContent = score;
      var le = document.getElementById('tet-lines'); if (le) le.textContent = lines;
    }
  }
  function rotate() {
    var rotated = [];
    for (var c = 0; c < piece.shape[0].length; c++) {
      var row = [];
      for (var r = piece.shape.length - 1; r >= 0; r--) row.push(piece.shape[r][c]);
      rotated.push(row);
    }
    if (valid({ shape: rotated, x: piece.x, y: piece.y }, 0, 0)) piece.shape = rotated;
  }
  function draw() {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#111';
    for (var r = 0; r <= ROWS; r++) { ctx.beginPath(); ctx.moveTo(0, r*SIZE); ctx.lineTo(canvas.width, r*SIZE); ctx.stroke(); }
    for (var c = 0; c <= COLS; c++) { ctx.beginPath(); ctx.moveTo(c*SIZE, 0); ctx.lineTo(c*SIZE, canvas.height); ctx.stroke(); }
    for (var r = 0; r < ROWS; r++)
      for (var c = 0; c < COLS; c++)
        if (board[r][c]) { ctx.fillStyle = board[r][c]; ctx.fillRect(c*SIZE+1, r*SIZE+1, SIZE-2, SIZE-2); }
    if (piece) {
      ctx.fillStyle = piece.color;
      for (var r = 0; r < piece.shape.length; r++)
        for (var c = 0; c < piece.shape[r].length; c++)
          if (piece.shape[r][c]) ctx.fillRect((piece.x+c)*SIZE+1, (piece.y+r)*SIZE+1, SIZE-2, SIZE-2);
    }
  }
  function tick() {
    if (!running) return;
    if (valid(piece, 0, 1)) { piece.y++; }
    else { lock(); clearLines(); piece = newPiece(); if (!valid(piece, 0, 0)) gameOver(); }
    draw();
  }
  function gameOver() {
    running = false; clearInterval(window._gameInterval);
    ctx.fillStyle = 'rgba(0,0,0,0.75)'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ff4444'; ctx.font = 'bold 36px Inter'; ctx.textAlign = 'center';
    ctx.fillText('Game Over!', canvas.width/2, canvas.height/2 - 10);
    ctx.fillStyle = '#00d4ff'; ctx.font = '20px Inter';
    ctx.fillText('Score: ' + score, canvas.width/2, canvas.height/2 + 20);
  }
  function startGame() {
    resetBoard(); score = 0; lines = 0; running = true;
    var se = document.getElementById('tet-score'); if (se) se.textContent = '0';
    var le = document.getElementById('tet-lines'); if (le) le.textContent = '0';
    piece = newPiece(); draw();
    if (window._gameInterval) clearInterval(window._gameInterval);
    window._gameInterval = setInterval(tick, 500);
  }

  if (window._gameKeyHandler) document.removeEventListener('keydown', window._gameKeyHandler);
  window._gameKeyHandler = function(e) {
    if (!running || !piece) return;
    if (e.key === 'ArrowLeft' && valid(piece, -1, 0)) { piece.x--; draw(); e.preventDefault(); }
    else if (e.key === 'ArrowRight' && valid(piece, 1, 0)) { piece.x++; draw(); e.preventDefault(); }
    else if (e.key === 'ArrowDown') { if (valid(piece, 0, 1)) { piece.y++; draw(); } e.preventDefault(); }
    else if (e.key === 'ArrowUp') { rotate(); draw(); e.preventDefault(); }
    else if (e.key === ' ') { while (valid(piece, 0, 1)) piece.y++; lock(); clearLines(); piece = newPiece(); if (!valid(piece, 0, 0)) gameOver(); draw(); e.preventDefault(); }
  };
  document.addEventListener('keydown', window._gameKeyHandler);
  document.getElementById('tet-start').onclick = startGame;
  resetBoard(); draw();
}

// ========== STATS ==========
function updateStats() {
  const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
  el('stat-pages', stats.pagesVisited || 0);
  el('stat-tabs', stats.tabsOpened || 0);
  el('stat-games', stats.gamesPlayed || 0);
  el('stat-time', Math.floor((Date.now() - startTime) / 60000));
  el('stat-install-date', stats.installDate ? new Date(stats.installDate).toLocaleDateString('ar-IQ') : '-');
  el('stat-last-visit', stats.lastVisit ? new Date(stats.lastVisit).toLocaleString('ar-IQ') : '-');
  const histEl = document.getElementById('stat-history');
  if (histEl) {
    histEl.innerHTML = '';
    (stats.visitHistory || []).slice(0, 15).forEach(url => {
      const d = document.createElement('div');
      d.className = 'history-item';
      d.textContent = url;
      histEl.appendChild(d);
    });
  }
}

function startTimer() {
  setInterval(() => {
    const e = document.getElementById('stat-time');
    if (e) e.textContent = Math.floor((Date.now() - startTime) / 60000);
  }, 60000);
}

// ========== EVENT LISTENERS ==========
function setupEventListeners() {
  // Titlebar
  var btnMin = document.getElementById('btn-minimize');
  var btnMax = document.getElementById('btn-maximize');
  var btnCls = document.getElementById('btn-close');
  if (btnMin) btnMin.addEventListener('click', function(e) { e.stopPropagation(); window.openBrowser.minimize(); });
  if (btnMax) btnMax.addEventListener('click', function(e) { e.stopPropagation(); window.openBrowser.maximize(); });
  if (btnCls) btnCls.addEventListener('click', function(e) { e.stopPropagation(); window.openBrowser.close(); });

  // Nav
  document.getElementById('btn-back').onclick = () => goBack();
  document.getElementById('btn-forward').onclick = () => goForward();
  document.getElementById('btn-reload').onclick = () => {
    const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`);
    if (wv) wv.reload();
  };
  document.getElementById('btn-home').onclick = () => {
    const tab = tabs.find(t => t.id === currentTabId);
    if (tab && tab.url && tab.url.startsWith('http')) {
      navigateTo('openbrowser://new-tab');
    } else {
      navigateTo('openbrowser://new-tab');
    }
  };

  // URL input
  const urlInput = document.getElementById('url-input');
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { navigateTo(urlInput.value.trim()); urlInput.blur(); }
  });
  urlInput.addEventListener('focus', () => urlInput.select());
  document.getElementById('btn-go').onclick = () => navigateTo(urlInput.value.trim());

  // Tabs
  document.getElementById('btn-add-tab').onclick = () => createTab();
  document.getElementById('tabs-container').addEventListener('click', (e) => {
    const closeBtn = e.target.closest('.tab-close');
    if (closeBtn) { closeTab(parseInt(closeBtn.dataset.close)); return; }
    const tab = e.target.closest('.tab');
    if (tab) switchTab(parseInt(tab.dataset.tabId));
  });
  // كليك يمين على التاب يفتح قائمة (تكرار / إغلاق الباقي)
  document.getElementById('tabs-container').addEventListener('contextmenu', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab) return;
    e.preventDefault();
    showTabContextMenu(e.clientX, e.clientY, parseInt(tab.dataset.tabId));
  });

  // شريط البحث داخل الصفحة
  document.getElementById('find-close')?.addEventListener('click', closeFindBar);
  document.getElementById('find-next')?.addEventListener('click', () => doFind(true));
  document.getElementById('find-prev')?.addEventListener('click', () => doFind(false));
  document.getElementById('find-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); doFind(!e.shiftKey); }
    if (e.key === 'Escape') { e.preventDefault(); closeFindBar(); }
  });

  // Panels
  document.getElementById('btn-settings').onclick = function() { navigateTo('openbrowser://settings'); };
  document.getElementById('btn-lang').onclick = function() { toggleLang(); };
  document.getElementById('btn-bookmark').onclick = function() {
    var tab = tabs.find(function(t) { return t.id === currentTabId; });
    if (!tab || !tab.url) return;
    if (isBookmarked(tab.url)) { removeBookmark(tab.url); }
    else { addBookmark(tab.url, tab.title); }
  };

  // NTP clicks
  document.addEventListener('click', (e) => {
    const shortcut = e.target.closest('.shortcut');
    if (shortcut?.dataset.url) navigateTo(shortcut.dataset.url);
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.classList.contains('ntp-search-input') && e.key === 'Enter') {
      navigateTo(e.target.value.trim());
    }
  });

  // Outside click closes panels
  // (stats panel removed)

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // لو شريط البحث مفتوح، ما نخلي اختصارات ثانية (زي Ctrl+T) تتعارض وياه
    const findOpen = document.getElementById('find-bar')?.classList.contains('open');

    if (e.ctrlKey && !e.shiftKey && e.key === 't') { e.preventDefault(); createTab(); }
    if (e.ctrlKey && e.key === 'w') { e.preventDefault(); closeTab(currentTabId); }
    if (e.ctrlKey && e.key === 'l') { e.preventDefault(); document.getElementById('url-input').focus(); }
    if (e.ctrlKey && e.key === 'r') { e.preventDefault(); document.getElementById('btn-reload')?.click(); }
    if (e.key === 'F5') { e.preventDefault(); document.getElementById('btn-reload')?.click(); }

    // 1) استرجاع آخر تاب مسكر
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 't') { e.preventDefault(); reopenClosedTab(); }

    // 2) التنقل بين التابات
    if (e.ctrlKey && e.key === 'Tab') { e.preventDefault(); cycleTab(e.shiftKey ? -1 : 1); }
    if (e.ctrlKey && !e.shiftKey && e.key === 'PageDown') { e.preventDefault(); cycleTab(1); }
    if (e.ctrlKey && !e.shiftKey && e.key === 'PageUp') { e.preventDefault(); cycleTab(-1); }

    // 3) تكبير وتصغير الصفحة
    if (e.ctrlKey && (e.key === '=' || e.key === '+')) { e.preventDefault(); setZoom('in'); }
    if (e.ctrlKey && e.key === '-') { e.preventDefault(); setZoom('out'); }
    if (e.ctrlKey && e.key === '0') { e.preventDefault(); setZoom('reset'); }

    // 4) بحث داخل الصفحة
    if (e.ctrlKey && e.key === 'f') { e.preventDefault(); openFindBar(); }
    if (e.key === 'Escape' && findOpen) { closeFindBar(); }
  });
}

// ========== البحث داخل الصفحة (Ctrl+F) ==========
function getCurrentWebview() {
  return document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`);
}

function openFindBar() {
  const bar = document.getElementById('find-bar');
  bar.classList.add('open');
  const input = document.getElementById('find-input');
  input.focus();
  input.select();
}

function closeFindBar() {
  const bar = document.getElementById('find-bar');
  bar.classList.remove('open');
  const wv = getCurrentWebview();
  if (wv && wv.stopFindInPage) wv.stopFindInPage('clearSelection');
  document.getElementById('find-count').textContent = '0/0';
}

function doFind(forward) {
  const text = document.getElementById('find-input').value;
  const wv = getCurrentWebview();
  if (!wv || !text) return;
  wv.findInPage(text, { forward: forward !== false, findNext: true });
}

// ========== قائمة كليك يمين على التاب ==========
function duplicateTab(id) {
  const tab = tabs.find(t => t.id === id);
  if (tab && tab.url) createTab(tab.url);
}

function closeOtherTabs(id) {
  const others = tabs.filter(t => t.id !== id).map(t => t.id);
  others.forEach(closeTab);
}

function showTabContextMenu(x, y, tabId) {
  closeTabContextMenu();
  const menu = document.createElement('div');
  menu.className = 'tab-context-menu';
  menu.id = 'tab-context-menu';
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.innerHTML = `
    <div class="ctx-item" data-action="duplicate">تكرار التبويب</div>
    <div class="ctx-item" data-action="close-others">إغلاق باقي التبويبات</div>
  `;
  document.body.appendChild(menu);
  menu.addEventListener('click', (e) => {
    const item = e.target.closest('.ctx-item');
    if (!item) return;
    if (item.dataset.action === 'duplicate') duplicateTab(tabId);
    if (item.dataset.action === 'close-others') closeOtherTabs(tabId);
    closeTabContextMenu();
  });
  // نسكر القائمة لو ضغط بمكان ثاني
  setTimeout(() => document.addEventListener('click', closeTabContextMenu, { once: true }), 0);
}

function closeTabContextMenu() {
  document.getElementById('tab-context-menu')?.remove();
}

function togglePanel(id) {
  const panel = document.getElementById(id);
  const wasOpen = panel.classList.contains('open');
  closePanel('stats-panel');
  if (!wasOpen) panel.classList.add('open');
}

function closePanel(id) {
  document.getElementById(id)?.classList.remove('open');
}

// ========== BOOT ==========
document.addEventListener('DOMContentLoaded', init);
