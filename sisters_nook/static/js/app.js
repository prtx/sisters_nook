(() => {
  function toMoney(value) {
    const n = Number(value || 0);
    if (Number.isNaN(n)) {
      return "NRs 0.00";
    }
    return `NRs ${n.toFixed(2)}`;
  }

  function readNumber(inputId) {
    const input = document.getElementById(inputId);
    if (!input) {
      return 0;
    }
    const n = Number(input.value || 0);
    return Number.isNaN(n) ? 0 : n;
  }

  function updateOrderTotals() {
    const lines = document.querySelectorAll("[data-price][data-qty-target]");
    let subtotal = 0;
    lines.forEach((el) => {
      const qtyInput = document.getElementById(el.dataset.qtyTarget);
      const qty = qtyInput ? Number(qtyInput.value || 0) : 0;
      const safeQty = Number.isNaN(qty) ? 0 : Math.max(0, qty);
      subtotal += Number(el.dataset.price || 0) * safeQty;
    });

    const tax = readNumber("tax_total");
    const discount = readNumber("discount_total");
    const tip = readNumber("tip_total");
    const total = Math.max(0, subtotal + tax - discount + tip);

    const subtotalEl = document.getElementById("subtotalValue");
    const taxEl = document.getElementById("taxValue");
    const totalEl = document.getElementById("totalValue");

    if (subtotalEl) subtotalEl.textContent = toMoney(subtotal);
    if (taxEl) taxEl.textContent = toMoney(tax);
    if (totalEl) totalEl.textContent = toMoney(total);
  }

  function bindOrderCreate() {
    const form = document.getElementById("createOrderForm");
    if (!form) return;

    form.querySelectorAll("input").forEach((el) => {
      if (
        el.name.startsWith("qty_") ||
        el.id === "tax_total" ||
        el.id === "discount_total" ||
        el.id === "tip_total"
      ) {
        el.addEventListener("input", updateOrderTotals);
      }
    });

    form.addEventListener("submit", (event) => {
      const qtyInputs = form.querySelectorAll("input[name^='qty_']");
      const hasItems = Array.from(qtyInputs).some((input) => Number(input.value || 0) > 0);
      if (!hasItems) {
        event.preventDefault();
        const error = document.getElementById("orderFormError");
        if (error) {
          error.textContent = "Add at least one menu item before saving the order.";
        }
      }
    });

    updateOrderTotals();
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindOrderCreate();
  });
})();
