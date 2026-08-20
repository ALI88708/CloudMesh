import type { Plugin } from "@opencode-ai/plugin";
import { exec } from 'child_process';

const BRIDGE = 'http://127.0.0.1:9876';

async function api(endpoint: string, method = 'GET', body?: any): Promise<any> {
  try {
    const opts: RequestInit = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(`${BRIDGE}${endpoint}`, opts);
    return await r.json();
  } catch (e: any) {
    return { error: 'OpenBrowser not running. Run: browser start' };
  }
}

export default {
  name: 'openbrowser',
  description: 'Full browser control - see, click, type, scroll, stream, listen, speak',
  hooks: {
    'tool.execute.before': async (input, context) => {
      if (context.tool !== 'bash') return undefined;
      const cmd = ((input.args as any).command || '').trim();
      const lc = cmd.toLowerCase();

      // ===== START =====
      if (lc === 'browser start' || lc === 'browser launch') {
        const p = require('path').join(process.cwd(), 'OpenBrowser');
        exec(`Start-Process -FilePath "${p}\\node_modules\\.bin\\electron.cmd" -ArgumentList "." -WorkingDirectory "${p}\\dist"`, { shell: 'powershell.exe' });
        await new Promise(r => setTimeout(r, 3000));
        const check = await api('/ping');
        return { result: check.ok ? 'OpenBrowser started!' : 'Starting... wait and try: browser status' };
      }

      // ===== STATUS =====
      if (lc === 'browser status' || lc === 'browser ping') {
        const r = await api('/ping');
        return { result: r.ok ? `OpenBrowser v${r.version} running` : `Not running: ${r.error}` };
      }

      // ===== NAVIGATE =====
      if (lc.startsWith('browser navigate ') || lc.startsWith('browser open ') || lc.startsWith('browser go ')) {
        const target = cmd.replace(/^browser (navigate|open|go)\s+/i, '').trim();
        if (!target) return { result: 'Usage: browser navigate <url or search>' };
        const r = await api('/navigate', 'POST', { url: target });
        await api('/wait', 'POST', { ms: 3000 });
        return { result: r.ok ? `Navigating to: ${target}` : r.error };
      }

      // ===== SEARCH =====
      if (lc.startsWith('browser search ') || lc.startsWith('browser google ')) {
        const q = cmd.replace(/^browser (search|google)\s+/i, '').trim();
        if (!q) return { result: 'Usage: browser search <query>' };
        const r = await api('/search', 'POST', { query: q });
        await api('/wait', 'POST', { ms: 3000 });
        return { result: r.ok ? `Searching: ${q}` : r.error };
      }

      // ===== URL =====
      if (lc === 'browser url' || lc === 'browser where' || lc === 'browser current') {
        const r = await api('/url');
        return { result: r.url ? `${r.title}\n${r.url}` : 'No active page' };
      }

      // ===== SEE (screenshot + text, auto-delete screenshot) =====
      if (lc === 'browser see' || lc === 'browser look' || lc === 'browser observe') {
        const [ss, url, text] = await Promise.all([
          api('/screenshot'),
          api('/url'),
          api('/text')
        ]);
        let result = `URL: ${url.url}\nTitle: ${url.title}\n\n`;
        if (ss.ok) {
          // Auto-delete after storing
          result += `Screenshot: ${ss.id} | ${(ss.size / 1024).toFixed(1)}KB (captured)\n\n`;
        }
        if (text.ok) result += text.text.substring(0, 3000);
        return { result };
      }

      // ===== SCREENSHOT (one-time, auto-delete after read) =====
      if (lc === 'browser screenshot' || lc === 'browser ss' || lc === 'browser capture') {
        const r = await api('/screenshot');
        if (!r.ok) return { result: r.error };
        return { result: `Screenshot captured\nID: ${r.id}\nSize: ${(r.size / 1024).toFixed(1)}KB` };
      }

      // ===== SCREENSHOT VIEW (get & auto-delete) =====
      if (lc.startsWith('browser ss view ') || lc.startsWith('browser ss get ')) {
        const id = cmd.replace(/^browser ss (view|get)\s+/i, '').trim();
        if (!id) return { result: 'Usage: browser ss view <id>' };
        const r = await api(`/screenshot-view/${id}`);
        if (!r.ok) return { result: r.error };
        return { result: `Screenshot: ${r.id} | ${(r.size / 1024).toFixed(1)}KB | Auto-deleted: ${r.deleted}` };
      }

      // ===== SCREENSHOT LIST =====
      if (lc === 'browser ss list' || lc === 'browser screenshots') {
        const r = await api('/screenshots');
        if (!r.ok) return { result: r.error };
        return { result: `Screenshots in RAM: ${r.count}\nIDs: ${(r.ids || []).join(', ')}` };
      }

      // ===== SCREENSHOT DELETE =====
      if (lc.startsWith('browser ss delete ') || lc.startsWith('browser ss rm ')) {
        const id = cmd.replace(/^browser ss (delete|rm)\s+/i, '').trim();
        if (!id) return { result: 'Usage: browser ss delete <id>' };
        const r = await api(`/screenshot-delete/${id}`, 'DELETE');
        return { result: r.ok ? `Deleted: ${r.deleted}` : r.error };
      }

      // ===== SCREENSHOT CLEAR =====
      if (lc === 'browser ss clear' || lc === 'browser ss reset') {
        const r = await api('/screenshots/clear', 'POST');
        return { result: r.ok ? 'Screenshot RAM cleared' : r.error };
      }

      // ===== STREAM START =====
      if (lc === 'browser stream start' || lc === 'browser stream on') {
        const fps = parseInt(cmd.match(/(\d+)/)?.[1] || '20');
        const r = await api('/stream/start', 'POST', { fps });
        return { result: r.ok ? `${r.message}` : r.error };
      }

      // ===== STREAM STOP =====
      if (lc === 'browser stream stop' || lc === 'browser stream off') {
        const r = await api('/stream/stop', 'POST');
        return { result: r.ok ? `${r.message} | Frames captured: ${r.framesCaptured}` : r.error };
      }

      // ===== STREAM STATUS =====
      if (lc === 'browser stream status' || lc === 'browser stream') {
        const r = await api('/stream/status');
        return { result: r.ok ? `Streaming: ${r.streaming} | Frames in buffer: ${r.framesInBuffer}` : r.error };
      }

      // ===== STREAM LAST FRAME =====
      if (lc === 'browser stream last' || lc === 'browser stream frame') {
        const r = await api('/stream/last');
        if (!r.ok) return { result: r.error };
        return { result: `Frame: ${r.id} | ${(r.size / 1024).toFixed(1)}KB | Total frames: ${r.totalFrames}` };
      }

      // ===== STREAM CLEAR =====
      if (lc === 'browser stream clear') {
        const r = await api('/stream/clear', 'POST');
        return { result: r.ok ? 'Stream buffer cleared' : r.error };
      }

      // ===== AUDIO RECORD START =====
      if (lc === 'browser audio start' || lc === 'browser mic start' || lc === 'browser record') {
        const r = await api('/audio/start', 'POST');
        return { result: r.ok ? r.message : r.error };
      }

      // ===== AUDIO RECORD STOP =====
      if (lc === 'browser audio stop' || lc === 'browser mic stop' || lc === 'browser record stop') {
        const r = await api('/audio/stop', 'POST');
        if (r.ok && r.audioUrl) {
          return { result: `Audio recorded! Size: ${(r.size / 1024).toFixed(1)}KB\nData URL: ${r.audioUrl.substring(0, 100)}...` };
        }
        return { result: r.ok ? 'Recording stopped (no data)' : r.error };
      }

      // ===== AUDIO STATUS =====
      if (lc === 'browser audio status') {
        const r = await api('/audio/status');
        return { result: r.ok ? `Recording: ${r.recording}` : r.error };
      }

      // ===== TEXT-TO-SPEECH =====
      if (lc.startsWith('browser say ') || lc.startsWith('browser speak ') || lc.startsWith('browser tts ')) {
        const text = cmd.replace(/^browser (say|speak|tts)\s+/i, '').trim();
        if (!text) return { result: 'Usage: browser say <text>' };
        const r = await api('/audio/tts', 'POST', { text, lang: 'ar-SA', rate: 1.0, pitch: 1.0, volume: 1.0 });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== PLAY SOUND =====
      if (lc.startsWith('browser play ')) {
        const url = cmd.replace(/^browser play\s+/i, '').trim();
        if (!url) return { result: 'Usage: browser play <url or text>' };
        const r = await api('/audio/play', 'POST', { url });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== STOP PLAYBACK =====
      if (lc === 'browser audio stop-playback' || lc === 'browser stop-sound' || lc === 'browser mute') {
        const r = await api('/audio/stop-playback', 'POST');
        return { result: r.ok ? 'Playback stopped' : r.error };
      }

      // ===== VOICES LIST =====
      if (lc === 'browser voices' || lc === 'browser langs') {
        const r = await api('/audio/voices');
        if (!r.ok) return { result: r.error };
        const list = (r.voices || []).slice(0, 20).map((v: any) => `${v.name} (${v.lang})${v.default ? ' [DEFAULT]' : ''}`).join('\n');
        return { result: list || 'No voices available' };
      }

      // ===== TEXT =====
      if (lc === 'browser text' || lc === 'browser read' || lc === 'browser content') {
        const r = await api('/text');
        if (!r.ok) return { result: r.error };
        return { result: r.text || '(empty page)' };
      }

      // ===== HTML =====
      if (lc === 'browser html') {
        const r = await api('/content');
        if (!r.ok) return { result: r.error };
        return { result: (r.html || '').substring(0, 8000) };
      }

      // ===== CLICK BY SELECTOR =====
      if (lc.startsWith('browser click ')) {
        const sel = cmd.replace(/^browser click\s+/i, '').trim();
        if (!sel) return { result: 'Usage: browser click <css-selector>' };
        const r = await api('/click', 'POST', { selector: sel });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== CLICK BY TEXT =====
      if (lc.startsWith('browser click-text ') || lc.startsWith('browser tap ')) {
        const text = cmd.replace(/^browser (click-text|tap)\s+/i, '').trim();
        if (!text) return { result: 'Usage: browser click-text <text>' };
        const r = await api('/click-text', 'POST', { text });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== TYPE =====
      if (lc.startsWith('browser type ')) {
        const parts = cmd.replace(/^browser type\s+/i, '').trim();
        const enter = parts.includes('--enter');
        const cleaned = parts.replace('--enter', '').trim();
        const spaceIdx = cleaned.indexOf(' ');
        if (spaceIdx === -1) return { result: 'Usage: browser type <selector> <text> [--enter]' };
        const sel = cleaned.substring(0, spaceIdx);
        const text = cleaned.substring(spaceIdx + 1);
        const r = await api('/type', 'POST', { selector: sel, text, enter });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== TYPE KEYS =====
      if (lc.startsWith('browser type-keys ') || lc.startsWith('browser keyboard ')) {
        const parts = cmd.replace(/^browser (type-keys|keyboard)\s+/i, '').trim();
        const spaceIdx = parts.indexOf(' ');
        if (spaceIdx === -1) return { result: 'Usage: browser type-keys <selector> <text>' };
        const sel = parts.substring(0, spaceIdx);
        const text = parts.substring(spaceIdx + 1);
        const r = await api('/type-keys', 'POST', { selector: sel, text });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== SCROLL =====
      if (lc === 'browser scroll down' || lc === 'browser scroll') {
        const r = await api('/scroll', 'POST', { direction: 'down', amount: 500 });
        return { result: r.ok ? r.result : r.error };
      }
      if (lc === 'browser scroll up') {
        const r = await api('/scroll', 'POST', { direction: 'up', amount: 500 });
        return { result: r.ok ? r.result : r.error };
      }
      if (lc === 'browser scroll top' || lc === 'browser scroll begin') {
        const r = await api('/scroll-top');
        return { result: r.ok ? r.result : r.error };
      }
      if (lc === 'browser scroll bottom' || lc === 'browser scroll end') {
        const r = await api('/scroll-bottom');
        return { result: r.ok ? r.result : r.error };
      }
      if (lc.startsWith('browser scroll to ')) {
        const sel = cmd.replace(/^browser scroll to\s+/i, '').trim();
        const r = await api('/scroll-to', 'POST', { selector: sel });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== HOVER =====
      if (lc.startsWith('browser hover ')) {
        const sel = cmd.replace(/^browser hover\s+/i, '').trim();
        const r = await api('/hover', 'POST', { selector: sel });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== FOCUS =====
      if (lc.startsWith('browser focus ')) {
        const sel = cmd.replace(/^browser focus\s+/i, '').trim();
        const r = await api('/focus', 'POST', { selector: sel });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== SUBMIT =====
      if (lc === 'browser submit' || lc === 'browser enter') {
        const r = await api('/submit', 'POST', { selector: 'form' });
        return { result: r.ok ? r.result : r.error };
      }

      // ===== BACK / FORWARD / RELOAD =====
      if (lc === 'browser back') {
        const r = await api('/back');
        await api('/wait', 'POST', { ms: 2000 });
        return { result: r.ok ? 'Going back' : r.error };
      }
      if (lc === 'browser forward') {
        const r = await api('/forward');
        await api('/wait', 'POST', { ms: 2000 });
        return { result: r.ok ? 'Going forward' : r.error };
      }
      if (lc === 'browser reload' || lc === 'browser refresh') {
        const r = await api('/reload');
        await api('/wait', 'POST', { ms: 2000 });
        return { result: r.ok ? 'Reloading...' : r.error };
      }

      // ===== ELEMENTS / LINKS =====
      if (lc === 'browser elements' || lc === 'browser buttons') {
        const r = await api('/elements');
        if (!r.ok) return { result: r.error };
        const list = (r.elements || []).slice(0, 40).map((e: any) =>
          `[${e.tag}] ${e.text || e.href || ''} → ${e.selector} (${e.x},${e.y})`
        ).join('\n');
        return { result: list || 'No interactive elements found' };
      }
      if (lc === 'browser links') {
        const r = await api('/links');
        if (!r.ok) return { result: r.error };
        const list = (r.links || []).map((l: any) => `${l.text} → ${l.href}`).join('\n');
        return { result: list || 'No links found' };
      }

      // ===== TABS =====
      if (lc === 'browser tabs') {
        const r = await api('/tabs');
        if (!r.ok) return { result: r.error };
        const list = (r.tabs || []).map((t: any) => `${t.active ? '>' : ' '} [${t.id}] ${t.title} - ${t.url}`).join('\n');
        return { result: list || 'No tabs' };
      }

      // ===== EXECUTE JS =====
      if (lc.startsWith('browser execute ') || lc.startsWith('browser runjs ') || lc.startsWith('browser js ')) {
        const code = cmd.replace(/^browser (execute|runjs|js)\s+/i, '').trim();
        if (!code) return { result: 'Usage: browser execute <javascript>' };
        const r = await api('/evaluate', 'POST', { code });
        return { result: r.ok ? `Result: ${r.result}` : r.error };
      }

      // ===== HISTORY =====
      if (lc === 'browser history') {
        const r = await api('/history');
        if (!r.ok) return { result: r.error };
        const list = (r.history || []).slice(0, 20).map((h: string, i: number) => `${i + 1}. ${h}`).join('\n');
        return { result: list || 'No history' };
      }

      // ===== HELP =====
      if (lc === 'browser help' || lc === 'browser') {
        return { result: `OpenBrowser v1.1 - Full Control Commands:

=== NAVIGATION ===
  browser start                - Launch browser
  browser status               - Check if running
  browser navigate <url>       - Go to URL
  browser search <query>       - Search Google
  browser back / forward       - Back/Forward
  browser reload               - Reload page

=== SEE & READ ===
  browser see                  - Screenshot + text
  browser screenshot           - Take screenshot (RAM)
  browser ss view <id>         - Get & auto-delete screenshot
  browser ss list              - List screenshots in RAM
  browser ss delete <id>       - Delete screenshot
  browser ss clear             - Clear all screenshots
  browser url                  - Current URL & title
  browser text                 - Read page text
  browser html                 - Get page HTML
  browser links                - List all links
  browser elements             - List interactive elements

=== STREAMING (20 FPS) ===
  browser stream start [fps]   - Start streaming (default 20fps)
  browser stream stop          - Stop streaming
  browser stream status        - Check stream status
  browser stream last          - Get last frame
  browser stream clear         - Clear frame buffer

=== AUDIO ===
  browser audio start          - Start recording mic
  browser audio stop           - Stop recording (returns data)
  browser audio status         - Check recording status
  browser say <text>           - Text-to-speech (Arabic)
  browser play <url>           - Play audio URL
  browser stop-sound           - Stop all playback
  browser voices               - List TTS voices

=== INTERACT ===
  browser click <selector>     - Click element (CSS selector)
  browser click-text <text>    - Click by visible text
  browser type <sel> <text>    - Type in input
  browser type-keys <sel> <txt>- Type char by char
  browser hover <selector>     - Hover element
  browser focus <selector>     - Focus element
  browser submit               - Submit form

=== SCROLL ===
  browser scroll down/up       - Scroll page
  browser scroll top/bottom    - Jump to top/bottom
  browser scroll to <selector>- Scroll to element

=== OTHER ===
  browser tabs                 - List tabs
  browser execute <js>         - Run JavaScript
  browser history              - Visit history` };
      }

      return undefined;
    },
  },
} satisfies Plugin;
