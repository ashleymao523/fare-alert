export default function Hero({ route, photos }) {
  if (!route) return null;
  const ph = (c) => {
    const p = (photos || {})[c];
    return p ? { backgroundImage: "url('" + p + "')" } : {};
  };
  const plane = (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M21 3L3 10.5l6 2.5 2.5 6L21 3z" fill="var(--accent)" opacity="0.9" />
      <path d="M21 3L9 13l2.5 6L21 3z" fill="var(--accent-2)" />
    </svg>
  );
  return (
    <div class="hero">
      <div class="hero-cities">
        <div class="hero-city">
          <div class="hc-photo" style={ph(route.from_city)}>
            {photos && photos[route.from_city] ? "" : <span class="hc-initial">{(route.from_city || "?").slice(0, 1)}</span>}
          </div>
          <div class="hc-name">{route.from_city}</div>
          <div class="hc-iata">{route.from_iata || "出发"}</div>
        </div>
        <div class="hero-mid">
          <div class="hero-plane">{route.trip_type === "roundtrip" ? "⇄" : plane}</div>
          <div class="hero-dir">{route.trip_type === "roundtrip" ? "往返" : (route.intl ? "国际单程" : "单程")}</div>
        </div>
        <div class="hero-city">
          <div class="hc-photo" style={ph(route.to_city)}>
            {photos && photos[route.to_city] ? "" : <span class="hc-initial">{(route.to_city || "?").slice(0, 1)}</span>}
          </div>
          <div class="hc-name">{route.to_city}</div>
          <div class="hc-iata">{route.to_iata || "到达"}</div>
        </div>
      </div>
    </div>
  );
}
