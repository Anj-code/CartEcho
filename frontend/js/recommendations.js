/* recommendations.js - "You might also need" suggestions from the rule engine. */
const Recommendations = {
  init() {
    document.getElementById("recommendations").addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-id]");
      if (button) await ShoppingList.add({ product_id: button.dataset.id });
    });
  },

  async load() {
    const data = await App.api("/recommend", { method: "POST", body: {} });
    this.render(data.recommendations);
  },

  render(recommendations) {
    const list = document.getElementById("recommendations");
    if (!recommendations.length) {
      list.innerHTML = '<li class="empty">Nothing to suggest yet. Mark items as purchased and ideas will appear here.</li>';
      return;
    }
    list.innerHTML = recommendations.map((r) => `
      <li class="suggestion">
        <div>
          <strong>${App.escapeHtml(r.name)}</strong>
          <span class="suggestion-sub">${App.escapeHtml(r.reason)}</span>
        </div>
        <button type="button" class="btn btn-small" data-id="${App.escapeHtml(r.product_id)}">Add to list</button>
      </li>`).join("");
  },
};
