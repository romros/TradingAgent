#!/usr/bin/env node
// Finite, read-only LINK setup monitor. It writes paper state only and cannot submit orders.

import { appendFile, rename, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumClient } = require('@ostium/builder-sdk');
const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('='); return [key, rest.join('=')];
}));
const output = options.output; const events = options.events;
const intervalSeconds = Number(options['interval-seconds'] ?? 60);
const durationHours = Number(options['duration-hours'] ?? 24);
if (!output || !events) throw new Error('--output and --events are required');
if (intervalSeconds < 30 || intervalSeconds > 300) throw new Error('interval must be 30..300 seconds');

const config = {
  expiresAt: Date.parse('2026-08-15T12:00:00Z'), notional: 250, collateral: 50,
  SHORT: {trigger: 8.72, stop: 8.78, target1: 8.55, target2: 8.40},
  LONG: {trigger: 8.865, stop: 8.80, target1: 9.00, target2: 9.02},
};
const client = await OstiumClient.createReadOnly();
const { pairs } = await client.getPairs();
const pair = pairs.find((x) => `${x.pairFrom}/${x.pairTo}`.toUpperCase() === 'LINK/USD');
if (!pair) throw new Error('LINK/USD unavailable');
const slippage = await client.getSimSlippage({pairIds: [pair.pairId], ntls: ['250']});
const impact = slippage[pair.pairId];
let state = {schema_version: 1, experiment_id: 'link-breakout-breakdown-paper-v39',
  status: 'WATCH', consecutive_long: 0, consecutive_short: 0, position: null,
  realized_pnl_usdc: 0, live_trading_authorized: false};
const deadline = Math.min(Date.now() + durationHours * 3600_000, config.expiresAt);
const executable = (mid, direction, opening) => {
  const side = (direction === 'LONG') === opening ? 'long' : 'short';
  const point = impact[side].find((x) => Number(x.ntl) === 250);
  const fraction = Number(point.slippage) / 100;
  return mid * (side === 'long' ? 1 + fraction : 1 - fraction);
};
const persist = async () => {
  const temp = `${output}.next`; await writeFile(temp, `${JSON.stringify(state, null, 2)}\n`); await rename(temp, output);
};
const record = async (kind, details) => appendFile(events, `${JSON.stringify({at: new Date().toISOString(), kind, ...details})}\n`);

while (Date.now() < deadline) {
  const { prices } = await client.getAllPrices(); const quote = prices[pair.pairId];
  const mid = Number(quote.mid); const now = new Date().toISOString();
  state.last_quote = {captured_at: now, mid, bid: Number(quote.bid), ask: Number(quote.ask)};
  const corridor = config.LONG.trigger - config.SHORT.trigger;
  state.watch_progress = {
    short_trigger_proximity_pct: Math.max(0, Math.min(100, (config.LONG.trigger - mid) / corridor * 100)),
    long_trigger_proximity_pct: Math.max(0, Math.min(100, (mid - config.SHORT.trigger) / corridor * 100)),
  };
  if (!pair.isMarketOpen || !Number.isFinite(mid)) { state.status = 'CANCELLED_BAD_MARKET_DATA'; await persist(); break; }
  if (!state.position) {
    state.consecutive_short = mid < config.SHORT.trigger ? state.consecutive_short + 1 : 0;
    state.consecutive_long = mid > config.LONG.trigger ? state.consecutive_long + 1 : 0;
    const direction = state.consecutive_short >= 3 ? 'SHORT' : (state.consecutive_long >= 3 ? 'LONG' : null);
    if (direction) {
      const setup = config[direction]; const entry = executable(mid, direction, true);
      state.position = {direction, entry, opened_at: now, remaining_fraction: 1,
        stop: setup.stop, target_1: setup.target1, target_2: setup.target2,
        open_fee_usdc: config.notional * Number(pair.openFee) / 10000, target_1_hit: false};
      state.status = 'PAPER_OPEN'; await record('PAPER_OPEN', state.position);
    }
  } else {
    const p = state.position; const s = config[p.direction];
    const sign = p.direction === 'LONG' ? 1 : -1;
    const travelled = sign * (mid - p.entry);
    state.position_progress = {
      target_1_pct: Math.max(0, Math.min(100, travelled / (sign * (s.target1 - p.entry)) * 100)),
      target_2_pct: Math.max(0, Math.min(100, travelled / (sign * (s.target2 - p.entry)) * 100)),
    };
    const stopHit = p.direction === 'LONG' ? mid <= p.stop : mid >= p.stop;
    const target1Hit = p.direction === 'LONG' ? mid >= s.target1 : mid <= s.target1;
    const target2Hit = p.direction === 'LONG' ? mid >= s.target2 : mid <= s.target2;
    if (!p.target_1_hit && target1Hit) {
      const exit = executable(mid, p.direction, false);
      state.realized_pnl_usdc += config.notional * .5 * sign * (exit / p.entry - 1) - p.open_fee_usdc * .5;
      p.remaining_fraction = .5; p.target_1_hit = true;
      const feeFraction = Number(pair.openFee) / 10000;
      p.stop = p.direction === 'LONG' ? p.entry * (1 + feeFraction) : p.entry * (1 - feeFraction);
      await record('TARGET_1', {exit, realized_pnl_usdc: state.realized_pnl_usdc, new_stop: p.stop});
    }
    if (target2Hit || stopHit) {
      const exit = executable(mid, p.direction, false);
      state.realized_pnl_usdc += config.notional * p.remaining_fraction * sign * (exit / p.entry - 1) - p.open_fee_usdc * p.remaining_fraction;
      state.status = target2Hit ? 'PAPER_TARGET_COMPLETE' : 'PAPER_STOPPED';
      await record(state.status, {exit, realized_pnl_usdc: state.realized_pnl_usdc}); state.position = null;
      await persist(); break;
    }
  }
  await persist(); await new Promise((resolve) => setTimeout(resolve, intervalSeconds * 1000));
}
if (Date.now() >= deadline) state.status = state.position ? 'PAPER_EXPIRED_OPEN' : 'CANCELLED_EXPIRED';
await persist();
