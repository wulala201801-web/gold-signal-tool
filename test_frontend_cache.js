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
    this.classList = {toggle() {}};
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

async function run(cached) {
  const elements = new Map();
  const storage = new Map();
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
    fetch: async () => {throw new TypeError('failed to fetch');},
    setTimeout: callback => {callback();}
  };
  vm.createContext(context);
  vm.runInContext(script, context);
  await vm.runInContext('load()', context);
  return elements;
}

(async () => {
  const cached = await run(true);
  assert.equal(cached.get('scoreNum').textContent, 46);
  assert.match(cached.get('status').innerHTML, /显示缓存数据/);
  assert.match(cached.get('status').innerHTML, /浏览器网络请求失败/);

  const empty = await run(false);
  assert.equal(empty.get('scoreNum').textContent, '--');
  assert.equal(empty.get('lamp').textContent, '无法连接');
  assert.match(empty.get('status').innerHTML, /浏览器网络请求失败/);
  console.log('frontend cache fallback ok');
})().catch(error => {console.error(error); process.exit(1);});
