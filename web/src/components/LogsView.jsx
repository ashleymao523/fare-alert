import { useEffect, useRef, useState } from "preact/hooks";
import { fetchLog } from "../lib/api.js";

export default function LogsView() {
  const [log, setLog] = useState("");
  const [err, setErr] = useState("");
  const [auto, setAuto] = useState(false);
  const timer = useRef(null);
  const load = () => fetchLog()
    .then((r) => { setLog(r.log || "(空)"); setErr(""); })
    .catch((e) => setErr("日志加载失败: " + (e.message || e)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    if (auto) timer.current = setInterval(load, 5000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [auto]);
  return (
    <div class="card">
      <div class="card-head">
        <h3>📜 运行日志</h3>
        <div class="row-btns">
          <label class="chk-inline">
            <input type="checkbox" checked={auto}
              onChange={(e) => setAuto(e.target.checked)} /> 自动刷新(5s)
          </label>
          <button class="btn sm" onClick={load}>刷新</button>
        </div>
      </div>
      {err ? <div class="warn-box">{err}</div> : null}
      <pre class="logbox2">{log || "加载中…"}</pre>
    </div>
  );
}
