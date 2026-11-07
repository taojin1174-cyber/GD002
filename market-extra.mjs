// 独立平台适配器：供应信息与采购意向严格分开，市场参考价保留转载来源。
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {classify,normalizePrice,excludeProduct,productCut} from './market-core.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const plain=s=>String(s||'').replace(/<[^>]*>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim();
function base(sourceId,sourceName,id,title,category,price,unit,url,checkedAt){return {id:`${sourceId}-${id}`,sourceId,sourceName,title,category,...classify(category,title),cut:productCut(category,title),price,unit,pricePerJin:normalizePrice(price,unit),packNetJin:null,url,recordKind:'offer',priceType:'供应商挂牌价',supplier:'未读取商家名称，见原页',origin:'',moq:'',freight:'运费待确认',quoteDate:null,checkedAt,active:true,notes:[]};}
export function parseRou(html,checkedAt=new Date().toISOString()){
 const supply=html.split('供应信息</span>')[1]?.split('采购信息</span>')[0];if(!supply)throw Error('未识别供应区，拒绝混入求购意向价');
 const heading=plain(supply.match(/<div class="hd sell-b-color">([\s\S]*?)<\/ul>/)?.[1]);
 if(!/综合 猪产品 牛产品 羊产品 鸡产品 鸭产品 水产类 其他肉类/.test(heading))throw Error('供应分类顺序改变，暂停采集避免误分类');
 const groups=[...supply.matchAll(/<ul class="data-list clearfix">([\s\S]*?)<\/ul>/g)],records=[];
 for(const [index,category] of [[1,'pig'],[4,'chicken'],[5,'duck']]){
  const group=groups[index]?.[1];if(!group)continue;
  for(const m of group.matchAll(/<dl>([\s\S]*?)<\/dl>/g)){
   const fields=Object.fromEntries([...m[1].matchAll(/<dd class="w(\d+)"[^>]*>([\s\S]*?)<\/dd>/g)].map(x=>[x[1],x[2]]));
   const title=plain(fields[1]),url=fields[1]?.match(/href="(https:\/\/www\.roujiaosuo\.com\/sell\/show\/\d+\/)"/)?.[1],priceMatch=plain(fields[4]).match(/^(\d+(?:\.\d+)?)\s*元\s*\/\s*(公斤|千克|斤|吨|箱|件|只)$/);
   const quoteDate=plain(fields[7]);if(!url||!title||excludeProduct(title)||/熟爪|熟鸭肠/.test(title)||!priceMatch||!/^\d{4}-\d{2}-\d{2}$/.test(quoteDate))continue;
   const price=Number(priceMatch[1]);if(!(price>0))continue;
   const r=base('roujiaosuo','肉交所',url.match(/show\/(\d+)/)[1],title,category,price,priceMatch[2],url,checkedAt);
   r.quoteDate=quoteDate;r.dateLabel='平台更新日期';r.origin=plain(fields[6]);r.spec=`货源产地：${plain(fields[3])}；供货数量：${plain(fields[5])}；货源状态：${plain(fields[2])}`;
   r.notes=['供货数量不等于起订量','现货不等于鲜品，鲜冻状态需核实'];records.push(r);
  }
 }
 if(!records.length)throw Error('供应区没有可解析的猪鸡鸭报价');return records;
}
export function parseFood21(html,url,checkedAt=new Date().toISOString()){
 const market=plain(html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)?.[1])||'北京新发地农副产品批发市场信息中心',records=[];
 for(const m of html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)){
  const title=plain(m[1].match(/class="dre_xr1"[^>]*>([\s\S]*?)<\/a>/)?.[1]);
  const category=title==='鸡蛋'?'egg':title==='白条鸡'?'chicken':/^猪|肥膘/.test(title)?'pig':null;
  const priceMatch=plain(m[1].match(/class="dre_xr3"[^>]*>([\s\S]*?)<\/span>/)?.[1]).match(/^(\d+(?:\.\d+)?)元\s*\/\s*(公斤|斤|吨)$/),quoteDate=plain(m[1].match(/class="dre_xr4"[^>]*>([\s\S]*?)<\/span>/)?.[1]);
  if(!category||!priceMatch||!/^\d{4}-\d{2}-\d{2}$/.test(quoteDate))continue;
  const id=m[1].match(/\/price\/product\/(\d+-\d+)\.html/)?.[1];if(!id)continue;
  const r=base('21food','食品商务网',id,title,category,Number(priceMatch[1]),priceMatch[2],new URL(`/price/product/${id}.html`,url).href,checkedAt);
  r.recordKind='market';r.priceType='批发市场参考价（转载）';r.supplier=market;r.origin='北京';r.quoteDate=quoteDate;r.spec=`市场：${market}；展示渠道：食品商务网；非特定供应商成交报价`;
  r.notes=['转载市场参考价，不能视为当前可采购的供货承诺'];records.push(r);
 }
 if(!records.length)throw Error('没有可解析的市场参考价');return records;
}
export async function collectExtra(get){
 const records=[],sources=[];
 for(const [id,name,url,parse,kind] of [['roujiaosuo','肉交所','https://www.roujiaosuo.com/',parseRou,'供应商挂牌价'],['21food','食品商务网','https://wap.21food.cn/price/market/1006.html',parseFood21,'批发市场参考价（转载）']]){
  const checkedAt=new Date().toISOString();try{const html=await get(url),rows=id==='21food'?parse(html,url,checkedAt):parse(html,checkedAt);records.push(...rows);sources.push({id,name,url,kind,status:'collected',checkedAt,recordCount:rows.length,note:id==='roujiaosuo'?'已读取猪、鸡、鸭供应区的挂牌报价、供货数量、仓库和平台更新日期；未使用采购意向价。':'已读取北京新发地市场的猪肉、白条鸡、鸡蛋参考价；信息转载自市场，单独归入市场参考价。'});console.log(`${name}：${rows.length} 条真实报价`);}catch(e){sources.push({id,name,url,kind,status:'failed',checkedAt,note:'本次未能取得可解析报价，旧数据保留原核查时间。',error:e.message});}}
 return {records,sources};
}
// 可单独运行新增平台核查，无需重复访问原有来源。
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const extra=await collectExtra(async url=>{const r=await fetch(url,{signal:AbortSignal.timeout(30000)});if(!r.ok)throw Error(`HTTP ${r.status}`);return r.text();});
 const data=JSON.parse(await fs.readFile(path.join(root,'market.json'),'utf8'));
 for(const source of extra.sources){const i=data.sources.findIndex(s=>s.id===source.id);if(i>=0)data.sources[i]=source;else data.sources.push(source);}
 const merged=new Map(data.records.map(r=>[r.id,r]));for(const r of extra.records)merged.set(r.id,r);data.records=[...merged.values()];data.updated=new Date().toISOString();
 const history=JSON.parse(await fs.readFile(path.join(root,'market-history.json'),'utf8'));for(const r of extra.records)history.observations.push({id:r.id,checkedAt:r.checkedAt,price:r.price,unit:r.unit,pricePerJin:r.pricePerJin,spec:r.spec});history.updated=data.updated;
 await fs.writeFile(path.join(root,'market.json'),JSON.stringify(data,null,2)+'\n');await fs.writeFile(path.join(root,'market-history.json'),JSON.stringify(history,null,2)+'\n');
 if(extra.sources.some(s=>s.status!=='collected'))process.exitCode=1;
}
