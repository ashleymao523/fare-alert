const j = async (r) => {
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
};

const post = (url, body) => fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
}).then(async (r) => {
  const x = await r.json().catch(() => ({}));
  if (!r.ok || x.ok === false) throw new Error(x.error || ("HTTP " + r.status));
  return x;
});

export function fetchSnapshot() {
  return fetch("/api/snapshot").then(j).then((x) => x.snapshot);
}

export function fetchDestIntel(routeId) {
  return fetch("/api/dest-intel?route=" + encodeURIComponent(routeId)).then(j);
}

export function fetchCityPhoto(name) {
  return fetch("/api/city-photo?name=" + encodeURIComponent(name)).then(j);
}

export function fetchCrawl() { return fetch("/api/crawl-status").then(j); }

export function fetchWeekly() { return fetch("/api/weekly-report").then(j); }

export function pushWeekly() { return post("/api/weekly-push", {}); }

export function fetchConfig() { return fetch("/api/config").then(j); }

export function saveConfig(cfg) { return post("/api/config", cfg); }

export function testPush() { return post("/api/test-push", {}); }

export function fetchSchedStats() { return fetch("/api/sched-stats").then(j); }

export function fetchAlerts() { return fetch("/api/alerts").then(j); }
