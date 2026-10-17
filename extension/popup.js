import { fetchAndPost } from "./usage.js";

const msg = document.getElementById("msg");
const stats = document.getElementById("stats");
const btn = document.getElementById("refresh");

function ago(ts) {
  const s = (Date.now() - ts) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  return Math.floor(s / 3600) + "h ago";
}

function render(status) {
  stats.innerHTML = "";
  if (!status) {
    msg.className = "dim";
    msg.textContent = "No data yet. Make sure receiver.py is running, then click Refresh now.";
    return;
  }
  if (status.ok) {
    msg.className = "ok";
    msg.textContent = "✓ Pushed " + ago(status.at);
    const add = (label, v) => {
      if (v == null) return;
      const d = document.createElement("div");
      d.className = "row";
      d.innerHTML = '<span class="dim">' + label + "</span><span>" + v + "% used</span>";
      stats.appendChild(d);
    };
    add("Session", status.session);
    add("Weekly", status.weekly);
  } else {
    msg.className = "warn";
    msg.textContent = "⚠ " + status.error + "  (" + ago(status.at) + ")";
  }
}

function load() {
  chrome.storage.local.get("status", (d) => render(d.status));
}

btn.addEventListener("click", async () => {
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await fetchAndPost();        // done right here — no service-worker messaging
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh now";
    load();
  }
});

load();
