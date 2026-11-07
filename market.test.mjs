// 业务验收：防止品种、商品部位、鲜冻口径以及无条件折算造成误导。
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {classify,excludeProduct,normalizePrice,productCut,selectRecords,stale,safeUrl} from './market-core.mjs';
import {parseProduct,listItems} from './market-fetch.mjs';
import {parseRou,parseFood21} from './market-extra.mjs';
test('肉交所只取供应区，分类顺序改变时拒绝解析',()=>{
 const heading='<div class="hd sell-b-color"><ul><li>综合</li><li>猪产品</li><li>牛产品</li><li>羊产品</li><li>鸡产品</li><li>鸭产品</li><li>水产类</li><li>其他肉类</li></ul></div>';
 const row='<dl><dd class="w1"><a href="https://www.roujiaosuo.com/sell/show/123/">白条鸭</a></dd><dd class="w2">现货</dd><dd class="w3">中国</dd><dd class="w4">4.2 元/公斤</dd><dd class="w5">5000 公斤</dd><dd class="w6">山东临沂市</dd><dd class="w7">2026-11-08</dd></dl>';
 const groups=Array.from({length:8},(_,i)=>'<ul class="data-list clearfix">'+(i===5?row:'')+'</ul>').join('');
 const html='供应信息</span>'+heading+groups+'采购信息</span>'+row;const rs=parseRou(html);assert.equal(rs.length,1);assert.equal(rs[0].category,'duck');assert.equal(rs[0].pricePerJin,2.1);assert.equal(rs[0].moq,'');assert.deepEqual(rs[0].formIds,['unknown']);assert.throws(()=>parseRou(html.replace('猪产品','变更分类')));
});
test('市场参考价保留转载口径与原始日期，不冒充供应商',()=>{
 const html='<tr><td><a href="/price/product/1006-1256.html" class="dre_xr1">白条鸡</a></td><td><span class="dre_xr3">13.0元<em>/公斤</em></span></td><td><span class="dre_xr4">2026-11-07</span></td></tr>';
 const r=parseFood21(html,'https://wap.21food.cn/price/market/1006.html')[0];assert.equal(r.recordKind,'market');assert.equal(r.pricePerJin,6.5);assert.equal(r.quoteDate,'2026-11-07');assert.equal(selectRecords([r],{kind:'offer'}).length,0);assert.equal(selectRecords([r],{kind:'market'}).length,1);
});
test('元/公斤、元/吨及明确箱净重换算',()=>{assert.equal(normalizePrice(17,'公斤'),8.5);assert.equal(normalizePrice(3400,'吨'),1.7);assert.equal(normalizePrice(120,'箱',20),6);});
test('缺净重和均重不强行折算，蛋不能按只当斤',()=>{assert.equal(normalizePrice(70,'只'),null);assert.equal(normalizePrice(200,'箱'),null);assert.equal(normalizePrice(1,'枚'),null);assert.equal(normalizePrice(Infinity,'斤'),null);});
test('青头鸭按品种筛选且不误判成鸭头分割品',()=>{assert.deepEqual(classify('duck','青头鸭活禽').breedIds,['qingtou']);assert.equal(productCut('duck','青头鸭活禽'),'whole');assert.equal(productCut('duck','冻鸭头'),'cut');});
test('清远麻鸡可通过清远鸡和麻鸡两个品种入口查找',()=>{assert.deepEqual(classify('chicken','冰鲜清远麻鸡').breedIds,['qingyuan','ma']);});
test('冷链不等于冻品；白条不等于鲜品',()=>{assert.deepEqual(classify('duck','白条鸭 冷链配送').formIds,['unknown']);assert.deepEqual(classify('pig','猪头肉','保存状态：冻肉').formIds,['frozen']);});
test('鲜冻描述冲突归待核实，明确的保存字段优先',()=>{assert.deepEqual(classify('chicken','新鲜冷冻三黄鸡').formIds,['unknown']);assert.deepEqual(classify('pig','新鲜活杀香猪肉','保存状态：冻肉').formIds,['frozen']);});
test('筛掉鹅苗、猪苗、种蛋、熟食，保留生鲜原料',()=>{for(const t of ['脱温狮头鹅小苗','黑猪仔猪','孵化种蛋','全熟开袋即食猪肉'])assert.equal(excludeProduct(t),true);assert.equal(excludeProduct('生扒猪头肉（卤菜好食材）'),false);});
test('标题无苗字但规格是脱温或作种的商品仍排除',()=>{assert.equal(excludeProduct('汕头澄海狮头鹅活体','鹅分类：脱温鹅；单只重：0.5-1'),true);assert.equal(excludeProduct('太湖猪','用途：作种；公母：母猪'),true);assert.equal(excludeProduct('老鸭 白条鸭 老种鸭','鸭肉状态：白条鸭；货品类别：冰冻鸭肉'),false);});
const fixture=(name='青头鸭活禽',extra='')=>`<script type="application/ld+json">${JSON.stringify({'@type':'Product',name,description:'青头鸭价格公道 70元/只,500只起批,从广东省肇庆市端州区发出,欢迎在线咨询、供应商家测试商家。',offers:{price:'70',areaServed:{name:'广东省肇庆市端州区'},availability:'https://schema.org/InStock'}})}</script><div class="detail-attrs-item"><div class="t1">单只重</div><div class="t2">7-8斤</div></div></div> ${extra}`;
test('公开商品字段解析，均重范围不擅自取平均',()=>{const r=parseProduct(fixture(),'https://www.cnhnb.com/gongying/123/','duck');assert.equal(r.price,70);assert.equal(r.unit,'只');assert.equal(r.pricePerJin,null);assert.equal(r.moq,'500只起批');assert.equal(r.quoteDate,null);assert.equal(r.cut,'whole');assert.match(r.spec,/7-8斤/);});
test('下架、非商品、苗种不进入商品数据',()=>{assert.throws(()=>parseProduct(fixture('青头鸭','已下架'),'https://www.cnhnb.com/gongying/123/','duck'));assert.throws(()=>parseProduct(fixture('脱温鹅苗'),'https://www.cnhnb.com/gongying/123/','goose'));assert.throws(()=>parseProduct('<html>登录</html>','https://www.cnhnb.com/gongying/123/','duck'));});
test('不执行网站脚本',()=>{const html=fixture()+'<script>throw new Error("远端代码不得执行")</script>';assert.equal(parseProduct(html,'https://www.cnhnb.com/gongying/123/','duck').price,70);});
test('列表只发现食材商品',()=>{const html='<div class="supply-item"><a href="/gongying/1/"><h2>青头鸭活禽</h2></a></div><div class="supply-item"><a href="/gongying/2/"><h2>鹅苗</h2></a></div>';assert.equal(listItems(html,'duck').length,1);});
test('三级筛选联动：鸭→活禽→青头鸭，鸡→冻品→清远鸡',()=>{const rows=[{category:'duck',formIds:['live'],breedIds:['qingtou'],pricePerJin:null},{category:'chicken',formIds:['frozen'],breedIds:['qingyuan'],pricePerJin:8}];assert.equal(selectRecords(rows,{category:'duck',form:'live',breed:'qingtou'}).length,1);assert.equal(selectRecords(rows,{category:'chicken',form:'frozen',breed:'qingyuan'}).length,1);assert.equal(selectRecords(rows,{category:'duck',form:'frozen'}).length,0);assert.equal(selectRecords(rows,{pricedOnly:true}).length,1);});
test('超过7天的旧核查要标记',()=>{assert.equal(stale({checkedAt:'2026-11-01T00:00:00Z'},Date.parse('2026-11-09T00:00:00Z')),true);});
test('原始链接只允许 HTTP(S)',()=>{assert.equal(safeUrl('javascript:alert(1)'),'#');assert.equal(safeUrl('https://www.cnhnb.com/'),'https://www.cnhnb.com/');});
test('真实数据验收：五类、唯一商品、来源与时间、无失效混入',async()=>{const d=JSON.parse(await fs.readFile(new URL('./market.json',import.meta.url),'utf8'));assert.equal(new Set(d.records.map(r=>r.id)).size,d.records.length);for(const cat of ['pig','chicken','duck','goose','egg'])assert.ok(d.records.some(r=>r.category===cat),cat);for(const r of d.records){assert.equal(excludeProduct(r.title,r.spec),false);assert.ok(r.price>0);assert.ok(r.checkedAt);assert.ok(['www.cnhnb.com','www.roujiaosuo.com','wap.21food.cn'].includes(new URL(r.url).hostname));assert.ok(!('phone' in r));assert.ok(!('contact' in r));}for(const s of d.sources.filter(s=>s.status==='collected'))assert.ok(d.records.some(r=>r.sourceId===s.id));});
