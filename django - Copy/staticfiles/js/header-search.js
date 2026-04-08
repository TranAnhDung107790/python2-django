(function () {
  const forms = document.querySelectorAll(".ads-search[data-suggest-url]");
  if (!forms.length) return;

  forms.forEach((form) => {
    const input = form.querySelector("input[name='q']");
    const box = form.querySelector(".ads-search__suggestions");
    const endpoint = form.getAttribute("data-suggest-url");
    let timer = null;

    if (!input || !box || !endpoint) return;

    const hideBox = () => {
      box.hidden = true;
      box.innerHTML = "";
    };

    const renderItems = (items) => {
      if (!items.length) {
        box.innerHTML = '<div class="ads-search__empty">Không tìm thấy sản phẩm phù hợp.</div>';
        box.hidden = false;
        return;
      }

      box.innerHTML = items
        .slice(0, 6)
        .map((item) => {
          const img = Array.isArray(item.images) && item.images[0]?.image
            ? item.images[0].image
            : "";
          const href = `/product/${item.id}/${item.slug || ""}/`;
          const price = Number(item.price || 0).toLocaleString("vi-VN");
          return `
            <a class="ads-search__item" href="${href}">
              <span class="ads-search__thumb">${img ? `<img src="${img}" alt="${item.name}">` : '<span>AD</span>'}</span>
              <span class="ads-search__meta">
                <strong>${item.name}</strong>
                <small>${price} đ</small>
              </span>
            </a>
          `;
        })
        .join("");
      box.hidden = false;
    };

    input.addEventListener("input", () => {
      const q = input.value.trim();
      clearTimeout(timer);

      if (q.length < 1) {
        hideBox();
        return;
      }

      timer = setTimeout(async () => {
        try {
          const url = `${endpoint}?q=${encodeURIComponent(q)}`;
          const res = await fetch(url, {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
          });
          if (!res.ok) {
            hideBox();
            return;
          }
          const data = await res.json();
          renderItems(Array.isArray(data) ? data : []);
        } catch (err) {
          hideBox();
        }
      }, 180);
    });

    document.addEventListener("click", (event) => {
      if (!form.contains(event.target)) {
        hideBox();
      }
    });

    input.addEventListener("focus", () => {
      if (box.innerHTML.trim()) {
        box.hidden = false;
      }
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideBox();
      }
    });
  });
})();
