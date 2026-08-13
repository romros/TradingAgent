#!/usr/bin/env node
// Read-only public fill export for temporary analysis. Do not version its output.

import { writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(`${process.cwd()}/package.json`);
const { OstiumSubgraphClient } = require('@ostium/builder-sdk');

const options = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...rest] = item.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
const output = options.output;
const days = Number(options.days ?? 90);
const limit = Number(options.limit ?? 10000);
const requestedEndTime = options['end-time-ms'] ? Number(options['end-time-ms']) : Date.now();
if (!output) throw new Error('--output is required');
if (!Number.isInteger(days) || days < 1 || days > 730) throw new Error('--days must be 1..730');
if (!Number.isInteger(limit) || limit < 1 || limit > 100000) throw new Error('--limit must be 1..100000');
if (!Number.isFinite(requestedEndTime) || requestedEndTime <= 0) throw new Error('--end-time-ms must be a positive Unix millisecond timestamp');

const client = await OstiumSubgraphClient.create({ testnet: false });
const endTime = requestedEndTime;
const startTime = endTime - days * 86_400_000;
const fills = await client.getFillsByTime({
  user: 'ALL', startTime, endTime, limit,
});
await writeFile(output, `${JSON.stringify({
  collectedAt: new Date().toISOString(), startTime, endTime, requestedLimit: limit,
  limitReached: fills.length === limit, fills,
})}\n`, 'utf8');
console.log(JSON.stringify({
  output, rows: fills.length, startTime, endTime, limitReached: fills.length === limit,
}));
