import { useRef, useState } from "preact/hooks";

export function filterAC(list, q, limit = 8) {
  q = (q || "").trim().toLowerCase();
  const out = [];
  for (const c of list) {
    if (out.length >= limit) break;
    const name = c.name || "";
    if (!q || name.indexOf(q) >= 0 ||
        (c.pinyin || "").indexOf(q) >= 0 || (c.py || "").indexOf(q) >= 0) {
      out.push(c);
    }
  }
  return out;
}

// v0.31 RoutesView/ReverseView shared autocomplete: pick from curated list
// (exact match, no fuzzy fallback) but free-text still allowed for cities.
export default function AcField({
  label, value, placeholder, ensure, onChange, emptyText, classExtra,
}) {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState(null); // null = still loading
  const [items, setItems] = useState([]);
  const [active, setActive] = useState(-1);
  const rootRef = useRef(null);

  const refresh = (q) => {
    const src = list;
    if (src == null) {
      ensure().then(setList).catch(() => setList(null)); // stay null: retry next focus
      setOpen(true);
      return;
    }
    const f = filterAC(src, q !== undefined ? q : value);
    setItems(f);
    setActive(f.length ? 0 : -1);
    setOpen(true);
  };

  const pick = (i) => {
    const it = items[i];
    if (!it) return;
    onChange(it.name);
    setOpen(false);
  };

  const onKey = (e) => {
    if (!open || !items.length) {
      if (e.key === "Escape") setOpen(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((active + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((active - 1 + items.length) % items.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (active >= 0) pick(active);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <label class={"field2 ac2" + (classExtra ? " " + classExtra : "")} ref={rootRef}>
      {label ? <span class="f-label2">{label}</span> : null}
      <div class="ac-wrap2">
        <input type="text" value={value || ""} placeholder={placeholder || "输入中文或拼音"}
          role="combobox" aria-expanded={open} aria-autocomplete="list"
          aria-controls="ac2-listbox"
          onFocus={() => refresh()}
          onInput={(e) => { onChange(e.target.value); refresh(e.target.value); }}
          onKeyDown={onKey}
          onBlur={() => setTimeout(() => setOpen(false), 150)} />
        {open ? (
          <div class="ac-list2" id="ac2-listbox" role="listbox">
            {list == null ? (
              <div class="ac-item2">加载中…</div>
            ) : items.length ? items.map((it, i) => (
              <div key={it.name} role="option" aria-selected={i === active}
                class={"ac-item2" + (i === active ? " active" : "")}
                onMouseDown={(e) => { e.preventDefault(); pick(i); }}
                onMouseEnter={() => setActive(i)}>
                <span class="ac-label2">{it.name}</span>
                {it.pinyin ? <span class="ac-sub2">{it.pinyin}</span> : null}
              </div>
            )) : (
              <div class="ac-item2">{emptyText || "无匹配(可直接输入全称)"}</div>
            )}
          </div>
        ) : null}
      </div>
    </label>
  );
}
