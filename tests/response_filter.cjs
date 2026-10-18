const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../scripts/domestic-ads.js'), 'utf8');
const zhihu = 'https://api.zhihu.com/topstory/recommend?limit=10';
const weibo = 'https://api.weibo.cn/2/statuses/container_timeline?count=20';
let count = 0;
function run(url, body) {
  let calls = 0, result, logs = [];
  vm.runInNewContext(script, {
    $request: {url}, $response: {body: typeof body === 'string' ? body : JSON.stringify(body)},
    $done: value => { calls++; result = value; }, console: {log: text => logs.push(text)}
  }, {timeout: 1500});
  assert.equal(calls, 1, '$done must be called once');
  if (result.body) JSON.parse(result.body);
  return {result, logs};
}
function test(name, check) { check(); count++; console.log('PASS ' + name); }
function unchanged(url, body) { assert.equal(Object.keys(run(url, body).result).length, 0); }

test('Zhihu: remove explicit ad cards, preserve ordinary items and cursors', () => {
  const paging = {next: 'https://api.zhihu.com/topstory/recommend?after_id=20', is_end: false};
  const normal = [{type: 'feed', target: {id: 'normal', title: '广告行业研究'}, ad: null},
                  {type: 'feed', ad: false, target: {id: 'video', type: 'zvideo'}}];
  const output = run(zhihu, {data: [...normal, {type: 'feed_advert'}, {type: 'market_card'},
    {type: 'feed', ad: {id: 'ad'}}, {extra: {type: 'SvipActivity'}}], paging});
  const parsed = JSON.parse(output.result.body);
  assert.deepEqual(parsed.data, normal);
  assert.deepEqual(parsed.paging, paging);
  assert.equal(output.logs.length, 1);
  assert(!output.logs.join('').includes('after_id'));
});
test('Zhihu: web-render and question feed endpoints', () => {
  for (const url of ['https://web-render.zhihu.com/topstory/recommend?x=1',
    'https://api.zhihu.com/questions/42/feeds?x=1', 'https://api.zhihu.com/next-render?x=1']) {
    assert.deepEqual(JSON.parse(run(url, {data: [{type: 'feed_advert'}]}).result.body).data, []);
  }
});
test('Weibo: identify ads through feed wrappers and nested card groups', () => {
  const normal = {data: {idstr: '1', text: '我想讨论广告，也不喜欢热推', ad_state: 0}};
  const value = {items: [normal, {data: {mblogtypename: '广告'}}, {status: {ad_state: 1}},
    {mblog: {promotion: {type: 'ad'}}}, {items: [{data: {is_ad: 1}}, {data: {idstr: '2'}}]}],
    cards: [{card_group: [{mblog: {ads_material_info: {is_ads: true}}}, {id: 'normal'}]}],
    next_cursor: 123};
  const output = JSON.parse(run(weibo, value).result.body);
  assert.deepEqual(output.items, [normal, {items: [{data: {idstr: '2'}}]}]);
  assert.deepEqual(output.cards, [{card_group: [{id: 'normal'}]}]);
  assert.equal(output.next_cursor, 123);
});
test('Weibo: newer API host variants and friends timeline', () => {
  for (const url of ['https://mapi.weibo.com/2/statuses/friends/timeline?x=1',
    'https://api.weibo.com/2/statuses/unread_friends_timeline?x=1',
    'https://mapi.weibo.cn/2/cardlist?x=1']) {
    assert.deepEqual(JSON.parse(run(url, {statuses: [{is_ad: '1'}, {text: 'normal'}]}).result.body).statuses,
      [{text: 'normal'}]);
  }
});
test('Weibo: preserve 64-bit IDs, quoted numeric text and escapes', () => {
  const body = '{"items":[{"data":{"id":1234567890123456789,"mid":-987654321098765432,"text":"\\\"1234567890123456789\\\"","tag":"__sr_integer_0"}},{"data":{"is_ad":1}}]}';
  const output = run(weibo, body).result.body;
  assert(output.includes('"id":1234567890123456789'));
  assert(output.includes('"mid":-987654321098765432'));
  assert(output.includes('"text":"\\\"1234567890123456789\\\""'));
  assert(output.includes('"tag":"__sr_integer_0"'));
});
test('Keep normal posts quoting promoted posts', () => {
  unchanged(weibo, {statuses: [{text: 'normal', retweeted_status: {is_ad: 1}}]});
});
test('Do not rewrite responses without recognized advertising', () => {
  unchanged(zhihu, '{ "data": [{"type":"feed","ad":null}], "paging":{} }');
  unchanged(weibo, {new_schema: [{is_ad: 1}]});
});
test('Fail open on malformed, empty, HTML or unexpected root data', () => {
  for (const body of ['{broken', '', '<html>upstream error</html>', 'null', '[]']) unchanged(zhihu, body);
});
test('Leave error and login responses intact', () => {
  unchanged(weibo, {code: 401, items: [{data: {is_ad: 1}}]});
  unchanged(zhihu, {error: {message: 'login needed'}, data: [{type: 'feed_advert'}]});
});
test('Exact host/path scope excludes lookalikes, login, payments and unrelated apps', () => {
  const value = {data: [{type: 'feed_advert'}], items: [{is_ad: 1}]};
  for (const url of ['https://api.zhihu.com.evil.example/topstory/recommend',
    'https://api.zhihu.com/topstory/recommendation', 'https://api.zhihu.com/people/me',
    'https://api.weibo.cn/2/account/login', 'https://api.weibo.cn/2/statuses/extend_other',
    'https://api.weibo.cn.evil.example/2/cardlist', 'https://www.alipay.com/pay',
    'https://api.bilibili.com/x/v2/feed/index']) unchanged(url, value);
});
test('Oversized or deeply nested data remains intact', () => {
  unchanged(zhihu, ' '.repeat(4000001));
  let value = {data: [{type: 'feed_advert'}]};
  for (let i = 0; i < 30; i++) value = {data: value};
  unchanged(zhihu, value);
});
console.log(`${count} response behavior checks passed (synthetic fixtures, not iOS tests).`);
