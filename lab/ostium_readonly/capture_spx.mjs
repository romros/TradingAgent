#!/usr/bin/env node
import { OstiumClient } from '@ostium/builder-sdk';
import { readFileSync } from 'node:fs';

const sdkPackage = JSON.parse(readFileSync(
  '/app/node_modules/@ostium/builder-sdk/package.json', 'utf8'));
const packageLock = JSON.parse(readFileSync('/app/package-lock.json', 'utf8'));
const lockedSdk = packageLock.packages?.['node_modules/@ostium/builder-sdk'];
if (!lockedSdk || sdkPackage.version !== lockedSdk.version) {
  throw new Error('OSTIUM_SDK_RUNTIME_LOCK_MISMATCH');
}
if (typeof lockedSdk.integrity !== 'string' || !lockedSdk.integrity.startsWith('sha512-')) {
  throw new Error('OSTIUM_SDK_LOCK_INTEGRITY_MISSING');
}

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
    version: sdkPackage.version,
    mode: 'read-only',
    builderFeeBps,
  },
  requestedNotionalsUsd: notionals,
  requestedPairSymbols: requestedSymbols,
  pair,
  simulatedSlippage: slippage[String(pair.pairId)] ?? null,
}, null, 2) + '\n');
