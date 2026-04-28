import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { initSentry } from "@/lib/sentry";
import { registerServiceWorker } from "@/lib/serviceWorker";

initSentry();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

registerServiceWorker();
