async function loadWeather() {
  try {
    const resp = await fetch("/api/weather");
    if (!resp.ok) return;
    const data = await resp.json();
    const el = document.getElementById("weather-chip");
    if (el) el.textContent = `${data.title}`;
  } catch (err) {
    console.error("Weather fetch failed:", err);
  }
}
document.addEventListener("DOMContentLoaded", loadWeather);
