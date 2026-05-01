// Detect in-app webviews (Gmail, Facebook, Instagram, LinkedIn, Twitter…)
// where Google OAuth and some other secure flows are blocked.
// Returns one of: 'safe', 'gmail', 'facebook', 'instagram', 'linkedin',
// 'twitter', 'tiktok', 'snapchat', 'webview' (generic), 'safari-ios-webview'.
export function detectWebview() {
  if (typeof navigator === 'undefined') return 'safe';
  const ua = (navigator.userAgent || '').toLowerCase();

  // Gmail in-app browser (Android/iOS)
  if (/gsa\//.test(ua) || /\bgmail\b/.test(ua)) return 'gmail';
  // Facebook (FB_IAB, FBAN, FBAV) — also Messenger
  if (/fb_iab|fban|fbav|messenger/i.test(ua)) return 'facebook';
  // Instagram
  if (/instagram/i.test(ua)) return 'instagram';
  // LinkedIn
  if (/linkedin/i.test(ua)) return 'linkedin';
  // Twitter / X
  if (/twitter/i.test(ua)) return 'twitter';
  // TikTok
  if (/musical_ly|bytelocale|aweme|tiktok/i.test(ua)) return 'tiktok';
  // Snapchat
  if (/snapchat/i.test(ua)) return 'snapchat';
  // iOS standalone webview (no Safari signature)
  // Safari UA contains 'safari' — webviews drop it.
  const isIOS = /iphone|ipod|ipad/.test(ua);
  if (isIOS && !/safari/.test(ua) && !/crios|fxios|opios|edgios/.test(ua)) {
    return 'safari-ios-webview';
  }
  // Android WebView (typical signatures)
  if (/wv\)/.test(ua) || /; wv;/.test(ua)) return 'webview';
  return 'safe';
}

export function isInWebview() {
  return detectWebview() !== 'safe';
}

// Friendly explanation per detected webview.
export function getWebviewHelpMessage(kind) {
  switch (kind) {
    case 'gmail':
      return "Tu as ouvert ce lien depuis Gmail. Pour des raisons de sécurité, Google bloque la connexion ici. Ouvre ce lien dans ton navigateur (Chrome, Safari…).";
    case 'facebook':
    case 'instagram':
    case 'linkedin':
    case 'twitter':
    case 'tiktok':
    case 'snapchat':
      return "Tu as ouvert ce lien depuis une application. Pour finaliser ta connexion, ouvre-le dans ton navigateur (Chrome, Safari…).";
    case 'safari-ios-webview':
    case 'webview':
    default:
      return "Pour finaliser ta connexion en toute sécurité, ouvre ce lien dans ton navigateur principal (Chrome, Safari, Firefox…).";
  }
}
