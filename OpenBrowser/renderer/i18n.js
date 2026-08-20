// OpenBrowser i18n - Arabic & English
const LANGUAGES = {
  ar: {
    newTab: 'تبويب جديد',
    urlPlaceholder: 'اكتب الرابط أو البحث...',
    ready: 'جاهز',
    loading: 'جاري التحميل...',
    settings: 'الإعدادات',
    history: 'السجل',
    about: 'حول',
    game: 'Snake',
    google: 'Google',
    youtube: 'YouTube',
    github: 'GitHub',
    search: 'بحث في الويب...',
    lightweight: 'خفيف • سريع • جاهز للذكاء الاصطناعي',
    settingsTitle: 'الإعدادات',
    settingsSub: 'خصّص تجربتك مع OpenBrowser',
    themes: 'الثيمات',
    homepage: 'الصفحة الرئيسية',
    searchEngine: 'محرك البحث الافتراضي',
    fontSize: 'حجم الخط',
    features: 'المميزات',
    aboutTitle: 'حول OpenBrowser',
    historyTitle: 'سجل الزيارات',
    clearHistory: 'مسح السجل',
    searchHistory: 'بحث في السجل...',
    noHistory: 'لا يوجد سجل بعد',
    pages: 'صفحات زرتها',
    tabsOpened: 'تبويبات فتحتها',
    gamesPlayed: 'مرات اللعب',
    minutesSpent: 'دقائق قضاها',
    installDate: 'تاريخ التثبيت',
    lastVisit: 'آخر زيارة',
    recentVisits: 'آخر الزيارات',
    snakeGame: 'Snake Game',
    easterEgg: 'Easter Egg v1',
    score: 'النقاط',
    highScore: 'الأعلى',
    startPlay: 'ابدأ اللعب',
    useArrows: 'الأسهم أو WASD للتحكم',
    gameOver: 'Game Over!',
    pressStart: 'اضغط ابدأ للعب مرة ثانية',
    langSwitch: 'EN',
    back: 'رجوع',
    forward: 'أمام',
    reload: 'تحديث',
    home: 'الرئيسية',
    minimize: 'تصغير',
    maximize: 'تكبير',
    close: 'إغلاق',
    newTabBtn: 'تبويب جديد',
    closeTab: 'إغلاق التبويب',
    amoledDark: 'AMOLED Dark',
    dark: 'Dark',
    midnightBlue: 'Midnight Blue',
    nord: 'Nord',
    light: 'Light',
    animations: 'الweet Animations',
    bookmarksBar: 'شريط الإشارات المرجعية',
    openBrowser: 'OpenBrowser',
    version: 'الإصدار',
    builtWith: 'متصفح خفيف وسريع مبني بـ Electron',
    easterHint: '💡 جرب: openbrowser://game-v1',
    pagesVisited: 'صفحات',
    tabsCount: 'تبويبات',
    gamesCount: 'ألعاب',
    timeMinutes: 'دقائق',
    lightFeatures: 'خفيف - 153 MB فقط',
    customThemes: '5 ثيمات مخصصة',
    hiddenGames: 'ألعاب مخفية',
    detailedStats: 'إحصائيات مفصلة'
  },
  en: {
    newTab: 'New Tab',
    urlPlaceholder: 'Type URL or search...',
    ready: 'Ready',
    loading: 'Loading...',
    settings: 'Settings',
    history: 'History',
    about: 'About',
    game: 'Snake',
    google: 'Google',
    youtube: 'YouTube',
    github: 'GitHub',
    search: 'Search the web...',
    lightweight: 'Lightweight • Fast • AI-Ready',
    settingsTitle: 'Settings',
    settingsSub: 'Customize your OpenBrowser experience',
    themes: 'Themes',
    homepage: 'Homepage',
    searchEngine: 'Default Search Engine',
    fontSize: 'Font Size',
    features: 'Features',
    aboutTitle: 'About OpenBrowser',
    historyTitle: 'History',
    clearHistory: 'Clear History',
    searchHistory: 'Search history...',
    noHistory: 'No history yet',
    pages: 'Pages Visited',
    tabsOpened: 'Tabs Opened',
    gamesPlayed: 'Games Played',
    minutesSpent: 'Minutes Spent',
    installDate: 'Install Date',
    lastVisit: 'Last Visit',
    recentVisits: 'Recent Visits',
    snakeGame: 'Snake Game',
    easterEgg: 'Easter Egg v1',
    score: 'Score',
    highScore: 'High Score',
    startPlay: 'Start Playing',
    useArrows: 'Arrow keys or WASD to control',
    gameOver: 'Game Over!',
    pressStart: 'Press Start to play again',
    langSwitch: 'عربي',
    back: 'Back',
    forward: 'Forward',
    reload: 'Reload',
    home: 'Home',
    minimize: 'Minimize',
    maximize: 'Maximize',
    close: 'Close',
    newTabBtn: 'New Tab',
    closeTab: 'Close Tab',
    amoledDark: 'AMOLED Dark',
    dark: 'Dark',
    midnightBlue: 'Midnight Blue',
    nord: 'Nord',
    light: 'Light',
    animations: 'Animations',
    bookmarksBar: 'Bookmarks Bar',
    openBrowser: 'OpenBrowser',
    version: 'Version',
    builtWith: 'Lightweight browser built with Electron',
    easterHint: '💡 Try: openbrowser://game-v1',
    pagesVisited: 'Pages',
    tabsCount: 'Tabs',
    gamesCount: 'Games',
    timeMinutes: 'Minutes',
    lightFeatures: 'Light - Only 153 MB',
    customThemes: '5 Custom Themes',
    hiddenGames: 'Hidden Games',
    detailedStats: 'Detailed Stats'
  }
};

let currentLang = 'ar';

function t(key) {
  return (LANGUAGES[currentLang] && LANGUAGES[currentLang][key]) || key;
}

function setLang(lang) {
  currentLang = lang;
  document.documentElement.setAttribute('data-lang', lang);
  document.documentElement.setAttribute('dir', lang === 'ar' ? 'ltr' : 'ltr');
  document.getElementById('lang-label').textContent = t('langSwitch');
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
  localStorage.setItem('ob-lang', lang);
}

function toggleLang() {
  setLang(currentLang === 'ar' ? 'en' : 'ar');
}

function initLang() {
  const saved = localStorage.getItem('ob-lang');
  if (saved) setLang(saved);
}
