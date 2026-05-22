"""
monitoring.py
=============
GET /metrics     → JSON snapshot من الـ counters (admin only)
GET /logs        → آخر سطور من app.log مفلترة بالـ level (admin only)
GET /dashboard   → HTML dashboard تفاعلي (admin only)
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.core.metrics import get_metrics, read_logs
from app.dependencies import require_admin
from app.models.user import User

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics")
def metrics_endpoint(current_user: User = Depends(require_admin)):
    """Snapshot فوري من الـ counters المستخرجة تلقائياً من الـ logger."""
    return get_metrics()


@router.get("/logs")
def logs_endpoint(
    min_level: str = Query("INFO", description="DEBUG | INFO | WARNING | ERROR | CRITICAL"),
    last_n: int = Query(100, ge=1, le=500),
    search: str = Query(None, description="فلتر نصي اختياري"),
    current_user: User = Depends(require_admin),
):
    """آخر سطور من app.log مع إمكانية الفلترة (admin only)."""
    return read_logs(min_level=min_level, last_n=last_n, search=search)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(current_user: User = Depends(require_admin)):
    """HTML dashboard يعرض الـ metrics والـ logs في الوقت الحقيقي."""
    return HTMLResponse(content=_DASHBOARD_HTML)


# ── Embedded dashboard HTML ──────────────────────────────────────
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SMS — Monitoring Dashboard</title>
<style>
  *{box-sizing:border-box}
  body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px;direction:rtl}
  h1{color:#38bdf8;border-bottom:1px solid #334155;padding-bottom:.5rem;font-size:1.4rem}
  h2{color:#7dd3fc;margin-top:2rem;font-size:1.1rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0}
  .card{background:#1e293b;border-radius:8px;padding:1rem;border:1px solid #334155;text-align:center}
  .card .val{font-size:1.8rem;font-weight:700;color:#38bdf8}
  .card .lbl{font-size:.75rem;color:#94a3b8;margin-top:.25rem}
  table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;font-size:.82rem}
  th{background:#0f4c7a;color:#bae6fd;text-align:right;padding:.55rem 1rem}
  td{padding:.45rem 1rem;border-top:1px solid #334155}
  .badge{padding:2px 7px;border-radius:4px;font-size:.72rem;font-weight:600}
  .DEBUG{background:#1e293b;color:#94a3b8}.INFO{background:#164e63;color:#7dd3fc}
  .WARNING{background:#451a03;color:#fed7aa}.ERROR{background:#450a0a;color:#fca5a5}
  .CRITICAL{background:#2d0036;color:#e879f9}
  button{background:#0284c7;color:#fff;border:none;padding:.45rem 1.1rem;border-radius:6px;cursor:pointer;font-size:.85rem}
  button:hover{background:#0369a1}
  select,input{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:.35rem .6rem;font-size:.85rem}
  #status{color:#64748b;font-size:.8rem;margin-right:1rem}
</style>
</head>
<body>
<h1>📊 Student Management System — Monitoring Dashboard</h1>
<button onclick="loadAll()">⟳ تحديث</button>
<span id="status"></span>

<h2>إحصائيات الطلبات</h2>
<div class="grid" id="req-cards"></div>

<h2>طلبات حسب الـ Endpoint</h2>
<div id="ep-table"></div>

<h2>المصادقة والعمليات</h2>
<div class="grid" id="auth-cards"></div>

<h2>السجلات الأخيرة</h2>
<div style="margin-bottom:.75rem;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
  <label>المستوى:
    <select id="lvl"><option>DEBUG</option><option selected>INFO</option>
    <option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select>
  </label>
  <label>بحث: <input id="srch" placeholder="نص للبحث..." style="width:180px"/></label>
  <button onclick="loadLogs()">بحث</button>
</div>
<div id="log-table"></div>

<script>
const token = (() => {
  let t = sessionStorage.getItem('jwt');
  if (!t) { t = prompt('الصق توكن الـ admin JWT:'); sessionStorage.setItem('jwt', t); }
  return t;
})();
const H = {'Authorization': 'Bearer ' + token};

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

async function loadMetrics(){
  const r = await fetch('/metrics', {headers: H});
  if(!r.ok){ document.body.innerHTML='<h2 style="color:#f87171">403 — التوكن غير صالح أو ليس admin</h2>'; return; }
  const d = await r.json();
  document.getElementById('req-cards').innerHTML = `
    <div class="card"><div class="val">${d.total_requests}</div><div class="lbl">إجمالي الطلبات</div></div>
    <div class="card"><div class="val">${d.avg_response_ms} ms</div><div class="lbl">متوسط وقت الاستجابة</div></div>
    <div class="card"><div class="val">${d.total_errors_4xx}</div><div class="lbl">أخطاء 4xx</div></div>
    <div class="card"><div class="val">${d.total_errors_5xx}</div><div class="lbl">أخطاء 5xx</div></div>
    <div class="card"><div class="val">${d.error_rate_pct}%</div><div class="lbl">نسبة الأخطاء</div></div>
  `;
  const rows = Object.entries(d.requests_per_endpoint)
    .sort((a,b)=>b[1]-a[1])
    .map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join('');
  document.getElementById('ep-table').innerHTML =
    `<table><tr><th>Endpoint</th><th>عدد</th></tr>${rows||'<tr><td colspan=2 style="color:#64748b">لا يوجد بيانات بعد</td></tr>'}</table>`;
  const a=d.auth, c=d.crud;
  document.getElementById('auth-cards').innerHTML = `
    <div class="card"><div class="val">${a.login_attempts}</div><div class="lbl">محاولات تسجيل الدخول</div></div>
    <div class="card"><div class="val">${a.login_failures}</div><div class="lbl">فشل تسجيل الدخول</div></div>
    <div class="card"><div class="val">${a.token_validations}</div><div class="lbl">التحقق من التوكن</div></div>
    <div class="card"><div class="val">${c.creates}</div><div class="lbl">إضافات</div></div>
    <div class="card"><div class="val">${c.reads}</div><div class="lbl">قراءات</div></div>
    <div class="card"><div class="val">${c.updates}</div><div class="lbl">تعديلات</div></div>
    <div class="card"><div class="val">${c.deletes}</div><div class="lbl">حذف</div></div>
  `;
}

async function loadLogs(){
  const lvl = document.getElementById('lvl').value;
  const q   = document.getElementById('srch').value;
  const url = `/logs?min_level=${lvl}&last_n=100${q?'&search='+encodeURIComponent(q):''}`;
  const r   = await fetch(url, {headers: H});
  if(!r.ok) return;
  const logs = await r.json();
  const rows = [...logs].reverse().map(l=>`<tr>
    <td>${l.timestamp}</td>
    <td><span class="badge ${l.level}">${l.level}</span></td>
    <td style="color:#94a3b8">${esc(l.logger)}</td>
    <td>${esc(l.message)}</td>
  </tr>`).join('');
  document.getElementById('log-table').innerHTML =
    `<table><tr><th>الوقت</th><th>المستوى</th><th>Logger</th><th>الرسالة</th></tr>${rows||'<tr><td colspan=4 style="color:#64748b">لا يوجد سجلات</td></tr>'}</table>`;
}

async function loadAll(){
  document.getElementById('status').textContent = 'جارٍ التحديث...';
  await loadMetrics();
  await loadLogs();
  document.getElementById('status').textContent = 'آخر تحديث: ' + new Date().toLocaleTimeString('ar-EG');
}

loadAll();
setInterval(loadAll, 30000);
</script>
</body>
</html>"""
