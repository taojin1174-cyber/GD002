// 行情分类与价格计算。这里只处理公开商品字段，不采集私人联系方式。
export const taxonomy = [
 {id:'pig',name:'猪',icon:'🐖',forms:['fresh','frozen','live','unknown'],breeds:[['black','黑猪',['黑猪','黑毛猪','黑土猪']],['white','白猪',['白猪','大白猪','长白猪']],['local','土猪／土杂猪',['土猪','土杂猪']],['xiang','香猪',['香猪']],['other','其他／未注明',[]]]},
 {id:'chicken',name:'鸡',icon:'🐔',forms:['fresh','frozen','live','unknown'],breeds:[['qingyuan','清远鸡',['清远鸡','清远麻鸡','清远肉鸡']],['ma','麻鸡',['麻鸡','黄麻鸡']],['sanhuang','三黄鸡',['三黄鸡','三黄肉鸡']],['local','土鸡／走地鸡',['土鸡','走地鸡','跑山鸡']],['black','乌鸡',['乌鸡','乌骨鸡']],['white','白羽肉鸡',['白羽鸡','白羽肉鸡']],['wenchang','文昌鸡',['文昌鸡']],['old','老母鸡／淘汰鸡',['老母鸡','淘汰鸡','老鸡']],['other','其他／未注明',[]]]},
 {id:'duck',name:'鸭',icon:'🦆',forms:['fresh','frozen','live','unknown'],breeds:[['qingtou','青头鸭',['青头鸭','青头麻鸭']],['ma','麻鸭',['麻鸭','草鸭']],['fan','番鸭',['番鸭','正番鸭','红脸鸭','瘤头鸭']],['half','半番鸭',['半番鸭','半翻鸭']],['cherry','樱桃谷鸭／白鸭',['樱桃谷鸭','白鸭']],['local','土鸭',['土鸭']],['old','老鸭',['老鸭','老种鸭']],['other','其他／未注明',[]]]},
 {id:'goose',name:'鹅',icon:'🪿',forms:['fresh','frozen','live','unknown'],breeds:[['shitou','狮头鹅',['狮头鹅']],['magang','马岗鹅',['马岗鹅']],['black','黑棕鹅／清远鹅',['黑棕鹅','黑鬃鹅','清远鹅']],['wanxi','皖西白鹅',['皖西白鹅']],['zhedong','浙东白鹅',['浙东白鹅']],['sanhua','三花鹅',['三花鹅']],['white','白鹅',['白鹅']],['grey','灰鹅',['灰鹅']],['other','其他／未注明',[]]]},
 {id:'egg',name:'鸡蛋',icon:'🥚',forms:['ambient','chilled','unknown'],breeds:[['white','白壳蛋',['白壳蛋','白鸡蛋']],['pink','粉壳蛋',['粉壳蛋','粉蛋']],['red','红壳蛋',['红壳蛋','红皮蛋','褐壳蛋']],['local','土鸡蛋',['土鸡蛋','柴鸡蛋','农家蛋']],['black','乌鸡蛋',['乌鸡蛋']],['green','绿壳蛋',['绿壳蛋']],['selenium','富硒蛋',['富硒蛋','富硒鸡蛋']],['ordinary','普通鸡蛋',['普通鸡蛋','洋鸡蛋']],['other','其他／未注明',[]]]},
];
export const formNames={fresh:'鲜品／冰鲜',frozen:'冻品',live:'活禽／生猪',ambient:'常温蛋',chilled:'冷藏蛋',unknown:'状态待核实'};
export function classify(category,title,attributes='') {
 const t=String(title||'')+' '+String(attributes||''), cat=taxonomy.find(c=>c.id===category);
 const breeds=cat.breeds.filter(b=>b[2].some(a=>t.includes(a))).map(b=>b[0]);
 const forms=[];
 if(category==='egg') {if(/冷藏|冷鲜/.test(t))forms.push('chilled');if(/常温/.test(t))forms.push('ambient');}
 else {if(/冷冻|冰冻|急冻|冻品|冻肉|冻鸡|冻鸭|冻鹅|冻猪|冻乳猪|速冻/.test(t))forms.push('frozen');if(/冰鲜|冷鲜|热鲜|鲜品|新鲜|现宰|现杀|鲜肉|鲜鸡|鲜鸭|鲜鹅|鲜猪/.test(t))forms.push('fresh');if(/活禽|活鸡|活鸭|活鹅|活体|活运|生猪|毛鸡|毛鸭|毛鹅/.test(t))forms.push('live');}
 // 明确的保存状态优先于标题中的营销用语；同一字段仍冲突则待核实。
 const declared=[...String(attributes).matchAll(/(?:保存状态|货品类别|储存方式|保存方式)[:：]([^；;]+)/g)].map(m=>m[1]).join(' ');
 if(declared){const frozen=/冷冻|冰冻|冻肉|急冻|速冻/.test(declared),fresh=/冰鲜|冷鲜|热鲜|鲜肉/.test(declared);if(frozen&&!fresh)return {breedIds:breeds.length?breeds:['other'],formIds:['frozen']};if(fresh&&!frozen)return {breedIds:breeds.length?breeds:['other'],formIds:['fresh']};}
 if(forms.length>1)return {breedIds:breeds.length?breeds:['other'],formIds:['unknown']};
 return {breedIds:breeds.length?breeds:['other'],formIds:forms.length?forms:['unknown']};
}
export function excludeProduct(title,spec=''){return /鸡苗|鸭苗|鹅苗|猪苗|仔猪|猪仔|种猪|种公猪|种母猪|育种|种蛋|受精蛋|孵化|宠物|观赏|野生|活苗|一斤苗|二斤苗|脱温|小苗|带窝|奶水分泌|产仔多|熟食|全熟|即食|酱香|烤乳猪|脆皮乳猪|腊肉|卤味|盐焗|香肠/.test(title)||/脱温|用途[:：]\s*(?:作种|育种|繁殖)|鹅分类[:：]\s*种鹅/.test(spec);}
export function productCut(category,title){if(category==='egg')return 'egg';return /鸡翅|鸭翅|鹅翅|鸡腿|鸭腿|鹅腿|鸡边腿|鸡上腿|鸡胸|小胸|大胸|鸭胸|鹅胸|鸡爪|鸭掌|鹅掌|鸡脖|鸭脖|鹅脖|鸡肝|鸭肝|鹅肝|鸡肠|鸭肠|鹅肠|鸡胗|鸭胗|鹅胗|鸡肾|鸭肾|鹅肾|鸡心|鸭心|鹅心|鸭舌|鸡头|鸭头|鹅头|猪头|猪骨|猪肚|猪蹄|排骨|五花|里脊|瘦肉|肥肉|板油|猪皮|分割|副产品|半片|二分体|切块/.test(title)?'cut':'whole';}
export function normalizePrice(price,unit,packNetJin=null,avgWeightJin=null){
 if(!Number.isFinite(Number(price))||Number(price)<=0)return null;
 const p=Number(price);if(unit==='斤')return p;if(['公斤','千克','kg'].includes(unit))return p/2;if(unit==='吨')return p/2000;
 if(['箱','件'].includes(unit)&&Number(packNetJin)>0)return p/Number(packNetJin);
 if(['只','头'].includes(unit)&&Number(avgWeightJin)>0)return p/Number(avgWeightJin);
 return null;
}
export function safeUrl(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}}
export function stale(record,now=Date.now()){return !record.checkedAt||now-Date.parse(record.checkedAt)>7*86400000;}
export function selectRecords(records,filters={}){
 const q=(filters.q||'').trim().toLowerCase();
 return records.filter(r=>(!filters.kind||(r.recordKind||'offer')===filters.kind)&&(!filters.category||r.category===filters.category)&&(!filters.form||r.formIds.includes(filters.form))&&(!filters.breed||r.breedIds.includes(filters.breed))&&(!filters.source||r.sourceId===filters.source)&&(!filters.region||String(r.origin).includes(filters.region))&&(!filters.cut||r.cut===filters.cut)&&(!filters.pricedOnly||r.pricePerJin!==null)&&(!q||[r.title,r.supplier,r.origin,r.spec,r.sourceName].join(' ').toLowerCase().includes(q)));
}
