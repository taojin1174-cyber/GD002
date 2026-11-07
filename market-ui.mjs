// 页面只读取本站生成的数据文件，第三方平台仅在点击原文时打开。
import {taxonomy,formNames,safeUrl,stale,selectRecords} from './market-core.mjs';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const decimal=n=>Number(n).toFixed(2),option=(v,t,selected=false)=>`<option value="${esc(v)}"${selected?' selected':''}>${esc(t)}</option>`;
const date=s=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未公开';
let data={records:[],sources:[]},page=1,tableView=false,historyData=null;
const size=24;
function filters(){return Object.fromEntries(['category','form','breed','source','region','cut','q'].map(k=>[k,$(k).value]).concat([['pricedOnly',$('pricedOnly').checked]]));}
function updateCascade(){
 const cat=taxonomy.find(c=>c.id===$('category').value),form=$('form').value,breed=$('breed').value;
 $('form').innerHTML=option('','全部状态')+(cat?.forms||Object.keys(formNames)).map(f=>option(f,f==='live'?(cat?.id==='pig'?'生猪':'活禽'):formNames[f],f===form)).join('');
 const base=data.records.filter(r=>(!cat||r.category===cat.id)&&(!$('form').value||r.formIds.includes($('form').value)));
 $('breed').innerHTML=option('','全部品种')+(cat?.breeds||[]).map(b=>option(b[0],`${b[1]}（${base.filter(r=>r.breedIds.includes(b[0])).length}）`,b[0]===breed)).join('');
 $('breed').disabled=!cat;
}
function formTags(r){return r.formIds.map(f=>`<span class="badge ${f==='unknown'?'orange':'green'}">${esc(formNames[f]||f)}</span>`).join('');}
function price(r){return `<span>${decimal(r.price)}</span><small> 元/${esc(r.unit)} 起</small>`;}
function converted(r){return r.pricePerJin===null?'暂无法折算 · 请核实净重／均重':`≈ ${decimal(r.pricePerJin)} 元/斤 · 未计运费`;}
function card(r){
 const old=stale(r);
 return `<article class="panel product${old?' old':''}"><div class="product-body"><div class="chips"><span class="badge">${esc(r.sourceName)} · 挂牌价</span>${formTags(r)}${old?'<span class="badge orange">核查已超7天</span>':''}${r.latestCheckFailed?'<span class="badge orange">本次核查失败</span>':''}</div><h3><a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a></h3><div class="price">${price(r)}</div><div class="converted">${converted(r)}</div><dl class="details"><dt>发货地</dt><dd>${esc(r.origin||'未注明')}</dd><dt>供应商</dt><dd>${esc(r.supplier)}</dd><dt>起订量</dt><dd>${esc(r.moq||'见原商品页')}</dd><dt>报价日期</dt><dd>${r.quoteDate?esc(r.quoteDate):'平台未公开'}</dd><dt>核查时间</dt><dd>${esc(date(r.checkedAt))}</dd></dl>${r.spec?`<p class="spec">${esc(r.spec)}</p>`:''}</div><div class="product-bottom"><button data-history="${esc(r.id)}">价格观察记录</button><a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">查看原商品 ↗</a></div></article>`;
}
function table(records){return `<div class="scroll" style="grid-column:1/-1"><table><thead><tr>${['商品／品种','状态','挂牌起报价','折合元/斤','来源／供应商','发货地','起订量','报价日期／核查时间','详情'].map(t=>`<th>${t}</th>`).join('')}</tr></thead><tbody>${records.map(r=>`<tr class="${stale(r)?'old':''}"><td>${esc(r.title)}${r.spec?`<p class="hint">${esc(r.spec)}</p>`:''}</td><td>${formTags(r)}${stale(r)?'<br>核查已超7天':''}</td><td>${decimal(r.price)} 元/${esc(r.unit)} 起</td><td>${r.pricePerJin===null?'缺少明确换算条件':decimal(r.pricePerJin)+'（未计运费）'}</td><td>${esc(r.sourceName)}<br>${esc(r.supplier)}</td><td>${esc(r.origin)}</td><td>${esc(r.moq||'见原页')}</td><td>报价：${esc(r.quoteDate||'未公开')}<br>核查：${esc(date(r.checkedAt))}</td><td><a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">原商品 ↗</a><br><button data-history="${esc(r.id)}">历史</button></td></tr>`).join('')}</tbody></table></div>`;}
function render(){
 const f=filters(),records=selectRecords(data.records,f),sort=$('sort').value;
 records.sort((a,b)=>sort==='checked'?Date.parse(b.checkedAt)-Date.parse(a.checkedAt):a.pricePerJin===null?(b.pricePerJin===null?0:1):b.pricePerJin===null?-1:(a.pricePerJin-b.pricePerJin)*(sort==='high'?-1:1));
 const cat=taxonomy.find(c=>c.id===f.category),totalPages=Math.max(1,Math.ceil(records.length/size));page=Math.min(page,totalPages);
 const shown=records.slice((page-1)*size,page*size);
 $('resultTitle').textContent=`${cat?.name||'全部'} · ${records.length} 条货源`;
 $('resultHint').textContent=sort==='checked'?'鲜冻状态及品种按商品公开文字识别，未注明的保留“待核实”；挂牌起报价需回原页确认具体规格。':'按挂牌起报价折算排序；不同品种、部位、起订量和运费条件不构成同口径最低价比较。';
 $('results').innerHTML=shown.length?(tableView?table(shown):shown.map(card).join('')):`<div class="panel empty"><b>当前条件还没有已采集的商品样本</b>可放宽鲜冻状态或品种筛选，也可以从下方平台入口继续查找。<br>未取得的数据不会用示例价格替代。</div>`;
 $('pagination').innerHTML=records.length?`<button id="prev" ${page===1?'disabled':''}>上一页</button><span>${page} / ${totalPages} 页 · 共 ${records.length} 条</span><button id="next" ${page===totalPages?'disabled':''}>下一页</button>`:'';
 if($('prev'))$('prev').onclick=()=>{page--;render();};if($('next'))$('next').onclick=()=>{page++;render();};
 document.querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>showHistory(b.dataset.history));
 document.querySelectorAll('[data-category]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.category===f.category)));
 // 仅把筛选条件写入网址，便于保存或分享具体品种入口。
 const params=new URLSearchParams();for(const [k,v] of Object.entries(f)){if(v)params.set(k,v===true?'1':v);}if(sort!=='checked')params.set('sort',sort);
 try{history.replaceState(null,'',location.pathname+(params.size?'?'+params:''));}catch{}
}
function renderSources(){
 const labels={collected:'已采集报价',login:'需要登录／验证',entry:'仅查价入口',failed:'本次未接通',pending:'待核查',unverified:'待验证入口'};
 $('sources').innerHTML=data.sources.map(s=>`<article class="panel source"><h3>${esc(s.name)}</h3><div class="chips" style="margin-top:8px"><span class="badge ${s.status==='collected'?'green':'orange'}">${esc(labels[s.status]||'待核查')}</span><span class="badge">${esc(s.kind)}</span></div><p>${esc(s.note)}${s.error?`（${esc(s.error)}）`:''}</p><time>${s.checkedAt?'核查：'+esc(date(s.checkedAt)):'尚未取得可验证的公开价目'}</time><a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${s.id==='kuailehou'?'美团官网':'前往平台'} ↗</a></article>`).join('');
}
async function showHistory(id){
 const record=data.records.find(r=>r.id===id);$('historyTitle').textContent=record.title+' · 价格观察记录';$('historyBody').textContent='正在读取…';$('history').showModal();
 try{if(!historyData){const res=await fetch('market-history.json',{cache:'no-cache'});if(!res.ok)throw Error();historyData=await res.json();}const rows=historyData.observations.filter(r=>r.id===id).sort((a,b)=>Date.parse(b.checkedAt)-Date.parse(a.checkedAt));$('historyBody').innerHTML=rows.length?`<div class="scroll"><table><thead><tr><th>核查时间</th><th>挂牌起报价</th><th>折合元/斤</th><th>规格</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(date(r.checkedAt))}</td><td>${decimal(r.price)} 元/${esc(r.unit)}</td><td>${r.pricePerJin===null?'—':decimal(r.pricePerJin)}</td><td>${esc(r.spec||'未注明')}</td></tr>`).join('')}</tbody></table></div>`:'尚无历史观察记录。后续成功采集会逐步积累。';}catch{$('historyBody').textContent='暂时无法读取历史数据，请稍后重试。';}
}
$('closeHistory').onclick=()=>$('history').close();
$('theme').onclick=()=>{const dark=document.documentElement.dataset.theme?document.documentElement.dataset.theme==='dark':matchMedia('(prefers-color-scheme:dark)').matches;const theme=dark?'light':'dark';document.documentElement.dataset.theme=theme;try{localStorage.setItem('theme',theme);}catch{}};
$('category').innerHTML=option('','全部大类')+taxonomy.map(c=>option(c.id,c.name)).join('');
updateCascade();
for(const k of ['category','form','breed','source','region','cut','pricedOnly','sort'])$(k).onchange=()=>{page=1;if(k==='category'){$('form').value='';$('breed').value='';$('cut').value='';}if(k==='category'||k==='form')updateCascade();render();};
$('q').oninput=()=>{page=1;render();};
$('view').onclick=()=>{tableView=!tableView;$('view').textContent=tableView?'卡片视图':'表格视图';$('view').setAttribute('aria-pressed',String(tableView));render();};
$('reset').onclick=()=>{for(const k of ['category','form','breed','source','region','cut','q'])$(k).value='';$('pricedOnly').checked=false;$('sort').value='checked';page=1;updateCascade();render();};
try{
 const res=await fetch('market.json',{cache:'no-cache'});if(!res.ok)throw Error(`HTTP ${res.status}`);data=await res.json();if(!Array.isArray(data.records)||!Array.isArray(data.sources))throw Error('数据结构无效');
 $('updated').textContent=date(data.updated);$('statRecords').textContent=data.records.length;$('statSources').textContent=data.sources.filter(s=>s.status==='collected').length;
 $('categories').innerHTML=taxonomy.map(c=>`<button class="category" data-category="${c.id}" aria-pressed="false"><span class="icon" aria-hidden="true">${c.icon}</span><span class="label">${c.name}</span><small>${data.records.filter(r=>r.category===c.id).length} 条货源</small></button>`).join('');
 document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{$('category').value=b.dataset.category;$('form').value='';$('breed').value='';$('cut').value='';page=1;updateCascade();render();});
 $('source').innerHTML=option('','全部平台')+data.sources.map(s=>option(s.id,s.name+(s.status==='collected'?'':'（暂无报价）'))).join('');
 const regions=[...new Set(data.records.map(r=>r.origin.match(/^(.+?[省市区])/u)?.[1]||r.origin).filter(Boolean))].sort();$('region').innerHTML=option('','全国')+regions.map(r=>option(r,r)).join('');
 const params=new URLSearchParams(location.search);for(const k of ['category','source','region','cut','q'])if(params.has(k))$(k).value=params.get(k);updateCascade();if(params.has('form'))$('form').value=params.get('form');updateCascade();if(params.has('breed'))$('breed').value=params.get('breed');$('pricedOnly').checked=params.get('pricedOnly')==='1';if(params.has('sort'))$('sort').value=params.get('sort');
 renderSources();render();
}catch(e){$('updated').textContent='数据加载失败';$('resultHint').textContent='请确认网络连接后刷新页面。';$('results').innerHTML='<div class="panel empty"><b>暂时无法读取行情数据</b>请稍后刷新重试。已有的本机数据不受影响。</div>';console.error('行情数据加载失败',e);}
