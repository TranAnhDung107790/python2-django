(function () {
  const selectors = [
    ".ads-surface",
    ".card",
    ".ads-badge",
    ".ads-collection-card",
    ".ads-product-rail__item",
    ".ads-footer__col"
  ];

  const elements = document.querySelectorAll(selectors.join(","));
  if (!elements.length || !("IntersectionObserver" in window)) return;

  elements.forEach((el) => el.classList.add("ads-reveal"));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("ads-reveal--visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -30px 0px" }
  );

  elements.forEach((el) => observer.observe(el));
})();
