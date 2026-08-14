const esc = v => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => v === null || v === undefined ? '—' : typeof v === 'number' ? Math.round(v * 100) / 100 : v;
const card = m => `<article class="card"><div class="badge">${esc(m.level)} · ${esc(m.status)}</div><div><h3>${esc(m.title)}</h3><p>${esc(m.body)}</p><div class="facts">${Object.entries(m.facts || {}).map(([k,v]) => `<code>${esc(k)}: ${esc(fmt(v))}</code>`).join('')}</div></div></article>`;
const positionCard = p => `<article class="card"><div class="badge">${esc(p.source_status)} · ${esc(p.side === 'B' ? 'LONG' : 'SHORT')}</div><div><h3>${esc(p.asset)} · ${esc(p.position)}</h3><p>Wallet: ${esc(p.wallet)} · última acció: ${esc(p.last_action)} · paper: ${esc(p.paper_status)}</p><div class="facts"><code>oberta: ${esc(fmt(p.opened_at))}</code><code>últim event: ${esc(fmt(p.last_event_at))}</code><code>PnL wallet: ${esc(fmt(p.source_pnl_usd))} USD</code><code>PnL paper: ${esc(fmt(p.paper_net_pnl_usdc))} USDC</code></div></div></article>`;
const wolfCard = w => `<article class="card"><div class="badge">${esc(w.status)}<br>${esc(w.confidence)}</div><div><h3>Wolf ${esc(w.wallet)}</h3><p>${esc((w.specialties||[]).join(' · ') || 'perfil en observació')}</p><div class="facts"><code>events: ${w.events}</code><code>font tancades: ${w.source_closed}</code><code>PnL font: ${esc(fmt(w.source_realized_pnl_usd))} USD</code><code>paper obertes: ${w.paper_open}</code><code>paper tancades: ${w.paper_closed}</code><code>PnL copiat: ${esc(fmt(w.copy_net_pnl_usdc))} USDC</code><code>candidat: ${esc(w.candidate_progress)}</code><code>titular: ${esc(w.titular_progress)}</code><code>latència mediana: ${esc(fmt(w.median_latency_seconds))} s</code><code>shortfall: ${esc(fmt(w.median_shortfall_bps))} bps</code><code>assets: ${esc((w.assets||[]).join(', ') || '—')}</code><code>risc: ${esc((w.risk_flags||[]).join(', ') || '—')}</code></div></div></article>`;
const progress = (label,value) => `<div class="progress-row"><span>${esc(label)}</span><div class="progress"><i style="width:${Math.max(0,Math.min(100,Number(value)||0))}%"></i></div><strong>${esc(fmt(value))}%</strong></div>`;
const linkWatch = w => {
  if(!w || !w.status) return '<div class="empty">Monitor LINK encara no iniciat.</div>';
  const q=w.last_quote||{}, p=w.position||{}, wp=w.watch_progress||{}, pp=w.position_progress||{};
  return `<article class="card"><div class="badge">${esc(w.status)}<br>PAPER ONLY</div><div><h3>LINK/USD · ${esc(p.direction||'esperant ruptura')}</h3><p>Actualització: ${esc(fmt(q.captured_at))} · expira 15/08 12:00 UTC</p><div class="facts"><code>mid: ${esc(fmt(q.mid))}</code><code>confirmació short: ${esc(fmt(w.consecutive_short))}/3</code><code>confirmació long: ${esc(fmt(w.consecutive_long))}/3</code><code>entrada: ${esc(fmt(p.entry))}</code><code>stop: ${esc(fmt(p.stop))}</code><code>target 1: ${esc(fmt(p.target_1))}</code><code>target 2: ${esc(fmt(p.target_2))}</code><code>PnL realitzat: ${esc(fmt(w.realized_pnl_usdc))} USDC</code></div>${p.direction?(progress('Progrés target 1',pp.target_1_pct)+progress('Progrés target 2',pp.target_2_pct)):(progress('Proximitat short 8,72',wp.short_trigger_proximity_pct)+progress('Proximitat long 8,865',wp.long_trigger_proximity_pct))}</div></article>`;
};
const marketOverview = m => `<table><thead><tr><th>Mercat</th><th>Estat</th><th>Mid</th><th>1 h</th><th>4 h</th><th>Spread</th><th>Obert</th></tr></thead><tbody>${(m.universe||[]).map(x=>`<tr><td><strong>${esc(x.instrument)}</strong></td><td>${esc(x.status)}</td><td>${esc(fmt(x.mid))}</td><td class="${(x.change_1h_pct||0)>=0?'good':'bad'}">${esc(fmt(x.change_1h_pct))}%</td><td class="${(x.change_4h_pct||0)>=0?'good':'bad'}">${esc(fmt(x.change_4h_pct))}%</td><td>${esc(fmt(x.spread_bps))} bps</td><td>${x.market_open===true?'sí':x.market_open===false?'no':'—'}</td></tr>`).join('')}</tbody></table><p>${esc(m.interpretation||'')}</p>`;
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
    const gs=s.global_signal;
    document.querySelector('#global-signal').innerHTML=`<strong>SENYAL GLOBAL: ${esc(gs.decision)}</strong> · ${esc(gs.reason)} · direcció ${esc(fmt(gs.direction))} · leverage ${esc(fmt(gs.leverage))} · guany esperat ${esc(fmt(gs.expected_net_gain_usdc))} USDC · pèrdua màxima ${esc(fmt(gs.maximum_loss_usdc))} USDC`;
    const pg=s.roster.portfolio_gate;
    document.querySelector('#portfolio').innerHTML=pg.pass?'<strong>CARTERA PAPER PREPARADA</strong> · només titulars elegibles':'<strong>CARTERA BLOQUEJADA</strong> · '+pg.blockers.map(esc).join(' · ');
    document.querySelector('#roster').innerHTML=s.roster.profiles.length?s.roster.profiles.map(wolfCard).join(''):'<div class="empty">Cap llop al roster.</div>';
    document.querySelector('#link-watch').innerHTML=linkWatch(s.link_watch);
    document.querySelector('#market-overview').innerHTML=marketOverview(s.opportunity_monitor.market);
    const cr=s.opportunity_monitor.codex_review;
    document.querySelector('#codex-review').innerHTML=`<strong>${esc(cr.status||'WAITING')}</strong> · ${esc(cr.decision||'Codex només s’activarà quan canviï materialment un setup o el règim.')}`;
    document.querySelector('#monitor-paper').innerHTML=`Equity: <strong>${esc(fmt(s.paper.ending_equity_usdc))} USDC</strong> · ${s.coverage.paper_open} obertes · ${s.coverage.paper_closed} tancades · cap ordre real autoritzada`;
    document.querySelector('#messages').innerHTML=s.messages.length?s.messages.map(card).join(''):'<div class="empty">Cap avís encara. El monitor continua observant.</div>';
    document.querySelector('#assets').innerHTML=s.assets.map(a=>`<tr><td><strong>${esc(a.asset)}</strong></td><td>${a.events}</td><td>${a.open_source}</td><td>${a.closed_source}</td><td class="${a.source_realized_pnl_usd>=0?'good':'bad'}">${fmt(a.source_realized_pnl_usd)} USD</td><td>${a.paper_open} obertes / ${a.paper_closed} tancades</td><td class="${a.paper_net_pnl_usdc>=0?'good':'bad'}">${fmt(a.paper_net_pnl_usdc)} USDC</td></tr>`).join('');
    document.querySelector('#tracking').innerHTML=s.tracking.length?s.tracking.map(positionCard).join(''):'<div class="empty">Encara no hi ha operacions observades.</div>';
    document.querySelector('#simulations').innerHTML=s.simulations.map(card).join('');
  } catch(e){ document.querySelector('#health').textContent='dashboard sense dades'; }
}
refresh(); setInterval(refresh,60000);
