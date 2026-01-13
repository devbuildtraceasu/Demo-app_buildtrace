import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import "./lib/debug"; // Initialize debug utilities

// Global error handler
window.addEventListener("error", (event) => {
  console.error("Global error:", event.error);
});

window.addEventListener("unhandledrejection", (event) => {
  console.error("Unhandled promise rejection:", event.reason);
});

createRoot(document.getElementById("root")!).render(<App />);
