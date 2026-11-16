'use strict';
(() => {
  let token = '', conversation = null, merchant = null;
  const $ = id => document.getElementById(id);
  const actions = {
    'merchant.profile.update':'Update business profile', 'catalogue.create':'Create products',
    'catalogue.read':'Read catalogue', 'content.caption':'Prepare caption drafts',
    'economics.expense.capture':'Capture expenses', 'economics.expense.read':'Read expenses',
    'economics.calculate':'Calculate supplied aggregates', 'sales.report.daily':'Prepare daily sales reports',
    'whatsapp.reply.send':'Send WhatsApp replies (requires server configuration)',
    'content.describe':'Prepare product descriptions'
  };
  const labels = {overview:'Overview',agent:'AI assistant',catalogue:'Catalogue',sales:'Sales & orders',expenses:'Expenses',plans:'Plans & budgets',media:'Documents & media',activity:'Activity',settings:'Workspace settings'};
  const node = (tag,text,cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  function notice(message,error=false){$('notice').hidden=false;$('notice').textContent=message;$('notice').classList.toggle('error',error);}
  async function api(path, options={}){
    if(!token)throw Error('Connect your workspace first.');
    const headers={Authorization:`Bearer ${token}`,...(options.headers||{})};
    if(options.body && typeof options.body!=='string' && !(options.body instanceof File)){options={...options,body:JSON.stringify(options.body)};headers['Content-Type']='application/json';}
    const r=await fetch(path,{...options,headers,cache:'no-store'});
    const data=await r.json();
    if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||'Request failed'));
    return data;
  }
  function localInputDate(d){const x=new Date(d.getTime()-d.getTimezoneOffset()*60000);return x.toISOString().slice(0,16);}
  function money(value,currency='NGN'){
    if(value===null||value===undefined)return 'Unknown';
    // Supported display scales are explicit; never guess for arbitrary currencies.
    if(!['NGN','USD','EUR','GBP','KES','GHS'].includes(currency))return `${value.toLocaleString()} minor units (${currency})`;
    return new Intl.NumberFormat('en-NG',{style:'currency',currency,maximumFractionDigits:2}).format(value/100);
  }
  function table(id,rows,empty='No records yet.'){
    const body=$(id);body.replaceChildren();
    if(!rows.length){const tr=node('tr'),td=node('td',empty,'empty-cell');td.colSpan=10;tr.append(td);body.append(tr);return;}
    rows.forEach(cells=>{const tr=node('tr');cells.forEach(value=>{const td=node('td');if(value instanceof Node)td.append(value);else td.textContent=value;tr.append(td);});body.append(tr);});
  }
  function view(name){document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==name);document.querySelectorAll('nav [data-view]').forEach(n=>n.classList.toggle('active',n.dataset.view===name));$('breadcrumb').textContent=labels[name]||name;}
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>view(b.dataset.view)));
  Object.entries(actions).forEach(([action,label])=>{const l=node('label',undefined,'check-label');const input=document.createElement('input');input.type='checkbox';input.value=action;l.append(input,document.createTextNode(label));$('action-checks').append(l);});
  $('report-day').value=new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Lagos',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  $('policy-expiry').value=localInputDate(new Date(Date.now()+7*86400000));
  $('expense-form').elements.occurred_at.value=localInputDate(new Date());
  const orderExample={source_system:'manual',source_id:'order-001',revision:1,occurred_at:new Date().toISOString(),currency:'NGN',verification_status:'merchant_reported',evidence_reference:'merchant-order-001',status:'open',payment_status:'pending',channel:'whatsapp',lines:[{sku:'YOUR-SKU',title:'Your product',quantity:1,unit_price_minor:450000,cogs_minor:null}],discounts_minor:0,refunds_minor:0,cash_collected_minor:null};
  $('order-json').value=JSON.stringify(orderExample,null,2);
  async function refresh(){
    if(!token)return;
    merchant=await api('/v1/me');
    $('business-name').textContent=merchant.name;$('connection-label').textContent=merchant.role+' access';
    $('connection-pill').textContent='● Connected';$('connection-pill').classList.add('connected');$('connect-panel').hidden=true;
    $('product-count').textContent=merchant.products.length+' records';
    table('catalogue-table',merchant.products.map(p=>[p.title,p.sku,money(p.price_minor,p.currency)]));
    if(merchant.policy){$('automation-enabled').checked=merchant.policy.enabled;document.querySelectorAll('#action-checks input').forEach(c=>c.checked=merchant.policy.actions.includes(c.value));$('policy-expiry').value=localInputDate(new Date(merchant.policy.expires_at));}
    if(merchant.profile){const f=$('profile-form');['business_name','sector','currency','timezone'].forEach(k=>f.elements[k].value=merchant.profile[k]);['catalogue','content','economics'].forEach(k=>f.elements[k].checked=merchant.profile.capabilities.includes(k));}
    const jobs=[loadReport(),loadOrders(),loadExpenses(),loadPlans(),loadMedia(),loadActivity(),loadProviders()];
    const results=await Promise.allSettled(jobs);const failed=results.filter(r=>r.status==='rejected');
    if(failed.length)notice(failed.map(r=>r.reason.message).join(' · '),true);
  }
  async function loadReport(){
    const currency=$('report-currency').value.toUpperCase();
    let report;
    try{report=await api(`/v1/reports/daily?day=${encodeURIComponent($('report-day').value)}&currency=${encodeURIComponent(currency)}`);}catch(e){['kpi-sales','kpi-orders','kpi-profit','kpi-operating'].forEach(k=>$(k).textContent='—');$('quality-summary').textContent=e.message;$('quality-tags').replaceChildren();$('sales-bars').replaceChildren(node('p','Report unavailable.','muted'));table('top-products',[]);return;}
    $('kpi-sales').textContent=money(report.net_sales_minor,currency);$('kpi-orders').textContent=report.orders;
    $('kpi-profit').textContent=money(report.gross_profit_minor,currency);$('kpi-operating').textContent=money(report.operating_profit_minor,currency);
    $('kpi-orders-note').textContent=`${report.pending_payment_orders} pending payment · ${report.cancelled_orders} cancelled`;
    $('quality-summary').textContent=report.missing.length?'Some records are incomplete. Missing costs and cash receipts stay unknown. This report covers recorded data only.':'Required figures are present for these records. Source totals still require independent reconciliation.';
    $('quality-tags').replaceChildren(...report.missing.map(x=>node('span',x.replaceAll('_',' '))));
    table('top-products',report.top_products.map(p=>[p.sku,p.units_ordered,money(p.gross_minor,currency)]));
    const chart=$('sales-bars');chart.replaceChildren();
    const series=[['Net sales',report.net_sales_minor,'#6b5bdd'],['Refunds',report.refunds_minor,'#61baa6'],['Expenses',report.reported_expenses_minor,'#c7cbd8']];
    const maximum=Math.max(1,...series.map(x=>x[1]||0));
    series.forEach(([label,value,color])=>{const row=node('div',undefined,'chart-row'),track=node('div',undefined,'chart-track'),fill=node('div',undefined,'chart-fill');fill.style.width=value===null?'0%':`${Math.max(0,value)/maximum*100}%`;fill.style.backgroundColor=color;track.append(fill);row.append(node('span',label),track,node('span',money(value,currency),'chart-value'));chart.append(row);});
  }
  async function loadOrders(){const data=await api('/v1/orders');table('orders-table',data.map(r=>[`${r.source_system} / ${r.source_id} · v${r.revision}`,r.channel,`${r.status} · ${r.payment_status}`,r.currency]));}
  async function loadExpenses(){const data=await api('/v1/financial-records');table('expenses-table',data.map(r=>[r.source_id,r.category,money(r.amount_minor,r.currency),r.verification_status]));}
  async function loadMedia(){const data=await api('/v1/media');table('media-table',data.map(r=>[r.id.slice(0,8),r.mime_type,r.byte_length,r.state]));}
  async function loadProviders(){const data=await api('/v1/integrations');const root=$('integrations-list');root.replaceChildren();data.forEach(p=>{const r=node('div',undefined,'record');r.append(node('strong',p.id),node('small',p.state.replaceAll('_',' ')));root.append(r);});}
  async function loadPlans(){const data=await api('/v1/plans');const root=$('plans-list');root.replaceChildren();if(!data.length)root.append(node('p','No plans yet. Start with a draft.','muted'));data.forEach(p=>{const card=node('article',undefined,'plan-card');card.append(node('h3',p.plan.title),node('p',`${p.plan.starts_on} → ${p.plan.ends_on} · ${p.state}`),node('p',`Revenue target ${money(p.plan.revenue_target_minor,p.plan.currency)} · Expense budget ${money(p.plan.expense_budget_minor,p.plan.currency)}`),node('p',p.plan.assumptions));if(p.state==='draft'){const b=node('button','Approve this exact plan','quiet-button');b.addEventListener('click',()=>run(async()=>{await api(`/v1/plans/${p.id}/approve`,{method:'POST',body:{payload_hash:p.payload_hash}});await loadPlans();notice('Plan approved. No spending has been committed.');}));card.append(b);}root.append(card);});}
  async function loadActivity(){const [runs,audit,issues]=await Promise.all([api('/v1/agent/runs'),api('/v1/audit'),api('/v1/data-quality')]);const root=$('runs-list');root.replaceChildren();if(!runs.length)root.append(node('p','Agent runs will appear here.','muted'));runs.slice(0,30).forEach(r=>{const item=node('div',undefined,'record'),text=node('div');text.append(node('strong',r.tool||'Planning'),node('small',r.result?.message||r.id));item.append(text,node('span',r.state,'pill'));if(r.state==='planning'){const b=node('button','Cancel abandoned run','quiet-button');b.addEventListener('click',()=>run(async()=>{await api(`/v1/agent/runs/${r.id}/cancel`,{method:'POST'});await loadActivity();}));item.append(b);}root.append(item);});table('audit-table',audit.slice().reverse().map(r=>[r.event,r.object_id,new Date(r.occurred_at).toLocaleString()]));const q=$('issues-list');q.replaceChildren(...(issues.length?issues.map(i=>node('p',i.details,'muted')):[node('p','No source conflicts recorded.','muted')]));}
  async function run(fn){try{await fn();}catch(e){notice(e.message,true);}}
  async function sendAgent(message){
    if(!conversation)conversation=(await api('/v1/conversations',{method:'POST'})).id;
    const log=$('chat-log');if(log.querySelector('.chat-welcome'))log.replaceChildren();log.append(node('div',message,'chat-message'));
    const result=await api(`/v1/conversations/${conversation}/messages`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:{message}});
    const bubble=node('div',result.result?.message||'Planning in progress. Inspect Activity for the result.','chat-message assistant');
    if(result.result?.caption)bubble.append(node('p',result.result.caption));
    if(result.result?.products)bubble.append(node('p',result.result.products.map(p=>`${p.title} · ${p.sku}`).join('\n')||'No products yet.'));
    if(result.result?.report){const pre=node('pre',JSON.stringify(result.result.report,null,2));bubble.append(pre);}
    bubble.append(node('small',`${result.state} · ${result.tool||'planner'}`));log.append(bubble);bubble.scrollIntoView({block:'nearest',behavior:'smooth'});return result;
  }
  function form(id,handler){$(id).addEventListener('submit',e=>{e.preventDefault();const button=e.submitter;if(button)button.disabled=true;run(()=>handler(new FormData(e.currentTarget))).finally(()=>{if(button)button.disabled=false;});});}
  form('connect-form',async()=>{token=$('access-key').value.trim();$('access-key').value='';try{await refresh();notice('Workspace connected.');}catch(e){token='';throw e;}});
  $('disconnect').addEventListener('click',()=>{token='';conversation=null;merchant=null;location.reload();});
  $('refresh').addEventListener('click',()=>run(refresh));['report-day','report-currency'].forEach(id=>$(id).addEventListener('change',()=>run(loadReport)));
  form('product-form',async f=>{await api('/v1/products',{method:'POST',body:{title:f.get('title'),sku:f.get('sku'),price_minor:Number(f.get('price_minor')),currency:f.get('currency')}});await refresh();notice('Product created.');$('product-form').reset();});
  form('order-form',async()=>{await api('/v1/orders/ingest',{method:'POST',body:JSON.parse($('order-json').value)});await refresh();notice('Source order snapshot imported.');});
  form('expense-form',async f=>{const source=f.get('source_id');await api('/v1/financial-records',{method:'POST',body:{source_system:'manual',source_id:source,revision:1,occurred_at:new Date(f.get('occurred_at')).toISOString(),currency:f.get('currency'),verification_status:'merchant_reported',evidence_reference:source,category:f.get('category'),amount_minor:Number(f.get('amount_minor')),note:f.get('note')}});await refresh();notice('Merchant-reported expense saved.');});
  $('save-coverage').addEventListener('click',()=>run(async()=>{await api('/v1/reports/expense-coverage',{method:'PUT',body:{day:$('report-day').value,currency:$('report-currency').value.toUpperCase(),complete:$('coverage-complete').checked}});await loadReport();notice('Expense coverage declaration saved.');}));
  form('plan-form',async f=>{await api('/v1/plans',{method:'POST',body:{title:f.get('title'),currency:f.get('currency'),starts_on:f.get('starts_on'),ends_on:f.get('ends_on'),revenue_target_minor:Number(f.get('revenue_target_minor')),expense_budget_minor:Number(f.get('expense_budget_minor')),assumptions:f.get('assumptions')}});await loadPlans();notice('Plan saved as a draft.');});
  form('media-form',async()=>{const file=$('media-file').files[0];if(!file)throw Error('Choose a file.');await api('/v1/media',{method:'POST',headers:{'Content-Type':file.type},body:file});await loadMedia();notice('File stored in quarantine. No extraction was performed.');});
  form('policy-form',async()=>{const selected=[...document.querySelectorAll('#action-checks input:checked')].map(x=>x.value);await api('/v1/policy',{method:'PUT',body:{enabled:$('automation-enabled').checked,actions:selected,expires_at:new Date($('policy-expiry').value).toISOString()}});notice('Autonomy permissions saved.');await refresh();});
  form('profile-form',async f=>{const data={business_name:f.get('business_name'),sector:f.get('sector'),currency:f.get('currency'),timezone:f.get('timezone'),capabilities:['catalogue','content','economics'].filter(k=>f.has(k))};const result=await sendAgent('/profile '+JSON.stringify(data));await refresh();notice(result.result?.message||result.state,result.state!=='completed');});
  form('chat-form',async()=>{const text=$('chat-input').value.trim();if(!text)return;$('chat-input').value='';await sendAgent(text);await refresh();});
  $('new-conversation').addEventListener('click',()=>run(async()=>{conversation=(await api('/v1/conversations',{method:'POST'})).id;$('chat-log').replaceChildren(node('div','A new conversation is ready.','chat-message assistant'));}));
  document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>{$('chat-input').value=b.dataset.prompt;$('chat-input').focus();}));
  $('sales-prompt').addEventListener('click',()=>{$('chat-input').value='/sales '+JSON.stringify({day:$('report-day').value,currency:$('report-currency').value});$('chat-input').focus();});
})();
