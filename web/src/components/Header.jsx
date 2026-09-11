export default function Header({ snap }) {
  let cls = "updated";
  let text = "";
  if (snap && snap.updated_at) {
    const ts = String(snap.updated_at);
    const mins = Math.round((Date.now() - new Date(ts).getTime()) / 60000);
    text = "更新于 " + ts.replace("T", " ") +
      (mins >= 0 ? " · " + (mins < 1 ? "刚刚" : mins + " 分钟前") : "");
    cls += mins < 60 ? " fresh" : mins < 100 ? " stale" : " old";
  }
  return (
    <header class="hd">
      <div class="hd-in">
        <div class="brand">
          <span class="brand-logo">✈</span>
          <span class="brand-name">FareAlert</span>
          <span class="ver">v2 · 0.29</span>
        </div>
        <div class="hd-right">
          <span class={cls}>{text}</span>
          <a class="btn small" href="/">经典版 ↩</a>
        </div>
      </div>
    </header>
  );
}
