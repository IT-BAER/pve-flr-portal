import test from 'node:test';
import assert from 'node:assert/strict';
import { loadApp } from './helpers.mjs';

// Lets the microtask queue drain so an un-awaited async call settles.
const flush = () => new Promise((r) => setImmediate(r));

test('apiFetch returns the response untouched when status is not 401', async () => {
  const { apiFetch } = loadApp({ window: { location: {} } });
  const original = globalThis.fetch;
  const body = { ok: true, status: 200, json: async () => ({ hi: true }) };
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/thing');
    assert.equal(init, undefined);
    return body;
  };
  try {
    const resp = await apiFetch('/api/thing');
    assert.equal(resp, body);
  } finally {
    globalThis.fetch = original;
  }
});

function csrfDocument(token) {
  return {
    querySelector: (sel) =>
      sel === 'meta[name="csrf-token"]' ? { getAttribute: (a) => (a === 'content' ? token : null) } : null,
    querySelectorAll: () => [],
  };
}

test('apiFetch sends the page CSRF token on a POST, keeping the existing headers', async () => {
  const { apiFetch } = loadApp({ window: { location: {} }, document: csrfDocument('tok123') });
  const original = globalThis.fetch;
  let seen;
  globalThis.fetch = async (url, init) => {
    seen = init;
    return { ok: true, status: 200 };
  };
  try {
    await apiFetch('/api/restore', { method: 'POST', body: 'x', headers: { Accept: 'application/json' } });
    assert.deepEqual(seen, {
      method: 'POST',
      body: 'x',
      headers: { Accept: 'application/json', 'X-CSRF-Token': 'tok123' },
    });
  } finally {
    globalThis.fetch = original;
  }
});

test('apiFetch does not add the CSRF header to a GET', async () => {
  const { apiFetch } = loadApp({ window: { location: {} }, document: csrfDocument('tok123') });
  const original = globalThis.fetch;
  let seen = 'unset';
  globalThis.fetch = async (url, init) => {
    seen = init;
    return { ok: true, status: 200 };
  };
  try {
    await apiFetch('/api/restore-jobs', { method: 'GET' });
    assert.deepEqual(seen, { method: 'GET' });
  } finally {
    globalThis.fetch = original;
  }
});

test('apiFetch redirects to /login?reason=expired on 401 and never resolves', async () => {
  const { apiFetch, window } = loadApp({ window: { location: {} } });
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({}) });
  try {
    let settled = false;
    apiFetch('/api/thing').then(() => {
      settled = true;
    });
    await flush();
    assert.equal(window.location.href, '/login?reason=expired');
    assert.equal(settled, false);
  } finally {
    globalThis.fetch = original;
  }
});

test('a burst of 401s triggers only one redirect', async () => {
  const { apiFetch, window } = loadApp({ window: { location: {} } });
  const original = globalThis.fetch;
  let navigations = 0;
  const loc = {};
  Object.defineProperty(loc, 'href', {
    set() {
      navigations += 1;
    },
  });
  window.location = loc;
  globalThis.fetch = async () => ({ status: 401 });
  try {
    apiFetch('/api/a');
    apiFetch('/api/b');
    apiFetch('/api/c');
    await flush();
    assert.equal(navigations, 1);
  } finally {
    globalThis.fetch = original;
  }
});
