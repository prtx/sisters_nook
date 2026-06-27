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

  function calculateAdjustmentAmount(typeId, valueId, totalId, subtotal, capToSubtotal = false) {
    const typeEl = document.getElementById(typeId);
    const valueEl = document.getElementById(valueId);
    const totalEl = document.getElementById(totalId);

    const adjustmentType = typeEl ? typeEl.value : "amount";
    let adjustmentValue = valueEl ? Number(valueEl.value || 0) : 0;
    if (Number.isNaN(adjustmentValue) || adjustmentValue < 0) {
      adjustmentValue = 0;
    }

    let adjustmentAmount = 0;
    if (adjustmentType === "percent") {
      const clampedPercent = Math.min(100, adjustmentValue);
      adjustmentAmount = subtotal * (clampedPercent / 100);
    } else {
      adjustmentAmount = capToSubtotal ? Math.min(subtotal, adjustmentValue) : adjustmentValue;
    }

    if (totalEl) totalEl.value = adjustmentAmount.toFixed(2);
    return adjustmentAmount;
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

    const discount = calculateAdjustmentAmount("discount_type", "discount_value", "discount_total", subtotal, true);
    const tax = calculateAdjustmentAmount("tax_type", "tax_value", "tax_total", subtotal);
    const tip = calculateAdjustmentAmount("tip_type", "tip_value", "tip_total", subtotal);
    const total = Math.max(0, subtotal - discount + tax + tip);

    const subtotalEl = document.getElementById("subtotalValue");
    const discountRowEl = document.getElementById("discountRow");
    const discountAmountEl = document.getElementById("discountAmountValue");
    const taxEl = document.getElementById("taxValue");
    const totalEl = document.getElementById("totalValue");

    if (subtotalEl) subtotalEl.textContent = toMoney(subtotal);
    if (discountRowEl) discountRowEl.hidden = !(discount > 0);
    if (discountAmountEl) discountAmountEl.textContent = toMoney(discount);
    if (taxEl) taxEl.textContent = toMoney(tax);
    if (totalEl) totalEl.textContent = toMoney(total);
  }

  function setQty(control, nextQty) {
    const targetId = control.dataset.qtyTarget;
    const input = targetId ? document.getElementById(targetId) : null;
    if (!input) return;
    const qty = Math.max(0, Number(nextQty) || 0);
    input.value = String(qty);

    const qtyDisplay = control.querySelector("[data-qty-display]");
    if (qtyDisplay) qtyDisplay.textContent = String(qty);
    const menuCard = control.closest(".menu-card");
    if (menuCard) {
      menuCard.classList.toggle("menu-card-selected", qty > 0);
    }
  }

  function bindMenuQuantitySteppers(form) {
    const controls = form.querySelectorAll("[data-price][data-qty-target]");
    controls.forEach((control) => {
      const targetId = control.dataset.qtyTarget;
      const input = targetId ? document.getElementById(targetId) : null;
      const startingQty = input ? Number(input.value || 0) : 0;
      setQty(control, startingQty);

      const plusBtn = control.querySelector("[data-plus-btn]");
      const minusBtn = control.querySelector("[data-minus-btn]");

      if (plusBtn) {
        plusBtn.addEventListener("click", () => {
          const current = input ? Number(input.value || 0) : 0;
          setQty(control, current + 1);
          updateOrderTotals();
        });
      }
      if (minusBtn) {
        minusBtn.addEventListener("click", () => {
          const current = input ? Number(input.value || 0) : 0;
          setQty(control, current - 1);
          updateOrderTotals();
        });
      }
    });
  }

  function bindOrderCreate() {
    const form = document.getElementById("createOrderForm");
    if (!form) return;

    bindMenuQuantitySteppers(form);

    form.querySelectorAll("input").forEach((el) => {
      if (
        el.name.startsWith("qty_") ||
        el.id === "tax_value" ||
        el.id === "discount_value" ||
        el.id === "tip_value"
      ) {
        el.addEventListener("input", updateOrderTotals);
      }
    });

    const discountType = document.getElementById("discount_type");
    if (discountType) {
      discountType.addEventListener("change", updateOrderTotals);
    }
    const taxType = document.getElementById("tax_type");
    if (taxType) {
      taxType.addEventListener("change", updateOrderTotals);
    }
    const tipType = document.getElementById("tip_type");
    if (tipType) {
      tipType.addEventListener("change", updateOrderTotals);
    }

    form.addEventListener("submit", (event) => {
      const qtyInputs = form.querySelectorAll("input[name^='qty_']");
      const hasItems = Array.from(qtyInputs).some((input) => Number(input.value || 0) > 0);
      if (!hasItems) {
        event.preventDefault();
        const error = document.getElementById("orderFormError");
        if (error) {
          error.textContent = "Add at least one menu item before saving the order.";
        }
      } else {
        updateOrderTotals();
      }
    });

    updateOrderTotals();
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindOrderCreate();
  });
})();
