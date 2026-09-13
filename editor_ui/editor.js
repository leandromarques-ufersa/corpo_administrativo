'use strict';
const $ = s => document.querySelector(s);
let state, tab = 'people', dirty = false, editing = null, busy = false;
const labels = {people:'servidor', units:'unidade', sectors:'setor'};
function message(text, error=false){$('#message').textContent=text;$('#message').classList.toggle('error',error);}
function mark(){dirty=true;$('#save-status').textContent='Alterações pendentes. Clique em Salvar na planilha.';}
async function api(path, data){
  const response=await fetch('/api/'+path, data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state?.csrf||''},body:JSON.stringify(data)});
  const result=await response.json();
  if(!response.ok) throw new Error(result.error||'Falha na operação.');
  return result;
}
async function start(){state=await api('state');$('#login').hidden=true;$('#workspace').hidden=false;render();}
$('#login-form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button');button.disabled=true;try{await api('login',Object.fromEntries(new FormData(form)));form.reset();await start();message('');}catch(e){message(e.message,true);}finally{button.disabled=false;}};
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{tab=button.dataset.tab;$('#search').value='';document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
$('#search').oninput=render;
function render(){
  $('#add').textContent=tab==='units'?'Nova unidade':tab==='sectors'?'Novo setor':'Novo servidor';
  const list=$('#list');list.replaceChildren();const query=$('#search').value.toLocaleLowerCase();
  state[tab].forEach((item,index)=>{
    const title=tab==='people'?item.Nome:item.name;
    const subtitle=tab==='people'?`${item.Setor} · ${item.Unidade} · SIAPE: ${item.Siape||'Indisponível'}`:tab==='units'?item.sector:`Endereço: ${item.slug}`;
    if(!(title+' '+subtitle).toLocaleLowerCase().includes(query))return;
    const row=document.createElement('div');row.className='record';const text=document.createElement('div');const strong=document.createElement('strong');strong.textContent=title;const p=document.createElement('p');p.textContent=subtitle;text.append(strong,p);const actions=document.createElement('div');actions.className='actions';
    for(const [name,action,cls] of [['Editar',()=>open(index),'secondary'],['Excluir',()=>remove(index),'danger']]){const button=document.createElement('button');button.textContent=name;button.className=cls;button.onclick=action;actions.append(button);}row.append(text,actions);list.append(row);
  });
  if(!list.children.length){const p=document.createElement('p');p.className='empty';p.textContent='Nenhum registro encontrado.';list.append(p);}
}
function field(name,label,value='',options=null,type='text',required=true){
  const wrapper=document.createElement('label');wrapper.textContent=label;const input=document.createElement(options?'select':'input');input.name=name;input.required=required;
  if(options){for(const option of options){const node=document.createElement('option');node.value=typeof option==='string'?option:option.value;node.textContent=typeof option==='string'?option:option.label;input.append(node);}}
  else{input.type=type;input.maxLength=500;}input.value=value;wrapper.append(input);$('#fields').append(wrapper);return input;
}
function open(index=null){
  if(busy)return;
  editing=index;const item=index===null?{}:state[tab][index];$('#fields').replaceChildren();$('#dialog-title').textContent=(index===null?'Criar ':'Editar ')+labels[tab];
  if(tab==='sectors'){
    field('page','Página oficial',item.page||'',null,'url',false);
    field('name','Nome',item.name);field('short','Nome no menu',item.short);const slug=field('slug','Endereço (letras minúsculas e hífens)',item.slug);slug.pattern='[a-z][a-z0-9-]{0,79}';field('color','Cor principal',item.color||'#1943c9',null,'color');field('pale','Cor de fundo',item.pale||'#edf2ff',null,'color');
  }else if(tab==='units'){
    if(!state.sectors.length){message('Crie um setor antes de cadastrar unidades.',true);return;}field('name','Nome da unidade',item.name);field('sector','Setor',item.sector||state.sectors[0].name,state.sectors.map(s=>s.name));
  }else{
    if(!state.units.length){message('Crie um setor e uma unidade antes de cadastrar servidores.',true);return;}
    field('Nome','Nome',item.Nome);field('Siape','Matrícula SIAPE',item.Siape,null,'text',false);field('Cargo','Cargo',item.Cargo,null,'text',false);
    field('Formação','Formação',item['Formação']||'',null,'text',false);
    field('Email','E-mail',item.Email||'',null,'email',false);
    const sector=field('Setor','Setor',item.Setor||state.units[0].sector,state.sectors.map(s=>s.name));
    const unit=field('Unidade','Unidade','',[]);function updateUnits(){unit.replaceChildren();state.units.filter(u=>u.sector===sector.value).forEach(u=>{const option=document.createElement('option');option.value=u.name;option.textContent=u.name;unit.append(option);});}sector.onchange=updateUnits;updateUnits();if(item.Unidade)unit.value=item.Unidade;
    const birthday=field('Nascimento','Aniversário (dia-mês)',item.Nascimento,null,'text',false);birthday.placeholder='25-12';birthday.pattern='[0-9]{2}-[0-9]{2}';field('Ramal','Ramal',item.Ramal,null,'text',false);field('WhatsApp','WhatsApp com DDD',item.WhatsApp,null,'text',false);field('Foto','Foto da pasta photos',item.Foto||'',[{value:'',label:'Sem foto'},...state.photos], 'text',false);
  }$('#dialog').showModal();
}
$('#add').onclick=()=>open();$('#cancel').onclick=()=>$('#dialog').close();
$('#record-form').onsubmit=event=>{
  event.preventDefault();const item=Object.fromEntries(new FormData(event.currentTarget));for(const key of Object.keys(item))item[key]=item[key].trim();const old=editing===null?null:state[tab][editing];
  if(tab==='sectors'){
    if(state.sectors.some((s,i)=>i!==editing&&(s.name.toLocaleLowerCase()===item.name.toLocaleLowerCase()||s.slug===item.slug))){alert('Nome ou endereço de setor já existe.');return;}
    if(old){state.units.filter(u=>u.sector===old.name).forEach(u=>u.sector=item.name);state.people.filter(p=>p.Setor===old.name).forEach(p=>p.Setor=item.name);}
  }else if(tab==='units'){
    if(state.units.some((u,i)=>i!==editing&&u.sector===item.sector&&u.name.toLocaleLowerCase()===item.name.toLocaleLowerCase())){alert('Esta unidade já existe no setor.');return;}
    item.id=old?.id||crypto.randomUUID();if(old)state.people.filter(p=>p.Setor===old.sector&&p.Unidade===old.name).forEach(p=>{p.Setor=item.sector;p.Unidade=item.name;});
  }else{
    if(item.Siape&&state.people.some((p,i)=>i!==editing&&p.Siape===item.Siape)){alert('Esta matrícula SIAPE já existe.');return;}item.ID=old?.ID||crypto.randomUUID();
  }
  if(old)state[tab][editing]=item;else state[tab].push(item);mark();render();$('#dialog').close();
};
function remove(index){
  if(busy)return;const item=state[tab][index];
  if(tab==='sectors'&&(state.units.some(u=>u.sector===item.name)||state.people.some(p=>p.Setor===item.name))){message('Mova ou exclua as unidades e servidores deste setor antes de excluí-lo.',true);return;}
  if(tab==='units'&&state.people.some(p=>p.Setor===item.sector&&p.Unidade===item.name)){message('Transfira ou exclua os servidores desta unidade antes de excluí-la.',true);return;}
  if(confirm(`Excluir ${item.Nome||item.name}? A exclusão será gravada ao salvar na planilha.`)){state[tab].splice(index,1);mark();render();}
}
$('#save').onclick=async()=>{busy=true;$('#workspace').inert=true;try{const result=await api('save',state);state.revision=result.revision;dirty=false;$('#save-status').textContent='Todas as alterações foram salvas.';message('Planilha salva, backup criado e páginas locais atualizadas. Envie as alterações ao GitHub para publicar.');}catch(e){message(e.message,true);}finally{busy=false;$('#workspace').inert=false;}};
$('#logout').onclick=async()=>{if(dirty&&!confirm('Sair e descartar as alterações não salvas?'))return;try{await api('logout',{});dirty=false;state=null;$('#workspace').hidden=true;$('#login').hidden=false;message('Sessão encerrada.');}catch(e){message(e.message,true);}};
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
start().catch(()=>{});
