import { currentLang, t, toggleLang, initLang } from './i18n';

declare global {
  interface Window {
    openBrowser: {
      privacyPreloadPath: string;
      getSettings: () => Promise<any>;
      saveSettings: (s: any) => Promise<boolean>;
      getStats: () => Promise<any>;
      saveStats: (s: any) => Promise<boolean>;
      minimize: () => Promise<void>;
      maximize: () => Promise<void>;
      close: () => Promise<void>;
      isMaximized: () => Promise<boolean>;
      openExternal: (url: string) => Promise<void>;
      getVersion: () => Promise<string>;
      getUserDataPath: () => Promise<string>;
      getPrivacyStats: () => Promise<any>;
      updatePrivacySettings: (s: any) => Promise<boolean>;
      toggleAdBlocker: (e: boolean) => Promise<boolean>;
      toggleTrackerBlocker: (e: boolean) => Promise<boolean>;
      toggleFingerprintProtection: (e: boolean) => Promise<boolean>;
      // Downloads
      getDownloads: () => Promise<any[]>;
      cancelDownload: (id: string) => Promise<boolean>;
      openDownload: (id: string) => Promise<boolean>;
      showDownloadFolder: () => Promise<boolean>;
      clearDownloads: () => Promise<boolean>;
      onDownloadStarted: (cb: (d: any) => void) => void;
      onDownloadProgress: (cb: (d: any) => void) => void;
      onDownloadDone: (cb: (d: any) => void) => void;
      // History
      getHistory: () => Promise<any[]>;
      addHistory: (url: string, title: string) => Promise<boolean>;
      clearHistory: () => Promise<boolean>;
      removeHistoryEntry: (url: string) => Promise<boolean>;
      // Incognito
      startIncognito: () => Promise<boolean>;
      stopIncognito: () => Promise<boolean>;
      getIncognitoSession: () => Promise<string | null>;
      // Fullscreen
      toggleFullscreen: () => Promise<boolean>;
      isFullscreen: () => Promise<boolean>;
      // Print
      printPage: () => Promise<boolean>;
      // Focus
      focusAddressBar: () => Promise<boolean>;
      onFocusAddressBar: (cb: () => void) => void;
    };
    _gameInterval: any;
    _gameKeyHandler: any;
  }
}

interface Tab {
  id: number;
  title: string;
  url: string;
  navHistory: string[];
  navIndex: number;
  zoom: number;
}

interface Bookmark {
  url: string;
  title: string;
  date: string;
}

let currentTabId: number = 0;
let tabCounter: number = 1;
let tabs: Tab[] = [{ id: 0, title: 'تبويب جديد', url: '', navHistory: [], navIndex: -1, zoom: 1 }];
let closedTabs: { url: string; title: string }[] = [];
let stats: any = {};
let settings: any = {};
let bookmarks: Bookmark[] = [];
let startTime: number = Date.now();
let isIncognito: boolean = false;
let downloadsPanelOpen: boolean = false;

// ========== INIT ==========
async function init(): Promise<void> {
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
function applyTheme(theme: string): void {
  document.documentElement.setAttribute('data-theme', theme);
  settings.theme = theme;
  document.querySelectorAll('.theme-card').forEach(c => c.classList.toggle('active', (c as HTMLElement).dataset.theme === theme));
  window.openBrowser.saveSettings(settings);
}

// ========== INTERNAL PAGES ==========
type PageRenderer = () => string;

const INTERNAL_PAGES: Record<string, PageRenderer | null> = {
  'settings': renderSettingsPage,
  'history': renderHistoryPage,
  'about': renderAboutPage,
  'help': renderHelpPage,
  'bookmarks': renderBookmarksPage,
  'new-tab': null,
  'game-v1': null,
  'game-v2': null
};

function isInternalPage(url: string): boolean {
  return url && url.startsWith('openbrowser://');
}

function getInternalPageId(url: string): string {
  return url.replace('openbrowser://', '');
}

function getInternalPageTitle(url: string): string {
  const id = getInternalPageId(url);
  const map: Record<string, string> = {
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

function renderSettingsPage(): string {
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
            <div class="theme-option ${settings.theme === 'amoled' ? 'active' : ''}" data-theme="amoled"><div class="to-preview amoled-preview"></div><span>AMOLED Dark</span></div>
            <div class="theme-option ${settings.theme === 'dark' ? 'active' : ''}" data-theme="dark"><div class="to-preview dark-preview"></div><span>Dark</span></div>
            <div class="theme-option ${settings.theme === 'midnight' ? 'active' : ''}" data-theme="midnight"><div class="to-preview midnight-preview"></div><span>Midnight Blue</span></div>
            <div class="theme-option ${settings.theme === 'nord' ? 'active' : ''}" data-theme="nord"><div class="to-preview nord-preview"></div><span>Nord</span></div>
            <div class="theme-option ${settings.theme === 'light' ? 'active' : ''}" data-theme="light"><div class="to-preview light-preview"></div><span>Light</span></div>
          </div>
        </div>
        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🏠</span><h3>الصفحة الرئيسية</h3></div>
          <input type="text" class="ip-input" id="ip-homepage" value="${settings.homepage || ''}" placeholder="اتركه فارغاً للصفحة الجديدة">
        </div>
        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🔍</span><h3>محرك البحث الافتراضي</h3></div>
          <div class="radio-group" id="ip-search-engine">
            <label class="radio-option ${settings.searchEngine === 'google' || !settings.searchEngine ? 'active' : ''}" data-value="google"><span class="radio-dot"></span><span>Google</span></label>
            <label class="radio-option ${settings.searchEngine === 'bing' ? 'active' : ''}" data-value="bing"><span class="radio-dot"></span><span>Bing</span></label>
            <label class="radio-option ${settings.searchEngine === 'duckduckgo' ? 'active' : ''}" data-value="duckduckgo"><span class="radio-dot"></span><span>DuckDuckGo</span></label>
            <label class="radio-option ${settings.searchEngine === 'brave' ? 'active' : ''}" data-value="brave"><span class="radio-dot"></span><span>Brave Search</span></label>
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
          <label class="switch-row"><span>الweet Animations</span><input type="checkbox" id="ip-animations" ${settings.enableAnimations !== false ? 'checked' : ''}><span class="toggle-slider"></span></label>
          <label class="switch-row"><span>شريط الإشارات المرجعية</span><input type="checkbox" id="ip-bookmarks" ${settings.showBookmarksBar !== false ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">🛡</span><h3>الخصوصية والأمان</h3></div>
          <label class="switch-row"><span>حجب الإعلانات</span><input type="checkbox" id="ip-adblocker" ${settings.adBlocker !== false ? 'checked' : ''}><span class="toggle-slider"></span></label>
          <label class="switch-row"><span>حجب المتتبعات</span><input type="checkbox" id="ip-trackerblocker" ${settings.trackerBlocker !== false ? 'checked' : ''}><span class="toggle-slider"></span></label>
          <label class="switch-row"><span>حماية البصمة</span><input type="checkbox" id="ip-fingerprint" ${settings.fingerprintProtection !== false ? 'checked' : ''}><span class="toggle-slider"></span></label>
          <div class="privacy-stats" id="privacy-stats-box">
            <div class="ps-row"><span>الإعلانات المحجوبة:</span><strong id="ps-ads">0</strong></div>
            <div class="ps-row"><span>المتتبعات المحجوبة:</span><strong id="ps-trackers">0</strong></div>
          </div>
        </div>
        <div class="settings-card">
          <div class="sc-header"><span class="sc-icon">ℹ️</span><h3>حول OpenBrowser</h3></div>
          <div class="about-block">
            <p><strong>OpenBrowser</strong> v1.0.0</p>
            <p>متصفح خفيف وسريع مبني بـ Electron</p>
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

function renderHistoryPage(): string {
  const isEn = currentLang === 'en';
  return `<div class="internal-page history-page"><div class="ip-header"><div class="ip-icon">📋</div><h1>${isEn ? 'Browsing History' : 'سجل الزيارات'}</h1><p class="ip-sub" id="history-count">...</p></div><div class="ip-content"><div class="history-controls"><input type="text" class="ip-input" id="history-search" placeholder="${isEn ? 'Search history...' : 'بحث في السجل...'}"><button class="ip-btn danger" id="clear-history">${isEn ? 'Clear History' : 'مسح السجل'}</button></div><div class="history-list-internal" id="history-list"><div class="empty-state">${isEn ? 'Loading...' : 'جاري التحميل...'}</div></div></div></div>`;
}

function renderAboutPage(): string {
  return `<div class="internal-page about-page"><div class="ip-header"><img class="ip-header-logo" src="logo.png" alt="OpenBrowser"><h1>OpenBrowser</h1><p class="ip-sub">v1.0.0 - First Release</p></div><div class="ip-content"><div class="about-center"><img class="about-logo-big" src="logo.png" alt="OpenBrowser Logo"><h2>OpenBrowser</h2><p class="about-tagline">Lightweight • Fast • Private • AI-Ready</p><div class="about-features"><div class="af-item"><span>⚡</span><span>خفيف - 153 MB فقط</span></div><div class="af-item"><span>🎨</span><span>5 ثيمات مخصصة</span></div><div class="af-item"><span>🐍</span><span>ألعاب مخفية</span></div><div class="af-item"><span>📊</span><span>إحصائيات مفصلة</span></div></div><p class="about-easter">💡 جرب: openbrowser://game-v1</p></div></div></div>`;
}

function renderHelpPage(): string {
  const isEn = currentLang === 'en';
  const pages = [
    { url: 'openbrowser://settings', icon: '⚙', title: isEn ? 'Settings' : 'الإعدادات', desc: isEn ? 'Customize themes, search, font' : 'تخصيص الثيمات ومحرك البحث' },
    { url: 'openbrowser://history', icon: '📋', title: isEn ? 'History' : 'السجل', desc: isEn ? 'Browsing history' : 'سجل التصفح' },
    { url: 'openbrowser://bookmarks', icon: '⭐', title: isEn ? 'Bookmarks' : 'الإشارات', desc: isEn ? 'Saved bookmarks' : 'الإشارات المحفوظة' },
    { url: 'openbrowser://help', icon: '❓', title: isEn ? 'Help' : 'المساعدة', desc: isEn ? 'Help page' : 'صفحة المساعدة' },
    { url: 'openbrowser://about', icon: 'ℹ', title: isEn ? 'About' : 'حول', desc: isEn ? 'About OpenBrowser' : 'حول المتصفح' },
    { url: 'openbrowser://game-v1', icon: '🐍', title: 'Snake', desc: isEn ? 'Classic snake game' : 'لعبة الثعبان' },
    { url: 'openbrowser://game-v2', icon: '💎', title: 'Tetris', desc: isEn ? 'Block puzzle game' : 'لعبة ترتيب المربعات' }
  ];
  const shortcuts = [
    { keys: 'Ctrl+T', desc: isEn ? 'New Tab' : 'تبويب جديد' },
    { keys: 'Ctrl+W', desc: isEn ? 'Close Tab' : 'إغلاق تبويب' },
    { keys: 'Ctrl+L', desc: isEn ? 'Address Bar' : 'شريط العناوين' },
    { keys: 'Ctrl+P', desc: isEn ? 'Print Page' : 'طباعة الصفحة' },
    { keys: 'F5', desc: isEn ? 'Reload' : 'تحديث' },
    { keys: 'F11', desc: isEn ? 'Fullscreen' : 'شاشة كاملة' }
  ];
  const pagesHtml = pages.map(p => `<div class="help-row" data-url="${p.url}"><span class="help-icon">${p.icon}</span><div class="help-info"><span class="help-title">${p.title}</span><span class="help-desc">${p.desc}</span></div><span class="help-url">${p.url}</span></div>`).join('');
  const shortcutsHtml = shortcuts.map(s => `<div class="shortcut-row"><kbd>${s.keys}</kbd><span>${s.desc}</span></div>`).join('');
  return `<div class="internal-page help-page"><div class="ip-header"><div class="ip-icon">❓</div><h1>${isEn ? 'Help & Commands' : 'المساعدة والأوامر'}</h1><p class="ip-sub">${isEn ? 'All available pages and shortcuts' : 'جميع الصفحات والاختصارات'}</p></div><div class="ip-content"><div class="settings-card"><div class="sc-header"><span class="sc-icon">📄</span><h3>${isEn ? 'Internal Pages' : 'الصفحات الداخلية'}</h3></div><div class="help-list">${pagesHtml}</div></div><div class="settings-card"><div class="sc-header"><span class="sc-icon">⌨</span><h3>${isEn ? 'Shortcuts' : 'الاختصارات'}</h3></div><div class="shortcuts-list">${shortcutsHtml}</div></div></div></div>`;
}

function renderBookmarksPage(): string {
  const isEn = currentLang === 'en';
  const list = bookmarks.map((b: Bookmark, i: number) => `<div class="history-row" data-url="${b.url}"><span class="hr-num">${i + 1}</span><span class="hr-url">${b.title}</span><button class="bm-remove" data-rm="${b.url}">×</button></div>`).join('');
  return `<div class="internal-page bookmarks-page"><div class="ip-header"><div class="ip-icon">⭐</div><h1>${isEn ? 'Bookmarks' : 'الإشارات المرجعية'}</h1><p class="ip-sub">${bookmarks.length} ${isEn ? 'saved' : 'محفوظة'}</p></div><div class="ip-content"><div class="history-list-internal" id="bookmarks-list">${list || '<div class="empty-state">' + (isEn ? 'No bookmarks' : 'لا يوجد إشارات') + '</div>'}</div></div></div>`;
}

// ========== NAVIGATION ==========
function navigateTo(url: string, tabId?: number, isBackForward?: boolean): void {
  const tid = tabId ?? currentTabId;
  const tab = tabs.find(t => t.id === tid);
  if (!tab) return;

  if (tab.url === 'openbrowser://game-v1' && url !== 'openbrowser://game-v1') {
    if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
    if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }
  }

  if (isInternalPage(url)) {
    const pageId = getInternalPageId(url);
    if (pageId === 'new-tab') {
      tab.url = '';
      tab.title = 'تبويب جديد';
      updateTabTitle(tid, tab.title);
      const urlInput = document.getElementById('url-input') as HTMLInputElement;
      if (urlInput) urlInput.value = '';
      updateAddressIcon('');
      const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tid}"]`);
      if (wrapper) wrapper.innerHTML = createNTP(tid);
      return;
    }

    tab.url = url;
    tab.title = getInternalPageTitle(url);
    updateTabTitle(tid, tab.title);
    const urlInput = document.getElementById('url-input') as HTMLInputElement;
    if (urlInput) urlInput.value = url;
    updateAddressIcon(url);

    if (pageId === 'game-v1') {
      stats.gamesPlayed = (stats.gamesPlayed || 0) + 1;
      window.openBrowser.saveStats(stats);
      renderGamePage(tid);
    } else if (pageId === 'game-v2') {
      stats.gamesPlayed = (stats.gamesPlayed || 0) + 1;
      window.openBrowser.saveStats(stats);
      renderGamePageV2(tid);
    } else {
      renderInternalPage(url, tid);
    }

    if (!isBackForward) {
      tab.navHistory = tab.navHistory.slice(0, tab.navIndex + 1);
      tab.navHistory.push(url);
      tab.navIndex = tab.navHistory.length - 1;
    }
    updateNavButtons(tid);
    return;
  }

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    if (url.includes('.') && !url.includes(' ')) {
      url = 'https://' + url;
    } else {
      const engine = settings.searchEngine || 'google';
      const engines: Record<string, string> = {
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
  updateTabTitle(tid, tab.title);
  const urlInput = document.getElementById('url-input') as HTMLInputElement;
  if (urlInput) urlInput.value = url;
  updateAddressIcon(url);
  renderWebview(url, tid);

  if (!isBackForward) {
    tab.navHistory = tab.navHistory.slice(0, tab.navIndex + 1);
    tab.navHistory.push(url);
    tab.navIndex = tab.navHistory.length - 1;
  }
  updateNavButtons(tid);

  stats.pagesVisited = (stats.pagesVisited || 0) + 1;
  stats.lastVisit = new Date().toISOString();
  window.openBrowser.saveStats(stats);
  window.openBrowser.addHistory(url, tab.title);
  updateStats();
}

function renderInternalPage(url: string, tabId: number): void {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`);
  if (!wrapper) return;
  const renderer = INTERNAL_PAGES[getInternalPageId(url)];
  if (renderer) {
    wrapper.innerHTML = (renderer as PageRenderer)();
    setupInternalPageEvents(url, tabId);
  }
}

const FP_INJECT = `(function(){try{Object.defineProperty(navigator,"plugins",{get:function(){return{0:{name:"PDF Viewer"},length:5,item:function(i){return this[i]},namedItem:function(){return null},refresh:function(){}}}});Object.defineProperty(navigator,"languages",{get:function(){return["en-US","en"]}});Object.defineProperty(navigator,"hardwareConcurrency",{get:function(){return 8}});Object.defineProperty(navigator,"deviceMemory",{get:function(){return 8}});Object.defineProperty(navigator,"maxTouchPoints",{get:function(){return 0}});Object.defineProperty(navigator,"webdriver",{get:function(){return false}});}catch(e){}try{var oTD=HTMLCanvasElement.prototype.toDataURL;HTMLCanvasElement.prototype.toDataURL=function(t){if(t==="image/webp")return oTD.apply(this,arguments);var c=this.getContext("2d");if(c){var d;try{d=c.getImageData(0,0,Math.min(this.width,16),Math.min(this.height,16));}catch(e){return oTD.apply(this,arguments);}for(var i=0;i<d.data.length;i+=4){d.data[i]=d.data[i]^((i%7)<1?1:0);d.data[i+1]=d.data[i+1]^((i%11)<1?1:0);d.data[i+2]=d.data[i+2]^((i%13)<1?1:0);}c.putImageData(d,0,0);}return oTD.apply(this,arguments);};}catch(e){}try{var oGP=WebGLRenderingContext.prototype.getParameter;WebGLRenderingContext.prototype.getParameter=function(p){if(p===37445)return"Inc.";if(p===37446)return"Iris OpenGL Engine";return oGP.apply(this,arguments);};}catch(e){}try{var oMT=CanvasRenderingContext2D.prototype.measureText;CanvasRenderingContext2D.prototype.measureText=function(){var r=oMT.apply(this,arguments);var w=r.width;Object.defineProperty(r,"width",{get:function(){return w+Math.random()*0.001}});return r};}catch(e){}try{var oGC=AudioBuffer.prototype.getChannelData;AudioBuffer.prototype.getChannelData=function(ch){var d=oGC.apply(this,arguments);for(var i=0;i<Math.min(d.length,10);i++){d[i]=d[i]+Math.random()*0.0000001;}return d};}catch(e){}})();`;

function renderWebview(url: string, tabId: number): void {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`) as HTMLElement;
  if (!wrapper) return;
  wrapper.innerHTML = '';
  const wv = document.createElement('webview') as any;
  wv.src = url;
  wv.preload = window.openBrowser.privacyPreloadPath;
  wv.style.width = '100%';
  wv.style.height = '100%';
  wv.style.border = 'none';
  wv.addEventListener('did-navigate', (e: any) => {
    const tab = tabs.find(t => t.id === tabId);
    if (tab) tab.url = e.url;
    const urlInput = document.getElementById('url-input') as HTMLInputElement;
    if (urlInput) urlInput.value = e.url;
    updateAddressIcon(e.url);
    updateTabTitle(tabId, e.url.replace(/https?:\/\//, '').split('/')[0]);
  });
  wv.addEventListener('page-title-updated', (e: any) => updateTabTitle(tabId, e.title));
  wv.addEventListener('did-start-loading', () => {});
  wv.addEventListener('did-stop-loading', () => {
    wv.executeJavaScript(FP_INJECT).catch(() => {});
  });
  wrapper.appendChild(wv);
}

function setupInternalPageEvents(url: string, tabId: number): void {
  const pageId = getInternalPageId(url);

  if (pageId === 'settings') {
    document.getElementById('ip-theme-grid')?.addEventListener('click', (e: Event) => {
      const target = (e.target as HTMLElement).closest('.theme-option') as HTMLElement;
      if (target) {
        applyTheme(target.dataset.theme || 'amoled');
        document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
        target.classList.add('active');
      }
    });
    document.getElementById('ip-homepage')?.addEventListener('change', (e: Event) => {
      settings.homepage = (e.target as HTMLInputElement).value;
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-search-engine')?.addEventListener('click', (e: Event) => {
      const opt = (e.target as HTMLElement).closest('.radio-option') as HTMLElement;
      if (opt) {
        settings.searchEngine = opt.dataset.value;
        window.openBrowser.saveSettings(settings);
        document.querySelectorAll('#ip-search-engine .radio-option').forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
      }
    });
    document.getElementById('ip-font-inc')?.addEventListener('click', () => {
      settings.fontSize = Math.min(24, (settings.fontSize || 14) + 2);
      const val = document.getElementById('ip-font-val');
      if (val) val.textContent = settings.fontSize + 'px';
      document.body.style.fontSize = settings.fontSize + 'px';
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-font-dec')?.addEventListener('click', () => {
      settings.fontSize = Math.max(10, (settings.fontSize || 14) - 2);
      const val = document.getElementById('ip-font-val');
      if (val) val.textContent = settings.fontSize + 'px';
      document.body.style.fontSize = settings.fontSize + 'px';
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-animations')?.addEventListener('change', (e: Event) => {
      settings.enableAnimations = (e.target as HTMLInputElement).checked;
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-bookmarks')?.addEventListener('change', (e: Event) => {
      settings.showBookmarksBar = (e.target as HTMLInputElement).checked;
      window.openBrowser.saveSettings(settings);
    });
    document.getElementById('ip-adblocker')?.addEventListener('change', (e: Event) => {
      settings.adBlocker = (e.target as HTMLInputElement).checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleAdBlocker((e.target as HTMLInputElement).checked);
    });
    document.getElementById('ip-trackerblocker')?.addEventListener('change', (e: Event) => {
      settings.trackerBlocker = (e.target as HTMLInputElement).checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleTrackerBlocker((e.target as HTMLInputElement).checked);
    });
    document.getElementById('ip-fingerprint')?.addEventListener('change', (e: Event) => {
      settings.fingerprintProtection = (e.target as HTMLInputElement).checked;
      window.openBrowser.saveSettings(settings);
      window.openBrowser.toggleFingerprintProtection((e.target as HTMLInputElement).checked);
    });
    window.openBrowser.getPrivacyStats().then((ps: any) => {
      const ae = document.getElementById('ps-ads'); if (ae) ae.textContent = ps.adsBlocked;
      const te = document.getElementById('ps-trackers'); if (te) te.textContent = ps.trackersBlocked;
    });
    document.querySelectorAll('.about-link').forEach(link => {
      link.addEventListener('click', () => navigateTo((link as HTMLElement).dataset.url || ''));
    });
  }

  if (pageId === 'history') {
    window.openBrowser.getHistory().then((hist: any[]) => {
      const list = document.getElementById('history-list');
      const countEl = document.getElementById('history-count');
      if (countEl) countEl.textContent = hist.length + (currentLang === 'en' ? ' pages visited' : ' صفحة في السجل');
      if (!list) return;
      if (hist.length === 0) {
        list.innerHTML = '<div class="empty-state">' + (currentLang === 'en' ? 'No history yet' : 'لا يوجد سجل بعد') + '</div>';
        return;
      }
      list.innerHTML = hist.map((h: any, i: number) => {
        const domain = h.url.replace(/https?:\/\//, '').split('/')[0];
        const date = new Date(h.timestamp).toLocaleDateString();
        return `<div class="history-row" data-url="${h.url}"><span class="hr-num">${i + 1}</span><span class="hr-url">${h.title || h.url}</span><span class="hr-domain">${domain}</span><span class="hr-date">${date}</span></div>`;
      }).join('');
      list.querySelectorAll('.history-row').forEach(row => {
        row.addEventListener('click', () => navigateTo((row as HTMLElement).dataset.url || ''));
      });
    });
    document.getElementById('history-search')?.addEventListener('input', (e: Event) => {
      const q = (e.target as HTMLInputElement).value.toLowerCase();
      document.querySelectorAll('.history-row').forEach(row => {
        const url = ((row as HTMLElement).dataset.url || '').toLowerCase();
        const title = (row.querySelector('.hr-url') as HTMLElement)?.textContent?.toLowerCase() || '';
        (row as HTMLElement).style.display = (url.includes(q) || title.includes(q)) ? '' : 'none';
      });
    });
    document.getElementById('clear-history')?.addEventListener('click', () => {
      window.openBrowser.clearHistory().then(() => {
        const list = document.getElementById('history-list');
        if (list) list.innerHTML = '<div class="empty-state">' + (currentLang === 'en' ? 'No history yet' : 'لا يوجد سجل بعد') + '</div>';
        const countEl = document.getElementById('history-count');
        if (countEl) countEl.textContent = '0 ' + (currentLang === 'en' ? 'pages visited' : 'صفحة في السجل');
      });
    });
  }

  if (pageId === 'help') {
    document.querySelectorAll('.help-row').forEach(row => {
      row.addEventListener('click', () => navigateTo((row as HTMLElement).dataset.url || ''));
      (row as HTMLElement).style.cursor = 'pointer';
    });
  }

  if (pageId === 'bookmarks') {
    document.querySelectorAll('.bm-remove').forEach(btn => {
      btn.addEventListener('click', (e: Event) => {
        e.stopPropagation();
        removeBookmark((btn as HTMLElement).dataset.rm || '');
        navigateTo('openbrowser://bookmarks');
      });
    });
    document.querySelectorAll('#bookmarks-list .history-row').forEach(row => {
      row.addEventListener('click', () => navigateTo((row as HTMLElement).dataset.url || ''));
    });
  }
}

function updateNavButtons(tabId: number): void {
  const tab = tabs.find(t => t.id === tabId);
  if (!tab) return;
  const backBtn = document.getElementById('btn-back');
  const fwdBtn = document.getElementById('btn-forward');
  if (backBtn) backBtn.style.opacity = (tab.navIndex > 0) ? '1' : '0.3';
  if (fwdBtn) fwdBtn.style.opacity = (tab.navIndex < (tab.navHistory || []).length - 1) ? '1' : '0.3';
}

function goBack(): void {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab || !tab.navHistory || tab.navIndex <= 0) return;
  tab.navIndex--;
  navigateTo(tab.navHistory[tab.navIndex], currentTabId, true);
}

function goForward(): void {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab || !tab.navHistory || tab.navIndex >= tab.navHistory.length - 1) return;
  tab.navIndex++;
  navigateTo(tab.navHistory[tab.navIndex], currentTabId, true);
}

function updateTabTitle(id: number, title: string): void {
  const tab = tabs.find(t => t.id === id);
  if (tab) tab.title = title;
  const tabEl = document.querySelector(`.tab[data-tab-id="${id}"] .tab-title`);
  if (tabEl) tabEl.textContent = title;
}

function updateAddressIcon(url: string): void {
  const icon = document.getElementById('address-icon');
  if (!icon) return;
  if (!url) { icon.textContent = '🔍'; return; }
  if (url.startsWith('https://')) icon.textContent = '🔒';
  else if (url.startsWith('http://')) icon.textContent = '⚠️';
  else if (url.startsWith('openbrowser://')) icon.textContent = '⚡';
  else icon.textContent = '🌐';
}

// ========== TABS ==========
function createTab(url?: string): void {
  const id = tabCounter++;
  tabs.push({ id, title: 'تبويب جديد', url: '', navHistory: [], navIndex: -1, zoom: 1 });

  const tabEl = document.createElement('div');
  tabEl.className = 'tab';
  tabEl.dataset.tabId = String(id);
  tabEl.draggable = true;
  tabEl.innerHTML = `<span class="tab-title">تبويب جديد</span><button class="tab-close" data-close="${id}">×</button>`;
  document.getElementById('tabs-container')?.appendChild(tabEl);

  const wrapper = document.createElement('div');
  wrapper.className = 'webview-wrapper';
  wrapper.dataset.tabId = String(id);
  wrapper.innerHTML = createNTP(id);
  document.getElementById('content-area')?.appendChild(wrapper);

  switchTab(id);
  stats.tabsOpened = (stats.tabsOpened || 0) + 1;
  window.openBrowser.saveStats(stats);
  if (url) navigateTo(url, id);
}

function switchTab(id: number): void {
  currentTabId = id;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', parseInt((t as HTMLElement).dataset.tabId || '0') === id));
  document.querySelectorAll('.webview-wrapper').forEach(w => w.classList.toggle('active', parseInt((w as HTMLElement).dataset.tabId || '0') === id));
  const tab = tabs.find(t => t.id === id);
  if (tab) {
    const urlInput = document.getElementById('url-input') as HTMLInputElement;
    if (urlInput) urlInput.value = tab.url || '';
    updateAddressIcon(tab.url);
  }
  updateNavButtons(id);
  updateBookmarkButton();

  const wv = document.querySelector(`.webview-wrapper[data-tab-id="${id}"] webview`) as any;
  if (wv && tab) {
    const applyZoom = () => wv.setZoomFactor(tab.zoom || 1);
    if (wv.getWebContentsId) { try { applyZoom(); } catch (e) {} }
    else wv.addEventListener('dom-ready', applyZoom, { once: true });
  }
}

function setZoom(action: string): void {
  const tab = tabs.find(t => t.id === currentTabId);
  if (!tab) return;
  if (action === 'in') tab.zoom = Math.min(3, +((tab.zoom || 1) + 0.1).toFixed(2));
  else if (action === 'out') tab.zoom = Math.max(0.3, +((tab.zoom || 1) - 0.1).toFixed(2));
  else tab.zoom = 1;
  const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`) as any;
  if (wv) wv.setZoomFactor(tab.zoom);
}

function closeTab(id: number): void {
  if (tabs.length === 1) return;
  const idx = tabs.findIndex(t => t.id === id);
  const closedTab = tabs[idx];
  if (closedTab && closedTab.url) {
    closedTabs.push({ url: closedTab.url, title: closedTab.title });
    if (closedTabs.length > 15) closedTabs.shift();
  }
  tabs.splice(idx, 1);
  document.querySelector(`.tab[data-tab-id="${id}"]`)?.remove();
  document.querySelector(`.webview-wrapper[data-tab-id="${id}"]`)?.remove();
  if (currentTabId === id) {
    switchTab(tabs[Math.min(idx, tabs.length - 1)].id);
  }
}

function reopenClosedTab(): void {
  const last = closedTabs.pop();
  if (last) createTab(last.url);
}

function cycleTab(direction: number): void {
  if (tabs.length < 2) return;
  const idx = tabs.findIndex(t => t.id === currentTabId);
  const nextIdx = (idx + direction + tabs.length) % tabs.length;
  switchTab(tabs[nextIdx].id);
}

function createNTP(tabId: number): string {
  const isEn = currentLang === 'en';
  return `<div class="new-tab-page" id="ntp-${tabId}"><div class="ntp-content"><img class="ntp-logo-img" src="logo.png" alt="OpenBrowser"><div class="ntp-search"><input type="text" class="ntp-search-input" placeholder="${t('search')}"></div><div class="ntp-shortcuts"><div class="shortcut" data-url="https://google.com"><div class="shortcut-icon">G</div><span>Google</span></div><div class="shortcut" data-url="https://youtube.com"><div class="shortcut-icon">Y</div><span>YouTube</span></div><div class="shortcut" data-url="https://github.com"><div class="shortcut-icon">H</div><span>GitHub</span></div><div class="shortcut" data-url="openbrowser://settings"><div class="shortcut-icon">⚙</div><span>${t('settings')}</span></div><div class="shortcut" data-url="openbrowser://bookmarks"><div class="shortcut-icon">⭐</div><span>${isEn ? 'Bookmarks' : 'الإشارات'}</span></div><div class="shortcut" data-url="openbrowser://history"><div class="shortcut-icon">📋</div><span>${t('history')}</span></div><div class="shortcut" data-url="openbrowser://game-v1"><div class="shortcut-icon">🐍</div><span>Snake</span></div><div class="shortcut" data-url="openbrowser://game-v2"><div class="shortcut-icon">💎</div><span>Tetris</span></div><div class="shortcut" data-url="openbrowser://help"><div class="shortcut-icon">❓</div><span>${isEn ? 'Help' : 'مساعدة'}</span></div></div><div class="ntp-footer"><span>v1.0.0 • ${isEn ? 'Lightweight • Fast • Private' : 'خفيف • سريع • خاص'}</span></div></div></div>`;
}

// ========== BOOKMARKS ==========
function saveBookmarks(): void { localStorage.setItem('ob-bookmarks', JSON.stringify(bookmarks)); }

function addBookmark(url: string, title: string): void {
  if (!url || bookmarks.find(b => b.url === url)) return;
  bookmarks.unshift({ url, title: title || url, date: new Date().toISOString() });
  saveBookmarks();
  updateBookmarkButton();
}

function removeBookmark(url: string): void {
  bookmarks = bookmarks.filter(b => b.url !== url);
  saveBookmarks();
  updateBookmarkButton();
}

function isBookmarked(url: string): boolean {
  return bookmarks.some(b => b.url === url);
}

function updateBookmarkButton(): void {
  const btn = document.getElementById('btn-bookmark');
  if (!btn) return;
  const tab = tabs.find(t => t.id === currentTabId);
  const url = tab ? tab.url : '';
  const bm = isBookmarked(url);
  btn.classList.toggle('active', bm);
  btn.innerHTML = bm
    ? '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 2h10v12l-5-3-5 3V2z" fill="currentColor"/></svg>'
    : '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 2h10v12l-5-3-5 3V2z" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
}

// ========== GAME SNAKE ==========
function renderGamePage(tabId: number): void {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`) as HTMLElement;
  if (!wrapper) return;
  if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
  if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }

  wrapper.innerHTML = `<div class="game-page"><div class="game-header-bar"><span class="game-title">🐍 Snake Game</span><span class="game-badge">Easter Egg v1</span></div><div class="game-info-bar"><span>النقاط: <strong id="game-score">0</strong></span><span>الأعلى: <strong id="game-hs">${parseInt(localStorage.getItem('snake-hs') || '0')}</strong></span></div><canvas id="game-canvas" width="400" height="400" tabindex="0"></canvas><div class="game-controls-info"><p>الأسهم أو WASD للتحكم</p><button class="game-start-btn" id="game-start-btn">▶ ابدأ اللعب</button></div></div>`;
  initSnakeGame();
}

function initSnakeGame(): void {
  const canvas = document.getElementById('game-canvas') as HTMLCanvasElement;
  if (!canvas) return;
  const ctx = canvas.getContext('2d')!;
  const grid = 20;
  const cells = canvas.width / grid;
  let snake: { x: number; y: number }[], food: { x: number; y: number }, dir: { x: number; y: number }, nextDir: { x: number; y: number }, score: number, running: boolean;

  // Expose game state for AI control
  (window as any)._snakeGame = {
    getState: () => ({ snake: [...snake], food: { ...food }, dir: { ...dir }, score, running, cells }),
    setDirection: (x: number, y: number) => { if (running) nextDir = { x, y }; },
    start: () => startGame(),
    isRunning: () => running
  };

  function reset(): void {
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

  function placeFood(): void {
    food = { x: Math.floor(Math.random() * cells), y: Math.floor(Math.random() * cells) };
    for (const s of snake) { if (s.x === food.x && s.y === food.y) return placeFood(); }
  }

  function draw(): void {
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

  function update(): void {
    dir = { ...nextDir };
    const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };
    if (head.x < 0 || head.x >= cells || head.y < 0 || head.y >= cells) return gameOver();
    for (const s of snake) { if (s.x === head.x && s.y === head.y) return gameOver(); }
    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) {
      score += 10;
      const se = document.getElementById('game-score'); if (se) se.textContent = String(score);
      placeFood();
    } else { snake.pop(); }
  }

  function gameOver(): void {
    running = false;
    if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
    const hs = parseInt(localStorage.getItem('snake-hs') || '0');
    if (score > hs) {
      localStorage.setItem('snake-hs', String(score));
      const hse = document.getElementById('game-hs'); if (hse) hse.textContent = String(score);
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
  }

  function startGame(): void {
    reset();
    running = true;
    canvas.focus();
    if (window._gameInterval) clearInterval(window._gameInterval);
    window._gameInterval = setInterval(() => { if (running) { update(); draw(); } }, 120);
  }

  if (window._gameKeyHandler) document.removeEventListener('keydown', window._gameKeyHandler);
  window._gameKeyHandler = (e: KeyboardEvent) => {
    if (!running) return;
    if (e.key === 'ArrowUp' && dir.y !== 1) { nextDir = { x: 0, y: -1 }; e.preventDefault(); }
    else if (e.key === 'ArrowDown' && dir.y !== -1) { nextDir = { x: 0, y: 1 }; e.preventDefault(); }
    else if (e.key === 'ArrowLeft' && dir.x !== 1) { nextDir = { x: -1, y: 0 }; e.preventDefault(); }
    else if (e.key === 'ArrowRight' && dir.x !== -1) { nextDir = { x: 1, y: 0 }; e.preventDefault(); }
    else if (e.key === 'w' || e.key === 'W') { if (dir.y !== 1) { nextDir = { x: 0, y: -1 }; e.preventDefault(); } }
    else if (e.key === 's' || e.key === 'S') { if (dir.y !== -1) { nextDir = { x: 0, y: 1 }; e.preventDefault(); } }
    else if (e.key === 'a' || e.key === 'A') { if (dir.x !== 1) { nextDir = { x: -1, y: 0 }; e.preventDefault(); } }
    else if (e.key === 'd' || e.key === 'D') { if (dir.x !== -1) { nextDir = { x: 1, y: 0 }; e.preventDefault(); } }
  };
  document.addEventListener('keydown', window._gameKeyHandler);

  document.getElementById('game-start-btn')?.addEventListener('click', startGame);
  canvas.focus();
  reset();
}

// ========== GAME V2 - TETRIS ==========
function renderGamePageV2(tabId: number): void {
  const wrapper = document.querySelector(`.webview-wrapper[data-tab-id="${tabId}"]`) as HTMLElement;
  if (!wrapper) return;
  if (window._gameInterval) { clearInterval(window._gameInterval); window._gameInterval = null; }
  if (window._gameKeyHandler) { document.removeEventListener('keydown', window._gameKeyHandler); window._gameKeyHandler = null; }
  const isEn = currentLang === 'en';
  wrapper.innerHTML = `<div class="game-page"><div class="game-header-bar"><span class="game-title">💎 Tetris</span><span class="game-badge">Easter Egg v1</span></div><div class="game-info-bar"><span>${isEn ? 'Score' : 'النقاط'}: <strong id="tet-score">0</strong></span><span>${isEn ? 'Lines' : 'الخطوط'}: <strong id="tet-lines">0</strong></span></div><canvas id="tet-canvas" width="300" height="600"></canvas><div class="game-controls-info"><p>${isEn ? 'Arrow keys to move/rotate, Down to drop' : 'الأسهم للتحريك، السفل للإسقاط'}</p><button class="game-start-btn" id="tet-start">${isEn ? '▶ Start' : '▶ ابدأ'}</button></div></div>`;
  initTetrisGame();
}

function initTetrisGame(): void {
  const canvas = document.getElementById('tet-canvas') as HTMLCanvasElement;
  if (!canvas) return;
  const ctx = canvas.getContext('2d')!;
  const COLS = 10, ROWS = 20, SIZE = 30;
  let board: any[] = [], piece: any, score = 0, lines = 0, running = false;
  const PIECES = [
    { shape: [[1,1,1,1]], color: '#00d4ff' },
    { shape: [[1,1],[1,1]], color: '#ffaa00' },
    { shape: [[0,1,0],[1,1,1]], color: '#aa55ff' },
    { shape: [[1,0,0],[1,1,1]], color: '#00ff88' },
    { shape: [[0,0,1],[1,1,1]], color: '#ff4444' },
    { shape: [[0,1,1],[1,1,0]], color: '#ff6699' },
    { shape: [[1,1,0],[0,1,1]], color: '#ffff00' }
  ];

  // Expose game state for AI control
  (window as any)._tetrisGame = {
    getState: () => ({
      board: board.map((r: any[]) => [...r]),
      piece: piece ? { shape: piece.shape.map((r: any[]) => [...r]), x: piece.x, y: piece.y, color: piece.color } : null,
      score, lines, running, cols: COLS, rows: ROWS
    }),
    moveLeft: () => { if (running && piece && valid(piece, -1, 0)) { piece.x--; draw(); } },
    moveRight: () => { if (running && piece && valid(piece, 1, 0)) { piece.x++; draw(); } },
    moveDown: () => { if (running && piece && valid(piece, 0, 1)) { piece.y++; draw(); } },
    rotate: () => { if (running && piece) { rotate(); draw(); } },
    drop: () => { if (running && piece) { while (valid(piece, 0, 1)) piece.y++; lock(); clearLines(); piece = newPiece(); draw(); if (!valid(piece, 0, 0)) gameOver(); } },
    start: () => startGame(),
    isRunning: () => running
  };

  function resetBoard(): void { board = []; for (let r = 0; r < ROWS; r++) board.push(new Array(COLS).fill(0)); }
  function newPiece(): any {
    const p = PIECES[Math.floor(Math.random() * PIECES.length)];
    return { shape: p.shape.map(r => r.slice()), color: p.color, x: 3, y: 0 };
  }
  function valid(p: any, dx: number, dy: number): boolean {
    for (let r = 0; r < p.shape.length; r++)
      for (let c = 0; c < p.shape[r].length; c++)
        if (p.shape[r][c]) {
          const nx = p.x + c + dx, ny = p.y + r + dy;
          if (nx < 0 || nx >= COLS || ny >= ROWS) return false;
          if (ny >= 0 && board[ny][nx]) return false;
        }
    return true;
  }
  function lock(): void {
    for (let r = 0; r < piece.shape.length; r++)
      for (let c = 0; c < piece.shape[r].length; c++)
        if (piece.shape[r][c] && piece.y + r >= 0) board[piece.y + r][piece.x + c] = piece.color;
  }
  function clearLines(): void {
    let cleared = 0;
    for (let r = ROWS - 1; r >= 0; r--) {
      if (board[r].every((c: any) => c !== 0)) {
        board.splice(r, 1);
        board.unshift(new Array(COLS).fill(0));
        cleared++; r++;
      }
    }
    if (cleared > 0) {
      lines += cleared;
      score += cleared * 10 * cleared;
      const se = document.getElementById('tet-score'); if (se) se.textContent = String(score);
      const le = document.getElementById('tet-lines'); if (le) le.textContent = String(lines);
    }
  }
  function rotate(): void {
    const rotated: any[] = [];
    for (let c = 0; c < piece.shape[0].length; c++) {
      const row: any[] = [];
      for (let r = piece.shape.length - 1; r >= 0; r--) row.push(piece.shape[r][c]);
      rotated.push(row);
    }
    if (valid({ shape: rotated, x: piece.x, y: piece.y }, 0, 0)) piece.shape = rotated;
  }
  function draw(): void {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#111';
    for (let r = 0; r <= ROWS; r++) { ctx.beginPath(); ctx.moveTo(0, r * SIZE); ctx.lineTo(canvas.width, r * SIZE); ctx.stroke(); }
    for (let c = 0; c <= COLS; c++) { ctx.beginPath(); ctx.moveTo(c * SIZE, 0); ctx.lineTo(c * SIZE, canvas.height); ctx.stroke(); }
    for (let r = 0; r < ROWS; r++)
      for (let c = 0; c < COLS; c++)
        if (board[r][c]) { ctx.fillStyle = board[r][c]; ctx.fillRect(c * SIZE + 1, r * SIZE + 1, SIZE - 2, SIZE - 2); }
    if (piece) {
      ctx.fillStyle = piece.color;
      for (let r = 0; r < piece.shape.length; r++)
        for (let c = 0; c < piece.shape[r].length; c++)
          if (piece.shape[r][c]) ctx.fillRect((piece.x + c) * SIZE + 1, (piece.y + r) * SIZE + 1, SIZE - 2, SIZE - 2);
    }
  }
  function tick(): void {
    if (!running) return;
    if (valid(piece, 0, 1)) { piece.y++; }
    else { lock(); clearLines(); piece = newPiece(); if (!valid(piece, 0, 0)) gameOver(); }
    draw();
  }
  function gameOver(): void {
    running = false; clearInterval(window._gameInterval);
    ctx.fillStyle = 'rgba(0,0,0,0.75)'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ff4444'; ctx.font = 'bold 36px Inter'; ctx.textAlign = 'center';
    ctx.fillText('Game Over!', canvas.width / 2, canvas.height / 2 - 10);
    ctx.fillStyle = '#00d4ff'; ctx.font = '20px Inter';
    ctx.fillText('Score: ' + score, canvas.width / 2, canvas.height / 2 + 20);
  }
  function startGame(): void {
    resetBoard(); score = 0; lines = 0; running = true;
    const se = document.getElementById('tet-score'); if (se) se.textContent = '0';
    const le = document.getElementById('tet-lines'); if (le) le.textContent = '0';
    piece = newPiece(); draw();
    if (window._gameInterval) clearInterval(window._gameInterval);
    window._gameInterval = setInterval(tick, 500);
  }

  if (window._gameKeyHandler) document.removeEventListener('keydown', window._gameKeyHandler);
  window._gameKeyHandler = (e: KeyboardEvent) => {
    if (!running || !piece) return;
    if (e.key === 'ArrowLeft' && valid(piece, -1, 0)) { piece.x--; draw(); e.preventDefault(); }
    else if (e.key === 'ArrowRight' && valid(piece, 1, 0)) { piece.x++; draw(); e.preventDefault(); }
    else if (e.key === 'ArrowDown') { if (valid(piece, 0, 1)) { piece.y++; draw(); } e.preventDefault(); }
    else if (e.key === 'ArrowUp') { rotate(); draw(); e.preventDefault(); }
    else if (e.key === ' ') { while (valid(piece, 0, 1)) piece.y++; lock(); clearLines(); piece = newPiece(); if (!valid(piece, 0, 0)) gameOver(); draw(); e.preventDefault(); }
  };
  document.addEventListener('keydown', window._gameKeyHandler);
  document.getElementById('tet-start')?.addEventListener('click', startGame);
  resetBoard(); draw();
}

// ========== STATS ==========
function updateStats(): void {
  const el = (id: string, val: string | number) => { const e = document.getElementById(id); if (e) e.textContent = String(val); };
  el('stat-pages', stats.pagesVisited || 0);
  el('stat-tabs', stats.tabsOpened || 0);
  el('stat-games', stats.gamesPlayed || 0);
  el('stat-time', Math.floor((Date.now() - startTime) / 60000));
}

function startTimer(): void {
  setInterval(() => {
    const e = document.getElementById('stat-time');
    if (e) e.textContent = String(Math.floor((Date.now() - startTime) / 60000));
  }, 60000);
}

function closeFindBar(): void {
  const bar = document.getElementById('find-bar');
  if (bar) bar.style.display = 'none';
}

function doFind(forward: boolean): void {
  const input = document.getElementById('find-input') as HTMLInputElement;
  const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`) as any;
  if (input && wv && wv.findInPage) {
    wv.findInPage(input.value, { forward, findNext: true });
  }
}

function showTabContextMenu(x: number, y: number, tabId: number): void {
  let existing = document.getElementById('tab-context-menu');
  if (existing) existing.remove();
  const menu = document.createElement('div');
  menu.id = 'tab-context-menu';
  menu.className = 'context-menu';
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.innerHTML = `<div class="context-menu-item" data-action="duplicate">تكرار التبويب</div><div class="context-menu-item" data-action="close-others">إغلاق الباقي</div>`;
  document.body.appendChild(menu);
  menu.addEventListener('click', (e) => {
    const action = (e.target as HTMLElement).dataset.action;
    if (action === 'duplicate') createTab(tabs.find(t => t.id === tabId)?.url);
    if (action === 'close-others') {
      tabs.filter(t => t.id !== tabId).forEach(t => {
        document.querySelector(`.tab[data-tab-id="${t.id}"]`)?.remove();
        document.querySelector(`.webview-wrapper[data-tab-id="${t.id}"]`)?.remove();
      });
      tabs = tabs.filter(t => t.id === tabId);
      switchTab(tabId);
    }
    menu.remove();
  });
  setTimeout(() => {
    document.addEventListener('click', () => menu.remove(), { once: true });
  }, 10);
}

// ========== EVENT LISTENERS ==========
function setupEventListeners(): void {
  const btnMin = document.getElementById('btn-minimize');
  const btnMax = document.getElementById('btn-maximize');
  const btnCls = document.getElementById('btn-close');
  if (btnMin) btnMin.addEventListener('click', (e: Event) => { e.stopPropagation(); window.openBrowser.minimize(); });
  if (btnMax) btnMax.addEventListener('click', (e: Event) => { e.stopPropagation(); window.openBrowser.maximize(); });
  if (btnCls) btnCls.addEventListener('click', (e: Event) => { e.stopPropagation(); window.openBrowser.close(); });

  const btnBack = document.getElementById('btn-back');
  const btnForward = document.getElementById('btn-forward');
  const btnReload = document.getElementById('btn-reload');
  const btnHome = document.getElementById('btn-home');
  if (btnBack) btnBack.addEventListener('click', () => goBack());
  if (btnForward) btnForward.addEventListener('click', () => goForward());
  if (btnReload) btnReload.addEventListener('click', () => {
    const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`) as any;
    if (wv) wv.reload();
  });
  if (btnHome) btnHome.addEventListener('click', () => navigateTo('openbrowser://new-tab'));

  const urlInput = document.getElementById('url-input') as HTMLInputElement;
  if (urlInput) {
    urlInput.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter') { navigateTo(urlInput.value.trim()); urlInput.blur(); }
    });
    urlInput.addEventListener('focus', () => urlInput.select());
  }
  const btnGo = document.getElementById('btn-go');
  if (btnGo) btnGo.addEventListener('click', () => navigateTo(urlInput.value.trim()));

  document.getElementById('btn-add-tab')?.addEventListener('click', () => createTab());
  document.getElementById('tabs-container')?.addEventListener('click', (e: Event) => {
    const closeBtn = (e.target as HTMLElement).closest('.tab-close') as HTMLElement;
    if (closeBtn) { closeTab(parseInt(closeBtn.dataset.close || '0')); return; }
    const tab = (e.target as HTMLElement).closest('.tab') as HTMLElement;
    if (tab) switchTab(parseInt(tab.dataset.tabId || '0'));
  });
  document.getElementById('tabs-container')?.addEventListener('contextmenu', (e: Event) => {
    const tab = (e.target as HTMLElement).closest('.tab') as HTMLElement;
    if (!tab) return;
    e.preventDefault();
    showTabContextMenu((e as MouseEvent).clientX, (e as MouseEvent).clientY, parseInt(tab.dataset.tabId || '0'));
  });

  document.getElementById('find-close')?.addEventListener('click', closeFindBar);
  document.getElementById('find-next')?.addEventListener('click', () => doFind(true));
  document.getElementById('find-prev')?.addEventListener('click', () => doFind(false));

  document.getElementById('btn-settings')?.addEventListener('click', () => navigateTo('openbrowser://settings'));
  document.getElementById('btn-lang')?.addEventListener('click', () => toggleLang());
  document.getElementById('btn-bookmark')?.addEventListener('click', () => {
    const tab = tabs.find(t => t.id === currentTabId);
    if (!tab || !tab.url) return;
    if (isBookmarked(tab.url)) removeBookmark(tab.url);
    else addBookmark(tab.url, tab.title);
  });

  document.addEventListener('click', (e: Event) => {
    const shortcut = (e.target as HTMLElement).closest('.shortcut') as HTMLElement;
    if (shortcut?.dataset.url) navigateTo(shortcut.dataset.url);
  });

  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === 't') { e.preventDefault(); createTab(); }
    if (e.ctrlKey && e.key === 'w') { e.preventDefault(); closeTab(currentTabId); }
    if (e.ctrlKey && e.key === 'l') { e.preventDefault(); urlInput?.focus(); }
    if (e.ctrlKey && e.shiftKey && e.key === 'T') { e.preventDefault(); reopenClosedTab(); }
    if (e.ctrlKey && (e.key === 'PageUp' || e.key === 'Tab')) { e.preventDefault(); cycleTab(-1); }
    if (e.ctrlKey && (e.key === 'PageDown' || (e.shiftKey && e.key === 'Tab'))) { e.preventDefault(); cycleTab(1); }
    if (e.ctrlKey && e.key === '=') { e.preventDefault(); setZoom('in'); }
    if (e.ctrlKey && e.key === '-') { e.preventDefault(); setZoom('out'); }
    if (e.ctrlKey && e.key === '0') { e.preventDefault(); setZoom('reset'); }
    if (e.key === 'F5') { e.preventDefault(); const wv = document.querySelector(`.webview-wrapper[data-tab-id="${currentTabId}"] webview`) as any; if (wv) wv.reload(); }
    if (e.key === 'F11') { e.preventDefault(); window.openBrowser.toggleFullscreen(); }
    if (e.ctrlKey && e.key === 'p') { e.preventDefault(); window.openBrowser.printPage(); }
    if (e.ctrlKey && e.key === 'f') {
      e.preventDefault();
      const bar = document.getElementById('find-bar');
      if (bar) bar.style.display = 'flex';
      document.getElementById('find-input')?.focus();
    }
  });

  // NTP search
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      const ntpInput = document.querySelector('.ntp-search-input') as HTMLInputElement;
      if (ntpInput && document.activeElement === ntpInput) {
        navigateTo(ntpInput.value.trim());
        ntpInput.blur();
      }
    }
  });

  // ===== Download Manager Button =====
  const dlBtn = document.getElementById('btn-downloads');
  if (dlBtn) {
    dlBtn.addEventListener('click', toggleDownloadsPanel);
    window.openBrowser.onDownloadStarted((d: any) => {
      dlBtn.classList.add('has-new');
      updateDownloadsBadge();
    });
    window.openBrowser.onDownloadProgress((d: any) => {
      const bar = document.querySelector(`.dl-progress[data-dl-id="${d.id}"]`) as HTMLElement;
      if (bar) {
        const pct = d.total > 0 ? (d.received / d.total * 100) : 0;
        bar.style.width = pct + '%';
      }
    });
    window.openBrowser.onDownloadDone((d: any) => {
      dlBtn.classList.remove('has-new');
      updateDownloadsBadge();
      const statusEl = document.querySelector(`.dl-status[data-dl-id="${d.id}"]`);
      if (statusEl) statusEl.textContent = d.status === 'completed' ? '✅' : '❌';
    });
  }

  // ===== Incognito Button =====
  const incBtn = document.getElementById('btn-incognito');
  if (incBtn) {
    incBtn.addEventListener('click', toggleIncognito);
  }

  // ===== Tab Drag Reorder =====
  setupTabDrag();

  // ===== Focus Address Bar from main process =====
  window.openBrowser.onFocusAddressBar(() => {
    urlInput?.focus();
  });
}

// ========== STARTUP ==========
init();

// ========== BRIDGE FUNCTIONS ==========
// Called by the HTTP bridge server to control the browser
(window as any)._bridgeNavigate = function(targetUrl: string): void {
  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://') && !targetUrl.startsWith('openbrowser://')) {
    if (targetUrl.includes('.') && !targetUrl.includes(' ')) {
      targetUrl = 'https://' + targetUrl;
    } else {
      const engine = settings.searchEngine || 'google';
      const engines: Record<string, string> = {
        google: 'https://www.google.com/search?q=',
        bing: 'https://www.bing.com/search?q=',
        duckduckgo: 'https://duckduckgo.com/?q=',
        brave: 'https://search.brave.com/search?q='
      };
      targetUrl = (engines[engine] || engines.google) + encodeURIComponent(targetUrl);
    }
  }
  navigateTo(targetUrl);
};

(window as any)._bridgeGetTabs = function(): { id: number; title: string; url: string; active: boolean }[] {
  return tabs.map(t => ({
    id: t.id,
    title: t.title,
    url: t.url,
    active: t.id === currentTabId
  }));
};

(window as any)._bridgeGetHistory = function(): string[] {
  return (stats.visitHistory || []).slice(0, 50);
};

// ========== DOWNLOAD MANAGER ==========
function toggleDownloadsPanel(): void {
  downloadsPanelOpen = !downloadsPanelOpen;
  let panel = document.getElementById('downloads-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'downloads-panel';
    panel.className = 'downloads-panel';
    document.body.appendChild(panel);
  }
  if (downloadsPanelOpen) {
    renderDownloadsPanel();
    panel.classList.add('open');
  } else {
    panel.classList.remove('open');
  }
}

async function renderDownloadsPanel(): Promise<void> {
  const panel = document.getElementById('downloads-panel');
  if (!panel) return;
  const isEn = currentLang === 'en';
  const downloads = await window.openBrowser.getDownloads();
  const items = downloads.map((d: any) => {
    const pct = d.totalBytes > 0 ? Math.round(d.receivedBytes / d.totalBytes * 100) : 0;
    const statusIcon = d.status === 'completed' ? '✅' : d.status === 'cancelled' ? '🚫' : d.status === 'failed' ? '❌' : '⏳';
    const size = d.totalBytes > 0 ? formatBytes(d.totalBytes) : '?';
    return `<div class="dl-item"><div class="dl-info"><span class="dl-name">${d.filename}</span><span class="dl-meta">${size} • ${statusIcon} ${d.status}</span></div><div class="dl-bar-container"><div class="dl-progress" data-dl-id="${d.id}" style="width:${pct}%"></div></div><div class="dl-actions"><button class="dl-btn" data-action="open" data-dl-id="${d.id}" title="${isEn ? 'Open' : 'فتح'}">📂</button><button class="dl-btn" data-action="cancel" data-dl-id="${d.id}" title="${isEn ? 'Cancel' : 'إلغاء'}">✕</button></div></div>`;
  }).join('');

  panel.innerHTML = `
    <div class="dl-header">
      <span class="dl-title">${isEn ? 'Downloads' : 'التنزيلات'} (${downloads.length})</span>
      <button class="dl-close-btn" id="dl-close">✕</button>
    </div>
    <div class="dl-list">${items || '<div class="empty-state">' + (isEn ? 'No downloads' : 'لا يوجد تنزيلات') + '</div>'}</div>
    <div class="dl-footer">
      <button class="dl-footer-btn" id="dl-open-folder">${isEn ? 'Open Folder' : 'فتح المجلد'}</button>
      <button class="dl-footer-btn danger" id="dl-clear-all">${isEn ? 'Clear All' : 'مسح الكل'}</button>
    </div>`;

  document.getElementById('dl-close')?.addEventListener('click', () => {
    downloadsPanelOpen = false;
    panel.classList.remove('open');
  });
  document.getElementById('dl-open-folder')?.addEventListener('click', () => window.openBrowser.showDownloadFolder());
  document.getElementById('dl-clear-all')?.addEventListener('click', async () => {
    await window.openBrowser.clearDownloads();
    renderDownloadsPanel();
  });
  panel.querySelectorAll('.dl-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const action = (btn as HTMLElement).dataset.action;
      const id = (btn as HTMLElement).dataset.dlId || '';
      if (action === 'open') await window.openBrowser.openDownload(id);
      if (action === 'cancel') await window.openBrowser.cancelDownload(id);
      renderDownloadsPanel();
    });
  });
}

function updateDownloadsBadge(): void {
  window.openBrowser.getDownloads().then((downloads: any[]) => {
    const active = downloads.filter((d: any) => d.status === 'downloading').length;
    const badge = document.getElementById('dl-badge');
    if (badge) {
      badge.textContent = active > 0 ? String(active) : '';
      badge.style.display = active > 0 ? 'flex' : 'none';
    }
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ========== INCOGNITO MODE ==========
async function toggleIncognito(): Promise<void> {
  isIncognito = !isIncognito;
  const btn = document.getElementById('btn-incognito');
  if (btn) btn.classList.toggle('active', isIncognito);
  if (isIncognito) {
    await window.openBrowser.startIncognito();
    document.body.classList.add('incognito');
  } else {
    await window.openBrowser.stopIncognito();
    document.body.classList.remove('incognito');
  }
}

// ========== TAB DRAG REORDER ==========
function setupTabDrag(): void {
  const container = document.getElementById('tabs-container');
  if (!container) return;
  let draggedTab: HTMLElement | null = null;

  container.addEventListener('dragstart', (e: Event) => {
    const me = e as DragEvent;
    const tab = (me.target as HTMLElement).closest('.tab') as HTMLElement;
    if (!tab) return;
    draggedTab = tab;
    tab.classList.add('dragging');
    me.dataTransfer!.effectAllowed = 'move';
  });

  container.addEventListener('dragover', (e: Event) => {
    e.preventDefault();
    const me = e as DragEvent;
    me.dataTransfer!.dropEffect = 'move';
    const target = (me.target as HTMLElement).closest('.tab') as HTMLElement;
    if (!target || target === draggedTab) return;
    const rect = target.getBoundingClientRect();
    const midX = rect.left + rect.width / 2;
    if (me.clientX < midX) {
      container.insertBefore(draggedTab!, target);
    } else {
      container.insertBefore(draggedTab!, target.nextSibling);
    }
  });

  container.addEventListener('dragend', (e: Event) => {
    if (draggedTab) draggedTab.classList.remove('dragging');
    draggedTab = null;
    syncTabsFromDOM();
  });

  container.addEventListener('drop', (e: Event) => {
    e.preventDefault();
  });
}

function syncTabsFromDOM(): void {
  const container = document.getElementById('tabs-container');
  if (!container) return;
  const tabElements = container.querySelectorAll('.tab');
  const newTabs: Tab[] = [];
  tabElements.forEach(el => {
    const id = parseInt((el as HTMLElement).dataset.tabId || '0');
    const tab = tabs.find(t => t.id === id);
    if (tab) newTabs.push(tab);
  });
  tabs = newTabs;
}
