#!/usr/bin/env node
// Finite, read-only prospective monitor. Target addresses and output stay outside Git.

import { appendFile, readFile, rename, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumClient, OstiumSubgraphClient } = require('@ostium/builder-sdk');
const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
const targetsPath = options.targets;
const output = options.output;
const heartbeat = options.heartbeat;
const durationHours = Number(options['duration-hours'] ?? 720);
const pollSeconds = Number(options['poll-seconds'] ?? 900);
const once = options.once === 'true';
const forwardStart = options['forward-start-ms'] ? Number(options['forward-start-ms']) : Date.now();
if (!targetsPath || !output) throw new Error('--targets and --output are required');
if (!Number.isFinite(durationHours) || durationHours <= 0 || durationHours > 1440) throw new Error('--duration-hours must be 0..1440');
if (!Number.isFinite(pollSeconds) || pollSeconds < 30 || pollSeconds > 3600) throw new Error('--poll-seconds must be 30..3600');
if (!Number.isFinite(forwardStart) || forwardStart <= 0) throw new Error('--forward-start-ms must be a positive Unix millisecond timestamp');

const sha = (value) => createHash('sha256').update(value.toLowerCase()).digest('hex');
const targets = new Set(JSON.parse(await readFile(targetsPath, 'utf8')).map((x) => x.toLowerCase()));
if (!targets.size) throw new Error('target list is empty');
const client = await OstiumSubgraphClient.create({ testnet: false });
const market = await OstiumClient.createReadOnly();
const seen = new Set();
try {
  const prior = await readFile(output, 'utf8');
  for (const line of prior.split('\n').filter(Boolean)) {
    const row = JSON.parse(line);
    if (row.position_sha256 && row.action && row.executed_at) {
      seen.add(`${row.position_sha256}:${row.action}:${row.executed_at}`);
    }
  }
} catch (error) {
  if (error?.code !== 'ENOENT') throw error;
}
const startedAt = Date.now();
const deadline = startedAt + durationHours * 3_600_000;
let cursor = Math.min(forwardStart, startedAt - 3_600_000);

do {
  const detectedAt = Date.now();
  let pairBySymbol = new Map();
  let prices = {};
  let quoteError = null;
  try {
    const [pairResponse, priceResponse] = await Promise.all([market.getPairs(), market.getAllPrices()]);
    prices = priceResponse.prices;
    pairBySymbol = new Map(pairResponse.pairs.map((pair) => [
      `${pair.pairFrom}/${pair.pairTo}`.toUpperCase(), pair,
    ]));
  } catch (error) {
    quoteError = String(error?.message ?? error);
  }
  const fills = await client.getFillsByTime({
    user: 'ALL', startTime: cursor, endTime: detectedAt, limit: 5000,
  });
  for (const fill of fills.sort((a, b) => a.time - b.time)) {
    const trader = fill.trader.toLowerCase();
    if (!targets.has(trader)) continue;
    if (fill.time * 1000 < forwardStart) continue;
    const positionSha = sha(`${trader}:${fill.pid}`);
    const executedAt = new Date(fill.time * 1000).toISOString();
    const eventId = `${positionSha}:${fill.action}:${executedAt}`;
    if (seen.has(eventId)) continue;
    seen.add(eventId);
    const pairSymbol = `${fill.pairFrom}/${fill.pairTo}`.toUpperCase();
    const pair = pairBySymbol.get(pairSymbol);
    const quote = pair ? prices[pair.pairId] : null;
    const normalized = {
      detected_at: new Date(detectedAt).toISOString(),
      detection_latency_seconds: detectedAt / 1000 - fill.time,
      wallet_sha256: sha(trader),
      position_sha256: positionSha,
      action: fill.action,
      pair: `${fill.pairFrom}/${fill.pairTo}`,
      side: fill.side,
      execution_price: fill.px,
      notional_usd: fill.ntl,
      collateral_usd: fill.collateralUsed,
      closed_pnl_usd: fill.closedPnl,
      executed_at: executedAt,
      observed_quote: quote ? {
        captured_at: new Date(detectedAt).toISOString(), pair_id: pair.pairId,
        market_open: pair.isMarketOpen, mid: quote.mid, bid: quote.bid, ask: quote.ask,
        open_fee_bps: pair.openFee, close_fee_bps: pair.closeFee,
        rollover_rate: pair.rolloverRate,
      } : null,
      quote_error: quote ? null : (quoteError ?? `pair ${pairSymbol} unavailable`),
      source: '@ostium/builder-sdk@0.7.0 public read-only subgraph',
    };
    await appendFile(output, `${JSON.stringify(normalized)}\n`, 'utf8');
  }
  if (heartbeat) {
    const temporary = `${heartbeat}.tmp`;
    await writeFile(temporary, `${JSON.stringify({
      checked_at: new Date().toISOString(), public_fills_seen: fills.length,
      target_events_written_total: seen.size, source: '@ostium/builder-sdk read-only',
    })}\n`, 'utf8');
    await rename(temporary, heartbeat);
  }
  cursor = Math.max(cursor, detectedAt - 3_600_000);
  if (once) break;
  if (Date.now() >= deadline) break;
  await new Promise((resolve) => setTimeout(resolve, pollSeconds * 1000));
} while (Date.now() < deadline);
