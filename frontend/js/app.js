/* app.js - startup, API helper and small UI utilities shared by every module. */
const App = {
  // Served by FastAPI -> same origin. Opened as a file -> talk to localhost:8000.
  API_BASE: window.location.protocol === "file:" ? "http://localhost:8000" : "",
  products: [],

  async api(path, { method = "GET", body } = {}) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(this.API_BASE + path, options);
    } catch (networkError) {
      throw new Error("Can't reach the server. Start the backend and reload this page.");
    }
    let data = null;
    try { data = await response.json(); } catch (parseError) { /* empty body */ }
    if (!response.ok) {
      const error = new Error(this.errorMessage(data));
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  },

  errorMessage(data) {
    if (!data) return "Something went wrong. Please try again.";
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; ");
    return data.message || "Something went wrong. Please try again.";
  },

  escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  },

  formatPrice(value) {
    return "₹" + Number(value).toLocaleString("en-IN");
  },

  sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); },

  /** Small pop-up message. type: "success" | "error" | "info" */
  toast(message, type = "info") {
    const box = document.createElement("div");
    box.className = `toast toast-${type}`;
    box.textContent = (type === "success" ? "✓ " : "") + message;
    const holder = document.getElementById("toasts");
    holder.appendChild(box);
    while (holder.children.length > 3) holder.firstElementChild.remove();   // keep the screen tidy
    setTimeout(() => box.remove(), 4200);
  },

  /** Run after anything changes the list. */
  async refreshAfterListChange() {
    await Promise.all([ShoppingList.load(), Recommendations.load()]);
  },

  async init() {
    try {
      this.products = await this.api("/products");
    } catch (error) {
      this.toast(error.message, "error");
    }
    Search.init();
    ShoppingList.init();
    Recommendations.init();
    Voice.init();
    ShoppingList.load().catch((e) => this.toast(e.message, "error"));
    Recommendations.load().catch(() => {});
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
