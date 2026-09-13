// Enhance native selects without changing their values, validation or change handlers.
const controls = new Map();
const optionOrder = new Intl.Collator('en', {numeric:true, sensitivity:'base', ignorePunctuation:true});
let serial = 0, scheduled = false;

function enhance(select) {
 const wrapper = document.createElement('div');
 wrapper.className = 'searchable-select';
 select.before(wrapper); wrapper.append(select);
 select.classList.add('searchable-native');
 select.tabIndex = -1; select.setAttribute('aria-hidden','true');
 const input = document.createElement('input');
 input.type = 'text'; input.autocomplete = 'off'; input.spellcheck = false;
 input.id = `select-search-${++serial}`;
 input.className = 'select-search';
 input.setAttribute('role','combobox'); input.setAttribute('aria-autocomplete','list');
 input.setAttribute('aria-expanded','false');
 const popup = document.createElement('div');
 popup.className = 'select-popup'; popup.hidden = true;
 const list = document.createElement('div');
 list.id = `${input.id}-options`; list.setAttribute('role','listbox');
 const status = document.createElement('div');
 status.className = 'select-search-status'; status.setAttribute('role','status');
 popup.append(list,status); wrapper.append(input,popup);
 input.setAttribute('aria-controls',list.id);
 let open = false, matches = [], active = -1, query = '';

 function label() {
  const labels = [...select.labels];
  if(labels.length) {
   for(const el of labels)if(!el.id)el.id=`select-label-${++serial}`;
   input.setAttribute('aria-labelledby',labels.map(el=>el.id).join(' '));
   input.removeAttribute('aria-label');
  } else input.setAttribute('aria-label',select.getAttribute('aria-label') || 'Choose an option');
 }
 function position() {
  if(!open)return;
  const rect=input.getBoundingClientRect();
  const below=window.innerHeight-rect.bottom-8, above=rect.top-8;
  const up=below<180 && above>below;
  const height=Math.min(300,Math.max(80,up?above:below));
  popup.style.left=`${Math.max(8,rect.left)}px`;
  popup.style.width=`${Math.min(rect.width,window.innerWidth-16)}px`;
  popup.style.maxHeight=`${height}px`;
  popup.style.top=up?'auto':`${rect.bottom+4}px`;
  popup.style.bottom=up?`${window.innerHeight-rect.top+4}px`:'auto';
 }
 function highlight(index, scroll=false) {
  active=index;
  [...list.children].forEach((el,i)=>el.classList.toggle('active-option',i===active));
  if(active>=0){input.setAttribute('aria-activedescendant',list.children[active].id);if(scroll)list.children[active].scrollIntoView({block:'nearest'});}
  else input.removeAttribute('aria-activedescendant');
 }
 function render() {
  matches=[...select.options].filter(o=>!o.hidden && o.textContent.toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a,b)=>optionOrder.compare(a.textContent.trim(),b.textContent.trim()));
  list.replaceChildren();
  matches.forEach((option,i)=>{
   const row=document.createElement('div');row.id=`${list.id}-${i}`;row.className='select-option';row.setAttribute('role','option');
   row.textContent=option.textContent;row.setAttribute('aria-selected',String(option.selected));
   row.setAttribute('aria-disabled',String(option.disabled || Boolean(option.parentElement.disabled)));
   row.addEventListener('pointerdown',event=>event.preventDefault());
   row.addEventListener('click',()=>choose(i));list.append(row);
  });
  status.textContent=matches.length?`${matches.length} options · type to filter`:'No matching options';
  highlight(matches.findIndex(o=>o.selected && enabled(o)));
  position();
 }
 function enabled(option){return option && !option.disabled && !option.parentElement.disabled;}
 function show() {
  if(select.disabled || select.hidden)return;
  for(const control of controls.values())if(control.select!==select)control.close();
  open=true;query='';popup.hidden=false;input.setAttribute('aria-expanded','true');
  render();input.select();
 }
 function close() {
  open=false;popup.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');
  input.value=select.selectedOptions[0]?.textContent || '';
 }
 function choose(index) {
  const option=matches[index];if(!enabled(option))return;
  const changed=select.selectedIndex!==option.index;
  select.selectedIndex=option.index;close();
  if(changed){select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));}
  schedule();
 }
 function sync() {
  label();wrapper.hidden=select.hidden;input.disabled=select.disabled;
  input.setAttribute('aria-required',String(select.required));
  if(select.disabled || select.hidden || !input.getClientRects().length)close();
  if(!open)input.value=select.selectedOptions[0]?.textContent || '';
  else render();
 }
 input.addEventListener('focus',show);
 input.addEventListener('click',()=>{if(!open)show();});
 input.addEventListener('input',()=>{if(!open)show();query=input.value;render();highlight(matches.findIndex(enabled));});
 // Typed text is a filter, never a free-form replacement for a catalogue value.
 input.addEventListener('change',event=>event.stopPropagation());
 input.addEventListener('blur',close);
 input.addEventListener('keydown',event=>{
  if(event.key==='Escape' && open){event.preventDefault();event.stopPropagation();close();return;}
  if(event.key==='Tab'){close();return;}
  if(event.key==='Enter' && open){event.preventDefault();choose(active);return;}
  if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
  if(!open && ['Home','End'].includes(event.key))return;
  event.preventDefault();if(!open)show();
  const choices=matches.map((o,i)=>enabled(o)?i:-1).filter(i=>i>=0);
  if(!choices.length)return;
  let next;
  if(event.key==='Home')next=choices[0];
  else if(event.key==='End')next=choices.at(-1);
  else {const pos=choices.indexOf(active),direction=event.key==='ArrowDown'?1:-1;next=choices[(pos+direction+choices.length)%choices.length];}
  highlight(next,true);
 });
 select.addEventListener('invalid',event=>{event.preventDefault();input.focus();input.setAttribute('aria-invalid','true');});
 select.addEventListener('change',()=>{input.removeAttribute('aria-invalid');schedule();});
 const control={select,sync,close,position,input};controls.set(select,control);sync();
}
function scan() {
 scheduled=false;
 for(const [select,control] of controls){if(!select.isConnected){control.close();controls.delete(select);}else control.sync();}
 for(const select of document.querySelectorAll('select'))if(!controls.has(select))enhance(select);
}
function schedule(){if(!scheduled){scheduled=true;queueMicrotask(scan);}}
new MutationObserver(records=>{
 if(records.some(r=>r.target instanceof Element && (r.target.closest('select') || (r.type==='attributes' && ['hidden','aria-label'].includes(r.attributeName) && !r.target.closest('.searchable-select')) || [...r.addedNodes,...r.removedNodes].some(n=>n instanceof Element && (n.matches('select') || n.querySelector('select'))))))schedule();
}).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['disabled','hidden','selected','required','aria-label']});
document.addEventListener('change',schedule);
document.addEventListener('click',event=>{
 const label=event.target.closest('label');
 if(label){const control=controls.get(label.control);if(control){event.preventDefault();control.input.focus();}}
});
document.addEventListener('scroll',event=>{for(const c of controls.values())if(!event.target.closest?.('.select-popup'))c.position();},true);
window.addEventListener('resize',()=>{for(const c of controls.values())c.position();});
scan();
