// 公开页面采集器：限量、串行访问，不登录、不绕过验证、不执行远端脚本。
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {taxonomy,formNames,classify,excludeProduct,normalizePrice,productCut} from './market-core.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const read=async(name,fallback)=>{try{return JSON.parse(await fs.readFile(path.join(root,name),'utf8'));}catch{return fallback;}};
export function text(html=''){return String(html).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,'').replace(/<[^>]+>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/\s+/g,' ').trim();}
export function listItems(html,category){
 return html.split(/<div\b[^>]*class="supply-item"[^>]*>/).slice(1).map(block=>{
  const id=block.match(/href="\/gongying\/(\d+)\//)?.[1];
  const title=text(block.match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/)?.[1]);
  return id&&title&&!excludeProduct(title)?{id,category,title,url:`https://www.cnhnb.com/gongying/${id}/`}:null;
 }).filter(Boolean);
}
export function parseProduct(html,url,category,checkedAt=new Date().toISOString()){
 const blocks=[...html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)];
 let p;for(const b of blocks){try{const v=JSON.parse(b[1]);if(v['@type']==='Product'){p=v;break;}}catch{}}
 if(!p?.name||excludeProduct(p.name))throw Error('非食材商品或没有有效商品结构');
 const main=html.split('window.__NUXT__=')[0],plain=text(main);
 if(/已下架|已失效|商品不存在|商品已删除|暂无现货/.test(plain))throw Error('商品下架或失效');
 let offer=Array.isArray(p.offers)?p.offers[0]:p.offers;if(!offer)throw Error('缺少报价');
 if(offer.availability&&/OutOfStock|Discontinued|SoldOut/.test(offer.availability))throw Error('商品无货');
 const price=Number(offer.price??offer.lowPrice);if(!Number.isFinite(price)||price<=0)throw Error('报价为空、面议或无效');
 const description=String(p.description||'');
 // 单位优先从主商品 SEO 描述提取，不从推荐商品中借用。
 const unit=description.match(/\d+(?:\.\d+)?\s*元\s*[/／]\s*(公斤|千克|斤|吨|箱|件|只|头|个|枚|托|袋)/)?.[1]||'';
 if(!unit)throw Error('无法确定报价单位');
 const attributes={};
 for(const m of main.matchAll(/class="detail-attrs-item"[^>]*>\s*<div\b[^>]*class="t1"[^>]*>([\s\S]*?)<\/div>\s*<div\b[^>]*class="t2"[^>]*>([\s\S]*?)<\/div>/g)){
  const key=text(m[1]);
  const value=text(m[2]);
  if(key&&value)attributes[key]=value;
 }
 const spec=Object.entries(attributes).filter(([k])=>!/电话|联系|微信/.test(k)).map(([k,v])=>`${k}：${v}`).join('；');
 const breedText=String(p.brand?.name||'')+' '+spec;
 const classification=classify(category,p.name,breedText);
 // 不把斤重范围、毛重或“十只一箱”擅自当成整箱净重。
 let packNetJin=null;
 for(const k of ['每箱净重','箱净重','单箱净重','每件净重']){const m=String(attributes[k]||'').match(/^(\d+(?:\.\d+)?)\s*(斤|公斤|千克|kg)$/i);if(m)packNetJin=Number(m[1])*(m[2]==='斤'?1:2);}
 const supplier=text(main.match(/class="shop-name[^\"]*"[^>]*>([\s\S]*?)<\//)?.[1])||description.match(/供应商家([^。]+)[。]?$/)?.[1]||'见原商品页';
 const moq=description.match(/[,，]\s*([^,，。]+起批)/)?.[1]||plain.match(/起批量\s+([^ ]+起批)/)?.[1]||'';
 const origin=offer.areaServed?.name||description.match(/从([^,，。]+)发出/)?.[1]||'';
 const pricePerJin=normalizePrice(price,unit,packNetJin);
 const cut=productCut(category,p.name);
 const id=url.match(/\/gongying\/(\d+)/)?.[1];
 return {id:`cnhnb-${id}`,sourceId:'cnhnb',sourceName:'惠农网',priceType:'供应商挂牌价',url,title:String(p.name),category,...classification,cut,price,unit,pricePerJin,packNetJin,spec,supplier,origin,moq,freight:'运费待确认',quoteDate:null,checkedAt,active:true,notes:['平台未明确报价日期','挂牌起报价，以具体规格与起订量为准',...(pricePerJin===null?['缺少明确净重或均重，暂不折算']:[])]};
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function get(url){
 await sleep(500);
 const r=await fetch(url,{signal:AbortSignal.timeout(20000),headers:{'User-Agent':'Mozilla/5.0 (compatible; FoodMarketReference/1.0; +https://gd008.bbroot.com/)'}});
 if(!r.ok)throw Error(`HTTP ${r.status}`);const s=await r.text();
 if(/_config_\s*=\s*\{[\s\S]{0,80}"action":\s*"login"|x5secdata|验证码验证|访问过于频繁/.test(s))throw Error('需要登录或访问验证');return s;
}
export async function collect(){
 const config=await read('market-sources.json',{}),old=await read('market.json',{records:[]}),now=new Date().toISOString();
 const diagnostics=[],discovered=new Map(),records=[],failedDetails=new Set(),seenDetails=new Set();
 for(const seed of config.seeds)discovered.set(seed.url,seed);
 // 发现失败不会清掉上次数据；不采集私人联系方式。
 for(const list of config.lists){try{const html=await get(list.url),items=listItems(html,list.category);if(!items.length)throw Error('没有可识别的公开食材条目');for(const item of items)if(!discovered.has(item.url))discovered.set(item.url,item);diagnostics.push({url:list.url,ok:true,count:items.length});console.log(`列表 ${list.category}: ${items.length} 条候选`);}catch(e){diagnostics.push({url:list.url,ok:false,error:e.message});console.log(`列表失败 ${list.url}: ${e.message}`);}}
 // 每个大类最多核查十二条，兼顾多种形态和品种；不对平台进行全站扫描。
 const chosen=[];
 for(const category of taxonomy){
  const candidates=[...discovered.values()].filter(x=>x.category===category.id),buckets=new Map();
  for(const x of candidates){const c=classify(x.category,x.title||'');const k=c.formIds.join(',')+':'+c.breedIds.join(',');if(!buckets.has(k))buckets.set(k,[]);buckets.get(k).push(x);}
  let count=0;while(count<12){let added=false;for(const bucket of buckets.values()){if(bucket.length&&count<12){chosen.push(bucket.shift());count++;added=true;}}if(!added)break;}
 }
 for(const item of chosen){seenDetails.add(item.url);try{const r=parseProduct(await get(item.url),item.url,item.category,new Date().toISOString());records.push(r);console.log(`商品成功 ${item.category}: ${r.title} ${r.price}元/${r.unit}`);}catch(e){failedDetails.add(item.url);diagnostics.push({url:item.url,ok:false,error:e.message});console.log(`商品跳过 ${item.url}: ${e.message}`);}}
 // 未抽样到的旧报价保留原核查时间；确认下架的条目不继续展示。
 const invalidUrls=new Set(diagnostics.filter(d=>/下架|失效|不存在|删除|无货/.test(d.error||'')).map(d=>d.url));
 const merged=new Map(records.map(r=>[r.id,r]));
 for(const r of old.records||[]){if(!merged.has(r.id)&&!excludeProduct(r.title)&&!invalidUrls.has(r.url)&&Date.now()-Date.parse(r.checkedAt)<30*86400000)merged.set(r.id,{...r,latestCheckFailed:failedDetails.has(r.url)||(!seenDetails.has(r.url)&&r.latestCheckFailed)||false});}
 const sources=[];
 for(const original of config.sources){const source={...original,checkedAt:new Date().toISOString()};
  if(source.id==='cnhnb'){source.status=records.length?'collected':'failed';source.recordCount=records.length;source.note=records.length?'已读取公开商品页的标题、挂牌起报价、单位、产地、起订量和部分规格；报价日期未公开，不代表成交价。':'本轮未取得商品报价；如有旧记录，仍保留原核查时间。';}
  else if(source.status==='unverified'){source.checkedAt=null;}
  else {try{const html=await get(source.probeUrl||source.url);source.status='entry';source.note=source.id==='1688'?'返回入口页面，尚未取得可解析的商品报价。':source.note;source.pageTitle=text(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]);}catch(e){source.status=/登录|验证/.test(e.message)?'login':'failed';source.error=e.cause?.code||e.message;}}
  delete source.probeUrl;sources.push(source);
 }
 const localDay=iso=>new Date(iso).toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});
 const history=await read('market-history.json',{version:1,observations:[]}),observations=history.observations.filter(x=>Date.now()-Date.parse(x.checkedAt)<90*86400000);
 for(const r of records){const obs={id:r.id,checkedAt:r.checkedAt,price:r.price,unit:r.unit,pricePerJin:r.pricePerJin,spec:r.spec};const index=observations.findIndex(x=>x.id===r.id&&localDay(x.checkedAt)===localDay(r.checkedAt));if(index>=0)observations[index]=obs;else observations.push(obs);}
 const output={version:1,title:'行情跳动',updated:new Date().toISOString(),taxonomy,formNames,sources,records:[...merged.values()],coverage:{scope:'公开列表首页的限量样本，并非全平台全部商品',discovered:discovered.size,attempted:chosen.length,collected:records.length},diagnostics};
 for(const [name,obj] of [['market.json',output],['market-history.json',{version:1,updated:now,observations}]]){const target=path.join(root,name),tmp=target+'.tmp';await fs.writeFile(tmp,JSON.stringify(obj,null,2)+'\n');await fs.rename(tmp,target);}
 console.log(`采集结束：本轮 ${records.length} 条，展示 ${merged.size} 条，候选 ${discovered.size} 条。`);
 if(!records.length)process.exitCode=1;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))collect().catch(e=>{console.error(e.message);process.exitCode=1;});
