import { session, BrowserWindow } from 'electron';

const BLOCK_PATTERNS: RegExp[] = [
  /doubleclick\.net/i, /googlesyndication\.com/i, /googleadservices\.com/i,
  /adservice\.google/i, /pagead2?\./i, /googletagmanager\.com/i,
  /google-analytics\.com/i, /googletagservices\.com/i,
  /\.google\.[a-z]+\/(pagead|ads|pcs\/pagead)/i,
  /facebook\.com\/tr/i, /facebook\.net\/tr/i, /connect\.facebook\.net/i,
  /analytics\.twitter\.com/i, /ads-twitter\.com/i, /platform\.twitter\.com\/i\/adsct/i,
  /analytics\.tiktok\.com/i, /ads\.tiktok\.com/i,
  /ads\.linkedin\.com/i, /snap\.licdn\.com/i,
  /bat\.bing\.com/i, /clarity\.ms/i,
  /amazon-adsystem\.com/i,
  /adnxs\.com/i, /adsrvr\.org/i, /adcolony\.com/i,
  /criteo\.com/i, /criteo\.net/i, /crwdcntrl\.net/i,
  /outbrain\.com/i, /taboola\.com/i, /chartbeat\.com/i,
  /moatads\.com/i, /quantserve\.com/i, /scorecardresearch\.com/i,
  /bluekai\.com/i, /demdex\.net/i, /everesttech\.net/i,
  /rubiconproject\.com/i, /pubmatic\.com/i, /openx\.net/i,
  /casalemedia\.com/i, /mathtag\.com/i, /mediaplex\.com/i,
  /serving-sys\.com/i, /bidswitch\.net/i,
  /sharethis\.com/i, /addthis\.com/i,
  /hotjar\.com/i, /mouseflow\.com/i, /fullstory\.com/i,
  /luckyorange\.com/i, /heap\.io/i, /heapanalytics\.com/i,
  /segment\.(io|com)/i, /cdn\.segment\.com/i,
  /amplitude\.com/i, /cdn\.amplitude\.com/i,
  /mixpanel\.com/i, /cdn\.mxpnl\.com/i,
  /logrocket\.com/i, /cdn\.logrocket\.com/i,
  /optimizely\.com/i, /cdn\.optimizely\.com/i,
  /newrelic\.com/i, /js-agent\.newrelic\.com/i,
  /sentry\.io/i, /browser\.sentry-cdn\.com/i,
  /branch\.io/i, /adjust\.com/i, /appsflyer\.com/i,
  /kochava\.com/i, /singular\.net/i,
  /pinterest\.com\/track/i, /ct\.pinterest\.com/i,
  /snap\.com\/tr/i, /tr\.snap\.com/i,
  /pixel\.quantserve\.com/i, /sb\.scorecardresearch\.com/i,
  /c\.bing\.com/i, /perfectaudience\.com/i
];

export const FP_SCRIPT: string = `
(function(){
  try{
    var fp={0:{name:'PDF Viewer',filename:'internal-pdf-viewer',description:'Portable Document Format',length:1},1:{name:'Chrome PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},2:{name:'Chromium PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},3:{name:'Microsoft Edge PDF Viewer',filename:'internal-pdf-viewer',description:'',length:1},4:{name:'WebKit built-in PDF',filename:'internal-pdf-viewer',description:'',length:1},length:5,item:function(i){return this[i]},namedItem:function(n){for(var i=0;i<5;i++)if(this[i]&&this[i].name===n)return this[i];return null},refresh:function(){}};
    Object.defineProperty(navigator,'plugins',{get:function(){return fp}});
    Object.defineProperty(navigator,'languages',{get:function(){return['en-US','en','ar']}});
    Object.defineProperty(navigator,'language',{get:function(){return'en-US'}});
    Object.defineProperty(navigator,'platform',{get:function(){return'Win32'}});
    Object.defineProperty(navigator,'hardwareConcurrency',{get:function(){return 8}});
    Object.defineProperty(navigator,'deviceMemory',{get:function(){return 8}});
    Object.defineProperty(navigator,'maxTouchPoints',{get:function(){return 0}});
    Object.defineProperty(navigator,'doNotTrack',{get:function(){return'1'}});
    Object.defineProperty(navigator,'webdriver',{get:function(){return false}});
    Object.defineProperty(navigator,'vendorSub',{get:function(){return''}});
    Object.defineProperty(navigator,'productSub',{get:function(){return'20030107'}});
    Object.defineProperty(navigator,'cookieEnabled',{get:function(){return true}});
  }catch(e){}
  try{
    Object.defineProperty(screen,'colorDepth',{get:function(){return 24}});
    Object.defineProperty(screen,'pixelDepth',{get:function(){return 24}});
    Object.defineProperty(screen,'availWidth',{get:function(){return 1920}});
    Object.defineProperty(screen,'availHeight',{get:function(){return 1040}});
    Object.defineProperty(screen,'width',{get:function(){return 1920}});
    Object.defineProperty(screen,'height',{get:function(){return 1080}});
  }catch(e){}
  try{
    var oTD=HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL=function(type){
      if(type==='image/webp')return oTD.apply(this,arguments);
      var ctx=this.getContext('2d');
      if(ctx){var d;try{d=ctx.getImageData(0,0,Math.min(this.width,16),Math.min(this.height,16));}catch(e){return oTD.apply(this,arguments);}
      for(var i=0;i<d.data.length;i+=4){d.data[i]=d.data[i]^((i%7)<1?1:0);d.data[i+1]=d.data[i+1]^((i%11)<1?1:0);d.data[i+2]=d.data[i+2]^((i%13)<1?1:0);}
      ctx.putImageData(d,0,0);}
      return oTD.apply(this,arguments);
    };
  }catch(e){}
  try{
    var oTB=HTMLCanvasElement.prototype.toBlob;
    if(oTB){HTMLCanvasElement.prototype.toBlob=function(cb,type,q){
      var ctx=this.getContext('2d');
      if(ctx){var d;try{d=ctx.getImageData(0,0,Math.min(this.width,16),Math.min(this.height,16));}catch(e){return oTB.apply(this,arguments);}
      for(var i=0;i<d.data.length;i+=4){d.data[i]=d.data[i]^((i%7)<1?1:0);d.data[i+1]=d.data[i+1]^((i%11)<1?1:0);d.data[i+2]=d.data[i+2]^((i%13)<1?1:0);}
      ctx.putImageData(d,0,0);}
      return oTB.apply(this,arguments);
    };}
  }catch(e){}
  try{
    var oGP=WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter=function(p){
      if(p===37445)return'Intel Inc.';
      if(p===37446)return'Intel Iris OpenGL Engine';
      return oGP.apply(this,arguments);
    };
    var oGP2=WebGL2RenderingContext.prototype.getParameter;
    if(oGP2){WebGL2RenderingContext.prototype.getParameter=function(p){
      if(p===37445)return'Intel Inc.';
      if(p===37446)return'Intel Iris OpenGL Engine';
      return oGP2.apply(this,arguments);
    };}
  }catch(e){}
  try{
    var AC=window.AudioContext||window.webkitAudioContext;
    if(AC){
      var oCO=AC.prototype.createOscillator;
      AC.prototype.createOscillator=function(){
        var o=oCO.apply(this,arguments);
        if(o.frequency){var ov=o.frequency.value;
        Object.defineProperty(o.frequency,'value',{get:function(){return ov},set:function(v){ov=v+Math.random()*0.0001}});}
        return o;
      };
    }
    var oGCD=AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData=function(ch){
      var d=oGCD.apply(this,arguments);
      for(var i=0;i<Math.min(d.length,10);i++)d[i]=d[i]+Math.random()*0.0000001;
      return d;
    };
  }catch(e){}
  try{
    var oMT=CanvasRenderingContext2D.prototype.measureText;
    CanvasRenderingContext2D.prototype.measureText=function(){
      var r=oMT.apply(this,arguments);
      var w=r.width;
      Object.defineProperty(r,'width',{get:function(){return w+Math.random()*0.001}});
      return r;
    };
  }catch(e){}
  try{Date.prototype.getTimezoneOffset=function(){return 0};}catch(e){}
  try{
    if(navigator.getBattery){
      navigator.getBattery=function(){return Promise.resolve({charging:true,chargingTime:0,dischargingTime:Infinity,level:1,addEventListener:function(){},removeEventListener:function(){}});};
    }
  }catch(e){}
  try{
    var oRTC=window.RTCPeerConnection;
    if(oRTC){
      window.RTCPeerConnection=function(cfg,cons){
        cfg=cfg||{};cfg.iceServers=[];
        return new oRTC(cfg,cons);
      };
      window.RTCPeerConnection.prototype=oRTC.prototype;
    }
  }catch(e){}
  try{
    var oGCR=Element.prototype.getClientRects;
    Element.prototype.getClientRects=function(){
      var rects=oGCR.apply(this,arguments);
      var fake=[];
      for(var i=0;i<rects.length;i++){
        var r=rects[i];
        fake.push({x:r.x+Math.random()*0.001,y:r.y+Math.random()*0.001,width:r.width+Math.random()*0.001,height:r.height+Math.random()*0.001,top:r.top+Math.random()*0.001,bottom:r.bottom+Math.random()*0.001,left:r.left+Math.random()*0.001,right:r.right+Math.random()*0.001});
      }
      return fake;
    };
  }catch(e){}
  console.log('[OpenBrowser] Privacy active on '+location.hostname);
})();
`;

export class PrivacyEngine {
  adBlockerEnabled: boolean = true;
  trackerBlockerEnabled: boolean = true;
  fingerprintProtectionEnabled: boolean = true;
  blockedCount: number = 0;
  trackerCount: number = 0;

  updateSettings(settings: any): void {
    this.adBlockerEnabled = settings.adBlocker !== false;
    this.trackerBlockerEnabled = settings.trackerBlocker !== false;
    this.fingerprintProtectionEnabled = settings.fingerprintProtection !== false;
  }

  shouldBlock(url: string): boolean {
    if (!url) return false;
    if (url.startsWith('openbrowser://') || url.startsWith('file://') || url.startsWith('about:')) return false;
    for (const pattern of BLOCK_PATTERNS) {
      if (pattern.test(url)) {
        this.blockedCount++;
        return true;
      }
    }
    return false;
  }

  setup(mainWindow: BrowserWindow): void {
    const self = this;

    session.defaultSession.webRequest.onBeforeRequest(
      { urls: ['*://*/*'] },
      (details: any, callback: (response: { cancel: boolean }) => void) => {
        if (details.url.startsWith('openbrowser://') || details.url.startsWith('file://') || details.url.startsWith('about:')) {
          return callback({ cancel: false });
        }
        if (self.shouldBlock(details.url)) {
          return callback({ cancel: true });
        }
        callback({ cancel: false });
      }
    );

    const inject = (wc: any) => {
      if (!self.fingerprintProtectionEnabled) return;
      wc.on('dom-ready', () => {
        wc.executeJavaScript(FP_SCRIPT).catch(() => {});
      });
      wc.on('did-finish-load', () => {
        wc.executeJavaScript(FP_SCRIPT).catch(() => {});
      });
    };

    inject(mainWindow.webContents);

    mainWindow.webContents.on('did-navigate', () => {
      if (self.fingerprintProtectionEnabled) {
        mainWindow.webContents.executeJavaScript(FP_SCRIPT).catch(() => {});
      }
    });
    mainWindow.webContents.on('did-navigate-in-page', () => {
      if (self.fingerprintProtectionEnabled) {
        mainWindow.webContents.executeJavaScript(FP_SCRIPT).catch(() => {});
      }
    });
  }

  getStats() {
    return {
      adsBlocked: this.blockedCount,
      trackersBlocked: this.trackerCount,
      adBlockerEnabled: this.adBlockerEnabled,
      trackerBlockerEnabled: this.trackerBlockerEnabled,
      fingerprintProtectionEnabled: this.fingerprintProtectionEnabled
    };
  }
}
