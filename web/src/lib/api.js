const j = async (r) => {
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
};

export function fetchSnapshot() {
  return fetch("/api/snapshot").then(j).then((x) => x.snapshot);
}

export function fetchDestIntel(routeId) {
  return fetch("/api/dest-intel?route=" + encodeURIComponent(routeId)).then(j);
}

export function fetchCityPhoto(name) {
  return fetch("/api/city-photo?name=" + encodeURIComponent(name)).then(j);
}
