export interface ThemeColors {
  bgPrimary: string;
  bgSecondary: string;
  accent: string;
  [key: string]: string;
}

export interface Theme {
  name: string;
  icon: string;
  colors: ThemeColors;
}

export interface Themes {
  [key: string]: Theme;
}

export const THEMES: Themes = {
  amoled: { name: 'AMOLED Dark', icon: '🌑', colors: { bgPrimary: '#000000', bgSecondary: '#0a0a0a', accent: '#00d4ff' } },
  dark: { name: 'Dark', icon: '🌙', colors: { bgPrimary: '#1a1b1e', bgSecondary: '#222326', accent: '#7c5cfc' } },
  midnight: { name: 'Midnight Blue', icon: '🌊', colors: { bgPrimary: '#0d1117', bgSecondary: '#161b22', accent: '#58a6ff' } },
  nord: { name: 'Nord', icon: '❄️', colors: { bgPrimary: '#2e3440', bgSecondary: '#3b4252', accent: '#88c0d0' } },
  light: { name: 'Light', icon: '☀️', colors: { bgPrimary: '#ffffff', bgSecondary: '#f5f5f5', accent: '#0066cc' } }
};
