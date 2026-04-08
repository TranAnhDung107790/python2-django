(function () {
  var root = document.getElementById("ads-toast-root");
  var src = document.getElementById("ads-flash-msgs");
  if (!root) return;

  function mapLevel(tags) {
    if (!tags) return "info";
    if (tags.indexOf("error") !== -1 || tags.indexOf("danger") !== -1) return "error";
    if (tags.indexOf("success") !== -1) return "success";
    if (tags.indexOf("warning") !== -1) return "warning";
    return "info";
  }

  function iconFor(level) {
    if (level === "success") return "fa-circle-check";
    if (level === "error") return "fa-circle-xmark";
    if (level === "warning") return "fa-triangle-exclamation";
    return "fa-circle-info";
  }

  function showToast(level, text, delay) {
    var el = document.createElement("div");
    el.className = "ads-toast ads-toast--" + level;
    el.setAttribute("role", "status");
    el.innerHTML =
      '<button type="button" class="ads-toast__close" aria-label="Đóng">&times;</button>' +
      '<div class="ads-toast__row">' +
      '<span class="ads-toast__icon"><i class="fa-solid ' +
      iconFor(level) +
      '"></i></span>' +
      '<div class="ads-toast__text"></div>' +
      "</div>" +
      '<div class="ads-toast__bar"></div>';
    el.querySelector(".ads-toast__text").textContent = text;
    var bar = el.querySelector(".ads-toast__bar");
    bar.style.animationDuration = delay + "ms";
    el.querySelector(".ads-toast__close").addEventListener("click", function () {
      el.remove();
    });
    root.appendChild(el);
    window.setTimeout(function () {
      el.classList.add("ads-toast--out");
      window.setTimeout(function () {
        el.remove();
      }, 320);
    }, delay);
  }

  if (src) {
    var nodes = src.querySelectorAll("[data-level]");
    nodes.forEach(function (el, i) {
      var level = mapLevel(el.getAttribute("data-level"));
      var text = (el.textContent || "").trim();
      if (text) showToast(level, text, 4200 + i * 350);
    });
    src.remove();
  }
})();
