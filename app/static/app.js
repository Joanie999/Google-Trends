import {
  COLORS,
  COUNTRIES,
  TIMES,
  PROPS,
  splitKeywords,
  uniqueKeywords,
  trendsUrl,
  searchUrl,
  safeUrl,
  resultCsv,
  summary,
  validSaved,
} from './utils.js';

const $ = (id) => document.getElementById(id);
const state = {
  keywords: ['ChatGPT', 'Gemini', 'Claude'],
  mode: 'demo',
  view: 'explore',
  result: null,
  related: 'rising',
  queryId: 0,
  trendingId: 0,
  saved: [],
};
const STORAGE = 'trendscope.saved.v1';
let toastTimer, exploreAbort, trendingAbort;
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
function button(text, cls, action) {
  const b = el('button', cls, text);
  b.type = 'button';
  b.addEventListener('click', action);
  return b;
}
function link(text, url, cls = '') {
  const a = el('a', cls, text);
  const safe = safeUrl(url);
  if (safe) a.href = safe;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
function color(node, index) {
  node.style.setProperty('--series-color', COLORS[index % COLORS.length]);
  return node;
}
function toast(text) {
  $('toast').textContent = text;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($('toast').hidden = true), 3300);
}
function notice(text) {
  $('notice').textContent = text || '';
  $('notice').hidden = !text;
}
function options(select, values, selected) {
  select.replaceChildren(
    ...Object.entries(values).map(([value, label]) => {
      const o = el('option', '', label);
      o.value = value;
      return o;
    })
  );
  select.value = selected;
}
function dateLabel(date, full = false) {
  const d = new Date(date);
  return Number.isNaN(d.getTime())
    ? String(date)
    : d.toLocaleDateString(
        'zh-CN',
        full
          ? { year: 'numeric', month: '2-digit', day: '2-digit' }
          : { month: 'short', day: 'numeric' }
      );
}
function fetched(date) {
  const d = new Date(date);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
}
function request() {
  return {
    keywords: [...state.keywords],
    geo: $('geo').value,
    timeframe: $('timeframe').value,
    gprop: $('gprop').value,
    mode: state.mode,
  };
}
function context(r) {
  return `${COUNTRIES[r.geo]} · ${TIMES[r.timeframe]} · ${PROPS[r.gprop]}`;
}

function renderChips() {
  $('keyword-chips').replaceChildren(
    ...state.keywords.map((word, i) => {
      const chip = color(el('span', 'chip'), i);
      chip.append(el('span', 'color-dot'), el('span', '', word));
      const remove = button('×', '', () => {
        state.keywords.splice(i, 1);
        renderChips();
        updateEmptyLink();
      });
      remove.setAttribute('aria-label', `移除 ${word}`);
      chip.append(remove);
      return chip;
    })
  );
  $('keyword-count').textContent = `${state.keywords.length} / 5 个关键词`;
}
function addKeywords() {
  const newWords = splitKeywords($('keyword-input').value);
  const words = uniqueKeywords([...state.keywords, ...newWords]);
  if (words.length > 5) {
    notice('最多比较 5 个关键词，请先移除部分关键词。');
    return false;
  }
  if (words.some((k) => k.length > 100)) {
    notice('每个关键词最多 100 个字符。');
    return false;
  }
  state.keywords = words;
  $('keyword-input').value = '';
  renderChips();
  updateEmptyLink();
  notice('');
  return true;
}
function updateEmptyLink() {
  $('empty-google').href = trendsUrl(request());
}
function setMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode;
  state.queryId++;
  state.trendingId++;
  exploreAbort?.abort();
  trendingAbort?.abort();
  state.result = null;
  setLoading(false);
  notice('');
  renderMode();
  $('explore-results').hidden = true;
  $('explore-empty').hidden = false;
  if (state.view === 'explore' && mode === 'demo') runExplore();
  if (state.view === 'trending') loadTrending();
}
function renderMode() {
  document.querySelectorAll('[data-mode]').forEach((b) => {
    b.classList.toggle('selected', b.dataset.mode === state.mode);
    b.setAttribute('aria-pressed', String(b.dataset.mode === state.mode));
  });
  const live = state.mode === 'live';
  $('mode-banner').classList.toggle('live', live);
  $('mode-banner').querySelector('strong').textContent = live
    ? '真实数据模式'
    : '你正在浏览演示数据';
  $('mode-banner').querySelector('p span').textContent = live
    ? '实时热搜来自 Google RSS；关键词趋势可能因网络或 Google 限流而暂不可用。'
    : '图表与话题均为合成示例，切换「真实数据」即可查询 Google。';
  $('go-live').hidden = live;
}
function setView(view) {
  state.view = view;
  notice('');
  document.querySelectorAll('.view').forEach((n) => (n.hidden = n.id !== `view-${view}`));
  const titles = {
    explore: ['趋势探索', '探索搜索趋势', '比较关键词的关注度，发现正在发生的变化。'],
    trending: ['实时热搜', '此刻，大家在搜什么', '追踪地区热门搜索，把新话题变成下一个研究方向。'],
    saved: ['我的收藏', '让研究继续发生', '把值得关注的关键词，留在你的研究工作区。'],
  };
  $('crumb').textContent = titles[view][0];
  $('page-title').replaceChildren(
    document.createTextNode(titles[view][1]),
    el('span', 'title-dot', '.')
  );
  $('page-description').textContent = titles[view][2];
  document.querySelectorAll('[data-view]').forEach((b) => {
    b.classList.toggle('active', b.dataset.view === view);
    if (b.dataset.view === view) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });
  if (view === 'trending') loadTrending();
  if (view === 'saved') renderSaved();
}
async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('本地服务返回了无效响应，请确认服务正在运行。');
  }
  if (!response.ok) throw new Error(data.error?.message || '暂时无法完成查询，请稍后重试。');
  return data;
}
function setLoading(loading) {
  $('loading').hidden = !loading;
  $('query-button').disabled = loading;
  $('query-button').firstElementChild.textContent = loading ? '查询中…' : '探索趋势';
}
async function runExplore() {
  if (!addKeywords()) return;
  if (!state.keywords.length) {
    notice('请至少输入一个关键词。');
    $('keyword-input').focus();
    return;
  }
  const payload = request(),
    id = ++state.queryId;
  exploreAbort?.abort();
  exploreAbort = new AbortController();
  state.result = null;
  notice('');
  setLoading(true);
  $('explore-results').hidden = true;
  $('explore-empty').hidden = true;
  try {
    const result = await api('/api/explore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: exploreAbort.signal,
    });
    if (id !== state.queryId) return;
    state.result = result;
    renderResult();
  } catch (error) {
    if (id !== state.queryId || error.name === 'AbortError') return;
    notice(
      error.message === 'Failed to fetch'
        ? '无法连接本地服务，请确认启动窗口仍在运行。'
        : error.message
    );
    $('explore-empty').hidden = false;
    updateEmptyLink();
  } finally {
    if (id === state.queryId) setLoading(false);
  }
}

function renderResult() {
  const r = state.result,
    q = r.request;
  $('explore-results').hidden = false;
  $('explore-empty').hidden = true;
  $('result-mode').textContent = q.mode === 'demo' ? '演示数据' : '真实数据';
  $('result-context').textContent = context(q);
  $('open-google').href = trendsUrl(q);
  $('fetched-time').textContent = `${r.cached ? '缓存 · ' : ''}${fetched(r.fetched_at)} 获取`;
  $('chart-legend').replaceChildren(
    ...q.keywords.map((word, i) => {
      const n = color(el('span'), i);
      n.append(el('i', 'color-dot'), document.createTextNode(word));
      return n;
    })
  );
  renderChart();
  renderSummaries();
  options($('region-keyword'), Object.fromEntries(q.keywords.map((k) => [k, k])), q.keywords[0]);
  renderRegions();
  renderRelated();
  renderTable();
}
function renderChart() {
  const svg = $('trend-chart'),
    data = state.result,
    points = data.series;
  svg.replaceChildren();
  $('chart-tooltip').hidden = true;
  const W = Math.max(300, svg.clientWidth),
    H = svg.clientHeight || 280,
    left = 34,
    right = 18,
    top = 18,
    bottom = 37,
    width = W - left - right,
    height = H - top - bottom;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const x = (i) => left + (i * width) / Math.max(1, points.length - 1),
    y = (v) => top + ((100 - v) / 100) * height;
  function s(tag, attrs = {}, text) {
    const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (text !== undefined) n.textContent = text;
    svg.append(n);
    return n;
  }
  s(
    'title',
    {},
    `搜索兴趣趋势：${data.request.keywords.join('、')}。使用左右方向键查看数据点，或打开下方数据表。`
  );
  [0, 25, 50, 75, 100].forEach((v) => {
    s('line', {
      x1: left,
      y1: y(v),
      x2: W - right,
      y2: y(v),
      stroke: '#edf1ee',
      'stroke-width': 1,
      'stroke-dasharray': v === 0 ? '0' : '3 5',
    });
    s(
      'text',
      { x: left - 12, y: y(v) + 4, 'text-anchor': 'end', fill: '#a2ada5', 'font-size': 11 },
      v
    );
  });
  const ticks = W < 500 ? 4 : 6;
  for (let i = 0; i < ticks; i++) {
    const idx = Math.round((i * (points.length - 1)) / (ticks - 1));
    s(
      'text',
      {
        x: x(idx),
        y: H - 9,
        'text-anchor': i === 0 ? 'start' : i === ticks - 1 ? 'end' : 'middle',
        fill: '#788b7e',
        'font-size': 11,
      },
      dateLabel(points[idx].date)
    );
  }
  data.request.keywords.forEach((k, i) => {
    const coords = points.map((p, j) => `${x(j)},${y(p.values[k])}`).join(' ');
    if (i === 0)
      s('polygon', {
        points: `${x(0)},${y(0)} ${coords} ${x(points.length - 1)},${y(0)}`,
        fill: COLORS[i],
        'fill-opacity': 0.045,
      });
    s('polyline', {
      points: coords,
      fill: 'none',
      stroke: COLORS[i],
      'stroke-width': 2.3,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
    });
  });
  const guide = s('line', {
    x1: left,
    y1: top,
    x2: left,
    y2: y(0),
    stroke: '#9bafa2',
    'stroke-width': 1,
    'stroke-dasharray': '3 4',
    visibility: 'hidden',
  });
  const dots = data.request.keywords.map((k, i) =>
    s('circle', { r: 4, fill: COLORS[i], stroke: '#fff', 'stroke-width': 2, visibility: 'hidden' })
  );
  let selected = 0;
  function show(idx) {
    selected = Math.max(0, Math.min(points.length - 1, idx));
    const p = points[selected];
    guide.setAttribute('visibility', 'visible');
    guide.setAttribute('x1', x(selected));
    guide.setAttribute('x2', x(selected));
    dots.forEach((d, i) => {
      d.setAttribute('visibility', 'visible');
      d.setAttribute('cx', x(selected));
      d.setAttribute('cy', y(p.values[data.request.keywords[i]]));
    });
    const tip = $('chart-tooltip');
    tip.replaceChildren(
      el('small', '', `${dateLabel(p.date, true)}${p.is_partial ? ' · 数据尚不完整' : ''}`)
    );
    data.request.keywords.forEach((k, i) => {
      const row = color(el('div'), i);
      const label = el('span');
      label.append(el('i', 'color-dot'), document.createTextNode(` ${k}`));
      row.append(label, el('strong', '', p.values[k]));
      tip.append(row);
    });
    tip.hidden = false;
    const rect = svg.getBoundingClientRect();
    const scale = Math.min(rect.width / W, rect.height / H);
    const offset = (rect.width - W * scale) / 2;
    const px = offset + x(selected) * scale;
    tip.style.left = `${Math.max(0, Math.min(px + 14, $('chart-wrap').clientWidth - tip.offsetWidth))}px`;
  }
  function hide() {
    guide.setAttribute('visibility', 'hidden');
    dots.forEach((d) => d.setAttribute('visibility', 'hidden'));
    $('chart-tooltip').hidden = true;
  }
  svg.onpointermove = (e) => {
    const rect = svg.getBoundingClientRect();
    const scale = Math.min(rect.width / W, rect.height / H),
      offset = (rect.width - W * scale) / 2;
    show(
      Math.round((((e.clientX - rect.left - offset) / scale - left) / width) * (points.length - 1))
    );
  };
  svg.onpointerleave = hide;
  svg.onblur = hide;
  svg.onfocus = () => show(points.length - 1);
  svg.onkeydown = (e) => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Escape'].includes(e.key)) {
      e.preventDefault();
      if (e.key === 'Escape') hide();
      else
        show(
          e.key === 'Home'
            ? 0
            : e.key === 'End'
              ? points.length - 1
              : selected + (e.key === 'ArrowLeft' ? -1 : 1)
        );
    }
  };
}
function renderSummaries() {
  const data = state.result;
  $('summary-cards').replaceChildren(
    ...data.request.keywords.map((k, i) => {
      const stats = summary(data.series, k),
        card = color(el('article', 'summary-card'), i),
        head = el('div', 'summary-label');
      head.append(el('span', '', k), link('↗', searchUrl(k)));
      head.lastChild.setAttribute('aria-label', `在 Google 搜索 ${k}`);
      const value = el('div', 'summary-value', stats.average ?? '—');
      value.append(el('small', '', '平均兴趣指数'));
      const foot = el('div', 'summary-foot');
      const change = el(
        'span',
        `change${stats.change < 0 ? ' negative' : ''}`,
        stats.change === null
          ? '变化不足以计算'
          : `${stats.change >= 0 ? '↗ +' : '↘ '}${stats.change}%`
      );
      change.title = '最近 4 个完整数据点的均值与前 4 个完整数据点比较';
      foot.append(change, el('span', '', `峰值 ${stats.peak ?? '—'} · 排除未完整数据`));
      card.append(head, value, foot);
      return card;
    })
  );
}
function renderRegions() {
  if (!state.result) return;
  const k = $('region-keyword').value,
    i = state.result.request.keywords.indexOf(k);
  const rows = [...state.result.regions].sort((a, b) => b.values[k] - a.values[k]).slice(0, 5);
  $('region-subtitle').textContent =
    state.result.request.keywords.length > 1
      ? '各地区内部的关键词相对份额'
      : '按地区内搜索占比归一化';
  if (!rows.length) {
    $('region-list').replaceChildren(el('div', 'inline-empty', '当前范围暂无地区数据。'));
    return;
  }
  $('region-list').replaceChildren(
    ...rows.map((r, j) => {
      const row = color(el('div', 'region-row'), i),
        track = el('div', 'region-track'),
        bar = el('div', 'region-bar');
      bar.style.width = `${r.values[k]}%`;
      track.append(bar);
      const name = el('span', 'region-name', r.name);
      name.title = r.name;
      row.append(
        el('span', 'rank', String(j + 1).padStart(2, '0')),
        name,
        track,
        el('span', 'region-value', r.values[k])
      );
      return row;
    })
  );
}
function exploreWord(word) {
  state.keywords = [word];
  $('keyword-input').value = '';
  renderChips();
  setView('explore');
  runExplore();
  $('main').scrollIntoView({ behavior: 'auto' });
}
function renderRelated() {
  const data = state.result;
  if (!data) return;
  document
    .querySelectorAll('[data-related]')
    .forEach((b) => b.classList.toggle('active', b.dataset.related === state.related));
  if (!data.related_available) {
    const n = el(
      'div',
      'inline-empty',
      '多词比较暂不提供相关搜索词。单独探索一个关键词，即可查看它的关联需求。'
    );
    n.append(
      button(`单独探索 ${data.request.keywords[0]} ↗`, '', () =>
        exploreWord(data.request.keywords[0])
      )
    );
    $('related-list').replaceChildren(n);
    return;
  }
  const rows = data.related[state.related] || [];
  $('related-list').replaceChildren(
    ...(rows.length
      ? rows.slice(0, 5).map((r, i) => {
          const row = el('div', 'related-row');
          row.append(
            el('span', 'rank', String(i + 1).padStart(2, '0')),
            button(r.query, '', () => exploreWord(r.query)),
            el(
              'span',
              'growth',
              r.formatted_value === 'Breakout' ? '飙升' : r.formatted_value || r.value
            ),
            link('↗', searchUrl(r.query))
          );
          row.lastChild.setAttribute('aria-label', `在 Google 搜索 ${r.query}`);
          return row;
        })
      : [el('div', 'inline-empty', '当前筛选范围暂无相关搜索数据。')])
  );
}
function renderTable() {
  const data = state.result,
    table = el('table'),
    head = el('thead'),
    hr = el('tr');
  ['日期', ...data.request.keywords, '数据状态'].forEach((t) => {
    const th = el('th', '', t);
    th.scope = 'col';
    hr.append(th);
  });
  head.append(hr);
  const body = el('tbody');
  data.series.forEach((p) => {
    const tr = el('tr');
    [
      dateLabel(p.date, true),
      ...data.request.keywords.map((k) => p.values[k]),
      p.is_partial ? '尚不完整' : '完整',
    ].forEach((t) => tr.append(el('td', '', t)));
    body.append(tr);
  });
  table.append(head, body);
  $('data-table-wrap').replaceChildren(table);
  $('data-table-wrap').hidden = true;
  $('toggle-table').setAttribute('aria-expanded', 'false');
  $('toggle-table').textContent = '查看数据表 ↓';
}

async function loadTrending() {
  const id = ++state.trendingId,
    mode = state.mode,
    geo = $('trending-geo').value;
  trendingAbort?.abort();
  trendingAbort = new AbortController();
  $('refresh-trending').disabled = true;
  $('trending-source').textContent = '正在获取…';
  $('trending-list').replaceChildren(el('div', 'inline-empty', '正在加载地区热搜…'));
  notice('');
  try {
    const result = await api(`/api/trending?${new URLSearchParams({ geo, mode })}`, {
      signal: trendingAbort.signal,
    });
    if (id !== state.trendingId) return;
    $('trending-source').textContent =
      `${result.mode === 'demo' ? '演示数据' : 'Google Trends RSS'} · ${COUNTRIES[result.geo]} · ${fetched(result.fetched_at)}${result.cached ? ' · 缓存' : ''}`;
    $('trending-list').replaceChildren(
      ...(result.trends.length
        ? result.trends.map((r, i) => {
            const row = el('article', 'trending-row'),
              content = el('div'),
              news = el('div', 'hot-news');
            content.append(link(r.keyword, searchUrl(r.keyword), 'hot-title'));
            (r.news || []).slice(0, 2).forEach((n) => {
              if (safeUrl(n.url))
                news.append(link(`${n.source ? n.source + ' · ' : ''}${n.headline} ↗`, n.url));
            });
            if (!news.childNodes.length)
              news.textContent =
                result.mode === 'demo' ? '演示话题 · 切换真实数据查看关联新闻' : '暂无关联新闻';
            content.append(news);
            const volume = el('div', 'hot-volume', r.volume_text || '—');
            volume.append(el('small', '', '搜索量区间下限'));
            row.append(
              el('span', 'hot-rank', String(i + 1).padStart(2, '0')),
              content,
              volume,
              button('探索关键词 ↗', 'hot-explore', () => {
                const country = result.geo;
                if (result.mode !== state.mode) setMode(result.mode);
                $('geo').value = country;
                exploreWord(r.keyword);
              })
            );
            return row;
          })
        : [el('div', 'inline-empty', '当前地区暂无热搜，试试其他地区。')])
    );
  } catch (error) {
    if (id !== state.trendingId || error.name === 'AbortError') return;
    $('trending-source').textContent = '获取失败';
    $('trending-list').replaceChildren(
      el('div', 'inline-empty', '热搜暂不可用。可更换地区或稍后刷新。')
    );
    notice(error.message);
  } finally {
    if (id === state.trendingId) $('refresh-trending').disabled = false;
  }
}

function readSaved() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE) || '[]');
    state.saved = Array.isArray(value) ? value.filter(validSaved).slice(0, 30) : [];
  } catch {
    state.saved = [];
  }
  updateSavedCount();
}
function writeSaved(next) {
  try {
    localStorage.setItem(STORAGE, JSON.stringify(next));
    state.saved = next;
    updateSavedCount();
    return true;
  } catch {
    toast('浏览器存储不可用，收藏未保存。');
    return false;
  }
}
function updateSavedCount() {
  $('saved-count').textContent = state.saved.length;
}
function saveQuery() {
  if (!state.result) return;
  const q = state.result.request;
  if (state.saved.some((s) => JSON.stringify(s.request) === JSON.stringify(q))) {
    toast('这个查询已在收藏中。');
    return;
  }
  if (state.saved.length >= 30) {
    toast('最多保存 30 个查询，请先删除部分收藏。');
    return;
  }
  const entry = {
    id: crypto.randomUUID(),
    request: structuredClone(q),
    created_at: new Date().toISOString(),
  };
  if (writeSaved([entry, ...state.saved])) toast('已收藏查询，可在「我的收藏」中继续研究。');
}
function renderSaved() {
  if (!state.saved.length) {
    const n = el('div', 'empty-state');
    n.append(
      el('div', 'empty-glyph', '▤'),
      el('h2', '', '留住值得关注的趋势'),
      el('p', '', '完成一次查询后，点击「收藏查询」保存研究条件。'),
      button('去探索趋势 ↗', 'text-link', () => setView('explore'))
    );
    $('saved-list').replaceChildren(n);
    return;
  }
  $('saved-list').replaceChildren(
    ...state.saved.map((item) => {
      const card = el('article', 'saved-card'),
        body = el('div'),
        actions = el('div', 'saved-actions');
      body.append(
        el('h3', '', item.request.keywords.join(' / ')),
        el('p', '', `${item.request.mode === 'demo' ? '演示' : '真实'} · ${context(item.request)}`)
      );
      actions.append(
        button('继续探索 ↗', 'secondary', () => {
          state.queryId++;
          exploreAbort?.abort();
          state.mode = item.request.mode;
          state.keywords = [...item.request.keywords];
          $('keyword-input').value = '';
          $('geo').value = item.request.geo;
          $('timeframe').value = item.request.timeframe;
          $('gprop').value = item.request.gprop;
          renderMode();
          renderChips();
          setView('explore');
          runExplore();
        }),
        button('删除', 'delete-saved', () => {
          if (writeSaved(state.saved.filter((s) => s.id !== item.id))) {
            renderSaved();
            toast('已删除收藏。');
          }
        })
      );
      card.append(body, actions);
      return card;
    })
  );
}
function downloadCsv() {
  if (!state.result) return;
  const blob = new Blob([resultCsv(state.result)], { type: 'text/csv;charset=utf-8' }),
    url = URL.createObjectURL(blob),
    a = el('a');
  a.href = url;
  a.download = `trends-${state.result.request.mode}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('CSV 已导出，包含数据来源与筛选条件。');
}

options($('geo'), COUNTRIES, 'US');
options($('timeframe'), TIMES, 'today 12-m');
options($('gprop'), PROPS, '');
options($('trending-geo'), Object.fromEntries(Object.entries(COUNTRIES).filter(([k]) => k)), 'US');
document
  .querySelectorAll('[data-view]')
  .forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
document
  .querySelectorAll('[data-mode]')
  .forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
document.querySelectorAll('[data-related]').forEach((b) =>
  b.addEventListener('click', () => {
    state.related = b.dataset.related;
    renderRelated();
  })
);
document.querySelectorAll('[data-preset]').forEach((b) =>
  b.addEventListener('click', () => {
    state.keywords = splitKeywords(b.dataset.preset);
    $('keyword-input').value = '';
    renderChips();
    updateEmptyLink();
    if (state.mode === 'demo') runExplore();
    else toast('关键词已填入，点击「探索趋势」查询。');
  })
);
$('explore-form').addEventListener('submit', (e) => {
  e.preventDefault();
  runExplore();
});
$('keyword-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    if (e.ctrlKey || !e.target.value.trim()) runExplore();
    else addKeywords();
  }
});
$('add-keyword').addEventListener('click', () => {
  addKeywords();
  $('keyword-input').focus();
});
$('go-live').addEventListener('click', () => setMode('live'));
['geo', 'timeframe', 'gprop'].forEach((id) => $(id).addEventListener('change', updateEmptyLink));
$('region-keyword').addEventListener('change', renderRegions);
$('toggle-table').addEventListener('click', () => {
  const show = $('data-table-wrap').hidden;
  $('data-table-wrap').hidden = !show;
  $('toggle-table').setAttribute('aria-expanded', String(show));
  $('toggle-table').textContent = show ? '收起数据表 ↑' : '查看数据表 ↓';
});
$('refresh-trending').addEventListener('click', loadTrending);
$('trending-geo').addEventListener('change', loadTrending);
$('save-query').addEventListener('click', saveQuery);
$('export-csv').addEventListener('click', downloadCsv);
window.addEventListener('storage', (e) => {
  if (e.key === STORAGE) {
    readSaved();
    if (state.view === 'saved') renderSaved();
  }
});
readSaved();
renderChips();
renderMode();
updateEmptyLink();
runExplore();
new ResizeObserver(() => {
  if (state.result && state.view === 'explore') renderChart();
}).observe($('chart-wrap'));
