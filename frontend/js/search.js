/* search.js - product search form, filters and result cards. */
const Search = {
  init() {
    // Fill the brand dropdown from the catalog.
    const brands = [...new Set(App.products.map((p) => p.brand))].sort();
    const select = document.getElementById("searchBrand");
    brands.forEach((brand) => {
      const option = document.createElement("option");
      option.value = brand;
      option.textContent = brand;
      select.appendChild(option);
    });

    document.getElementById("searchForm").addEventListener("submit", (event) => {
      event.preventDefault();
      this.runFromForm();
    });
    document.getElementById("searchResults").addEventListener("click", (event) => this.onClick(event));
  },

  numberOrNull(id) {
    const value = document.getElementById(id).value;
    return value === "" ? null : Number(value);
  },

  async runFromForm() {
    const filters = {
      query: document.getElementById("searchQuery").value.trim(),
      brand: document.getElementById("searchBrand").value || null,
      min_price: this.numberOrNull("searchMin"),
      max_price: this.numberOrNull("searchMax"),
    };
    try {
      const data = await App.api("/search", { method: "POST", body: filters });
      this.render(data);
      App.toast("Search completed", "success");
    } catch (error) { App.toast(error.message, "error"); }
  },

  /** Called by voice.js with the products the backend found. */
  showVoiceResults(response) {
    const f = response.filters || {};
    document.getElementById("searchQuery").value = f.query || "";
    document.getElementById("searchBrand").value = f.brand || "";
    document.getElementById("searchMin").value = f.min_price ?? "";
    document.getElementById("searchMax").value = f.max_price ?? "";
    this.render({ count: response.count, filters: f, products: response.products });
    document.getElementById("searchResults").scrollIntoView({ behavior: "smooth", block: "nearest" });
  },

  render(data) {
    const summary = document.getElementById("searchSummary");
    const box = document.getElementById("searchResults");
    const f = data.filters || {};
    const parts = [];
    if (f.query) parts.push(`"${f.query}"`);
    if (f.brand) parts.push(`brand ${f.brand}`);
    if (f.size) parts.push(`size ${f.size}`);
    if (f.min_price != null) parts.push(`from ${App.formatPrice(f.min_price)}`);
    if (f.max_price != null) parts.push(`up to ${App.formatPrice(f.max_price)}`);
    summary.hidden = false;
    summary.textContent = data.count
      ? `${data.count} product${data.count === 1 ? "" : "s"} found${parts.length ? " for " + parts.join(", ") : ""}`
      : `No products matched${parts.length ? " " + parts.join(", ") : ""}. Try a shorter name or wider prices.`;

    box.innerHTML = data.products.map((p) => this.cardHtml(p)).join("");

    // Show alternatives right away when the search is narrow and something is unavailable.
    const unavailable = data.products.find((p) => !p.available);
    if (unavailable && data.products.length <= 3) {
      Substitutes.show({ product: unavailable, substitutes: unavailable.substitutes || [] });
    }
  },

  cardHtml(p) {
    const id = App.escapeHtml(p.id);
    const action = p.available
      ? `<button type="button" class="btn btn-small" data-action="add" data-id="${id}">Add to list</button>`
      : `<button type="button" class="btn btn-small btn-quiet" data-action="alternatives" data-id="${id}">See alternatives</button>`;
    return `
      <article class="product ${p.available ? "" : "is-unavailable"}">
        <div class="product-top">
          <h3>${App.escapeHtml(p.name)}</h3>
          <span class="price">${App.formatPrice(p.price)}</span>
        </div>
        <dl class="facts">
          <div><dt>Brand</dt><dd>${App.escapeHtml(p.brand)}</dd></div>
          <div><dt>Category</dt><dd>${App.escapeHtml(p.category)}</dd></div>
          <div><dt>Size</dt><dd>${App.escapeHtml(p.size)}</dd></div>
        </dl>
        <div class="product-foot">
          <span class="badge ${p.available ? "badge-ok" : "badge-out"}">${p.available ? "In stock" : "Unavailable"}</span>
          ${action}
        </div>
      </article>`;
  },

  async onClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    if (button.dataset.action === "add") {
      await ShoppingList.add({ product_id: button.dataset.id });
    } else if (button.dataset.action === "alternatives") {
      await Substitutes.load(button.dataset.id);
    }
  },
};

/* The "Suggested substitutes" panel lives here because search is where it is used most. */
const Substitutes = {
  init() {
    document.getElementById("closeSubstitutes").addEventListener("click", () => this.hide());
    document.getElementById("substitutes").addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-id]");
      if (button) await ShoppingList.add({ product_id: button.dataset.id });
    });
  },

  async load(productId) {
    try {
      this.show(await App.api(`/substitutes/${encodeURIComponent(productId)}`));
    } catch (error) { App.toast(error.message, "error"); }
  },

  /** data = { product: {name}, substitutes: [ ... ] } */
  show(data) {
    const card = document.getElementById("substitutesCard");
    const name = data.product ? data.product.name : "That product";
    document.getElementById("substitutesIntro").textContent = data.substitutes.length
      ? `${name} is unavailable. You could try one of these instead:`
      : `${name} is unavailable and we have no alternatives for it yet.`;
    document.getElementById("substitutes").innerHTML = data.substitutes.map((s) => `
      <li class="suggestion">
        <div>
          <strong>${App.escapeHtml(s.name)}</strong>
          <span class="suggestion-sub">${App.escapeHtml(s.size || "")}, ${App.formatPrice(s.price)}</span>
        </div>
        <button type="button" class="btn btn-small" data-id="${App.escapeHtml(s.id)}">Add</button>
      </li>`).join("");
    card.hidden = false;
  },

  hide() { document.getElementById("substitutesCard").hidden = true; },
};
document.addEventListener("DOMContentLoaded", () => Substitutes.init());
