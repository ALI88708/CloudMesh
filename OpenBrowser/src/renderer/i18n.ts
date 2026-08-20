export interface LanguageStrings {
  [key: string]: string;
}

export interface Languages {
  ar: LanguageStrings;
  en: LanguageStrings;
}

export const LANGUAGES: Languages = {
  ar: {
    newTab: 'تبويب جديد',
    urlPlaceholder: 'اكتب الرابط أو البحث...',
    ready: 'جاهز',
    loading: 'جاري التحميل...',
    settings: 'الإعدادات',
    history: 'السجل',
    about: 'حول',
    game: 'Snake',
    search: 'بحث في الويب...',
    langSwitch: 'EN'
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
    search: 'Search the web...',
    langSwitch: 'عربي'
  }
};

export let currentLang: string = 'ar';

export function t(key: string): string {
  return (LANGUAGES[currentLang as keyof Languages] && LANGUAGES[currentLang as keyof Languages][key]) || key;
}

export function setLang(lang: string): void {
  currentLang = lang;
  document.documentElement.setAttribute('data-lang', lang);
  document.documentElement.setAttribute('dir', 'ltr');
  const langLabel = document.getElementById('lang-label');
  if (langLabel) langLabel.textContent = t('langSwitch');
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key) el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (key) (el as HTMLInputElement).placeholder = t(key);
  });
  localStorage.setItem('ob-lang', lang);
}

export function toggleLang(): void {
  setLang(currentLang === 'ar' ? 'en' : 'ar');
}

export function initLang(): void {
  const saved = localStorage.getItem('ob-lang');
  if (saved) setLang(saved);
}
