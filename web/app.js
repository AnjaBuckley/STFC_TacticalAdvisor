const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = v => String(v ?? '').replaceAll('_', ' ');
const number = v => new Intl.NumberFormat('en', {maximumFractionDigits:1, notation:Math.abs(v) >= 100000 ? 'compact' : 'standard'}).format(v || 0);
const percent = v => `${Number(v || 0).toFixed(1)}%`;
const initials = name => name.replace(/[^\p{L}\p{N} ]/gu,'').split(' ').filter(Boolean).slice(0,2).map(s=>s[0]).join('');
let syncState, syncPolling = false;
let shipBuildPreview = null, shipBuildSeq = 0;
const shipResearchFields = [["weapon_damage","Weapon damage"],["hull_health","Hull health"],["shield_health","Shield health"],["armor","Armor"],["shield_deflection","Shield deflection"],["dodge","Dodge"],["armor_piercing","Armor piercing"],["shield_piercing","Shield piercing"],["accuracy","Accuracy"]];
let state, result, selectedResult = 0, preview, editingShip, running = false, rosterPage = 0, runClock;
const PAGE_SIZE = 30;
const unlocked = o => (o.level ?? 1) > 0 && (o.rank ?? o.tier ?? 1) > 0;
const statFields = [
 ['hp','Hull health',1,false],['shield_hp','Shield health',0,false],['armor','Armor',0,false],['shield_deflection','Shield deflection',0,false],['dodge','Dodge',0,false],['critical_mitigation_points','Critical Mitigation points',0,false],['critical_floor','Critical multiplier floor (×)',1,false],['base_damage','Damage per round',0,false],
 ['armor_piercing','Armor piercing',0,false],['shield_piercing','Shield piercing',0,false],['accuracy','Accuracy',0,false],
 ['crit_chance','Critical chance (%)',0,true],['crit_multiplier','Critical multiplier (×)',1,false],
 ['iso_defense','Isolytic defense (%)',0,true],['isolytic_damage_bonus','Isolytic damage (%)',0,true],
 ['apex_barrier','Apex Barrier points',0,false],['apex_shred','Apex Shred (%)',0,true],
 ['hyperthermic_decay_fraction','Decay per round (%)',0,true]
];

async function api(path, options = {}) {
 const headers = {'X-STFC-Token':state?.token || '', ...options.headers};
 if(options.body && !(options.body instanceof FormData)) headers['Content-Type']='application/json';
 const response = await fetch(path, {...options, headers});
 const data = await response.json();
 if(!response.ok) {
  const message = Array.isArray(data.detail) ? data.detail.map(d=>`${d.loc.slice(1).join('.')}: ${d.msg}`).join('; ') : data.detail;
  throw new Error(message || `Request failed (${response.status}).`);
 }
 return data;
}
function toast(message) { $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').hidden=true,5500); }
function showError(error) {$('#global-error').innerHTML=`<div class="notice error">${esc(error.message || error)}</div>`; $('#global-error').hidden=false;}
function clearError() {$('#global-error').hidden=true;}
function download(data, name) {
 const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function options(entries, selected) {return entries.map(([value,label])=>`<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`).join('');}
function heading(title, subtitle, action='') {return `<div class="screen-heading"><div><div class="heading-overline"><span></span> Your command console</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;}
function showView(view) {
 if(!['planner','fleet','roster','account','rules'].includes(view)) view='planner';
 $$('.view').forEach(el=>el.hidden=el.id!==`view-${view}`);
 $$('.nav-button').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);if(el.dataset.view===view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 $('#breadcrumb').textContent=$(`.nav-button[data-view="${view}"]`).textContent.replace(/[⌘◇♙☷◎]/g,'').replace(/\d+/g,'').trim();
 history.replaceState(null,'',`#${view}`);
 if(view==='fleet') renderFleet();
 if(view==='roster') renderRoster();
 if(view==='account') renderAccount();
 if(view==='rules') renderRules();
}
function updateAccountChrome() {
 $('#ops-number').textContent=state.profile.ops_level;
 $('#account-ops').textContent=`Operations ${state.profile.ops_level} · Local account`;
 $('#fleet-count').textContent=state.profile.ships.length;
 $('#roster-count').textContent=state.profile.officers.length;
 const selected=$('#ship-select').value;
 $('#ship-select').innerHTML=options([['','Compare available ships'],...state.profile.ships.filter(s=>s.available!==false).map(s=>[s.name,`${s.name} · Level ${s.level || 1}`])],selected);
}
function updateTargets() {
 const task=$('#task').value, pvp=['pvp','pvp_station','station_raid'].includes(task);
 $('#objective option[value="loot"]').disabled=pvp;
 if(pvp) $('#objective').value='combat';
 $('#hostile-control').hidden=pvp;$('#enemy-control').hidden=!pvp;
 const filter=h=>task==='pve_academy_drone'?h.type==='Academy Drone':task==='dreadnought'?h.type==='Dreadnought':task==='pve_hostile'?!['Academy Drone','Dreadnought'].includes(h.type):true;
 $('#target').innerHTML=options(state.hostiles.filter(filter).map(t=>[t.name,t.name]),$('#target').value);
 $$('#target-stats input').forEach(i=>i.value='');
 if(pvp) $('.target-details').open=true;
 updateBriefing(true);
 invalidateResults();
}
function updateBriefing(resetLevel=false) {
 const task=$('#task').value,pvp=['pvp','pvp_station','station_raid'].includes(task);
 const target=state.hostiles.find(t=>t.name===$('#target').value);
 if(pvp) {
  $('#briefing-name').textContent=task==='pvp'?'Player combat':'Station encounter';
  $('#briefing-notes').textContent='Set your opponent’s ship class and combat stats. Compare your available crews against a specific encounter.';
  $('#target-class').textContent=$('#enemy-class').value;
  $('#target-traits').innerHTML='<span class="trait gold">Opponent stats required</span><span class="trait">PvP abilities</span>';
 } else if(target) {
  $('#briefing-name').textContent=target.name;
  $('#briefing-notes').textContent=target.notes || 'Compare your crew against this target.';
  $('#target-class').textContent=target.ship_class;
  if(resetLevel) $('#target-level').value=(target.available_levels || [target.level_range?.[0] || 60])[0];
  const traits=[...(target.standard_damage_immune?['Isolytic damage required']:[]),...(target.requires_crit_mitigation?['Critical Mitigation']:[]),...(target.hyperthermic_decay?['Hyperthermic Decay']:[]),...(target.priority_stats || []).slice(0,2).map(pretty)];
  $('#target-traits').innerHTML=[...new Set(traits)].map((t,i)=>`<span class="trait ${i===0?'gold':''}">${esc(t)}</span>`).join('');
 }
 const variants=(target?.variants || []).filter(v=>v.level===Number($('#target-level').value));
 $('#target-variant').innerHTML=options(variants.map(v=>[String(v.id),`${v.id} · Power ${number(v.strength)}`]),$('#target-variant').value);
 $('#target-variant').hidden=pvp;
 $('#briefing-data').textContent=pvp?'Manually configured opponent':`Target catalogue · Requested level ${$('#target-level').value}`;
}
function invalidateResults() {if(result) $('#results-subtitle').textContent='Parameters changed. Run again to update these results.';}
async function runMission(event) {
 event.preventDefault();if(running)return;
 running=true;clearError();$('#recommend-button').disabled=true;$('#run-status').textContent='Comparing bridge crews…';
 const stats={}; for(const [key,, ,pct] of statFields){const el=$(`#stat-${key}`);if(el.value!=='')stats[key]=Number(el.value)/(pct?100:1);}
 const body={objective:$('#objective').value,task_type:$('#task').value,target_name:$('#target').value,level:Number($('#target-level').value),top_n:Number($('#top-n').value),ship_name:$('#ship-select').value || null,enemy_class:$('#enemy-class').value,target_stats:stats,hostile_id:$('#target-variant').value?Number($('#target-variant').value):null};
 $$('#mission-form input, #mission-form select').forEach(el=>el.disabled=true);
 const start=Date.now();
 $('#results').innerHTML='<div class="empty-state"><div class="loading-line"></div><h3>Assembling your away team…</h3><p>Comparing captain positions, assigning below deck, and estimating combat outcomes.</p></div>';
 $('#results-subtitle').textContent='Evaluating your saved account';$('#export-results').hidden=true;
 runClock=setInterval(()=>$('#run-status').textContent=`Comparing crews and simulating finalists · ${Math.floor((Date.now()-start)/1000)}s`,1000);
 try {
  result=await api('/api/recommend',{method:'POST',body:JSON.stringify(body)});selectedResult=0;renderResults();
  $('#results-subtitle').textContent=`${state.tasks[result.task_type]} · ${result.target.real_hostile?.name || result.target.name} · Level ${result.target.real_hostile?.level || body.level}`;
  $('#export-results').hidden=false;
 } catch(error) {
  result=null;$('#results').innerHTML=`<div class="notice error"><h3>Mission needs attention</h3><p>${esc(error.message)}</p></div>`;
  $('#results-subtitle').textContent='Adjust the mission or your account, then try again.';
 } finally {running=false;$$('#mission-form input, #mission-form select').forEach(el=>el.disabled=false);clearInterval(runClock);$('#recommend-button').disabled=false;$('#run-status').textContent='Based on your saved account';}
}
function activeAbility(name, captain=false, below=false) {
 const entry=state.abilities[name] || {};
 const slots=below?['bda']:captain?['cm','oa']:['oa'];
 return slots.filter(s=>entry[s]).map(s=>`${s.toUpperCase()}: ${pretty(entry[s].effect)}`).join(' · ') || 'Stats contribution; ability data unavailable';
}
function crewCard(name,index) {
 const o=state.profile.officers.find(o=>o.name===name) || {};
 return `<div class="crew-card ${index===0?'captain':''}"><div class="crew-avatar">${esc(initials(name))}</div><span class="crew-role">${index===0?'Captain':`Bridge officer ${index}`}</span><strong>${esc(name)}</strong><p>${esc(o.group || 'Group unknown')} · Rank ${o.rank || o.tier || '?'}</p><div class="ability-line">${esc(activeAbility(name,index===0))}</div></div>`;
}
function renderResults() {
 if(!result)return;
 const recs=result.recommendations;
 if(!recs.length){$('#results').innerHTML='<div class="empty-state"><h3>No valid crew found</h3><p>Add an available combat ship and at least three officers in your account.</p></div>';return;}
 const rec=recs[selectedResult],sim=rec.simulation;
 const trace=sim.damage_trace || {};
 $('#results').innerHTML=`<div class="result-tabs" role="tablist" aria-label="Crew recommendations">${recs.map((r,i)=>`<button class="result-tab ${i===selectedResult?'selected':''}" role="tab" aria-selected="${i===selectedResult}" data-result="${i}">#${i+1} ${esc(r.captain)}</button>`).join('')}</div>
 ${result.pvp_counter?`<div class="notice"><p>Combat triangle: ${esc(result.pvp_counter.recommended_ship_class)} against ${esc(result.target.ship_class)}. Baseline ${esc(result.pvp_counter.recommended_team)}: ${esc(result.pvp_counter.available.join(', ') || 'none available')}${result.pvp_counter.missing.length?`. Missing: ${esc(result.pvp_counter.missing.join(', '))}`:''}. ${esc(result.pvp_counter.note)}</p></div>`:''}
 <article class="recommendation panel"><div class="rec-heading"><div><span class="pill">${selectedResult===0?'Top ranked crew':'Alternative crew'}</span><h3>${esc(rec.ship)}</h3><p>${esc(rec.ship_details.ship_class)} · Level ${rec.ship_details.level || '?'} · ${rec.below_deck_slots} below-deck slots</p></div><div class="rec-score">${(rec.score*100).toFixed(1)}<small>Relative score · not a win rate</small></div></div>
 <div class="rec-body"><div class="subsection-title"><h3>Bridge assignment</h3><span>${esc(rec.synergy)}</span></div><div class="bridge-grid">${[rec.captain,rec.officer_1,rec.officer_2].map(crewCard).join('')}</div>
 <div class="metric-grid">${[[percent(sim.survival_probability),'Estimated survival'],[percent(sim.kill_probability),'Estimated kill rate'],[number(sim.avg_combat_rounds),'Average combat rounds'],[percent(sim.standard_mitigation*100),'Standard mitigation']].map(([v,label])=>`<div class="metric"><strong>${v}</strong><span>${label}</span></div>`).join('')}</div>
 <div class="subsection-title"><h3>Below-deck complement</h3><span>${rec.below_deck.length} / ${rec.below_deck_slots} slots filled</span></div><div class="below-grid">${rec.below_deck.map(o=>`<div class="below-officer">${esc(o.name)}<small>${esc(activeAbility(o.name,false,true))}</small></div>`).join('') || '<p>No below-deck slots unlocked.</p>'}</div>
 <div class="field-help">Isolytic bonus: ${percent(sim.isolytic_bonus*100)} · Cascade: ${percent(sim.isolytic_cascade_bonus*100)} · Initial Critical Mitigation: ${percent(sim.initial_critical_mitigation*100)}${rec.cost_per_kill?` · Estimated repair resources / kill: ${number(rec.cost_per_kill)}`:''}</div>
 <details class="notice" open><summary>Model coverage and uncertainty</summary><p>Kill estimate 95% sampling interval: ${sim.kill_interval_95.map(percent).join(' – ')}. This interval excludes model error. Timeouts: ${percent(sim.timeout_probability)}.</p><ul>${sim.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>
 <details class="reasoning" open><summary>Why this crew</summary><ul>${rec.reasoning.map(r=>`<li>${esc(r)}</li>`).join('')}</ul><p class="field-help">${rec.search.bridge_candidates} of ${rec.search.available_officers} available officers in the heuristic bridge shortlist. Every captain position evaluated.</p></details>
 <details class="reasoning"><summary>First simulated round · incoming damage layers</summary><p class="field-help">${trace.raw===undefined?'No incoming weapon hit occurred in this run.':`${trace.is_critical?'Critical':'Normal'} incoming hit, round ${trace.round || '?'} of the first seeded run. Both damage tracks use Apex once.`}</p><div class="trace">${[['raw','Raw damage'],['after_standard','After standard mitigation'],['after_apex','After Apex + critical multiplier'],['after_critical','After Critical Mitigation'],['isolytic','Parallel isolytic'],['decay','Decay']].map(([k,n])=>`<div><small>${n}</small><strong>${number(trace[k])}</strong></div>`).join('')}</div></details>
 ${sim.unmodelled_abilities.length?`<details class="reasoning" open><summary>${sim.unmodelled_abilities.length} ability effects need battle-log verification</summary><p class="field-help">These effects are missing or only partly modelled. Review each note: conditions, timing, or exact values still need verification.</p><ul>${sim.unmodelled_abilities.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></details>`:''}</div></article>
 <details class="notice" open><summary>How to read these estimates</summary>${result.warnings.map(w=>`<p>${esc(w)}</p>`).join('')}</details>`;
}
async function persist(profile, revision=state.revision) {
 const saved=await api('/api/profile',{method:'PUT',body:JSON.stringify({profile,revision})});
 state.profile=profile;state.revision=saved.revision;updateAccountChrome();invalidateResults();toast(saved.message);return saved;
}
function renderFleet() {
 $('#view-fleet').innerHTML=heading('Your fleet. Ready to deploy.','Manage owned ships and enter the stats for your current build.','<button class="secondary-button" id="add-ship">+ Add a ship</button>')+
 `<div class="notice"><p>Use unbuffed ship base stats here. Ship research is applied separately in Account & research. Select a catalogue ship, level, tier and component upgrades to fill base stats from the bundled database. Account bonuses are applied separately.</p></div><div class="fleet-grid">${state.profile.ships.map((s,i)=>`<article class="fleet-card panel"><span class="pill">${esc(s.ship_class)}</span><h2>${esc(s.name)}</h2><p>Tier ${s.tier || 1} · Level ${s.level || 1}${s.simulacrum_refit?' · Simulacrum refit owned':''}</p><div class="fleet-stats">${[['attack','Base weapon damage'],['health','Base hull'],['armor','Armor'],['shield_deflection','Shield deflection']].map(([k,label])=>`<div><span>${label}</span><strong>${number(s.base_stats?.[k])}</strong></div>`).join('')}</div><div class="fleet-actions"><label class="checkbox-label"><input type="checkbox" data-ship-available="${i}" ${s.available!==false?'checked':''}> Available</label><button class="secondary-button" data-edit-ship="${i}">Edit ship</button></div></article>`).join('')}</div>`;
}
function field(name,label,value,min=0,max='',step='any') {return `<div><label for="${name}">${label}</label><input type="number" id="${name}" name="${name}" value="${esc(value ?? '')}" min="${min}" ${max!==''?`max="${max}"`:''} step="${step}"></div>`;}
function openShip(index=null) {
 editingShip=index; shipBuildPreview=null; shipBuildSeq++;
 const ship=index===null?{}:state.profile.ships[index];
 $('#edit-title').textContent=index===null?'Add an owned ship':`Edit ${ship.name}`;
 $('#edit-fields').innerHTML=`${index===null?`<label for="catalog-ship">Ship catalogue</label><select id="catalog-ship">${options([['','Enter a ship manually'],...state.ships.map(s=>[s.name,s.name])])}</select>`:''}<label for="edit-name">Ship name</label><input id="edit-name" required value="${esc(ship.name || '')}"><div class="dialog-grid"><div><label for="edit-class">Ship class</label><select id="edit-class">${options(['Explorer','Battleship','Interceptor','Survey'].map(s=>[s,s]),ship.ship_class || 'Explorer')}</select></div>${field('edit-level','Level',ship.level || 1,1,200,1)}${field('edit-tier','Tier',ship.tier || 1,1,30,1)}${field('edit-slots','Below-deck slots (blank: auto)',ship.below_deck_slots,0,20,1)}</div><p class="field-help">Level changes hull/shield bonuses and slots; tier and components determine the build. Autofill replaces base fields only.</p><div class="dialog-grid">${[['attack','Weapon damage / round (no criticals)'],['health','Hull health'],['shield_health','Shield health'],['armor','Armor'],['shield_deflection','Shield deflection'],['dodge','Dodge'],['armor_piercing','Armor piercing'],['shield_piercing','Shield piercing'],['accuracy','Accuracy']].map(([k,l])=>field(`edit-${k}`,l,ship.base_stats?.[k] ?? (k==='health'?1:0),k==='health'?1:0)).join('')}${field('edit-iso','Ship isolytic bonus (%)',(ship.isolytic_damage_bonus || 0)*100)}${field('edit-cascade','Ship Cascade (%)',(ship.isolytic_cascade_bonus || 0)*100)}${field('edit-shred','Apex Shred (%)',(ship.apex_shred || 0)*100,0,100)}${field('edit-stabilizer','Hyperthermic Stabilizer (%)',(ship.hyperthermic_stabilizer || 0)*100)}${field('edit-critical-chance','Critical chance (%)',(ship.crit_chance || 0)*100,0,100)}${field('edit-critical-multiplier','Critical multiplier (×)',ship.crit_multiplier ?? 1.5,1)}${field('edit-crit-points','Refit Critical Mitigation points',ship.crit_mitigation_points)}</div><label class="checkbox-label" style="margin-top:20px"><input id="edit-refit" type="checkbox" ${ship.simulacrum_refit?'checked':''}> Simulacrum refit owned</label><p class="field-help">Refit eligibility is checked by ship name or faction, grade and rarity. Leave points blank to retain an existing legacy percentage.</p>`;
 $('#edit-fields').insertAdjacentHTML('beforeend',`<div class="settings-section"><label class="checkbox-label"><input id="edit-autofill" type="checkbox" ${index===null || ship.stat_source?.provider==='STFC Space'?'checked':''}> Autofill base stats from bundled catalogue</label><p class="field-help">Existing manual builds stay manual until enabled. Account and ship-specific bonuses are retained.</p><div id="build-status" role="status"></div><div id="build-components" class="dialog-grid"></div><div id="build-reference" class="field-help"></div><details><summary>Abilities, refits and crew reference</summary><div id="catalogue-reference"></div></details></div><details class="settings-section"><summary>Extra research bonuses for this ship</summary><p class="field-help">Additional additive percentages for this ship/class only. Exclude bonuses already entered in Account & research.</p><div class="dialog-grid">${shipResearchFields.map(([k,l])=>field(`ship-research-${k}`,`${l} (%)`,(ship.research_bonuses?.[`ship_${k}`] || 0)*100)).join('')}</div></details><details class="settings-section"><summary>Movement, cargo and weapon schedule</summary><p class="field-help">Movement/cargo are base reference values; travel and hauling are not simulated. Weapon schedules are used in combat.</p><div class="dialog-grid">${[['warp_range','Warp range'],['warp_speed','Warp speed'],['impulse_speed','Impulse speed'],['cargo_capacity','Cargo capacity'],['protected_cargo','Protected cargo'],['apex_barrier','Ship Apex Barrier points']].map(([k,l])=>field(`ship-extra-${k}`,l,ship[k] || 0)).join('')}${field('ship-critical-chance-bonus','Extra critical chance (percentage points)',(ship.crit_chance_bonus || 0)*100,0,100)}${field('ship-critical-damage-bonus','Extra critical damage (%)',(ship.crit_damage_bonus || 0)*100)}${field('ship-shield-absorption','Shield absorption (%)',(ship.shield_mitigation ?? .8)*100,0,100)}</div><label for="ship-weapons">Weapons JSON (blank: aggregate attack)</label><textarea id="ship-weapons" rows="7">${esc(ship.weapons?JSON.stringify(ship.weapons,null,2):'')}</textarea></details>`);
 const buildSection=$('#edit-autofill').closest('.settings-section');$('#edit-fields').insertBefore(buildSection,$('#edit-fields > .field-help').nextElementSibling);
 $('#dialog-error').textContent='';$('#edit-dialog').showModal();
 if(ship.name && $('#edit-autofill').checked)autofillShip(ship.component_tiers || {});
}
async function autofillShip(componentTiers={}) {
 const seq=++shipBuildSeq;
 const automatic=$('#edit-autofill').checked;
 for(const k of ['attack','health','shield_health','armor','shield_deflection','dodge','armor_piercing','shield_piercing','accuracy','critical-chance','critical-multiplier'])$(`#edit-${k}`).readOnly=automatic;
 $('#ship-weapons').readOnly=automatic;$('#edit-class').disabled=automatic;
 if(!automatic){$('#build-status').textContent='Manual build: base stats and weapon schedule are editable.';$('#build-components').innerHTML='';return;}
 shipBuildPreview=null;
 const name=$('#edit-name').value.trim();if(!name)return;
 const button=$('#edit-form button[type=submit]');button.disabled=true;
 $('#build-status').textContent='Loading bundled ship build…';
 try {
  const data=await api('/api/ships/build',{method:'POST',body:JSON.stringify({name,level:Number($('#edit-level').value),tier:Number($('#edit-tier').value),component_tiers:componentTiers})});
  if(seq!==shipBuildSeq || !$('#edit-dialog').open)return;
  shipBuildPreview=data.ship;const s=data.ship;
  for(const [k,v] of Object.entries(s.base_stats))$(`#edit-${k}`).value=v;
  $('#edit-class').value=s.ship_class;$('#edit-critical-chance').value=s.crit_chance*100;$('#edit-critical-multiplier').value=s.crit_multiplier;
  for(const k of ['warp_range','warp_speed','impulse_speed','cargo_capacity','protected_cargo'])$(`#ship-extra-${k}`).value=s[k];
  $('#ship-shield-absorption').value=s.shield_mitigation*100;
  $('#ship-weapons').value=s.weapons?JSON.stringify(s.weapons,null,2):'';
  $('#build-components').innerHTML=data.components.filter(c=>c.tiers.length>1).map(c=>`<div><label for="component-${c.slot}">${esc(c.label)}</label><select id="component-${c.slot}" data-build-component="${c.slot}">${options(c.tiers.map(t=>[t,t===s.tier?'Current tier component':'Next tier upgrade installed']),c.selected)}</select></div>`).join('');
  $('#build-status').textContent=`Base build loaded · STFC Space snapshot ${s.stat_source.version}. ${data.notes.join(' ')}`;
  $('#build-reference').textContent=data.reference.ability?`Sheet reference: ${data.reference.ability} · Level value: ${data.reference.level_value ?? 'unavailable'} (native units; not automatically applied).`:'';
  const ref=data.catalogue_reference;
  $('#catalogue-reference').innerHTML=`<p>${esc(s.faction)} · Grade ${s.grade} · ${esc(s.ship_class)}</p><p>${esc(ref.coverage)}</p>${[['abilities','Ship abilities'],['active_abilities','Active abilities'],['refits','Catalogue refits']].map(([key,label])=>`<h3>${label}</h3>${ref[key].map(a=>`<p><strong>${esc(a.name)}</strong><br>${esc(a.description)}${a.level_value?`<br>Selected level value (native): ${esc(JSON.stringify(a.level_value))}`:''}</p>`).join('') || '<p>None listed.</p>'}`).join('')}<h3>Below-deck unlocks</h3><p>${ref.crew_slots.map(c=>`${esc(c.slots)} slots at level ${c.unlock_level}`).join(' · ')}</p><h3>Officer stat thresholds</h3>${Object.entries(ref.officer_bonus).map(([key,rows])=>`<p>${esc(key)}: ${rows.map(r=>`${number(r.value)} → ${number(r.bonus*100)}%`).join(' · ')}</p>`).join('')}<a href="${esc(s.stat_source.url)}" target="_blank" rel="noopener noreferrer">View source on STFC Space ↗</a>`;

 }catch(e){if(seq===shipBuildSeq)$('#build-status').textContent=e.message;}
 finally{if(seq===shipBuildSeq)button.disabled=false;}
}
async function saveShip(event) {
 event.preventDefault();const button=$('#edit-form button[type=submit]');button.disabled=true;
 try {
  if($('#edit-autofill').checked && !shipBuildPreview)throw new Error('Load a valid catalogue build or switch off autofill to enter manual stats.');
  const profile=structuredClone(state.profile),old=editingShip===null?{}:profile.ships[editingShip];
  const selected=state.ships.find(s=>s.name===$('#edit-name').value.trim());
  const ship={...selected,...old,...(shipBuildPreview || {}),name:$('#edit-name').value.trim(),ship_class:$('#edit-class').value,level:Number($('#edit-level').value),tier:Number($('#edit-tier').value),base_stats:{...old.base_stats},simulacrum_refit:$('#edit-refit').checked,isolytic_damage_bonus:Number($('#edit-iso').value)/100};
  for(const k of ['attack','health','shield_health','armor','shield_deflection','dodge','armor_piercing','shield_piercing','accuracy'])ship.base_stats[k]=Number($(`#edit-${k}`).value);
  for(const [id,key] of [['edit-cascade','isolytic_cascade_bonus'],['edit-shred','apex_shred'],['edit-stabilizer','hyperthermic_stabilizer'],['edit-critical-chance','crit_chance']])ship[key]=Number($(`#${id}`).value)/100;
  ship.research_bonuses={...old.research_bonuses};
  for(const [k] of shipResearchFields)ship.research_bonuses[`ship_${k}`]=Number($(`#ship-research-${k}`).value)/100;
  for(const k of ['warp_range','warp_speed','impulse_speed','cargo_capacity','protected_cargo','apex_barrier'])ship[k]=Number($(`#ship-extra-${k}`).value);
  ship.crit_chance_bonus=Number($('#ship-critical-chance-bonus').value)/100;ship.crit_damage_bonus=Number($('#ship-critical-damage-bonus').value)/100;
  ship.shield_mitigation=Number($('#ship-shield-absorption').value)/100;
  if($('#ship-weapons').value.trim())ship.weapons=JSON.parse($('#ship-weapons').value);else delete ship.weapons;
  if(!$('#edit-autofill').checked)ship.stat_source={provider:'manual'};
  ship.crit_multiplier=Number($('#edit-critical-multiplier').value);
  if($('#edit-slots').value!=='')ship.below_deck_slots=Number($('#edit-slots').value);else delete ship.below_deck_slots;
  if($('#edit-crit-points').value!=='')ship.crit_mitigation_points=Number($('#edit-crit-points').value);
  if(editingShip===null)profile.ships.push(ship);else profile.ships[editingShip]=ship;
  await persist(profile);$('#edit-dialog').close();renderFleet();
 } catch(e){$('#dialog-error').innerHTML=`<p class="error-message">${esc(e.message)}</p>`;}finally{button.disabled=false;}
}
function renderRoster() {
 $('#view-roster').innerHTML=heading('Officers, at your command.','Search your roster. Exclude officers assigned elsewhere before planning a mission.')+`<div class="toolbar"><input id="officer-search" placeholder="Search name, group, or ability…" aria-label="Search officers"><select id="officer-rarity" aria-label="Filter rarity"><option value="">All rarities</option><option value="E">Epic</option><option value="R">Rare</option><option value="U">Uncommon</option><option value="C">Common</option></select><span id="roster-summary"></span></div><div id="roster-table"></div>`;
 renderRosterRows();
}
function renderRosterRows() {
 const search=$('#officer-search').value.toLowerCase(),rarity=$('#officer-rarity').value;
 const officers=state.profile.officers.map((o,i)=>({...o,index:i})).filter(o=>(!rarity || o.rarity===rarity || o.rarity?.[0]===rarity)&&`${o.name} ${o.group} ${o.description}`.toLowerCase().includes(search));
 const pages=Math.max(1,Math.ceil(officers.length/PAGE_SIZE));rosterPage=Math.min(rosterPage,pages-1);
 $('#roster-summary').textContent=`${officers.length} officers · ${state.profile.officers.filter(o=>o.available!==false && unlocked(o)).length} available`;
 $('#roster-table').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Available</th><th>Officer</th><th>Rank / level</th><th>Group</th><th>Attack</th><th>Defense</th><th>Health</th><th>Abilities</th></tr></thead><tbody>${officers.slice(rosterPage*PAGE_SIZE,(rosterPage+1)*PAGE_SIZE).map(o=>`<tr><td><input type="checkbox" aria-label="${esc(o.name)} available" data-officer-available="${o.index}" ${o.available!==false && unlocked(o)?'checked':''} ${unlocked(o)?'':'disabled title="Officer not unlocked"'}></td><td class="officer-name">${esc(o.name)}<small class="badge-${['E','Epic'].includes(o.rarity)?'epic':'rare'}">${esc(({E:'Epic',R:'Rare',U:'Uncommon',C:'Common'})[o.rarity] || o.rarity)}</small></td><td>${o.rank || o.tier || '?'} / ${o.level || '?'}</td><td>${esc(o.group || 'Unknown')}</td>${['attack','defense','health'].map(k=>`<td>${number(o[k] || o.stats?.[k])}</td>`).join('')}<td class="roster-description">${esc(o.description || 'No description imported.')}</td></tr>`).join('') || '<tr><td colspan="8">No officers match. Try another name or rarity.</td></tr>'}</tbody></table></div><div class="pagination"><button class="secondary-button" id="roster-prev" ${rosterPage===0?'disabled':''}>Previous</button><span>Page ${rosterPage+1} of ${pages}</span><button class="secondary-button" id="roster-next" ${rosterPage>=pages-1?'disabled':''}>Next</button></div>`;
}
function renderAccount() {
 const p=state.profile,r=p.research || {},c=r.combat || {},crit=r.critical_mitigation || {};
 $('#view-account').innerHTML=heading('Your account is the starting point.','Keep research, ship stats and officer ownership aligned with your game.')+`<div class="account-layout"><form id="account-form" class="panel settings-panel"><h2>Account & combat research</h2><p>Bonuses below are percentages: enter 920 for a 920% bonus. Use additive totals from your account.</p><div class="field-row">${field('account-ops-input','Operations level',p.ops_level,1,100,1)}${field('account-syndicate','Syndicate level',p.syndicate_level || 0,0,200,1)}</div><div class="settings-section"><h3>Ship research</h3><div class="field-row">${field('research-weapon','Weapon damage (%)',(c.ship_weapon_damage || 0)*100)}${field('research-hull','Hull health (%)',(c.ship_hull_health || 0)*100)}${field('research-shield','Shield health (%)',(c.ship_shield_health || 0)*100)}${shipResearchFields.slice(3).map(([k,l])=>field(`research-${k}`,`${l} (%)`,(c[`ship_${k}`] || 0)*100)).join('')}${field('research-apex','Apex Barrier points',r.mirror_tree?.apex_barrier || 0)}${field('research-iso','Isolytic damage (%)',(r.star_path?.isolytic_damage_bonus || 0)*100)}${field('research-iso-defense','Isolytic defense (%)',(r.star_path?.isolytic_defense_bonus || 0)*100)}</div></div><div class="settings-section"><h3>Officer research</h3><div class="field-row">${field('research-all','All officer stats (%)',(c.all_research || 0)*100)}${field('research-atk','Officer attack (%)',(c.atk_only_research || 0)*100)}${field('research-def','Officer defense (%)',(c.def_only_research || 0)*100)}${field('research-hth','Officer health (%)',(c.hth_only_research || 0)*100)}</div></div><div class="settings-section"><h3>Critical Mitigation</h3><p class="field-help">Enter points shown in-game. Remote Campus applies to Academy encounters; the Matter Beam applies to PvP. Blank values preserve legacy saved percentages.</p><div class="field-row">${field('research-campus','Remote Campus points',crit.remote_campus_points)}${field('research-beam','Matter Beam points',crit.programmable_matter_beam_points)}</div><label class="checkbox-label" style="margin-top:18px"><input type="checkbox" id="research-beam-owned" ${crit.programmable_matter_beam?'checked':''}> Programmable Matter Beam owned</label>${crit.remote_campus_bonus || crit.programmable_matter_beam_value?'<p class="field-help">This profile contains legacy percentages. Enter points to replace them for each source.</p>':''}</div><details class="settings-section"><summary>Attributed combat sources (advanced)</summary><p>Imported research is retained here for review. Each enabled source needs an effect, native unit, explicit contexts and status manual or reviewed. Do not include bonuses already counted in the totals above. Unknown records remain excluded.</p><label for="combat-sources">Sources JSON</label><textarea id="combat-sources" rows="12">${esc(JSON.stringify(p.combat_sources || [],null,2))}</textarea></details><div class="settings-actions"><button class="primary-button" type="submit">Save account</button><span class="field-help">A backup is created on every save.</span></div><div id="account-error" role="alert"></div></form>
 <div><div id="sheet-sync-panel" class="panel settings-panel" style="margin-bottom:20px"></div><div class="panel settings-panel"><h2>Import your progress</h2><p>Preview the changes before updating your account.</p>${[['research','Spocks.club research','Import attributed research values for scope review; existing totals are preserved.','.csv'],['officers','STFC Officers Tool','Upload the Excel workbook to refresh officer ranks, levels and stats.','.xlsx'],['profile','Restore an account','Load a previously exported STFC account JSON file.','.json']].map(([kind,title,desc,accept])=>`<form class="import-option" data-import-kind="${kind}"><h3>${title}</h3><p>${desc}</p><input type="file" accept="${accept}" aria-label="${title} file" required>${kind==='research'?'<label class="checkbox-label"><input type="checkbox" name="enable-mapped"> Enable reviewed research effects. My manual account and ship totals exclude these bonuses.</label>':''}<button class="secondary-button" type="submit">Preview import</button></form>`).join('')}<form id="sheet-import-form" class="import-option"><h3>Import from Google Sheets</h3><p>Paste your shared STFC Officers Tool link. The sheet needs viewer access via the link.</p><label for="sheet-url">Google Sheets URL</label><input id="sheet-url" value="${esc(syncState?.url || '')}" type="url" placeholder="https://docs.google.com/spreadsheets/d/…" required><button class="secondary-button" type="submit">Preview sheet</button><button class="primary-button" id="enable-sheet-sync" type="button">Enable auto-sync</button></form></div><div id="import-preview"></div><div class="notice"><p>These are local settings. Saving here does not modify your in-game account.</p></div></div></div>`;
 renderSyncStatus();
}
async function saveAccount(event) {
 event.preventDefault();const button=$('#account-form button[type=submit]');button.disabled=true;
 try {
  const p=structuredClone(state.profile);p.ops_level=Number($('#account-ops-input').value);p.syndicate_level=Number($('#account-syndicate').value);
  const r=p.research ||= {};const c=r.combat ||= {};r.mirror_tree ||= {};r.star_path ||= {};r.critical_mitigation ||= {};
  c.ship_weapon_damage=Number($('#research-weapon').value)/100;c.ship_hull_health=Number($('#research-hull').value)/100;
  c.all_research=Number($('#research-all').value)/100;c.atk_only_research=Number($('#research-atk').value)/100;c.hth_only_research=Number($('#research-hth').value)/100;
  c.ship_shield_health=Number($('#research-shield').value)/100;c.def_only_research=Number($('#research-def').value)/100;
  for(const [k] of shipResearchFields.slice(3))c[`ship_${k}`]=Number($(`#research-${k}`).value)/100;
  c.total_officer_bonus=c.all_research;
  r.mirror_tree.apex_barrier=Number($('#research-apex').value);
  r.star_path.isolytic_damage_bonus=Number($('#research-iso').value)/100;r.star_path.isolytic_defense_bonus=Number($('#research-iso-defense').value)/100;
  for(const [id,key] of [['research-campus','remote_campus_points'],['research-beam','programmable_matter_beam_points']])if($(`#${id}`).value!=='')r.critical_mitigation[key]=Number($(`#${id}`).value);
  r.critical_mitigation.programmable_matter_beam=$('#research-beam-owned').checked;
  p.combat_sources=JSON.parse($('#combat-sources').value);
  await persist(p);$('#account-error').textContent='';
 }catch(e){$('#account-error').innerHTML=`<p class="error-message">${esc(e.message)}</p>`;}finally{button.disabled=false;}
}
async function importFile(form) {
 const file=$('input[type=file]',form).files[0];if(!file)return;
 const button=$('button',form);button.disabled=true;$('#import-preview').innerHTML='<div class="panel settings-panel"><p>Reading file and preparing the preview…</p></div>';
 try {
  const data=new FormData();data.append('file',file);
  preview=await api(`/api/import/preview?kind=${form.dataset.importKind}&enable_mapped=${!!$('[name="enable-mapped"]',form)?.checked}`,{method:'POST',body:data});
  $('#import-preview').innerHTML=`<div class="panel settings-panel"><h2>Review import</h2><p>${esc(preview.message)}</p><ul class="import-diff">${preview.diff.map(d=>`<li>${esc(d)}</li>`).join('') || '<li>No changes found.</li>'}</ul><div class="settings-actions"><button class="primary-button" id="apply-import" ${preview.diff.length?'':'disabled'}>Apply changes</button><button class="secondary-button" id="cancel-import">Discard</button></div></div>`;
 }catch(e){preview=null;$('#import-preview').innerHTML=`<div class="notice error">${esc(e.message)}</div>`;}finally{button.disabled=false;}
}
async function importGoogleSheet(event) {
 event.preventDefault();const button=$('#sheet-import-form button');button.disabled=true;
 $('#import-preview').innerHTML='<div class="panel settings-panel"><p>Fetching the sheet and preparing your preview…</p></div>';
 try {
  preview=await api('/api/import/sheet-preview',{method:'POST',body:JSON.stringify({url:$('#sheet-url').value})});
  $('#import-preview').innerHTML=`<div class="panel settings-panel"><h2>Review sheet import</h2><p>${esc(preview.message)}</p><ul class="import-diff">${preview.diff.map(d=>`<li>${esc(d)}</li>`).join('') || '<li>No changes found.</li>'}</ul><div class="settings-actions"><button class="primary-button" id="apply-import" ${preview.diff.length?'':'disabled'}>Apply changes</button><button class="secondary-button" id="cancel-import">Discard</button></div></div>`;
 }catch(e){preview=null;$('#import-preview').innerHTML=`<div class="notice error">${esc(e.message)}</div>`;}finally{button.disabled=false;}
}

function renderSyncStatus() {
 const s=syncState;
 const badge=$('#sheet-sync-indicator');
 if(badge) badge.textContent=!s?'Sheet sync: checking…':s.syncing?'Sheet sync: syncing…':s.last_error?'Sheet sync: needs attention':s.enabled?'Sheet sync: every 5 minutes':'Sheet sync: paused';
 const panel=$('#sheet-sync-panel');
 if(!panel || !s)return;
 const date=v=>v?new Date(v).toLocaleString():'Not yet';
 panel.innerHTML=`<h2>Google Sheets auto-sync</h2><p>One-way updates to officer ranks, levels, stats, Operations and Syndicate. Checks every five minutes while the app server runs, even with this tab closed. Sheet values replace these local fields; fleet, research and availability settings are preserved.</p><span class="pill">${s.syncing?'Syncing…':s.enabled?'Auto-sync enabled':'Auto-sync paused'}</span>${s.url?`<p><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open connected sheet ↗</a></p>`:''}<p>Last successful check: ${esc(date(s.last_success))}<br>Last account update: ${esc(date(s.last_changed))}<br>Next check: ${s.enabled?esc(date(s.next_check)):'Paused'}${s.officers_in_sheet?`<br>${s.officers_in_sheet} officer records in the sheet`:''}</p>${s.last_error?`<p class="error-message" role="alert">${esc(s.last_error)}</p>`:''}${s.last_result==='unchanged'?'<p class="field-help">Already up to date. No account backup needed.</p>':''}<div class="settings-actions">${s.url?`<button class="secondary-button" id="toggle-sheet-sync">${s.enabled?'Pause sync':'Resume sync'}</button><button class="secondary-button" id="sync-sheet-now" ${!s.enabled || s.syncing?'disabled':''}>Sync now</button>`:''}</div><p class="field-help">A backup is created before changed data is saved. Failed checks retain your account and retry automatically.</p>`;
}
async function refreshSync() {
 if(syncPolling)return;
 syncPolling=true;
 try {
  syncState=await api('/api/sync');renderSyncStatus();
  const changed=syncState.profile_revision!==state.revision;
  $('#sheet-update-notice').hidden=!changed;
 } catch(e) {
  $('#sheet-sync-indicator').textContent='Sheet sync: connection unavailable';
 } finally {syncPolling=false;}
}
async function configureSheetSync(url, enabled) {
 syncState=await api('/api/sync',{method:'PUT',body:JSON.stringify({url,enabled})});
 renderSyncStatus();
 toast(enabled?'Auto-sync enabled. The sheet will be checked now.':'Google Sheets auto-sync paused.');
}

function renderRules() {
 $('#view-rules').innerHTML=heading('Know the rules behind the result.','Verified mechanics, documented assumptions, and the limits of the current model.')+`<div class="notice"><p>Sources checked ${esc(state.rules.checked)}. The application is an advisor, not an exhaustive recreation of the live game. Some imported officer records are inferred, and numerical estimates need battle-log calibration.</p></div><div class="rules-grid">${state.rules.rules.map(r=>`<article class="panel rule-card"><span class="pill">${esc(r.status)}</span><h2>${esc(r.title)}</h2><p>${esc(r.description)}</p>${r.formula?`<div class="code-note">${esc(r.formula)}</div>`:''}<p>${esc(r.coverage)}</p>${r.url?`<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source)} ↗</a>`:''}</article>`).join('')}</div><div class="panel settings-panel" style="margin-top:20px"><h2>What still needs modelling</h2><p>${esc(state.rules.limitations.join(' '))}</p></div>`;
}

document.addEventListener('click', async event=>{
 const nav=event.target.closest('[data-view]');if(nav && state){showView(nav.dataset.view);return;}
 const tab=event.target.closest('[data-result]');if(tab){selectedResult=Number(tab.dataset.result);renderResults();return;}
 const edit=event.target.closest('[data-edit-ship]');if(edit){openShip(Number(edit.dataset.editShip));return;}
 const id=event.target.closest('button')?.id;
 try {
  if(id==='reload-synced-account')location.reload();
  if(id==='enable-sheet-sync'){
   if(!$('#sheet-import-form').reportValidity())return;
   await configureSheetSync($('#sheet-url').value,true);
  }
  if(id==='toggle-sheet-sync'&&syncState?.url)await configureSheetSync(syncState.url,!syncState.enabled);
  if(id==='sync-sheet-now'){
   event.target.closest('button').disabled=true;
   syncState=await api('/api/sync/run',{method:'POST'});renderSyncStatus();await refreshSync();
  }
  if(id==='add-ship')openShip();
  if(id==='close-dialog'||id==='cancel-dialog')$('#edit-dialog').close();
  if(id==='export-account')download((await api('/api/bootstrap')).profile,'stfc-account.json');
  if(id==='export-results'&&result)download(result,'stfc-recommendations.json');
  if(id==='roster-prev'){rosterPage--;renderRosterRows();}
  if(id==='roster-next'){rosterPage++;renderRosterRows();}
  if(id==='cancel-import'){preview=null;$('#import-preview').innerHTML='';}
  if(id==='apply-import'&&preview){const button=event.target.closest('button');button.disabled=true;try{await persist(preview.profile,preview.revision);preview=null;renderAccount();}catch(e){button.disabled=false;throw e;}}
 } catch(e){showError(e);}
});
document.addEventListener('input',event=>{if(event.target.id==='officer-search'){rosterPage=0;renderRosterRows();}});
document.addEventListener('change',async event=>{
 const el=event.target;
 if(el.id==='task'){updateTargets();return;}
 if(el.id==='target'){updateBriefing(true);invalidateResults();return;}
 if(['enemy-class','target-level'].includes(el.id)){updateBriefing();invalidateResults();return;}
 if(el.closest('#mission-form'))invalidateResults();
 if(el.id==='officer-rarity'){rosterPage=0;renderRosterRows();}
 if(el.id==='catalog-ship'){
  const s=state.ships.find(s=>s.name===el.value);if(s){$('#edit-name').value=s.name;$('#edit-class').value=s.ship_class;$('#edit-level').value=1;$('#edit-tier').value=1;autofillShip();}
 }
 if(['edit-level','edit-tier','edit-name','edit-autofill'].includes(el.id)){const components=el.id==='edit-level'?(shipBuildPreview?.component_tiers || {}):{};shipBuildPreview=null;shipBuildSeq++;$('#edit-form button[type=submit]').disabled=false;autofillShip(components);}
 if(el.matches('[data-build-component]'))autofillShip(Object.fromEntries($$('[data-build-component]').map(e=>[e.dataset.buildComponent,Number(e.value)])));
 if(el.matches('[data-ship-available], [data-officer-available]')){
  el.disabled=true;
  try {const p=structuredClone(state.profile);if(el.dataset.shipAvailable!==undefined)p.ships[Number(el.dataset.shipAvailable)].available=el.checked;else p.officers[Number(el.dataset.officerAvailable)].available=el.checked;await persist(p);}
  catch(e){el.checked=!el.checked;showError(e);}finally{el.disabled=false;}
 }
});
document.addEventListener('submit',event=>{
 if(event.target.id==='mission-form')runMission(event);
 if(event.target.id==='edit-form')saveShip(event);
 if(event.target.id==='account-form')saveAccount(event);
 if(event.target.id==='sheet-import-form')importGoogleSheet(event);
 if(event.target.matches('[data-import-kind]')){event.preventDefault();importFile(event.target);}
});
window.addEventListener('hashchange',()=>{if(state)showView(location.hash.slice(1));});
async function boot(){
 try {
  state=await api('/api/bootstrap');
  $('#task').innerHTML=options(Object.entries(state.tasks),'pve_hostile');
  $('#target-stats').innerHTML=statFields.map(([key,label,min,pct])=>`<div><label for="stat-${key}">${label}</label><input id="stat-${key}" type="number" min="${min}" ${['crit_chance','apex_shred','hyperthermic_decay_fraction'].includes(key)?'max="100"':''} step="any" placeholder="Catalogue"></div>`).join('');
  updateAccountChrome();updateTargets();showView(location.hash.slice(1)||'planner');
  await refreshSync();setInterval(refreshSync,15000);
 }catch(e){showError(e);$('#recommend-button').disabled=true;$('#run-status').textContent='Connection unavailable. Reload to reconnect.';}
}
boot();
