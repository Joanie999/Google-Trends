import test from 'node:test';
import assert from 'node:assert/strict';
import {
  splitKeywords,
  uniqueKeywords,
  trendsUrl,
  safeUrl,
  csvCell,
  resultCsv,
  summary,
  validSaved,
} from '../app/static/utils.js';

test('Chinese separators and duplicate keywords', () =>
  assert.deepEqual(uniqueKeywords(splitKeywords(' 咖啡  机，Coffee,coffee\n茶 ')), [
    '咖啡 机',
    'Coffee',
    '茶',
  ]));
test('Google deep link retains special characters and all filters', () => {
  const r = { keywords: ['C++', '茶 & 咖啡'], geo: 'JP', timeframe: 'today 3-m', gprop: 'youtube' };
  const u = new URL(trendsUrl(r));
  assert.equal(u.searchParams.get('q'), 'C++,茶 & 咖啡');
  assert.equal(u.searchParams.get('date'), 'today 3-m');
  assert.equal(u.searchParams.get('gprop'), 'youtube');
  assert.equal(u.searchParams.get('geo'), 'JP');
});
test('Unsafe news links rejected', () => {
  for (const u of ['javascript:alert(1)', 'data:text/html,x', 'file:///secret', 'not a url'])
    assert.equal(safeUrl(u), null);
  assert.equal(safeUrl('https://example.com/a'), 'https://example.com/a');
});
test('Spreadsheet formula protection including whitespace', () => {
  for (const s of ['=1+1', '+CMD', '-2+3', '@SUM(1)', ' \t=1', '\r=1', '\ttext'])
    assert.ok(csvCell(s).startsWith('"\''));
  assert.equal(csvCell('a,"b"'), '"a,""b"""');
});
test('Export binds original filters and preserves partial markers', () => {
  const result = {
    request: { keywords: ['=1+1'], geo: 'US', timeframe: 'today 12-m', gprop: '', mode: 'demo' },
    fetched_at: '2026-09-24',
    series: [{ date: '2026-09-01', values: { '=1+1': 20 }, is_partial: true }],
  };
  const csv = resultCsv(result);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('演示合成数据'));
  assert.ok(csv.includes('"\'=1+1"'));
  assert.ok(csv.includes('"true"'));
  assert.ok(csv.includes('美国'));
});
test('Summaries exclude incomplete periods and avoid zero-base percentages', () => {
  const points = [10, 10, 10, 10, 20, 20, 20, 20].map((v) => ({
    values: { a: v },
    is_partial: false,
  }));
  points.push({ values: { a: 100 }, is_partial: true });
  assert.deepEqual(summary(points, 'a'), { average: 15, peak: 20, change: 100 });
  assert.equal(summary([{ values: { a: 0 }, is_partial: false }], 'a').change, null);
  assert.equal(summary([{ values: { a: 20 }, is_partial: true }], 'a').average, null);
});
test('Reject malformed local storage entries', () => {
  assert.ok(!validSaved({ id: '1', request: { keywords: ['x'], geo: 'evil' } }));
  assert.ok(
    validSaved({
      id: '1',
      request: { keywords: ['茶'], geo: 'JP', timeframe: 'now 7-d', gprop: '', mode: 'live' },
    })
  );
});
