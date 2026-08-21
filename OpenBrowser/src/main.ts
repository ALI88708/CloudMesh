import { app, BrowserWindow, ipcMain, shell, session, dialog } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { PrivacyEngine } from './privacy';
import { startBridge } from './bridge';

app.name = 'OpenBrowser';

let mainWindow: BrowserWindow | null = null;
let cursorOverlay: BrowserWindow | null = null;
let privacy: PrivacyEngine | null = null;

const SETTINGS_PATH = path.join(app.getPath('userData'), 'settings.json');
const STATS_PATH = path.join(app.getPath('userData'), 'stats.json');
const HISTORY_PATH = path.join(app.getPath('userData'), 'history.json');
const DOWNLOADS_PATH = path.join(app.getPath('userData'), 'downloads.json');

// ===== Download Manager State =====
interface DownloadItem {
  id: string;
  filename: string;
  url: string;
  totalBytes: number;
  receivedBytes: number;
  status: 'downloading' | 'completed' | 'cancelled' | 'failed';
  path: string;
  startTime: number;
}
let downloads: DownloadItem[] = [];
let downloadIdCounter = 0;

// ===== Real History =====
interface HistoryEntry {
  url: string;
  title: string;
  timestamp: number;
}
let historyData: HistoryEntry[] = [];

function loadHistory(): HistoryEntry[] {
  try {
    if (fs.existsSync(HISTORY_PATH)) {
      return JSON.parse(fs.readFileSync(HISTORY_PATH, 'utf8'));
    }
  } catch (e) {}
  return [];
}

function saveHistory(): void {
  fs.writeFileSync(HISTORY_PATH, JSON.stringify(historyData, null, 2));
}

function addHistoryEntry(url: string, title: string): void {
  if (!url || url.startsWith('openbrowser://') || url === 'about:blank') return;
  const last = historyData[0];
  if (last && last.url === url) return;
  historyData.unshift({ url, title, timestamp: Date.now() });
  if (historyData.length > 5000) historyData = historyData.slice(0, 5000);
  saveHistory();
}

// ===== Downloads =====
function loadDownloads(): DownloadItem[] {
  try {
    if (fs.existsSync(DOWNLOADS_PATH)) {
      return JSON.parse(fs.readFileSync(DOWNLOADS_PATH, 'utf8'));
    }
  } catch (e) {}
  return [];
}

function saveDownloads(): void {
  fs.writeFileSync(DOWNLOADS_PATH, JSON.stringify(downloads, null, 2));
}

function setupDownloadHandler(): void {
  if (!mainWindow) return;
  mainWindow.webContents.session.on('will-download', (event, item) => {
    const id = `dl-${++downloadIdCounter}-${Date.now()}`;
    const defaultPath = path.join(app.getPath('downloads'), item.getFilename());
    item.setSavePath(defaultPath);

    const dl: DownloadItem = {
      id,
      filename: item.getFilename(),
      url: item.getURL(),
      totalBytes: item.getTotalBytes(),
      receivedBytes: 0,
      status: 'downloading',
      path: defaultPath,
      startTime: Date.now()
    };
    downloads.unshift(dl);
    saveDownloads();

    if (mainWindow) mainWindow.webContents.send('download-started', dl);

    item.on('updated', (_e, state) => {
      if (state === 'progressing') {
        dl.receivedBytes = item.getReceivedBytes();
        dl.totalBytes = item.getTotalBytes();
        if (mainWindow) mainWindow.webContents.send('download-progress', { id: dl.id, received: dl.receivedBytes, total: dl.totalBytes });
      }
      if (state === 'interrupted') {
        dl.status = 'failed';
        saveDownloads();
        if (mainWindow) mainWindow.webContents.send('download-failed', dl.id);
      }
    });

    item.once('done', (_e, state) => {
      if (state === 'completed') {
        dl.status = 'completed';
        dl.receivedBytes = item.getTotalBytes();
      } else if (state === 'cancelled') {
        dl.status = 'cancelled';
      } else {
        dl.status = 'failed';
      }
      saveDownloads();
      if (mainWindow) mainWindow.webContents.send('download-done', { id: dl.id, status: dl.status });
    });
  });
}

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

function createCursorOverlay(): void {
  if (!mainWindow) return;
  const bounds = mainWindow.getBounds();

  cursorOverlay = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  cursorOverlay.setAlwaysOnTop(true, 'screen-saver');
  cursorOverlay.setIgnoreMouseEvents(true);
  cursorOverlay.setVisibleOnAllWorkspaces(true);
  cursorOverlay.loadFile(path.join(__dirname, 'renderer', 'cursor.html'));

  // Sync position with main window
  const syncPosition = () => {
    if (!mainWindow || !cursorOverlay || cursorOverlay.isDestroyed()) return;
    const b = mainWindow.getBounds();
    cursorOverlay.setBounds({ x: b.x, y: b.y, width: b.width, height: b.height });
  };

  mainWindow.on('resize', syncPosition);
  mainWindow.on('move', syncPosition);
  mainWindow.on('maximize', syncPosition);
  mainWindow.on('unmaximize', syncPosition);
  mainWindow.on('close', () => {
    if (cursorOverlay && !cursorOverlay.isDestroyed()) cursorOverlay.close();
  });
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
    createCursorOverlay();
    startBridge(mainWindow, cursorOverlay);

    const settings = loadSettings();
    privacy = new PrivacyEngine();
    privacy.updateSettings(settings);
    privacy.setup(mainWindow!);

    historyData = loadHistory();
    downloads = loadDownloads();
    setupDownloadHandler();
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

// ===== Download Manager IPC =====
ipcMain.handle('get-downloads', () => downloads);
ipcMain.handle('cancel-download', (_event: any, id: string) => {
  const dl = downloads.find(d => d.id === id);
  if (dl && dl.status === 'downloading') dl.status = 'cancelled';
  return true;
});
ipcMain.handle('open-download', (_event: any, id: string) => {
  const dl = downloads.find(d => d.id === id);
  if (dl && dl.path && fs.existsSync(dl.path)) {
    shell.openPath(dl.path);
  }
  return true;
});
ipcMain.handle('show-download-folder', () => {
  shell.openPath(app.getPath('downloads'));
  return true;
});
ipcMain.handle('clear-downloads', () => {
  downloads = [];
  saveDownloads();
  return true;
});

// ===== Real History IPC =====
ipcMain.handle('get-history', () => historyData);
ipcMain.handle('add-history', (_event: any, url: string, title: string) => {
  addHistoryEntry(url, title);
  return true;
});
ipcMain.handle('clear-history', () => {
  historyData = [];
  saveHistory();
  return true;
});
ipcMain.handle('remove-history-entry', (_event: any, url: string) => {
  historyData = historyData.filter(h => h.url !== url);
  saveHistory();
  return true;
});

// ===== Incognito Mode IPC =====
let incognitoSession: Electron.Session | null = null;

ipcMain.handle('start-incognito', () => {
  if (!mainWindow) return false;
  incognitoSession = session.fromPartition('incognito-' + Date.now());
  mainWindow.webContents.loadURL('about:blank');
  if (privacy) privacy.setup(mainWindow);
  return true;
});
ipcMain.handle('stop-incognito', () => {
  if (!mainWindow) return false;
  incognitoSession = null;
  const settings = loadSettings();
  mainWindow.webContents.loadURL(settings.homepage || 'about:blank');
  if (privacy) privacy.setup(mainWindow);
  return true;
});
ipcMain.handle('get-incognito-session', () => {
  return incognitoSession ? incognitoSession.partition : null;
});

// ===== Fullscreen IPC =====
ipcMain.handle('toggle-fullscreen', () => {
  if (!mainWindow) return false;
  const isFull = mainWindow.isFullScreen();
  mainWindow.setFullScreen(!isFull);
  return !isFull;
});
ipcMain.handle('is-fullscreen', () => mainWindow?.isFullScreen() ?? false);

// ===== Print IPC =====
ipcMain.handle('print-page', () => {
  if (!mainWindow) return false;
  const webContents = mainWindow.webContents;
  webContents.print({ silent: false, printBackground: true });
  return true;
});

// ===== Focus Address Bar IPC =====
ipcMain.handle('focus-address-bar', () => {
  if (mainWindow) mainWindow.webContents.send('focus-address-bar');
  return true;
});
