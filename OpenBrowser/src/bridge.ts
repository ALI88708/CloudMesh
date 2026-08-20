import * as http from 'http';

let mainWindowRef: any = null;

// ===== RAM SCREENSHOT STORAGE =====
const screenshotCache = new Map<string, string>(); // id -> base64 data URL
let screenshotCounter = 0;

// ===== STREAMING STATE =====
let streamInterval: any = null;
let streamFrameCounter = 0;
const streamBuffer = new Map<string, string>(); // frame id -> base64
const MAX_STREAM_FRAMES = 100; // keep last 100 frames (~5 seconds at 20fps)

// ===== AUDIO STATE =====
let audioChunks: Buffer[] = [];
let audioRecording = false;
let audioInterval: any = null;

function storeScreenshot(dataUrl: string): string {
  const id = `ss-${Date.now()}-${screenshotCounter++}`;
  screenshotCache.set(id, dataUrl);
  if (screenshotCache.size > 50) {
    const firstKey = screenshotCache.keys().next().value;
    if (firstKey) screenshotCache.delete(firstKey);
  }
  return id;
}

function getAndDeleteScreenshot(id: string): string | null {
  const dataUrl = screenshotCache.get(id);
  if (dataUrl) screenshotCache.delete(id); // auto-delete after viewing
  return dataUrl || null;
}

function deleteScreenshot(id: string): boolean {
  return screenshotCache.delete(id);
}

function clearScreenshots(): void {
  screenshotCache.clear();
}

function storeStreamFrame(dataUrl: string): string {
  const id = `frame-${Date.now()}-${streamFrameCounter++}`;
  streamBuffer.set(id, dataUrl);
  // Auto-cleanup: keep only last N frames
  if (streamBuffer.size > MAX_STREAM_FRAMES) {
    const firstKey = streamBuffer.keys().next().value;
    if (firstKey) streamBuffer.delete(firstKey);
  }
  return id;
}

function runInRenderer(code: string): Promise<any> {
  return mainWindowRef.webContents.executeJavaScript(code);
}

function runInWebview(code: string): Promise<any> {
  return runInRenderer(`
    (function() {
      var wv = document.querySelector('.webview-wrapper.active webview');
      if (!wv) return null;
      return wv.executeJavaScript(${JSON.stringify(code)});
    })()
  `);
}

async function captureFrame(): Promise<{ id: string; dataUrl: string; size: number } | null> {
  if (!mainWindowRef) return null;
  try {
    const img = await mainWindowRef.webContents.capturePage();
    const buf = img.toPNG();
    const dataUrl = 'data:image/png;base64,' + buf.toString('base64');
    const id = storeStreamFrame(dataUrl);
    return { id, dataUrl, size: dataUrl.length };
  } catch (e) {
    return null;
  }
}

export function startBridge(win: any): void {
  mainWindowRef = win;

  const server = http.createServer(async (req: any, res: any) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Content-Type', 'application/json');

    const url = req.url || '';
    const method = req.method || 'GET';

    if (method === 'OPTIONS') {
      res.writeHead(200);
      return res.end();
    }

    try {
      // ===== BASIC =====
      if (url === '/ping' && method === 'GET') {
        return send(res, { ok: true, browser: 'OpenBrowser', version: '1.1.0' });
      }

      // ===== SCREENSHOT (RAM-based, one-time use) =====
      if (url === '/screenshot' && method === 'GET') {
        if (!mainWindowRef) return send(res, { error: 'No window' }, 400);
        try {
          const img = await mainWindowRef.webContents.capturePage();
          const buf = img.toPNG();
          const dataUrl = 'data:image/png;base64,' + buf.toString('base64');
          const id = storeScreenshot(dataUrl);
          return send(res, { ok: true, id, dataUrl, size: dataUrl.length });
        } catch (e: any) {
          return send(res, { error: 'Screenshot failed: ' + e.message }, 500);
        }
      }

      // ===== GET & DELETE SCREENSHOT (one-time read) =====
      if (url.startsWith('/screenshot-view/') && method === 'GET') {
        const id = url.split('/screenshot-view/')[1];
        const dataUrl = getAndDeleteScreenshot(id);
        if (!dataUrl) return send(res, { error: 'Screenshot not found or already viewed' }, 404);
        return send(res, { ok: true, id, dataUrl, size: dataUrl.length, deleted: true });
      }

      // ===== DELETE SCREENSHOT =====
      if (url.startsWith('/screenshot-delete/') && method === 'DELETE') {
        const id = url.split('/screenshot-delete/')[1];
        const deleted = deleteScreenshot(id);
        return send(res, { ok: true, deleted });
      }

      // ===== LIST ALL SCREENSHOTS IN RAM =====
      if (url === '/screenshots' && method === 'GET') {
        const ids = Array.from(screenshotCache.keys());
        return send(res, { ok: true, count: ids.length, ids });
      }

      // ===== CLEAR SCREENSHOT RAM =====
      if (url === '/screenshots/clear' && method === 'POST') {
        clearScreenshots();
        return send(res, { ok: true, message: 'Screenshot RAM cleared' });
      }

      // ===== STREAMING (20 FPS) =====
      if (url === '/stream/start' && method === 'POST') {
        if (streamInterval) return send(res, { ok: true, message: 'Stream already running' });
        const body = await readBody(req);
        const fps = Math.min(Math.max(body.fps || 20, 1), 30);
        const interval = 1000 / fps;
        streamFrameCounter = 0;
        streamBuffer.clear();
        streamInterval = setInterval(async () => {
          await captureFrame();
        }, interval);
        return send(res, { ok: true, message: `Stream started at ${fps} FPS`, fps });
      }

      if (url === '/stream/stop' && method === 'POST') {
        if (streamInterval) {
          clearInterval(streamInterval);
          streamInterval = null;
        }
        const frameCount = streamBuffer.size;
        return send(res, { ok: true, message: 'Stream stopped', framesCaptured: frameCount });
      }

      if (url === '/stream/status' && method === 'GET') {
        return send(res, {
          ok: true,
          streaming: !!streamInterval,
          framesInBuffer: streamBuffer.size
        });
      }

      if (url === '/stream/frames' && method === 'GET') {
        const ids = Array.from(streamBuffer.keys());
        return send(res, { ok: true, count: ids.length, ids });
      }

      if (url.startsWith('/stream/frame/') && method === 'GET') {
        const id = url.split('/stream/frame/')[1];
        const dataUrl = streamBuffer.get(id);
        if (!dataUrl) return send(res, { error: 'Frame not found' }, 404);
        return send(res, { ok: true, id, dataUrl, size: dataUrl.length });
      }

      if (url === '/stream/last' && method === 'GET') {
        const ids = Array.from(streamBuffer.keys());
        if (ids.length === 0) return send(res, { error: 'No frames' }, 404);
        const lastId = ids[ids.length - 1];
        const dataUrl = streamBuffer.get(lastId);
        return send(res, { ok: true, id: lastId, dataUrl, size: dataUrl?.length || 0, totalFrames: ids.length });
      }

      if (url === '/stream/clear' && method === 'POST') {
        streamBuffer.clear();
        return send(res, { ok: true, message: 'Stream buffer cleared' });
      }

      // ===== AUDIO CAPTURE =====
      if (url === '/audio/start' && method === 'POST') {
        if (audioRecording) return send(res, { ok: true, message: 'Already recording' });
        audioChunks = [];
        audioRecording = true;

        // Capture audio via renderer (not webview)
        await runInRenderer(`
          (async function() {
            try {
              const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
              const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
              window._audioRecorder = recorder;
              window._audioStream = stream;
              window._audioDataChunks = [];
              recorder.ondataavailable = (e) => { window._audioDataChunks.push(e.data); };
              recorder.start(100);
              return 'Audio recording started';
            } catch(e) {
              return 'Audio error: ' + e.message;
            }
          })()
        `);

        return send(res, { ok: true, message: 'Audio recording started' });
      }

      if (url === '/audio/stop' && method === 'POST') {
        if (!audioRecording) return send(res, { ok: true, message: 'Not recording' });
        audioRecording = false;

        // Stop recording via renderer
        const result = await runInRenderer(`
          (async function() {
            try {
              if (window._audioRecorder && window._audioRecorder.state !== 'inactive') {
                window._audioRecorder.stop();
                window._audioStream.getTracks().forEach(t => t.stop());
                // Wait for data to be available
                await new Promise(r => setTimeout(r, 200));
                const chunks = window._audioDataChunks || [];
                if (chunks.length === 0) return 'No audio data';
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const reader = new FileReader();
                return new Promise((resolve) => {
                  reader.onload = () => resolve(reader.result);
                  reader.readAsDataURL(blob);
                });
              }
              return 'No recorder found';
            } catch(e) {
              return 'Error: ' + e.message;
            }
          })()
        `);

        if (result && typeof result === 'string' && result.startsWith('data:')) {
          return send(res, { ok: true, audioUrl: result, size: result.length });
        }
        return send(res, { ok: false, error: String(result) });
      }

      if (url === '/audio/status' && method === 'GET') {
        return send(res, { ok: true, recording: audioRecording });
      }

      // ===== PLAY SOUND =====
      if (url === '/audio/play' && method === 'POST') {
        const body = await readBody(req);
        const soundUrl = body.url;
        const text = body.text;
        const volume = body.volume || 1.0;

        if (text) {
          // Text-to-speech via renderer (not webview)
          const result = await runInRenderer(`
            (function() {
              try {
                const utterance = new SpeechSynthesisUtterance(${JSON.stringify(text)});
                utterance.volume = ${volume};
                utterance.rate = 1.0;
                utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
                return 'Speaking: ' + ${JSON.stringify(text)};
              } catch(e) {
                return 'TTS error: ' + e.message;
              }
            })()
          `);
          return send(res, { ok: true, result: String(result) });
        }

        if (soundUrl) {
          // Play audio URL via renderer
          const result = await runInRenderer(`
            (function() {
              try {
                const audio = new Audio(${JSON.stringify(soundUrl)});
                audio.volume = ${volume};
                audio.play();
                return 'Playing: ' + ${JSON.stringify(soundUrl)};
              } catch(e) {
                return 'Play error: ' + e.message;
              }
            })()
          `);
          return send(res, { ok: true, result: String(result) });
        }

        return send(res, { error: 'Missing url or text' }, 400);
      }

      if (url === '/audio/stop-playback' && method === 'POST') {
        await runInRenderer(`
          (function() {
            window.speechSynthesis.cancel();
            document.querySelectorAll('audio').forEach(a => { a.pause(); a.currentTime = 0; });
          })()
        `);
        return send(res, { ok: true, message: 'Playback stopped' });
      }

      if (url === '/audio/tts' && method === 'POST') {
        const body = await readBody(req);
        const text = body.text;
        const lang = body.lang || 'ar-SA';
        const rate = body.rate || 1.0;
        const pitch = body.pitch || 1.0;
        const volume = body.volume || 1.0;

        if (!text) return send(res, { error: 'Missing text' }, 400);

        // TTS via renderer (not webview)
        const result = await runInRenderer(`
          (function() {
            try {
              window.speechSynthesis.cancel();
              const utterance = new SpeechSynthesisUtterance(${JSON.stringify(text)});
              utterance.lang = ${JSON.stringify(lang)};
              utterance.rate = ${rate};
              utterance.pitch = ${pitch};
              utterance.volume = ${volume};
              window.speechSynthesis.speak(utterance);
              return 'Speaking in ' + ${JSON.stringify(lang)} + ': ' + ${JSON.stringify(text)};
            } catch(e) {
              return 'TTS error: ' + e.message;
            }
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      if (url === '/audio/voices' && method === 'GET') {
        // Get voices via renderer
        const result = await runInRenderer(`
          (function() {
            return window.speechSynthesis.getVoices().map(v => ({
              name: v.name,
              lang: v.lang,
              localService: v.localService,
              default: v.default
            }));
          })()
        `);
        return send(res, { ok: true, voices: result || [] });
      }

      // ===== URL / TITLE =====
      if (url === '/url' && method === 'GET') {
        try {
          const result = await runInRenderer(`
            (function() {
              var tabs = window._bridgeGetTabs ? window._bridgeGetTabs() : [];
              var active = tabs.find(function(t) { return t.active; });
              return active || { url: '', title: '' };
            })()
          `);
          return send(res, { url: result?.url || '', title: result?.title || '' });
        } catch (e: any) {
          return send(res, { url: '', title: '', error: e.message });
        }
      }

      // ===== READ CONTENT =====
      if (url === '/content' && method === 'GET') {
        const html = await runInWebview('document.documentElement.outerHTML');
        if (html === null) return send(res, { error: 'No active webview' }, 400);
        return send(res, { ok: true, html: String(html).substring(0, 500000) });
      }

      if (url === '/text' && method === 'GET') {
        const text = await runInWebview('document.body.innerText');
        if (text === null) return send(res, { error: 'No active webview' }, 400);
        return send(res, { ok: true, text: String(text).substring(0, 500000) });
      }

      // ===== NAVIGATION =====
      if (url === '/navigate' && method === 'POST') {
        const body = await readBody(req);
        const targetUrl = body.url;
        if (!targetUrl) return send(res, { error: 'Missing url' }, 400);
        await runInRenderer(`window._bridgeNavigate && window._bridgeNavigate(${JSON.stringify(targetUrl)})`);
        return send(res, { ok: true, navigating: targetUrl });
      }

      if (url === '/back' && method === 'GET') {
        await runInWebview('history.back()');
        return send(res, { ok: true, action: 'back' });
      }

      if (url === '/forward' && method === 'GET') {
        await runInWebview('history.forward()');
        return send(res, { ok: true, action: 'forward' });
      }

      if (url === '/reload' && method === 'GET') {
        await runInWebview('location.reload()');
        return send(res, { ok: true, action: 'reload' });
      }

      // ===== CLICK =====
      if (url === '/click' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        if (!selector) return send(res, { error: 'Missing selector' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found: ${selector.replace(/'/g, "\\'")}';
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.click();
            return 'Clicked: ' + el.tagName + ' - ' + (el.textContent || '').trim().substring(0, 50);
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      if (url === '/click-text' && method === 'POST') {
        const body = await readBody(req);
        const text = body.text;
        if (!text) return send(res, { error: 'Missing text' }, 400);
        const result = await runInWebview(`
          (function() {
            var all = document.querySelectorAll('a, button, [role="button"], [onclick], span, div');
            for (var i = 0; i < all.length; i++) {
              if (all[i].textContent.trim().toLowerCase().indexOf('${text.replace(/'/g, "\\'").toLowerCase()}') !== -1) {
                all[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
                all[i].click();
                return 'Clicked: ' + all[i].tagName + ' - ' + all[i].textContent.trim().substring(0, 50);
              }
            }
            return 'No element found with text: ${text.replace(/'/g, "\\'")}';
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      // ===== TYPE =====
      if (url === '/type' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        const text = body.text;
        const pressEnter = body.enter;
        if (!selector || text === undefined) return send(res, { error: 'Missing selector or text' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found: ${selector.replace(/'/g, "\\'")}';
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.focus();
            el.value = '';
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(el, ${JSON.stringify(text)});
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            ${pressEnter ? "el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));" : ''}
            return 'Typed in ' + el.tagName + ': ' + ${JSON.stringify(text)};
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      if (url === '/type-keys' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        const text = body.text;
        if (!selector || text === undefined) return send(res, { error: 'Missing selector or text' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found';
            el.focus();
            el.value = '';
            var chars = ${JSON.stringify(text)};
            for (var i = 0; i < chars.length; i++) {
              el.value += chars[i];
              el.dispatchEvent(new KeyboardEvent('keydown', { key: chars[i], bubbles: true }));
              el.dispatchEvent(new KeyboardEvent('keypress', { key: chars[i], bubbles: true }));
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new KeyboardEvent('keyup', { key: chars[i], bubbles: true }));
            }
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return 'Typed ' + chars.length + ' chars';
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      // ===== SCROLL =====
      if (url === '/scroll' && method === 'POST') {
        const body = await readBody(req);
        const direction = body.direction || 'down';
        const amount = body.amount || 500;
        const result = await runInWebview(`
          (function() {
            var x = 0;
            var y = ${direction === 'up' ? '-' : ''}${amount};
            window.scrollBy({ left: x, top: y, behavior: 'smooth' });
            return 'Scrolled ' + ${JSON.stringify(direction)} + ' ' + ${amount} + 'px';
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      if (url === '/scroll-to' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        if (!selector) return send(res, { error: 'Missing selector' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found';
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return 'Scrolled to: ' + el.tagName;
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      if (url === '/scroll-bottom' && method === 'GET') {
        await runInWebview('window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })');
        return send(res, { ok: true, result: 'Scrolled to bottom' });
      }

      if (url === '/scroll-top' && method === 'GET') {
        await runInWebview('window.scrollTo({ top: 0, behavior: "smooth" })');
        return send(res, { ok: true, result: 'Scrolled to top' });
      }

      // ===== HOVER =====
      if (url === '/hover' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        if (!selector) return send(res, { error: 'Missing selector' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found';
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
            return 'Hovered: ' + el.tagName;
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      // ===== FOCUS =====
      if (url === '/focus' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector;
        if (!selector) return send(res, { error: 'Missing selector' }, 400);
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Element not found';
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.focus();
            return 'Focused: ' + el.tagName;
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      // ===== SUBMIT =====
      if (url === '/submit' && method === 'POST') {
        const body = await readBody(req);
        const selector = body.selector || 'form';
        const result = await runInWebview(`
          (function() {
            var el = document.querySelector('${selector.replace(/'/g, "\\'")}');
            if (!el) return 'Form not found';
            el.submit();
            return 'Submitted form';
          })()
        `);
        return send(res, { ok: true, result: String(result) });
      }

      // ===== GET ELEMENTS =====
      if (url === '/elements' && method === 'GET') {
        const result = await runInWebview(`
          (function() {
            var els = document.querySelectorAll('a[href], button, input, textarea, select, [role="button"], [onclick]');
            var out = [];
            for (var i = 0; i < Math.min(els.length, 100); i++) {
              var el = els[i];
              var rect = el.getBoundingClientRect();
              if (rect.width === 0 || rect.height === 0) continue;
              out.push({
                tag: el.tagName,
                type: el.type || '',
                text: (el.textContent || '').trim().substring(0, 60),
                href: el.href || '',
                selector: el.id ? '#' + el.id : (el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ').filter(function(c){return c}).join('.') : el.tagName.toLowerCase()),
                x: Math.round(rect.x + rect.width/2),
                y: Math.round(rect.y + rect.height/2),
                visible: rect.y >= 0 && rect.y < window.innerHeight
              });
            }
            return out;
          })()
        `);
        return send(res, { ok: true, elements: result || [] });
      }

      // ===== GET LINKS =====
      if (url === '/links' && method === 'GET') {
        const result = await runInWebview(`
          (function() {
            var links = document.querySelectorAll('a[href]');
            var out = [];
            for (var i = 0; i < Math.min(links.length, 50); i++) {
              var a = links[i];
              if (a.textContent.trim()) {
                out.push({ text: a.textContent.trim().substring(0, 60), href: a.href });
              }
            }
            return out;
          })()
        `);
        return send(res, { ok: true, links: result || [] });
      }

      // ===== EVALUATE JS (in webview) =====
      if (url === '/evaluate' && method === 'POST') {
        const body = await readBody(req);
        const code = body.code;
        if (!code) return send(res, { error: 'Missing code' }, 400);
        const result = await runInWebview(code);
        if (result === null) return send(res, { error: 'No active webview' }, 400);
        return send(res, { ok: true, result: String(result).substring(0, 100000) });
      }

      // ===== EVALUATE JS (in renderer - for internal pages) =====
      if (url === '/eval-renderer' && method === 'POST') {
        const body = await readBody(req);
        const code = body.code;
        if (!code) return send(res, { error: 'Missing code' }, 400);
        try {
          const result = await runInRenderer(code);
          return send(res, { ok: true, result: String(result).substring(0, 100000) });
        } catch (e: any) {
          return send(res, { error: e.message }, 500);
        }
      }

      // ===== TABS =====
      if (url === '/tabs' && method === 'GET') {
        const result = await runInRenderer(`JSON.stringify(window._bridgeGetTabs ? window._bridgeGetTabs() : [])`);
        return send(res, { ok: true, tabs: JSON.parse(result || '[]') });
      }

      // ===== SEARCH =====
      if (url === '/search' && method === 'POST') {
        const body = await readBody(req);
        const query = body.query;
        if (!query) return send(res, { error: 'Missing query' }, 400);
        await runInRenderer(`window._bridgeNavigate && window._bridgeNavigate(${JSON.stringify(query)})`);
        return send(res, { ok: true, searching: query });
      }

      // ===== HISTORY =====
      if (url === '/history' && method === 'GET') {
        const result = await runInRenderer(`JSON.stringify(window._bridgeGetHistory ? window._bridgeGetHistory() : [])`);
        return send(res, { ok: true, history: JSON.parse(result || '[]') });
      }

      // ===== WAIT =====
      if (url === '/wait' && method === 'POST') {
        const body = await readBody(req);
        const ms = body.ms || 2000;
        await new Promise(r => setTimeout(r, Math.min(ms, 10000)));
        return send(res, { ok: true, waited: ms });
      }

      send(res, { error: 'Unknown endpoint' }, 404);
    } catch (err: any) {
      send(res, { error: err.message || String(err) }, 500);
    }
  });

  server.listen(9876, '127.0.0.1', () => {
    console.log('[OpenBrowser Bridge v1.1] http://127.0.0.1:9876');
  });

  server.on('error', () => {
    server.listen(9877, '127.0.0.1', () => {
      console.log('[OpenBrowser Bridge v1.1] http://127.0.0.1:9877');
    });
  });
}

function send(res: any, data: any, status = 200): void {
  res.writeHead(status);
  res.end(JSON.stringify(data));
}

function readBody(req: any): Promise<any> {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (c: any) => body += c);
    req.on('end', () => {
      try { resolve(JSON.parse(body)); } catch (e) { resolve({}); }
    });
  });
}
