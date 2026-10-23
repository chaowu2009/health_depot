// Health Depot shared behaviour (no inline scripts — CSP friendly).
(function () {
  "use strict";

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }
  window.HD = { csrfToken: csrfToken };

  // Show/hide questions that depend on another answer (data-show-if-field / -equals).
  function currentValue(form, name) {
    var inputs = form.querySelectorAll('[name="' + name + '"]');
    var values = [];
    inputs.forEach(function (el) {
      if (el.type === "checkbox" || el.type === "radio") {
        if (el.checked) values.push(el.type === "checkbox" && inputs.length === 1 ? "true" : el.value);
      } else if (el.value) {
        values.push(el.value);
      }
    });
    return values;
  }

  function applyConditions(form) {
    var prefix = form.dataset.prefix ? form.dataset.prefix + "-" : "";
    form.querySelectorAll("[data-question]").forEach(function (wrapper) {
      var field = wrapper.dataset.showIfField;
      if (!field) return;
      var visible = currentValue(form, prefix + field).indexOf(wrapper.dataset.showIfEquals) !== -1;
      wrapper.hidden = !visible;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-conditional]").forEach(function (form) {
      applyConditions(form);
      form.addEventListener("change", function () { applyConditions(form); });
    });

    // Drag-to-reorder questions in the form builder.
    var list = document.getElementById("question-list");
    if (list && window.Sortable && list.dataset.reorderUrl) {
      window.Sortable.create(list, {
        handle: "[data-drag-handle]",
        animation: 150,
        onEnd: function () {
          var order = Array.prototype.map.call(list.querySelectorAll("[data-key]"), function (el) {
            return el.dataset.key;
          });
          fetch(list.dataset.reorderUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ order: order }),
          }).then(function (resp) {
            if (resp.ok) window.location.reload();
          });
        },
      });
    }

    // Auto-submit filters: <select data-autosubmit>
    document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () { el.form && el.form.submit(); });
    });
    // Preview forms never submit.
    document.querySelectorAll("form[data-no-submit]").forEach(function (form) {
      form.addEventListener("submit", function (event) { event.preventDefault(); });
    });

    // Confirm buttons: <button data-confirm="Are you sure?">
    document.addEventListener("submit", function (event) {
      var button = event.submitter;
      if (button && button.dataset.confirm && !window.confirm(button.dataset.confirm)) {
        event.preventDefault();
      }
    }, true);

    // Copy-to-clipboard buttons: <button data-copy="text">
    document.querySelectorAll("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        navigator.clipboard.writeText(btn.dataset.copy).then(function () {
          var old = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = old; }, 1500);
        });
      });
    });
  });
})();
