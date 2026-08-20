// OpenBrowser Privacy Preload
// Runs BEFORE any page scripts — this is the KEY to fingerprint protection
// Must be loaded as webview preload

(function() {
  // 1. Navigator
  try {
    var fp = {0:{name:'PDF Viewer',filename:'internal-pdf-viewer',description:'Portable Document Format',length:1},1:{name:'Chrome PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},2:{name:'Chromium PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},3:{name:'Microsoft Edge PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},4:{name:'WebKit built-in PDF',filename:'internal-pdf-viewer',description:'',length:1},length:5,item:function(i){return this[i]},namedItem:function(n){for(var i=0;i<5;i++)if(this[i]&&this[i].name===n)return this[i];return null},refresh:function(){}};
    Object.defineProperty(navigator, 'plugins', {get:function(){return fp}});
    Object.defineProperty(navigator, 'languages', {get:function(){return['en-US','en','ar']}});
    Object.defineProperty(navigator, 'language', {get:function(){return'en-US'}});
    Object.defineProperty(navigator, 'platform', {get:function(){return'Win32'}});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get:function(){return 8}});
    Object.defineProperty(navigator, 'deviceMemory', {get:function(){return 8}});
    Object.defineProperty(navigator, 'maxTouchPoints', {get:function(){return 0}});
    Object.defineProperty(navigator, 'doNotTrack', {get:function(){return'1'}});
    Object.defineProperty(navigator, 'webdriver', {get:function(){return false}});
    Object.defineProperty(navigator, 'vendorSub', {get:function(){return''}});
    Object.defineProperty(navigator, 'productSub', {get:function(){return'20030107'}});
    Object.defineProperty(navigator, 'cookieEnabled', {get:function(){return true}});
    Object.defineProperty(navigator, 'buildID', {get:function(){return'20181001000000'}});
    Object.defineProperty(navigator, 'oscpu', {get:function(){return undefined}});
    Object.defineProperty(navigator, 'mimeTypes', {get:function(){return{length:1,item:function(i){return{type:'application/pdf',suffixes:'',description:'Portable Document Format'}},namedItem:function(){return null}}}});
  } catch(e) {}

  // 2. Screen
  try {
    Object.defineProperty(screen, 'colorDepth', {get:function(){return 24}});
    Object.defineProperty(screen, 'pixelDepth', {get:function(){return 24}});
    Object.defineProperty(screen, 'availWidth', {get:function(){return 1920}});
    Object.defineProperty(screen, 'availHeight', {get:function(){return 1040}});
    Object.defineProperty(screen, 'width', {get:function(){return 1920}});
    Object.defineProperty(screen, 'height', {get:function(){return 1080}});
  } catch(e) {}

  // 3. Canvas fingerprint
  try {
    var oTD = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
      if (type === 'image/webp') return oTD.apply(this, arguments);
      var ctx = this.getContext('2d');
      if (ctx) {
        var d;
        try { d = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16)); } catch(e) { return oTD.apply(this, arguments); }
        for (var i = 0; i < d.data.length; i += 4) {
          d.data[i] = d.data[i] ^ ((i%7)<1 ? 1 : 0);
          d.data[i+1] = d.data[i+1] ^ ((i%11)<1 ? 1 : 0);
          d.data[i+2] = d.data[i+2] ^ ((i%13)<1 ? 1 : 0);
        }
        ctx.putImageData(d, 0, 0);
      }
      return oTD.apply(this, arguments);
    };
    var oTB = HTMLCanvasElement.prototype.toBlob;
    if (oTB) {
      HTMLCanvasElement.prototype.toBlob = function(cb, type, q) {
        var ctx = this.getContext('2d');
        if (ctx) {
          var d;
          try { d = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16)); } catch(e) { return oTB.apply(this, arguments); }
          for (var i = 0; i < d.data.length; i += 4) {
            d.data[i] = d.data[i] ^ ((i%7)<1 ? 1 : 0);
            d.data[i+1] = d.data[i+1] ^ ((i%11)<1 ? 1 : 0);
            d.data[i+2] = d.data[i+2] ^ ((i%13)<1 ? 1 : 0);
          }
          ctx.putImageData(d, 0, 0);
        }
        return oTB.apply(this, arguments);
      };
    }
    // CanvasRenderingContext2D.getImageData - add noise
    var oGID = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function() {
      var data = oGID.apply(this, arguments);
      for (var i = 0; i < Math.min(data.data.length, 40); i++) {
        data.data[i] = data.data[i] ^ ((i%3)<1 ? 1 : 0);
      }
      return data;
    };
  } catch(e) {}

  // 4. WebGL fingerprint
  try {
    var oGP = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
      if (p === 37445) return 'Intel Inc.';
      if (p === 37446) return 'Intel Iris OpenGL Engine';
      return oGP.apply(this, arguments);
    };
    var oGP2 = WebGL2RenderingContext.prototype.getParameter;
    if (oGP2) {
      WebGL2RenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Intel Inc.';
        if (p === 37446) return 'Intel Iris OpenGL Engine';
        return oGP2.apply(this, arguments);
      };
    }
    // getSupportedExtensions
    var oGSE = WebGLRenderingContext.prototype.getSupportedExtensions;
    WebGLRenderingContext.prototype.getSupportedExtensions = function() {
      return ['OES_texture_float', 'OES_texture_half_float', 'WEBGL_lose_context', 'EXT_color_buffer_float'];
    };
    // getShaderPrecisionFormat
    var oGSPF = WebGLRenderingContext.prototype.getShaderPrecisionFormat;
    if (oGSPF) {
      WebGLRenderingContext.prototype.getShaderPrecisionFormat = function() {
        var r = oGSPF.apply(this, arguments);
        return { rangeMin: r.rangeMin, rangeMax: r.rangeMax, precision: r.precision };
      };
    }
  } catch(e) {}

  // 5. AudioContext fingerprint
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (AC) {
      var oCO = AC.prototype.createOscillator;
      if (oCO) {
        AC.prototype.createOscillator = function() {
          var o = oCO.apply(this, arguments);
          if (o.frequency) {
            var ov = o.frequency.value;
            Object.defineProperty(o.frequency, 'value', {
              get: function() { return ov },
              set: function(v) { ov = v + Math.random() * 0.0001 }
            });
          }
          return o;
        };
      }
      // AnalyserNode
      var oCA = AC.prototype.createAnalyser;
      if (oCA) {
        AC.prototype.createAnalyser = function() {
          var a = oCA.apply(this, arguments);
          var oGFD = a.getFloatFrequencyData;
          a.getFloatFrequencyData = function(d) { for (var i=0;i<d.length;i++) d[i]=d[i]+Math.random()*0.0001; return oGFD.apply(this, arguments); };
          var oGID2 = a.getIntegerFrequencyData;
          if (oGID2) { a.getIntegerFrequencyData = function(d) { for (var i=0;i<d.length;i++) d[i]=d[i]+((Math.random()>0.5)?1:0); return oGID2.apply(this, arguments); }; }
          return a;
        };
      }
    }
    // AudioBuffer.getChannelData
    var oGCD = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function(ch) {
      var d = oGCD.apply(this, arguments);
      for (var i = 0; i < Math.min(d.length, 10); i++) d[i] = d[i] + Math.random() * 0.0000001;
      return d;
    };
  } catch(e) {}

  // 6. Fonts
  try {
    var oMT = CanvasRenderingContext2D.prototype.measureText;
    CanvasRenderingContext2D.prototype.measureText = function() {
      var r = oMT.apply(this, arguments);
      var w = r.width;
      Object.defineProperty(r, 'width', {get:function(){return w + Math.random() * 0.001}});
      return r;
    };
  } catch(e) {}

  // 7. Timezone
  try {
    Date.prototype.getTimezoneOffset = function() { return 0 };
    // Override Intl.DateTimeFormat resolvedOptions
    if (Intl && Intl.DateTimeFormat) {
      var oRes = Intl.DateTimeFormat.prototype.resolvedOptions;
      if (oRes) {
        Intl.DateTimeFormat.prototype.resolvedOptions = function() {
          var r = oRes.apply(this, arguments);
          r.timeZone = 'UTC';
          return r;
        };
      }
    }
  } catch(e) {}

  // 8. Battery API
  try {
    if (navigator.getBattery) {
      navigator.getBattery = function() {
        return Promise.resolve({
          charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1,
          addEventListener: function() {}, removeEventListener: function() {}, dispatchEvent: function(){return true}
        });
      };
    }
  } catch(e) {}

  // 9. Connection API
  try {
    Object.defineProperty(navigator, 'connection', {
      get: function() { return { effectiveType: '4g', rtt: 50, downlink: 10, saveData: false }; }
    });
  } catch(e) {}

  // 10. Permissions API
  try {
    var oPQ = navigator.permissions && navigator.permissions.query;
    if (oPQ) {
      navigator.permissions.query = function() {
        return Promise.resolve({ state: 'prompt', status: 'prompt', addEventListener: function(){}, removeEventListener: function(){} });
      };
    }
  } catch(e) {}

  // 11. WebRTC leak protection
  try {
    var oRTC = window.RTCPeerConnection;
    if (oRTC) {
      window.RTCPeerConnection = function(cfg, cons) {
        cfg = cfg || {};
        cfg.iceServers = [];
        return new oRTC(cfg, cons);
      };
      window.RTCPeerConnection.prototype = oRTC.prototype;
    }
  } catch(e) {}

  // 12. ClientRects
  try {
    var oGCR = Element.prototype.getClientRects;
    Element.prototype.getClientRects = function() {
      var rects = oGCR.apply(this, arguments);
      var fake = [];
      for (var i = 0; i < rects.length; i++) {
        var r = rects[i];
        fake.push({
          x: r.x + Math.random()*0.001, y: r.y + Math.random()*0.001,
          width: r.width + Math.random()*0.001, height: r.height + Math.random()*0.001,
          top: r.top + Math.random()*0.001, bottom: r.bottom + Math.random()*0.001,
          left: r.left + Math.random()*0.001, right: r.right + Math.random()*0.001
        });
      }
      return fake;
    };
  } catch(e) {}

  // 13. Performance.now() spoofing
  try {
    var oPN = performance.now.bind(performance);
    performance.now = function() { return oPN() + Math.random() * 0.001; };
  } catch(e) {}

  // 14. localStorage quota
  try {
    Object.defineProperty(navigator, 'storage', {
      get: function() {
        return {
          estimate: function() { return Promise.resolve({ quota: 2147483648, usage: 0 }); },
          persist: function() { return Promise.resolve(true); },
          persisted: function() { return Promise.resolve(false); }
        };
      }
    });
  } catch(e) {}

  console.log('[OpenBrowser] Preload privacy active');
})();
