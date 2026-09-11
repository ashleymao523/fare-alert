export default function Hero({ route, photos }) {
  if (!route) return null;
  const ph = (c) => {
    const p = (photos || {})[c];
    return p ? { backgroundImage: "url('" + p + "')" } : {};
  };
  return (
    <div class="hero">
      <div class="hero-cities">
        <div class="hero-city">
          <div class="hc-photo" style={ph(route.from_city)}>{photos && photos[route.from_city] ? "" : "🛫"}</div>
          <div class="hc-name">{route.from_city}</div>
          <div class="hc-iata">{route.from_iata || "出发"}</div>
        </div>
        <div class="hero-mid">
          <div class="hero-plane">{route.trip_type === "roundtrip" ? "⇄" : "✈"}</div>
          <div class="hero-dir">{route.trip_type === "roundtrip" ? "往返" : (route.intl ? "国际单程" : "单程")}</div>
        </div>
        <div class="hero-city">
          <div class="hc-photo" style={ph(route.to_city)}>{photos && photos[route.to_city] ? "" : "🏙"}</div>
          <div class="hc-name">{route.to_city}</div>
          <div class="hc-iata">{route.to_iata || "到达"}</div>
        </div>
      </div>
    </div>
  );
}
