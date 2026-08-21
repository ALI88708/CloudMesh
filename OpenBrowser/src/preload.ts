import { contextBridge, ipcRenderer } from 'electron';
const { pathToFileURL } = require('url');

// __dirname is available in preload, no need for 'path' module
// 'url' module is allowed in sandboxed preload, 'path' is NOT
const privacyPreloadPath = pathToFileURL(`${__dirname}/privacy-preload.js`).href;

contextBridge.exposeInMainWorld('openBrowser', {
  privacyPreloadPath,
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings: any) => ipcRenderer.invoke('save-settings', settings),
  getStats: () => ipcRenderer.invoke('get-stats'),
  saveStats: (stats: any) => ipcRenderer.invoke('save-stats', stats),
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close'),
  isMaximized: () => ipcRenderer.invoke('is-maximized'),
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  getVersion: () => ipcRenderer.invoke('get-app-version'),
  getUserDataPath: () => ipcRenderer.invoke('get-user-data-path'),
  getPrivacyStats: () => ipcRenderer.invoke('get-privacy-stats'),
  updatePrivacySettings: (s: any) => ipcRenderer.invoke('update-privacy-settings', s),
  toggleAdBlocker: (e: boolean) => ipcRenderer.invoke('toggle-ad-blocker', e),
  toggleTrackerBlocker: (e: boolean) => ipcRenderer.invoke('toggle-tracker-blocker', e),
  toggleFingerprintProtection: (e: boolean) => ipcRenderer.invoke('toggle-fingerprint-protection', e),

  // Download Manager
  getDownloads: () => ipcRenderer.invoke('get-downloads'),
  cancelDownload: (id: string) => ipcRenderer.invoke('cancel-download', id),
  openDownload: (id: string) => ipcRenderer.invoke('open-download', id),
  showDownloadFolder: () => ipcRenderer.invoke('show-download-folder'),
  clearDownloads: () => ipcRenderer.invoke('clear-downloads'),
  onDownloadStarted: (cb: any) => ipcRenderer.on('download-started', (_e: any, d: any) => cb(d)),
  onDownloadProgress: (cb: any) => ipcRenderer.on('download-progress', (_e: any, d: any) => cb(d)),
  onDownloadDone: (cb: any) => ipcRenderer.on('download-done', (_e: any, d: any) => cb(d)),

  // Real History
  getHistory: () => ipcRenderer.invoke('get-history'),
  addHistory: (url: string, title: string) => ipcRenderer.invoke('add-history', url, title),
  clearHistory: () => ipcRenderer.invoke('clear-history'),
  removeHistoryEntry: (url: string) => ipcRenderer.invoke('remove-history-entry', url),

  // Incognito
  startIncognito: () => ipcRenderer.invoke('start-incognito'),
  stopIncognito: () => ipcRenderer.invoke('stop-incognito'),
  getIncognitoSession: () => ipcRenderer.invoke('get-incognito-session'),

  // Fullscreen
  toggleFullscreen: () => ipcRenderer.invoke('toggle-fullscreen'),
  isFullscreen: () => ipcRenderer.invoke('is-fullscreen'),

  // Print
  printPage: () => ipcRenderer.invoke('print-page'),

  // Focus
  focusAddressBar: () => ipcRenderer.invoke('focus-address-bar'),
  onFocusAddressBar: (cb: any) => ipcRenderer.on('focus-address-bar', () => cb())
});
