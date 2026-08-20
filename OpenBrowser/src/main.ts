import { app, BrowserWindow, ipcMain, shell, session } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { PrivacyEngine } from './privacy';
import { startBridge } from './bridge';

app.name = 'OpenBrowser';

let mainWindow: BrowserWindow | null = null;
let privacy: PrivacyEngine | null = null;

const SETTINGS_PATH = path.join(app.getPath('userData'), 'settings.json');
const STATS_PATH = path.join(app.getPath('userData'), 'stats.json');

interface AppSettings {
  theme: string;
  homepage: string;
  searchEngine: string;
  showBookmarksBar: boolean;
  enableAnimations: boolean;
  fontSize: number;
  volume: number;
  adBlocker: boolean;
  trackerBlocker: boolean;
  fingerprintProtection: boolean;
  [key: string]: any;
}

interface AppStats {
  pagesVisited: number;
  tabsOpened: number;
  downloadsCount: number;
  timeSpent: number;
  gamesPlayed: number;
  lastVisit: string | null;
  installDate: string;
  visitHistory: string[];
  [key: string]: any;
}

const DEFAULT_SETTINGS: AppSettings = {
  theme: 'amoled',
  homepage: 'about:blank',
  searchEngine: 'google',
  showBookmarksBar: true,
  enableAnimations: true,
  fontSize: 14,
  volume: 80,
  adBlocker: true,
  trackerBlocker: true,
  fingerprintProtection: true
};

const DEFAULT_STATS: AppStats = {
  pagesVisited: 0,
  tabsOpened: 0,
  downloadsCount: 0,
  timeSpent: 0,
  gamesPlayed: 0,
  lastVisit: null,
  installDate: new Date().toISOString(),
  visitHistory: []
};

function loadSettings(): AppSettings {
  try {
    if (fs.existsSync(SETTINGS_PATH)) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8')) };
    }
  } catch (e) {}
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(settings: AppSettings): void {
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 2));
}

function loadStats(): AppStats {
  try {
    if (fs.existsSync(STATS_PATH)) {
      return { ...DEFAULT_STATS, ...JSON.parse(fs.readFileSync(STATS_PATH, 'utf8')) };
    }
  } catch (e) {}
  return { ...DEFAULT_STATS };
}

function saveStats(stats: AppStats): void {
  fs.writeFileSync(STATS_PATH, JSON.stringify(stats, null, 2));
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webviewTag: true
    },
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    show: false
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    startBridge(mainWindow);

    const settings = loadSettings();
    privacy = new PrivacyEngine();
    privacy.updateSettings(settings);
    privacy.setup(mainWindow!);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// IPC Handlers
ipcMain.handle('get-settings', () => loadSettings());
ipcMain.handle('save-settings', (_event: any, settings: AppSettings) => {
  saveSettings(settings);
  return true;
});
ipcMain.handle('get-stats', () => loadStats());
ipcMain.handle('save-stats', (_event: any, stats: AppStats) => {
  saveStats(stats);
  return true;
});

ipcMain.handle('window-minimize', () => mainWindow?.minimize());
ipcMain.handle('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle('window-close', () => mainWindow?.close());
ipcMain.handle('is-maximized', () => mainWindow?.isMaximized() ?? false);

ipcMain.handle('open-external', (_event: any, url: string) => {
  shell.openExternal(url);
});

ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('get-user-data-path', () => app.getPath('userData'));

// Privacy IPC
ipcMain.handle('get-privacy-stats', () => {
  return privacy ? privacy.getStats() : { adsBlocked: 0, trackersBlocked: 0 };
});
ipcMain.handle('update-privacy-settings', (_event: any, settings: AppSettings) => {
  if (privacy) privacy.updateSettings(settings);
  return true;
});
ipcMain.handle('toggle-ad-blocker', (_event: any, enabled: boolean) => {
  if (privacy) privacy.adBlockerEnabled = enabled;
  return true;
});
ipcMain.handle('toggle-tracker-blocker', (_event: any, enabled: boolean) => {
  if (privacy) privacy.trackerBlockerEnabled = enabled;
  return true;
});
ipcMain.handle('toggle-fingerprint-protection', (_event: any, enabled: boolean) => {
  if (privacy) privacy.fingerprintProtectionEnabled = enabled;
  return true;
});
