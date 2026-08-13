#!/usr/bin/env node
// Finite, read-only prospective monitor. Target addresses and output stay outside Git.

import { appendFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumSubgraphClient } = require('@ostium/builder-sdk');
const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
const targetsPath = options.targets;
const output = options.output;
const durationHours = Number(options['duration-hours'] ?? 720);
const pollSeconds = Number(options['poll-seconds'] ?? 900);
const once = options.once === 'true';
if (!targetsPath || !output) throw new Error('--targets and --output are required');
if (!Number.isFinite(durationHours) || durationHours <= 0 || durationHours > 1440) throw new Error('--duration-hours must be 0..1440');
if (!Number.isFinite(pollSeconds) || pollSeconds < 30 || pollSeconds > 3600) throw new Error('--poll-seconds must be 30..3600');

const sha = (value) => createHash('sha256').update(value.toLowerCase()).digest('hex');
const targets = new Set(JSON.parse(await readFile(targetsPath, 'utf8')).map((x) => x.toLowerCase()));
if (!targets.size) throw new Error('target list is empty');
const client = await OstiumSubgraphClient.create({ testnet: false });
const seen = new Set();
const startedAt = Date.now();
const deadline = startedAt + durationHours * 3_600_000;
let cursor = startedAt - 3_600_000;

do {
  const detectedAt = Date.now();
  const fills = await client.getFillsByTime({
    user: 'ALL', startTime: cursor, endTime: detectedAt, limit: 5000,
  });
  for (const fill of fills.sort((a, b) => a.time - b.time)) {
    const trader = fill.trader.toLowerCase();
    if (!targets.has(trader)) continue;
    if (fill.time * 1000 < startedAt) continue;
    const eventId = `${fill.oid}:${fill.action}:${fill.time}`;
    if (seen.has(eventId)) continue;
    seen.add(eventId);
    const normalized = {
      detected_at: new Date(detectedAt).toISOString(),
      detection_latency_seconds: detectedAt / 1000 - fill.time,
      wallet_sha256: sha(trader),
      position_sha256: sha(`${trader}:${fill.pid}`),
      action: fill.action,
      pair: `${fill.pairFrom}/${fill.pairTo}`,
      side: fill.side,
      execution_price: fill.px,
      notional_usd: fill.ntl,
      collateral_usd: fill.collateralUsed,
      closed_pnl_usd: fill.closedPnl,
      executed_at: new Date(fill.time * 1000).toISOString(),
      source: '@ostium/builder-sdk@0.7.0 public read-only subgraph',
    };
    await appendFile(output, `${JSON.stringify(normalized)}\n`, 'utf8');
  }
  cursor = Math.max(cursor, detectedAt - 3_600_000);
  if (once) break;
  if (Date.now() >= deadline) break;
  await new Promise((resolve) => setTimeout(resolve, pollSeconds * 1000));
} while (Date.now() < deadline);
