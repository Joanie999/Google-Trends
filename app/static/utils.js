export const COLORS = ['#087f74', '#6671d9', '#db9050', '#bd5f87', '#418db3'];
export const COUNTRIES = {
  '': '全球',
  US: '美国',
  GB: '英国',
  JP: '日本',
  TW: '中国台湾',
  HK: '中国香港',
  SG: '新加坡',
  CA: '加拿大',
  AU: '澳大利亚',
  DE: '德国',
  FR: '法国',
  IN: '印度',
  BR: '巴西',
  KR: '韩国',
};
export const TIMES = {
  'now 7-d': '过去 7 天',
  'today 1-m': '过去 30 天',
  'today 3-m': '过去 90 天',
  'today 12-m': '过去 12 个月',
  'today 5-y': '过去 5 年',
};
export const PROPS = {
  '': '网页搜索',
  youtube: 'YouTube',
  news: '新闻搜索',
  images: '图片搜索',
  froogle: '购物搜索',
};
export function splitKeywords(text) {
  return text
    .split(/[,，\n]/)
    .map((s) => s.trim().replace(/\s+/g, ' '))
    .filter(Boolean);
}
export function uniqueKeywords(words) {
  const seen = new Set();
  return words.filter((w) => {
    const k = w.toLocaleLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}
export function trendsUrl(request) {
  const params = new URLSearchParams({
    q: request.keywords.join(','),
    geo: request.geo,
    date: request.timeframe,
    hl: 'zh-CN',
  });
  if (request.gprop) params.set('gprop', request.gprop);
  return `https://trends.google.com/trends/explore?${params}`;
}
export function searchUrl(keyword) {
  return `https://www.google.com/search?${new URLSearchParams({ q: keyword })}`;
}
export function safeUrl(value) {
  try {
    const u = new URL(value);
    return ['https:', 'http:'].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}
export function csvCell(value) {
  let text = String(value ?? '');
  if (/^[\s\uFEFF]*[=+\-@\t\r]/.test(text) || /^[\t\r\n]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}
export function resultCsv(result) {
  const r = result.request;
  const rows = [
    ['数据模式', r.mode === 'demo' ? '演示合成数据' : 'Google Trends 真实数据'],
    ['获取时间', result.fetched_at],
    ['地区', COUNTRIES[r.geo] ?? r.geo],
    ['时间范围', TIMES[r.timeframe]],
    ['搜索类型', PROPS[r.gprop]],
    ['口径', '0–100 相对兴趣指数，非搜索次数；不完整时间点标记为 true'],
    [],
    ['时间', ...r.keywords, '不完整时间点'],
    ...result.series.map((p) => [p.date, ...r.keywords.map((k) => p.values[k]), p.is_partial]),
  ];
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n');
}
export function summary(series, keyword) {
  const complete = series
    .filter((p) => !p.is_partial)
    .map((p) => p.values[keyword])
    .filter(Number.isFinite);
  if (!complete.length) return { average: null, peak: null, change: null };
  const average = Math.round(complete.reduce((a, b) => a + b, 0) / complete.length);
  const recent = complete.slice(-4),
    prior = complete.slice(-8, -4);
  const sum = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
  const change =
    recent.length === 4 && prior.length === 4 && sum(prior) > 0
      ? Math.round((sum(recent) / sum(prior) - 1) * 100)
      : null;
  return { average, peak: Math.max(...complete), change };
}
export function validSaved(item) {
  return (
    item &&
    typeof item.id === 'string' &&
    item.request &&
    Array.isArray(item.request.keywords) &&
    item.request.keywords.length >= 1 &&
    item.request.keywords.length <= 5 &&
    item.request.keywords.every((k) => typeof k === 'string' && k.trim() && k.length <= 100) &&
    Object.hasOwn(COUNTRIES, item.request.geo) &&
    Object.hasOwn(TIMES, item.request.timeframe) &&
    Object.hasOwn(PROPS, item.request.gprop) &&
    ['demo', 'live'].includes(item.request.mode)
  );
}
