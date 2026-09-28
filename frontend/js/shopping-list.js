/* shopping-list.js - load, draw and change the shopping list. */
const ShoppingList = {
  items: [],

  init() {
    const list = document.getElementById("shoppingList");
    list.addEventListener("click", (event) => this.onClick(event));
    list.addEventListener("change", (event) => this.onChange(event));

    document.getElementById("addItemForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const nameInput = document.getElementById("addName");
      const qtyInput = document.getElementById("addQty");
      const added = await this.add({ name: nameInput.value.trim(), quantity: Number(qtyInput.value) || 1 });
      if (added) { nameInput.value = ""; qtyInput.value = 1; }
    });

    document.getElementById("clearPurchased").addEventListener("click", async () => {
      try {
        await App.api("/shopping-list/clear-purchased", { method: "POST" });
        App.toast("Purchased items cleared", "success");
        await App.refreshAfterListChange();
      } catch (error) { App.toast(error.message, "error"); }
    });
  },

  async load() {
    this.items = await App.api("/shopping-list");
    this.render();
  },

  render() {
    const list = document.getElementById("shoppingList");
    const pending = this.items.filter((i) => !i.purchased);
    const done = this.items.filter((i) => i.purchased);

    list.innerHTML = [...pending, ...done].map((item) => this.rowHtml(item)).join("");
    document.getElementById("listEmpty").hidden = this.items.length > 0;
    document.getElementById("clearPurchased").hidden = done.length === 0;
    document.getElementById("listCount").textContent =
      this.items.length ? `${pending.length} to buy` : "";
  },

  rowHtml(item) {
    const id = App.escapeHtml(item.id);
    const name = App.escapeHtml(item.name);
    const disabled = item.purchased ? "disabled" : "";
    return `
      <li class="item ${item.purchased ? "is-purchased" : ""}" data-id="${id}">
        <div class="item-main">
          <span class="item-name">${name}</span>
          <span class="chip">${App.escapeHtml(item.category)}</span>
          ${item.purchased ? '<span class="chip chip-done">Purchased</span>' : ""}
        </div>
        <div class="qty" role="group" aria-label="Quantity for ${name}">
          <button type="button" class="qty-btn" data-action="dec" aria-label="Decrease quantity" ${disabled}>−</button>
          <input class="qty-input" type="number" min="1" step="any" value="${item.quantity}" aria-label="Quantity" ${disabled}>
          <input class="unit-input" type="text" value="${App.escapeHtml(item.unit || "")}" placeholder="unit" maxlength="20" aria-label="Unit" ${disabled}>
          <button type="button" class="qty-btn" data-action="inc" aria-label="Increase quantity" ${disabled}>+</button>
        </div>
        <div class="item-actions">
          ${item.purchased ? "" : '<button type="button" class="btn btn-small" data-action="purchase">Mark purchased</button>'}
          <button type="button" class="btn btn-small btn-danger" data-action="remove">Remove</button>
        </div>
      </li>`;
  },

  // ---- actions (each one talks to the backend, then redraws) ----
  async add({ name, product_id, quantity = 1, unit }) {
    try {
      const result = await App.api("/shopping-list/add", {
        method: "POST", body: { name, product_id, quantity, unit } });
      App.toast(result.message, "success");
      await App.refreshAfterListChange();
      return true;
    } catch (error) {
      if (error.data && error.data.substitutes) {
        Substitutes.show(error.data);
        App.toast(error.message, "error");
      } else {
        App.toast(error.message, "error");
      }
      return false;
    }
  },

  async remove(id) {
    try {
      const result = await App.api("/shopping-list/remove", { method: "POST", body: { item_id: id } });
      App.toast(result.message, "success");
      await App.refreshAfterListChange();
    } catch (error) { App.toast(error.message, "error"); }
  },

  async update(id, quantity, unit) {
    try {
      await App.api("/shopping-list/update", { method: "POST", body: { item_id: id, quantity, unit } });
      await this.load();
    } catch (error) {
      App.toast(error.message, "error");
      await this.load();
    }
  },

  async purchase(id) {
    try {
      const result = await App.api("/purchase", { method: "POST", body: { item_id: id } });
      App.toast(result.message, "success");
      await App.refreshAfterListChange();
    } catch (error) { App.toast(error.message, "error"); }
  },

  // ---- DOM events ----
  onClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const row = button.closest(".item");
    const id = row.dataset.id;
    const action = button.dataset.action;
    const qtyInput = row.querySelector(".qty-input");
    const unitInput = row.querySelector(".unit-input");

    if (action === "remove") this.remove(id);
    else if (action === "purchase") this.purchase(id);
    else if (action === "inc") this.update(id, (Number(qtyInput.value) || 0) + 1, unitInput.value);
    else if (action === "dec") {
      const next = (Number(qtyInput.value) || 1) - 1;
      if (next >= 1) this.update(id, next, unitInput.value);
    }
  },

  onChange(event) {
    const row = event.target.closest(".item");
    if (!row) return;
    const quantity = Number(row.querySelector(".qty-input").value);
    if (!(quantity > 0)) { this.load(); return; }
    this.update(row.dataset.id, quantity, row.querySelector(".unit-input").value);
  },
};
