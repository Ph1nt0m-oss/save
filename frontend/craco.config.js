// craco.config.js
const path = require("path");
require("dotenv").config();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // iter121 — Webpack 5 persistent filesystem cache.
      // Reduces full rebuilds from ~20s → ~5-8s on warm cache (local + Docker).
      // Cache invalidates automatically when craco.config.js or package.json changes.
      webpackConfig.cache = {
        type: 'filesystem',
        version: require('./package.json').version + '-' + process.env.NODE_ENV,
        cacheDirectory: path.resolve(__dirname, 'node_modules/.cache/webpack'),
        buildDependencies: {
          config: [__filename, path.resolve(__dirname, 'package.json')],
        },
        compression: 'gzip',  // smaller cache footprint
      };

      // iter121 — Faster source maps in development (eval = no full file regen on HMR).
      // Prod build keeps default 'source-map' for debuggability.
      if (process.env.NODE_ENV === 'development') {
        webpackConfig.devtool = 'eval-cheap-module-source-map';
      }

      // iter121 — Smarter chunk splitting reduces bundle size + improves caching.
      if (webpackConfig.optimization && process.env.NODE_ENV === 'production') {
        webpackConfig.optimization.splitChunks = {
          chunks: 'all',
          cacheGroups: {
            // Radix UI gets its own chunk (large, infrequently changing)
            radix: {
              test: /[\\/]node_modules[\\/]@radix-ui[\\/]/,
              name: 'vendor-radix',
              priority: 30,
              reuseExistingChunk: true,
            },
            // Monaco editor (heavy, lazy-loaded)
            monaco: {
              test: /[\\/]node_modules[\\/](@monaco-editor|monaco-editor)[\\/]/,
              name: 'vendor-monaco',
              priority: 30,
              reuseExistingChunk: true,
            },
            // React + ReactDOM
            react: {
              test: /[\\/]node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
              name: 'vendor-react',
              priority: 30,
              reuseExistingChunk: true,
            },
            // Charts / animations
            viz: {
              test: /[\\/]node_modules[\\/](recharts|framer-motion|d3)[\\/]/,
              name: 'vendor-viz',
              priority: 25,
              reuseExistingChunk: true,
            },
            // Everything else from node_modules
            vendor: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendor',
              priority: 10,
              reuseExistingChunk: true,
            },
          },
        };
      }

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}

module.exports = webpackConfig;
