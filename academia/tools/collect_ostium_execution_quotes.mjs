#!/usr/bin/env node
// Ephemeral, read-only Ostium quote collector. Raw JSONL belongs in /tmp, not git.

import { appendFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumClient } = require('@ostium/builder-sdk');

const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
const output = options.output;
const count = Number(options.count ?? 20);
const intervalMs = Number(options['interval-ms'] ?? 2000);
const sessionWindow = options.window ?? 'unknown';
const notionals = (options.notionals ?? '60,100,200,400,500')
  .split(',').map((value) => value.trim()).filter(Boolean);
if (!output) throw new Error('--output is required');

const client = await OstiumClient.createReadOnly();
const { pairs } = await client.getPairs();
const pair = pairs.find((row) => {
  const symbol = `${row.pairFrom}/${row.pairTo}`.toUpperCase();
  return symbol === 'SPX/USD' || symbol === 'USD/SPX' || symbol === 'US500/USD' || symbol === 'USD/US500';
});
if (!pair) throw new Error(`SPX/USD pair not found; available=${JSON.stringify(pairs.map((row) => [row.pairId, row.pairFrom, row.pairTo]))}`);
const simulated = await client.getSimSlippage({ pairIds: [pair.pairId], ntls: notionals });

for (let index = 0; index < count; index += 1) {
  const { prices } = await client.getAllPrices();
  const quote = prices[pair.pairId];
  const row = {
    captured_at: new Date().toISOString(),
    instrument: 'US500/USD',
    ostium_pair: 'SPX/USD',
    pair_id: pair.pairId,
    is_market_open: pair.isMarketOpen,
    session_window: sessionWindow,
    mid: Number(quote.mid),
    bid: Number(quote.bid),
    ask: Number(quote.ask),
    open_fee_bps: pair.openFee,
    close_fee_bps: pair.closeFee,
    rollover_rate: pair.rolloverRate,
    simulated_slippage: simulated[pair.pairId],
    source: '@ostium/builder-sdk read-only',
  };
  await appendFile(output, `${JSON.stringify(row)}\n`, 'utf8');
  if (index + 1 < count) await new Promise((resolve) => setTimeout(resolve, intervalMs));
}
