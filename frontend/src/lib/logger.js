/**
 * Tiny logger that strips dev noise from production bundles.
 *
 * Behavior:
 *   logger.log/info/warn  → no-op in production (NODE_ENV === 'production')
 *   logger.error          → always logs (so Sentry / browser devtools see it)
 *
 * Use this instead of bare console.* calls in feature code. Bare console.*
 * is OK in lib/sentry.js and lib/serviceWorker.js where the message is
 * the actual point of the file.
 */
const isProd = process.env.NODE_ENV === 'production';

const noop = () => {};

export const logger = {
  log: isProd ? noop : (...args) => console.log(...args),
  info: isProd ? noop : (...args) => console.info(...args),
  warn: isProd ? noop : (...args) => console.warn(...args),
  error: (...args) => console.error(...args),
};

export default logger;
