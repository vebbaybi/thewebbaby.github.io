document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".news-card");
  cards.forEach(card => {
    card.addEventListener("click", () => {
      const link = card.dataset.url;
      if (link) window.open(link, "_blank");
    });
  });
});
w