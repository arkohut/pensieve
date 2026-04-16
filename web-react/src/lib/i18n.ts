import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from '$/locales/en.json';
import zh from '$/locales/zh.json';

const LANG_KEY = 'i18nextLng';

function detectInitialLanguage(): string {
  const saved = typeof window !== 'undefined' ? localStorage.getItem(LANG_KEY) : null;
  if (saved === 'en' || saved === 'zh') return saved;
  const nav = typeof navigator !== 'undefined' ? navigator.language : 'en';
  return nav.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    zh: { translation: zh },
  },
  lng: detectInitialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
