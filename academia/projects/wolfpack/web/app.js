const esc = v => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => v === null || v === undefined ? '—' : typeof v === 'number' ? Math.round(v * 100) / 100 : v;
const card = m => `<article class="card"><div class="badge">${esc(m.level)} · ${esc(m.status)}</div><div><h3>${esc(m.title)}</h3><p>${esc(m.body)}</p><div class="facts">${Object.entries(m.facts || {}).map(([k,v]) => `<code>${esc(k)}: ${esc(fmt(v))}</code>`).join('')}</div></div></article>`;
const positionCard = p => `<article class="card"><div class="badge">${esc(p.source_status)} · ${esc(p.side === 'B' ? 'LONG' : 'SHORT')}</div><div><h3>${esc(p.asset)} · ${esc(p.position)}</h3><p>Wallet: ${esc(p.wallet)} · última acció: ${esc(p.last_action)} · paper: ${esc(p.paper_status)}</p><div class="facts"><code>oberta: ${esc(fmt(p.opened_at))}</code><code>últim event: ${esc(fmt(p.last_event_at))}</code><code>PnL wallet: ${esc(fmt(p.source_pnl_usd))} USD</code><code>PnL paper: ${esc(fmt(p.paper_net_pnl_usdc))} USDC</code></div></div></article>`;
const wolfCard = w => `<article class="card"><div class="badge">${esc(w.status)}<br>${esc(w.confidence)}</div><div><h3>Wolf ${esc(w.wallet)}</h3><p>${esc((w.specialties||[]).join(' · ') || 'perfil en observació')}</p><div class="facts"><code>events: ${w.events}</code><code>font tancades: ${w.source_closed}</code><code>PnL font: ${esc(fmt(w.source_realized_pnl_usd))} USD</code><code>paper obertes: ${w.paper_open}</code><code>paper tancades: ${w.paper_closed}</code><code>PnL copiat: ${esc(fmt(w.copy_net_pnl_usdc))} USDC</code><code>candidat: ${esc(w.candidate_progress)}</code><code>titular: ${esc(w.titular_progress)}</code><code>latència mediana: ${esc(fmt(w.median_latency_seconds))} s</code><code>shortfall: ${esc(fmt(w.median_shortfall_bps))} bps</code><code>assets: ${esc((w.assets||[]).join(', ') || '—')}</code><code>risc: ${esc((w.risk_flags||[]).join(', ') || '—')}</code></div></div></article>`;
document.querySelectorAll('.tab').forEach(button=>button.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===button));
  document.querySelectorAll('.tab-panel').forEach(x=>x.classList.toggle('active',x.id===`tab-${button.dataset.tab}`));
}));
async function refresh(){
  try {
    const r=await fetch('/api/state',{cache:'no-store'}); const s=await r.json();
    document.querySelector('#health').textContent=`follower ${s.health.follower}`;
    document.querySelector('#updated').textContent=new Date(s.generated_at).toLocaleTimeString('ca-ES');
    document.querySelector('#metrics').innerHTML=[['Events',s.coverage.events],['Paper obertes',s.coverage.paper_open],['Paper tancades',s.coverage.paper_closed],['Equity',`${fmt(s.paper.ending_equity_usdc)} USDC`]].map(([k,v])=>`<div class="metric"><strong>${v}</strong><span>${k}</span></div>`).join('');
    document.querySelector('#realism').innerHTML=s.paper.execution_realism_pass?'<strong>REALISM PASS</strong> · el PnL paper pot entrar als gates':'<strong>PROTOTIP PAPER</strong> · encara no pot demostrar edge: '+s.paper.execution_realism_blockers.map(esc).join(' · ');
    const pg=s.roster.portfolio_gate;
    document.querySelector('#portfolio').innerHTML=pg.pass?'<strong>CARTERA PAPER PREPARADA</strong> · només titulars elegibles':'<strong>CARTERA BLOQUEJADA</strong> · '+pg.blockers.map(esc).join(' · ');
    document.querySelector('#roster').innerHTML=s.roster.profiles.length?s.roster.profiles.map(wolfCard).join(''):'<div class="empty">Cap llop al roster.</div>';
    document.querySelector('#messages').innerHTML=s.messages.length?s.messages.map(card).join(''):'<div class="empty">Cap avís encara. El monitor continua observant.</div>';
    document.querySelector('#assets').innerHTML=s.assets.map(a=>`<tr><td><strong>${esc(a.asset)}</strong></td><td>${a.events}</td><td>${a.open_source}</td><td>${a.closed_source}</td><td class="${a.source_realized_pnl_usd>=0?'good':'bad'}">${fmt(a.source_realized_pnl_usd)} USD</td><td>${a.paper_open} obertes / ${a.paper_closed} tancades</td><td class="${a.paper_net_pnl_usdc>=0?'good':'bad'}">${fmt(a.paper_net_pnl_usdc)} USDC</td></tr>`).join('');
    document.querySelector('#tracking').innerHTML=s.tracking.length?s.tracking.map(positionCard).join(''):'<div class="empty">Encara no hi ha operacions observades.</div>';
    document.querySelector('#simulations').innerHTML=s.simulations.map(card).join('');
  } catch(e){ document.querySelector('#health').textContent='dashboard sense dades'; }
}
refresh(); setInterval(refresh,15000);
