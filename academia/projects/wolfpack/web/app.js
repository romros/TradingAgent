const esc = v => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => v === null || v === undefined ? '—' : typeof v === 'number' ? Math.round(v * 100) / 100 : v;
const card = m => `<article class="card"><div class="badge">${esc(m.level)} · ${esc(m.status)}</div><div><h3>${esc(m.title)}</h3><p>${esc(m.body)}</p><div class="facts">${Object.entries(m.facts || {}).map(([k,v]) => `<code>${esc(k)}: ${esc(fmt(v))}</code>`).join('')}</div></div></article>`;
async function refresh(){
  try {
    const r=await fetch('/api/state',{cache:'no-store'}); const s=await r.json();
    document.querySelector('#health').textContent=`follower ${s.health.follower}`;
    document.querySelector('#updated').textContent=new Date(s.generated_at).toLocaleTimeString('ca-ES');
    document.querySelector('#metrics').innerHTML=[['Events',s.coverage.events],['Paper obertes',s.coverage.paper_open],['Paper tancades',s.coverage.paper_closed],['Equity',`${fmt(s.paper.ending_equity_usdc)} USDC`]].map(([k,v])=>`<div class="metric"><strong>${v}</strong><span>${k}</span></div>`).join('');
    document.querySelector('#messages').innerHTML=s.messages.length?s.messages.map(card).join(''):'<div class="empty">Cap avís encara. El monitor continua observant.</div>';
    document.querySelector('#simulations').innerHTML=s.simulations.map(card).join('');
  } catch(e){ document.querySelector('#health').textContent='dashboard sense dades'; }
}
refresh(); setInterval(refresh,15000);
