#!/usr/bin/env node
// Finite read-only market diary. Raw hourly JSONL belongs in /tmp, not Git.

import { appendFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumClient } = require('@ostium/builder-sdk');
const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
const output = options.output;
const durationHours = Number(options['duration-hours'] ?? 720);
const intervalSeconds = Number(options['interval-seconds'] ?? 3600);
const once = options.once === 'true';
if (!output) throw new Error('--output is required');
if (!Number.isFinite(durationHours) || durationHours <= 0 || durationHours > 1440) throw new Error('--duration-hours must be 0..1440');
if (!Number.isFinite(intervalSeconds) || intervalSeconds < 60 || intervalSeconds > 86400) throw new Error('--interval-seconds must be 60..86400');

const postInfo = async (body) => {
  const response = await fetch('https://api.hyperliquid.xyz/info', {
    method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Hyperliquid info ${response.status}`);
  return response.json();
};
const finite = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const ostium = await OstiumClient.createReadOnly();
const deadline = Date.now() + durationHours * 3_600_000;
do {
  const capturedAt = new Date().toISOString();
  const row = {schema_version: 1, captured_at: capturedAt, sources: {}, errors: {}};
  try {
    const [{pairs}, {prices}] = await Promise.all([ostium.getPairs(), ostium.getAllPrices()]);
    const wanted = new Map([
      ['EUR/USD', 'EUR/USD'], ['SPX/USD', 'US500/USD'], ['US500/USD', 'US500/USD'],
      ['XAU/USD', 'XAU/USD'],
    ]);
    const selected = pairs.filter((pair) => wanted.has(`${pair.pairFrom}/${pair.pairTo}`.toUpperCase()));
    const slippage = await ostium.getSimSlippage({pairIds: selected.map((x) => x.pairId), ntls: ['100', '500']});
    row.sources.ostium = selected.map((pair) => {
      const symbol = `${pair.pairFrom}/${pair.pairTo}`.toUpperCase();
      const quote = prices[pair.pairId];
      const mid = finite(quote?.mid); const bid = finite(quote?.bid); const ask = finite(quote?.ask);
      return {
        instrument: wanted.get(symbol), venue_contract: symbol, pair_id: pair.pairId,
        market_open: pair.isMarketOpen, mid, bid, ask,
        spread_bps: mid && bid !== null && ask !== null ? (ask - bid) / mid * 10000 : null,
        open_fee_bps: finite(pair.openFee), close_fee_bps: finite(pair.closeFee),
        rollover_rate: pair.rolloverRate, simulated_price_impact: slippage[pair.pairId],
      };
    });
  } catch (error) {
    row.errors.ostium = String(error?.message ?? error);
  }
  for (const dex of ['xyz', 'mkts']) {
    try {
      const [meta, contexts] = await postInfo({type: 'metaAndAssetCtxs', dex});
      const wanted = new Set(dex === 'xyz'
        ? ['xyz:GOLD', 'xyz:EUR', 'xyz:CL', 'xyz:COPPER', 'xyz:SILVER']
        : ['mkts:US500']);
      row.sources[`hyperliquid_${dex}`] = meta.universe.map((asset, index) => [asset, contexts[index]])
        .filter(([asset]) => wanted.has(asset.name)).map(([asset, context]) => {
          const impactBid = finite(context.impactPxs?.[0]); const impactAsk = finite(context.impactPxs?.[1]);
          const mid = finite(context.midPx);
          return {
            venue_contract: asset.name, max_leverage: asset.maxLeverage,
            mark: finite(context.markPx), oracle: finite(context.oraclePx), mid,
            impact_bid: impactBid, impact_ask: impactAsk,
            impact_spread_bps: mid && impactBid !== null && impactAsk !== null
              ? (impactAsk - impactBid) / mid * 10000 : null,
            funding_raw: finite(context.funding), premium_raw: finite(context.premium),
            open_interest_base: finite(context.openInterest), day_notional_volume_usd: finite(context.dayNtlVlm),
          };
        });
    } catch (error) {
      row.errors[`hyperliquid_${dex}`] = String(error?.message ?? error);
    }
  }
  await appendFile(output, `${JSON.stringify(row)}\n`, 'utf8');
  if (once || Date.now() >= deadline) break;
  await new Promise((resolve) => setTimeout(resolve, intervalSeconds * 1000));
} while (Date.now() < deadline);
