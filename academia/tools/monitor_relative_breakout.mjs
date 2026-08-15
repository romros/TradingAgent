#!/usr/bin/env node
// Finite preregistered relative-breakout monitor. Paper state only; no signer or order path.

import { appendFile, readFile, rename, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumClient } = require('@ostium/builder-sdk');
const args = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('='); return [key, rest.join('=')];
}));
if (!args.config || !args.output || !args.events) throw new Error('--config, --output and --events required');
const config = JSON.parse(await readFile(args.config, 'utf8'));
const intervalSeconds = Number(config.interval_seconds);
if (intervalSeconds < 30 || intervalSeconds > 300) throw new Error('invalid interval');
const expiresAt = Date.parse(config.expires_at);
const client = await OstiumClient.createReadOnly();
const { pairs } = await client.getPairs();
let pair = pairs.find((x) => `${x.pairFrom}/${x.pairTo}`.toUpperCase() === config.asset);
if (!pair) throw new Error(`${config.asset} unavailable`);
const notional = Number(config.paper_execution.notional_usdc);
const impact = (await client.getSimSlippage({pairIds: [pair.pairId], ntls: [String(notional)]}))[pair.pairId];
const point = (side) => impact[side].find((x) => Number(x.ntl) === notional);
const executable = (mid, direction, opening) => {
  const side = (direction === 'LONG') === opening ? 'long' : 'short';
  const fraction = Number(point(side).slippage) / 100;
  return mid * (side === 'long' ? 1 + fraction : 1 - fraction);
};
const contract = () => ({captured_at: new Date().toISOString(), pair_id: pair.pairId,
  open_fee_bps: Number(pair.openFee), close_fee_bps: Number(pair.closeFee),
  rollover_rate: pair.rolloverRate, market_open: pair.isMarketOpen});
const levels = (anchor) => Object.fromEntries(Object.entries(config.geometry).map(([name, g]) => {
  const trigger = anchor * (1 + Number(g.trigger_anchor_pct) / 100);
  return [name.toUpperCase(), {trigger, stop: trigger * (1 + Number(g.stop_from_trigger_pct) / 100),
    target_1: trigger * (1 + Number(g.target_1_from_trigger_pct) / 100),
    target_2: trigger * (1 + Number(g.target_2_from_trigger_pct) / 100)}];
}));
let state = {schema_version: 1, experiment_id: config.id, status: 'WARMUP', anchor: null,
  levels: null, consecutive_long: 0, consecutive_short: 0, position: null,
  realized_pnl_usdc: 0, live_trading_authorized: false};
const persist = async () => { const temp = `${args.output}.next`; await writeFile(temp, `${JSON.stringify(state, null, 2)}\n`); await rename(temp, args.output); };
const event = async (kind, details) => appendFile(args.events, `${JSON.stringify({at: new Date().toISOString(), experiment_id: config.id, kind, ...details})}\n`);
const close = async (kind, mid, now) => {
  const p = state.position; const exit = executable(mid, p.direction, false);
  const sign = p.direction === 'LONG' ? 1 : -1; const fraction = p.remaining_fraction;
  const gross = notional * fraction * sign * (exit / p.entry - 1);
  const closeFee = notional * fraction * Number(pair.closeFee) / 10000;
  const hours = (Date.parse(now) - Date.parse(p.opened_at)) / 3600000;
  const rateKey = p.direction.toLowerCase();
  const adverseRate = Math.max(0, -Number(p.entry_contract.rollover_rate[rateKey]), -Number(pair.rolloverRate[rateKey]));
  const carry = notional * fraction * adverseRate / 100 * hours / 8;
  state.realized_pnl_usdc += gross - closeFee - carry;
  await event(kind, {exit, gross_pnl_usdc: gross, close_fee_usdc: closeFee,
    carry_cost_usdc: carry, realized_pnl_usdc: state.realized_pnl_usdc,
    exit_contract: contract()});
  state.position = null; state.status = kind;
};

while (Date.now() < expiresAt) {
  const refreshedPairs = (await client.getPairs()).pairs;
  pair = refreshedPairs.find((x) => `${x.pairFrom}/${x.pairTo}`.toUpperCase() === config.asset);
  const { prices } = await client.getAllPrices(); const quote = prices[pair.pairId];
  const mid = Number(quote?.mid); const now = new Date().toISOString();
  state.last_quote = {captured_at: now, mid, bid: Number(quote?.bid), ask: Number(quote?.ask)};
  if (!pair.isMarketOpen || !Number.isFinite(mid)) { state.status = 'WAIT_MARKET'; await persist(); await new Promise(r => setTimeout(r, intervalSeconds * 1000)); continue; }
  if (!state.anchor) { state.anchor = mid; state.levels = levels(mid); state.status = 'WATCH'; await event('ANCHOR_FROZEN', {anchor: mid, levels: state.levels, contract: contract()}); }
  if (!state.position) {
    state.consecutive_long = mid > state.levels.LONG.trigger ? state.consecutive_long + 1 : 0;
    state.consecutive_short = mid < state.levels.SHORT.trigger ? state.consecutive_short + 1 : 0;
    const direction = state.consecutive_long >= config.confirmation_samples ? 'LONG' : state.consecutive_short >= config.confirmation_samples ? 'SHORT' : null;
    if (direction) {
      const openFee = notional * Number(pair.openFee) / 10000;
      state.position = {direction, entry: executable(mid, direction, true), opened_at: now,
        remaining_fraction: 1, target_1_hit: false, open_fee_remaining_usdc: openFee,
        ...state.levels[direction], entry_contract: contract()};
      state.realized_pnl_usdc -= openFee; state.status = 'PAPER_OPEN';
      await event('PAPER_OPEN', state.position);
    }
  } else {
    const p = state.position; const long = p.direction === 'LONG';
    const stopHit = long ? mid <= p.stop : mid >= p.stop;
    const target1Hit = long ? mid >= p.target_1 : mid <= p.target_1;
    const target2Hit = long ? mid >= p.target_2 : mid <= p.target_2;
    if (!p.target_1_hit && target1Hit) {
      const original = p.remaining_fraction; p.remaining_fraction = 0.5;
      const saved = p.remaining_fraction; p.remaining_fraction = original - saved;
      await close('TARGET_1_PARTIAL_INTERNAL', mid, now);
      // close() clears the position; restore the surviving half with fee-adjusted breakeven.
      state.position = {...p, remaining_fraction: saved, target_1_hit: true,
        stop: long ? p.entry * (1 + Number(pair.openFee) / 10000) : p.entry * (1 - Number(pair.openFee) / 10000)};
      state.status = 'PAPER_OPEN_AFTER_TARGET_1';
    }
    if (state.position && (target2Hit || stopHit)) await close(target2Hit ? 'PAPER_TARGET_COMPLETE' : 'PAPER_STOPPED', mid, now);
    if (!state.position) { await persist(); break; }
  }
  await persist(); await new Promise(r => setTimeout(r, intervalSeconds * 1000));
}
if (Date.now() >= expiresAt && state.position) await close('PAPER_EXPIRED_CLOSE', Number(state.last_quote.mid), new Date().toISOString());
else if (Date.now() >= expiresAt) state.status = 'CANCELLED_EXPIRED';
await persist();
