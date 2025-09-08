document.addEventListener("mousemove", e => {
  const circle = document.getElementById("cursor-effect");
  if (circle) {
    circle.style.left = `${e.pageX}px`;
    circle.style.top = `${e.pageY}px`;
  }
});
