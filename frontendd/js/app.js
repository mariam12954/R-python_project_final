const App = (() => {
  const API   = '';
  let token   = localStorage.getItem('uni_token') || '';
  let user    = JSON.parse(localStorage.getItem('uni_user') || 'null');
  let page    = 0;
  const LIMIT = 10;
  const DEPTS = ['CS','IT','AI','IS','Robotics','Multimedia'];
 
  const $   = id => document.getElementById(id);
  const esc = s  => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
 
  async function apiFetch(path, opts = {}) {
    const res  = await fetch(path, {
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      ...opts
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
    return data;
  }
 
  function gpaColor(g) {
    if (g >= 3.5) return '#6ee7b7';
    if (g >= 2.5) return '#93c5fd';
    if (g >= 1.5) return '#fde68a';
    return '#fca5a5';
  }
 
  function gpaBar(g) {
    const pct = ((g / 4) * 100).toFixed(0);
    const col = gpaColor(g);
    return `<div class="gpa-wrap"><div class="gpa-bar"><div class="gpa-fill" style="width:${pct}%;background:${col};"></div></div><span class="gpa-text" style="color:${col};">${Number(g).toFixed(2)}</span></div>`;
  }
 
  function initials(name) { return (name||'?').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase(); }
  function timeAgo(iso)   { return new Date(iso).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'}); }
  function greet()        { const h=new Date().getHours(); return h<12?'Good morning!':h<17?'Good afternoon!':'Good evening!'; }
 
  function toast(msg, type='success') {
    const c=$('toast-container');
    const el=document.createElement('div');
    el.className=`toast ${type}`;
    el.innerHTML=`<div class="toast-dot"></div>${esc(msg)}`;
    c.appendChild(el);
    setTimeout(()=>el.remove(),3800);
  }
 
  /* ══════════ AUTH ══════════ */
  function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
    document.querySelectorAll('.auth-form').forEach(f=>f.classList.remove('active'));
    $('form-'+tab).classList.add('active');
    const ind=document.querySelector('.tab-indicator');
    if(ind) ind.classList.toggle('right',tab==='register');
    hideAuthMsg();
  }
 
  function showAuthMsg(msg, type='error') {
    const el=$('auth-message');
    el.textContent=msg; el.className=`auth-message ${type}`; el.style.display='block';
  }
  function hideAuthMsg() { const el=$('auth-message'); if(el) el.style.display='none'; }
 
  async function login(e) {
    e.preventDefault();
    const username=$('login-user').value.trim();
    const password=$('login-pass').value;
    if(!username||!password){ showAuthMsg('Please fill in all fields'); return; }
    try {
      const res=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
      const data=await res.json().catch(()=>({}));
      if(!res.ok){ showAuthMsg(data.detail||'Invalid username or password'); return; }
      token=data.access_token;
      localStorage.setItem('uni_token',token);
      const payload=JSON.parse(atob(token.split('.')[1]));
      user={username:payload.sub,role:payload.role};
      localStorage.setItem('uni_user',JSON.stringify(user));
      bootApp();
    } catch(err){ showAuthMsg('Connection error — is the server running?'); }
  }
 
  async function register(e) {
    e.preventDefault();
    const username=$('reg-user').value.trim();
    const email=$('reg-email').value.trim();
    const password=$('reg-pass').value;
    const role=$('reg-role').value;
    if(!username||!email||!password){ showAuthMsg('Please fill in all fields'); return; }
    try {
      const res=await fetch('/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,email,password,role})});
      const data=await res.json().catch(()=>({}));
      if(!res.ok){ showAuthMsg(data.detail||'Registration failed'); return; }
      showAuthMsg(`Done! Your User ID = ${data.id} — give it to Admin to create your profile.`,'success');
      setTimeout(()=>switchTab('login'),3000);
    } catch(err){ showAuthMsg('Connection error — is the server running?'); }
  }
 
  function logout() {
    token=''; user=null;
    localStorage.removeItem('uni_token'); localStorage.removeItem('uni_user');
    $('auth-screen').classList.add('active');
    $('app-screen').classList.remove('active');
    $('login-user').value=''; $('login-pass').value='';
  }
 
  /* ══════════ BOOT ══════════ */
  function bootApp() {
    $('auth-screen').classList.remove('active');
    $('app-screen').classList.add('active');
    $('sidebar-name').textContent=user.username;
    $('sidebar-avatar').textContent=user.username[0].toUpperCase();
    const badge=$('sidebar-role-badge');
    badge.textContent=user.role; badge.className=`user-badge ${user.role}`;
    const isAdmin=user.role==='admin';
    document.querySelectorAll('.admin-only').forEach(el=>{
      el.style.display=isAdmin?(el.tagName==='P'?'block':'flex'):'none';
    });
    document.querySelectorAll('.student-only').forEach(el=>{
      el.style.display=isAdmin?'none':(el.tagName==='P'?'block':'flex');
    });
    navigate(isAdmin?'dashboard':'profile');
  }
 
  /* ══════════ NAVIGATION ══════════ */
  function navigate(pg) {
    document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
    const btn=document.querySelector(`[data-page="${pg}"]`);
    if(btn) btn.classList.add('active');
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    $('page-'+pg).classList.add('active');
    const titles={dashboard:'Dashboard',students:'Students',profile:'My Profile',audit:'Audit Logs'};
    $('topbar-title').textContent=titles[pg]||pg;
    $('topbar-actions').innerHTML='';
    if(pg==='dashboard') loadDashboard();
    if(pg==='students')  { page=0; loadStudents(); }
    if(pg==='profile')   loadProfile();
    if(pg==='audit')     loadAuditLogs();
  }
 
  function toggleSidebar() { $('sidebar').classList.toggle('open'); }
 
  /* ══════════ DASHBOARD ══════════ */
  async function loadDashboard() {
    $('welcome-greeting').textContent=greet();
    $('welcome-title').textContent=`Welcome back, ${user.username}`;
    if(user.role!=='admin'){
      ['stat-total','stat-depts','stat-gpa','stat-logs'].forEach(id=>$(id).textContent='—');
      $('dash-top').innerHTML='<div class="empty-state">Admin only</div>';
      $('dash-recent').innerHTML='<div class="empty-state">Admin only</div>';
      return;
    }
    try {
      const students=await apiFetch('/students/?limit=100');
      const total=students.length;
      const depts=new Set(students.map(s=>s.department)).size;
      const avgGpa=total?(students.reduce((a,s)=>a+s.gpa,0)/total).toFixed(2):'0.00';
      $('stat-total').textContent=total;
      $('stat-depts').textContent=depts;
      $('stat-gpa').textContent=avgGpa;
      $('nav-count').textContent=total;
      renderMiniTable('dash-top',[...students].sort((a,b)=>b.gpa-a.gpa).slice(0,5));
      renderMiniTable('dash-recent',[...students].reverse().slice(0,5));
      try{ const logs=await apiFetch('/audit-logs/'); $('stat-logs').textContent=logs.length; }
      catch{ $('stat-logs').textContent='—'; }
    } catch(err){ toast(err.message,'error'); }
  }
 
  function renderMiniTable(id,rows) {
    const el=$(id);
    if(!rows.length){ el.innerHTML='<div class="empty-state">No students yet</div>'; return; }
    el.innerHTML=`<div class="table-scroll"><table class="data-table">
      <thead><tr><th>Name</th><th>Dept</th><th>GPA</th></tr></thead>
      <tbody>${rows.map(s=>`<tr>
        <td class="td-name">${esc(s.full_name)}</td>
        <td><span class="dept-pill">${esc(s.department)}</span></td>
        <td>${gpaBar(s.gpa)}</td>
      </tr>`).join('')}</tbody>
    </table></div>`;
  }
 
  /* ══════════ STUDENTS (Admin) ══════════ */
  async function loadStudents() {
    const dept=$('f-dept').value;
    const minGpa=$('f-gpa-min').value;
    const maxGpa=$('f-gpa-max').value;
    let url=`/students/?skip=${page*LIMIT}&limit=${LIMIT}`;
    if(dept)   url+=`&department=${encodeURIComponent(dept)}`;
    if(minGpa) url+=`&min_gpa=${minGpa}`;
    if(maxGpa) url+=`&max_gpa=${maxGpa}`;
    $('students-tbody').innerHTML='<tr><td colspan="6"><div class="loading-state"><div class="spinner"></div></div></td></tr>';
    try {
      const students=await apiFetch(url);
      renderStudents(students);
      $('table-info').textContent=students.length?`Showing ${page*LIMIT+1}–${page*LIMIT+students.length}`:'No results';
      $('page-num').textContent=page+1;
      $('btn-prev').disabled=page===0;
      $('btn-next').disabled=students.length<LIMIT;
    } catch(err){
      $('students-tbody').innerHTML=`<tr><td colspan="6"><div class="empty-state">${esc(err.message)}</div></td></tr>`;
    }
  }
 
  function renderStudents(students) {
    const tbody=$('students-tbody');
    if(!students.length){ tbody.innerHTML='<tr><td colspan="6"><div class="empty-state">No students found</div></td></tr>'; return; }
    tbody.innerHTML=students.map((s,i)=>`<tr>
      <td style="color:var(--text-3);font-size:12px;">${page*LIMIT+i+1}</td>
      <td>
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#a78bfa,#06b6d4);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;">${initials(s.full_name)}</div>
          <div>
            <div class="td-name">${esc(s.full_name)}</div>
            <div style="font-size:11px;color:var(--text-3);">ID: ${s.id} · User ID: ${s.user_id}</div>
          </div>
        </div>
      </td>
      <td><span class="dept-pill">${esc(s.department)}</span></td>
      <td>Year ${s.year}</td>
      <td>${gpaBar(s.gpa)}</td>
      <td>
        <div class="action-group">
          <button class="action-btn edit" onclick='App.openModal("edit",${JSON.stringify(s)})'>Edit</button>
          <button class="action-btn del"  onclick='App.openModal("delete",${JSON.stringify(s)})'>Delete</button>
        </div>
      </td>
    </tr>`).join('');
  }
 
  function clearFilters() {
    $('f-dept').value=''; $('f-gpa-min').value=''; $('f-gpa-max').value='';
    page=0; loadStudents();
  }
  function prevPage() { if(page>0){ page--; loadStudents(); } }
  function nextPage() { page++; loadStudents(); }
 
  /* ══════════ PROFILE ══════════ */
  async function loadProfile() {
    $('profile-content').innerHTML='<div class="loading-state" style="padding:60px;"><div class="spinner spinner--lg"></div></div>';
    try {
      const s=await apiFetch('/students/me');
      $('profile-content').innerHTML=`
        <div class="glass-card profile-hero" style="margin-bottom:20px;">
          <div class="profile-avatar-lg">${initials(s.full_name)}</div>
          <div>
            <h2 class="profile-name">${esc(s.full_name)}</h2>
            <p class="profile-meta">${esc(s.department)} · Year ${s.year}</p>
            <p style="font-size:11px;color:var(--text-3);margin-top:4px;">Student ID: ${s.id} · User ID: ${s.user_id}</p>
          </div>
          <div style="margin-left:auto;">
            <button class="btn-primary" onclick='App.openModal("edit",${JSON.stringify(s)})'>Edit Profile</button>
          </div>
        </div>
        <div class="profile-fields-grid">
          <div class="profile-field">
            <p class="pf-label">GPA</p>
            <p class="pf-value" style="color:${gpaColor(s.gpa)};font-size:28px;font-weight:700;">${Number(s.gpa).toFixed(2)}</p>
            <div style="margin-top:8px;">${gpaBar(s.gpa)}</div>
          </div>
          <div class="profile-field"><p class="pf-label">Academic Year</p><p class="pf-value">Year ${s.year}</p></div>
          <div class="profile-field"><p class="pf-label">Department</p><p class="pf-value"><span class="dept-pill">${esc(s.department)}</span></p></div>
          <div class="profile-field"><p class="pf-label">Phone</p><p class="pf-value">${esc(s.phone||'—')}</p></div>
          <div class="profile-field"><p class="pf-label">Address</p><p class="pf-value">${esc(s.address||'—')}</p></div>
          <div class="profile-field"><p class="pf-label">Member Since</p><p class="pf-value" style="font-size:13px;">${new Date(s.created_at).toLocaleDateString('en-GB',{year:'numeric',month:'long',day:'numeric'})}</p></div>
        </div>`;
    } catch(err) {
      /* ── No profile yet ── */
      let uid='—';
      try{ uid=JSON.parse(atob(token.split('.')[1])).user_id||'—'; }catch{}
      $('profile-content').innerHTML=`
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-size:56px;margin-bottom:16px;">🎓</div>
          <h3 style="font-size:22px;font-weight:700;margin-bottom:10px;color:var(--text);">No Profile Yet</h3>
          <p style="color:var(--text-2);font-size:14px;line-height:1.8;max-width:380px;margin:0 auto 28px;">
            Your student profile hasn't been created yet.<br/>
            Give your <strong style="color:#c4b5fd;">User ID</strong> to the Admin.
          </p>
          <div style="background:rgba(167,139,250,0.1);border:1px solid rgba(167,139,250,0.3);border-radius:16px;padding:24px 32px;display:inline-block;">
            <p style="font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">Your User ID</p>
            <p style="font-size:48px;font-weight:800;color:#c4b5fd;line-height:1;" id="uid-display">—</p>
            <p style="font-size:12px;color:var(--text-3);margin-top:8px;">Share this with your Admin</p>
          </div>
        </div>`;
      fetchUserId();
    }
  }
 
  async function fetchUserId() {
    try {
      const me=await apiFetch('/auth/me');
      const el=$('uid-display');
      if(el) el.textContent=me.id;
    } catch{}
  }
 
  /* ══════════ AUDIT ══════════ */
  async function loadAuditLogs() {
    $('audit-content').innerHTML='<div class="loading-state" style="padding:60px;"><div class="spinner spinner--lg"></div></div>';
    try {
      const logs=await apiFetch('/audit-logs/');
      if(!logs.length){ $('audit-content').innerHTML='<div class="empty-state" style="padding:60px;">No audit events yet</div>'; return; }
      $('audit-content').innerHTML=`<div class="audit-timeline">${logs.map(l=>{
        let fields='';
        try{ fields=Object.entries(JSON.parse(l.updated_fields||'{}')).map(([k,v])=>`${k}: <strong>${v}</strong>`).join(' · '); }catch{}
        return `<div class="audit-item">
          <div class="audit-dot"></div>
          <div style="flex:1;min-width:0;">
            <p class="audit-action">${esc(l.action)} — Student #${l.target_student_id}</p>
            <p class="audit-detail">${fields||'No details'} · By user #${l.user_id}</p>
          </div>
          <span class="audit-time">${timeAgo(l.timestamp)}</span>
        </div>`;
      }).join('')}</div>`;
    } catch(err){ $('audit-content').innerHTML=`<div class="empty-state" style="padding:60px;">${esc(err.message)}</div>`; }
  }
 
  /* ══════════ MODAL ══════════ */
  function deptOptions(sel='') {
    return DEPTS.map(d=>`<option value="${d}" ${sel===d?'selected':''}>${d}</option>`).join('');
  }
 
  function studentFormHTML(s={}, showUserId=false) {
    return `
      <div class="field-row">
        <div class="field-group">
          <label class="field-label">Full Name</label>
          <div class="field-wrap"><input id="mf-name" class="field-input" value="${esc(s.full_name||'')}" placeholder="Ahmed Mohamed"/></div>
        </div>
        <div class="field-group">
          <label class="field-label">Department</label>
          <div class="field-wrap">
            <select id="mf-dept" class="field-input field-select" style="padding-left:14px;">
              <option value="">Select…</option>${deptOptions(s.department||'')}
            </select>
          </div>
        </div>
      </div>
      <div class="field-row">
        <div class="field-group">
          <label class="field-label">GPA (0–4)</label>
          <div class="field-wrap"><input id="mf-gpa" type="number" step="0.01" min="0" max="4" class="field-input" style="padding-left:14px;" value="${s.gpa??''}" placeholder="3.50"/></div>
        </div>
        <div class="field-group">
          <label class="field-label">Year</label>
          <div class="field-wrap">
            <select id="mf-year" class="field-input field-select" style="padding-left:14px;">
              ${[1,2,3,4,5,6].map(y=>`<option value="${y}" ${s.year==y?'selected':''}>${y}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
      <div class="field-row">
        <div class="field-group">
          <label class="field-label">Phone</label>
          <div class="field-wrap"><input id="mf-phone" class="field-input" style="padding-left:14px;" value="${esc(s.phone||'')}" placeholder="+20 100 000 0000"/></div>
        </div>
        <div class="field-group">
          <label class="field-label">Address</label>
          <div class="field-wrap"><input id="mf-address" class="field-input" style="padding-left:14px;" value="${esc(s.address||'')}" placeholder="Cairo, Egypt"/></div>
        </div>
      </div>
      ${showUserId?`
      <div class="field-group">
        <label class="field-label">User ID <span style="color:var(--text-3);font-weight:400;text-transform:none;">(from student registration)</span></label>
        <div class="field-wrap"><input id="mf-userid" type="number" class="field-input" style="padding-left:14px;" placeholder="e.g. 3"/></div>
      </div>`:''}
      <div class="modal-error" id="modal-err"></div>`;
  }
 
  function openModal(type, data={}) {
    if(type==='create'){
      $('modal-title').textContent='Add New Student';
      $('modal-body').innerHTML=studentFormHTML({},true);
      $('modal-footer').innerHTML=`<button class="btn-ghost" onclick="App.closeModal()">Cancel</button><button class="btn-primary" onclick="App.submitCreate()">Create Student</button>`;
    } else if(type==='edit'){
      $('modal-title').textContent='Edit Student';
      $('modal-body').innerHTML=studentFormHTML(data,false);
      $('modal-footer').innerHTML=`<button class="btn-ghost" onclick="App.closeModal()">Cancel</button><button class="btn-primary" onclick="App.submitEdit(${data.id})">Save Changes</button>`;
    } else if(type==='delete'){
      $('modal-title').textContent='Delete Student';
      $('modal-body').innerHTML=`<p style="color:var(--text-2);font-size:14px;line-height:1.8;">Are you sure you want to delete<br/><strong style="color:var(--text);font-size:16px;">${esc(data.full_name)}</strong>?<br/><span style="color:var(--danger);">This cannot be undone.</span></p>`;
      $('modal-footer').innerHTML=`<button class="btn-ghost" onclick="App.closeModal()">Cancel</button><button class="btn-danger" onclick="App.submitDelete(${data.id},'${esc(data.full_name)}')">Yes, Delete</button>`;
    }
    $('modal-backdrop').classList.add('open');
  }
 
  function closeModal() { $('modal-backdrop').classList.remove('open'); }
  function showModalErr(msg) { const el=$('modal-err'); if(el){ el.textContent=msg; el.style.display='block'; } }
 
  async function submitCreate() {
    const name   =$('mf-name').value.trim();
    const dept   =$('mf-dept').value;
    const gpa    =parseFloat($('mf-gpa').value);
    const year   =parseInt($('mf-year').value);
    const phone  =$('mf-phone').value.trim();
    const address=$('mf-address').value.trim();
    const userId =parseInt($('mf-userid').value);
    if(!name||!dept||isNaN(gpa)||isNaN(userId)){ showModalErr('Please fill: Name, Department, GPA, User ID'); return; }
    try {
      await apiFetch('/students/',{method:'POST',body:JSON.stringify({full_name:name,department:dept,gpa,year,phone:phone||null,address:address||null,user_id:userId})});
      toast('Student created!'); closeModal(); loadStudents(); loadDashboard();
    } catch(err){ showModalErr(err.message); }
  }
 
  async function submitEdit(id) {
    const upd={};
    const name   =$('mf-name').value.trim();
    const dept   =$('mf-dept').value;
    const gpa    =$('mf-gpa').value;
    const year   =$('mf-year').value;
    const phone  =$('mf-phone').value.trim();
    const address=$('mf-address').value.trim();
    if(name) upd.full_name=name; if(dept) upd.department=dept;
    if(gpa)  upd.gpa=parseFloat(gpa); if(year) upd.year=parseInt(year);
    if(phone) upd.phone=phone; if(address) upd.address=address;
    if(!Object.keys(upd).length){ showModalErr('No changes to save'); return; }
    try {
      await apiFetch(`/students/${id}`,{method:'PUT',body:JSON.stringify(upd)});
      toast('Student updated!'); closeModal(); loadStudents(); loadDashboard();
      if($('page-profile').classList.contains('active')) loadProfile();
    } catch(err){ showModalErr(err.message); }
  }
 
  async function submitDelete(id, name) {
    try {
      await apiFetch(`/students/${id}`,{method:'DELETE'});
      toast(`${name} deleted`); closeModal(); loadStudents(); loadDashboard();
    } catch(err){ toast(err.message,'error'); }
  }
 
  function init() { if(token&&user) bootApp(); }
 
  return { switchTab,login,register,logout,navigate,toggleSidebar,loadStudents,clearFilters,prevPage,nextPage,openModal,closeModal,submitCreate,submitEdit,submitDelete,init };
})();
 
document.addEventListener('DOMContentLoaded',()=>App.init());