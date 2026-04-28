/**
 * Sentry initialization (env-gated, no-op when DSN absent).
 *
 * Set REACT_APP_SENTRY_DSN in frontend/.env to enable error tracking.
 * Safe to call unconditionally — does nothing if the DSN is missing,
 * so dev / preview / unconfigured environments never ship telemetry.
 */
import * as Sentry from '@sentry/react';

let initialized = false;

export function initSentry() {
  if (initialized) return;
  const dsn = process.env.REACT_APP_SENTRY_DSN;
  if (!dsn) return; // explicitly opt-in
  try {
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV || 'production',
      release: process.env.REACT_APP_RELEASE || undefined,
      tracesSampleRate: 0.1,
      // Avoid leaking PII into Sentry events
      sendDefaultPii: false,
      ignoreErrors: [
        // Browser extensions and noisy non-actionable errors
        'ResizeObserver loop',
        'Non-Error promise rejection captured',
      ],
    });
    initialized = true;
    // eslint-disable-next-line no-console
    console.info('[sentry] enabled');
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[sentry] init failed', e);
  }
}

export { Sentry };
