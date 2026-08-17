const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const html = fs.readFileSync('index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace("document.getElementById('refresh').onclick=load;if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js');load();", '');

class Element {
  constructor() {
    this.textContent = '';
    this.innerHTML = '';
    this.className = '';
    this.disabled = false;
    this.style = {};
    this.classList = {add() {}, remove() {}, toggle() {}};
  }
}

function completePayload() {
  const data = {};
  for (const key of ['gold', 'dxy', 'usdjpy', 'nasdaq', 'vix', 'real_yield']) {
    data[key] = {ok: true, value: 100, previous: 99, source: 'test'};
  }
  return {
    fetchedAt: 1,
    data,
    scores: {
      macroRisk: 25, priceHeatRisk: 60, combinedRisk: 46, signal: 'yellow',
      priceHeat: {percentile: 80, return20: 10}, macroReasons: [], guards: [],
      conclusion: 'test', actions: ['hold', 'wait', 'pause']
    }
  };
}

async function run(cached, recover = false) {
  const elements = new Map();
  const storage = new Map();
  const timers = [];
  let requests = 0;
  if (cached) {
    storage.set('goldSignalLastPayload', JSON.stringify(completePayload()));
    storage.set('goldSignalLastUpdated', new Date(1000).toISOString());
  }
  const context = {
    console,
    document: {getElementById(id) {if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id);}},
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key)
    },
    location: {protocol: 'https:'},
    navigator: {},
    fetch: async () => {
      requests++;
      if (recover && requests > 1) return {ok: true, json: async () => completePayload()};
      throw new TypeError('failed to fetch');
    },
    setTimeout: (callback, delay) => {if (delay < 1000) callback(); else timers.push(callback); return timers.length;},
    clearTimeout: () => {},
    setInterval: () => 1,
    clearInterval: () => {}
  };
  vm.createContext(context);
  vm.runInContext(script, context);
  await vm.runInContext('load()', context);
  return {elements, timers};
}

(async () => {
  const cachedRun = await run(true);
  assert.equal(cachedRun.elements.get('scoreNum').textContent, 46);
  assert.equal(cachedRun.elements.get('marketDate').textContent, '1970.1.1');
  assert.match(cachedRun.elements.get('status').innerHTML, /显示缓存数据/);
  assert.match(cachedRun.elements.get('status').innerHTML, /浏览器网络请求失败/);

  const emptyRun = await run(false);
  assert.equal(emptyRun.elements.get('scoreNum').textContent, '--');
  assert.equal(emptyRun.elements.get('lamp').textContent, '正在重新连接');
  assert.equal(emptyRun.elements.get('marketDate').textContent, '数据待更新');
  assert.match(emptyRun.elements.get('progressNote').textContent, /5秒后重新连接/);

  const recoveryRun = await run(false, true);
  recoveryRun.timers.shift()();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(recoveryRun.elements.get('scoreNum').textContent, 46);
  assert.equal(recoveryRun.elements.get('lamp').textContent, '🟡 黄灯');
  assert.equal(recoveryRun.elements.get('marketDate').textContent, '1970.1.1');
  assert.equal(recoveryRun.elements.get('progressPercent').textContent, '100%');
  assert.equal(recoveryRun.elements.get('progressStage').textContent, '数据更新完成');
  console.log('frontend cache fallback ok');
})().catch(error => {console.error(error); process.exit(1);});
