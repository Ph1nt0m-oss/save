/**
 * Service worker registration helper.
 * - Only registers in production builds (CRA sets NODE_ENV automatically).
 * - The actual SW file is served from /sw.js at the root of the deployed app.
 * - Safe no-op in dev / unsupported browsers.
 */
export function registerServiceWorker() {
  if (typeof window === 'undefined') return;
  if (process.env.NODE_ENV !== 'production') return;
  if (!('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((reg) => {
        // eslint-disable-next-line no-console
        console.info('[sw] registered, scope:', reg.scope);
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn('[sw] registration failed:', err);
      });
  });
}
