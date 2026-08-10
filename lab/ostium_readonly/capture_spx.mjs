#!/usr/bin/env node
import { OstiumClient } from '@ostium/builder-sdk';

const notionals = (process.env.OSTIUM_NOTIONALS || '10,20,50,100,200,500,1000')
  .split(',').map((value) => value.trim()).filter(Boolean);
const requestedSymbols = (process.env.OSTIUM_PAIR || 'US500/USD,SPX/USD')
  .split(',').map((value) => value.trim().toUpperCase()).filter(Boolean);
const client = await OstiumClient.createReadOnly();
if (!client.isReadOnly()) throw new Error('OSTIUM_CLIENT_NOT_READ_ONLY');

const builderFeeBps = 0;
const all = await client.getPairs({ builderFeeBps });
const pair = all.pairs.find((item) => {
  const symbol = `${item.pairFrom}/${item.pairTo}`.toUpperCase();
  return requestedSymbols.includes(symbol);
});
if (!pair) throw new Error(`OSTIUM_PAIR_NOT_FOUND:${requestedSymbols.join(',')}`);

const slippage = await client.getSimSlippage({
  pairIds: [pair.pairId],
  ntls: notionals,
});

process.stdout.write(JSON.stringify({
  schemaVersion: 1,
  capturedAt: new Date().toISOString(),
  source: {
    package: '@ostium/builder-sdk',
    version: '0.7.0',
    mode: 'read-only',
    builderFeeBps,
  },
  requestedNotionalsUsd: notionals,
  requestedPairSymbols: requestedSymbols,
  pair,
  simulatedSlippage: slippage[String(pair.pairId)] ?? null,
}, null, 2) + '\n');
