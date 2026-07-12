import assert from 'node:assert/strict';
import test from 'node:test';

import { cloudApiUrlFromHost } from './cloudApiUrl.js';

test('defaults public IPv4 cloud hosts to HTTPS', () => {
  assert.equal(cloudApiUrlFromHost('118.145.244.188'), 'https://118.145.244.188');
  assert.equal(cloudApiUrlFromHost('http://118.145.244.188/api/v1'), 'https://118.145.244.188');
});

test('keeps HTTP only for explicitly local development hosts', () => {
  assert.equal(cloudApiUrlFromHost('localhost:47831'), 'http://localhost:47831');
  assert.equal(cloudApiUrlFromHost('127.0.0.1:47831'), 'http://127.0.0.1:47831');
  assert.equal(cloudApiUrlFromHost('[::1]:47831'), 'http://[::1]:47831');
});

test('preserves an explicit valid origin', () => {
  assert.equal(cloudApiUrlFromHost('https://cloud.example.com/api/v1'), 'https://cloud.example.com');
  assert.equal(cloudApiUrlFromHost('http://127.0.0.1:47831/health'), 'http://127.0.0.1:47831');
});
