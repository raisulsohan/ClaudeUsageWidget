// Shared logic for the service worker and the popup.
// Both run in an extension context with the manifest's host_permissions, so both
// can fetch claude.ai with the live login and POST to the local receiver.

const RECEIVER = "http://127.0.0.1:8765/data";

function setStatus(s) {
  chrome.storage.local.set({ status: { ...s, at: Date.now() } });
}

function pct(usage, kind, legacy) {
  const lim = (usage.limits || []).find((l) => l.kind === kind);
  if (lim && lim.percent != null) return Math.round(lim.percent);
  const lg = usage[legacy];
  if (lg && lg.utilization != null) return Math.round(lg.utilization);
  return null;
}

export async function fetchAndPost() {
  try {
    // 1. organization id
    const orgsRes = await fetch("https://claude.ai/api/organizations", { credentials: "include" });
    if (!orgsRes.ok) {
      setStatus({ ok: false, error: "Not logged in to claude.ai (HTTP " + orgsRes.status + ")" });
      return;
    }
    const orgs = await orgsRes.json();
    const org = Array.isArray(orgs) ? orgs[0] : null;
    if (!org) { setStatus({ ok: false, error: "No organization on this account" }); return; }
    const orgId = org.uuid || org.id;

    // 2. usage
    const usageRes = await fetch(`https://claude.ai/api/organizations/${orgId}/usage`, { credentials: "include" });
    if (!usageRes.ok) { setStatus({ ok: false, error: "Usage API error (HTTP " + usageRes.status + ")" }); return; }
    const usage = await usageRes.json();

    // 3. hand the raw payload to the local receiver, which does the parsing
    let post;
    try {
      post = await fetch(RECEIVER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usage, org }),
      });
    } catch (e) {
      setStatus({ ok: false, error: "receiver.py not running (127.0.0.1:8765)" });
      return;
    }
    if (!post.ok) { setStatus({ ok: false, error: "Receiver error (HTTP " + post.status + ")" }); return; }

    setStatus({ ok: true, weekly: pct(usage, "weekly_all", "seven_day") });
    console.log("[widget] pushed usage to the desktop widget");
  } catch (e) {
    setStatus({ ok: false, error: e.message });
    console.warn("[widget] push failed:", e.message);
  }
}
