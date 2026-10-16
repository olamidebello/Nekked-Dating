const $=id=>document.getElementById(id);
const categories={emotional:'Emotional connection',intimacy:'Intimacy & boundaries',financial:'Money & priorities',living:'Sharing a home',moods:'Moods',communication:'Communication'};
const questions={animal:['If you could pick any animal, what animal would you choose?','Give three reasons why you chose that animal.'],color:['If you could pick one color to represent you, what color would you pick?','Give three reasons why you chose it.'],paradise:['If you could be in your own paradise (only you), how would you feel?','Give three feelings you would have in your version of paradise.'],box:["Imagine you woke up in a white box: no windows, no doors, no way out. You are fine, not hurt or hungry, but you cannot leave.",'Give three feelings you would have being in this box.']};
function el(tag,text){const n=document.createElement(tag);if(text)n.textContent=text;return n;}
for(const [key,title] of Object.entries(categories)){const label=el('label',title),select=el('select');select.name=key;for(const [value,text] of [['similar','I value shared approaches'],['flexible','I enjoy flexibility'],['independent','I value independence']]){const o=el('option',text);o.value=value;select.append(o);}label.append(select);$('preferences').append(label);}
for(const [key,[prompt,interpretation]] of Object.entries(questions)){const box=el('fieldset'),legend=el('legend',prompt);box.append(legend,el('p',interpretation));const label=el('label',key==='paradise'||key==='box'?'Scene description (optional)':'Your answer'),input=el('input');input.name=key;input.required=key==='animal'||key==='color';input.maxLength=1000;label.append(input);box.append(label);const row=el('div');row.className='grid';for(let i=0;i<3;i++){const l=el('label',key==='paradise'||key==='box'?`Feeling ${i+1}`:`Reason ${i+1}`),n=el('input');n.name=key+i;n.required=true;n.maxLength=500;l.append(n);row.append(l);}box.append(row);$('questions').append(box);}
const profileFields={
 gender:['Your gender',['woman','man','nonbinary','self-described']],
 seeking:['Who would you like to meet?',['woman','man','nonbinary','any']],
 relationship_goal:['Relationship goal',['long-term','marriage','dating','friendship','open-to-exploring']],
 current_location:['Current city / region (private)',null],
 min_age:['Minimum preferred age',null],max_age:['Maximum preferred age',null],
 interests:['Interests (comma separated, optional)',null],
 children:['Children and family plans',['prefer-not-to-say','want-children','have-children','do-not-want','open']],
 smoking:['Smoking preference',['prefer-not-to-say','non-smoker','smoker','open']],
};
for(const [key,[title,options]] of Object.entries(profileFields)){
 const l=el('label',title),n=el(options?'select':'input');n.name=key;
 if(options){const empty=el('option','Choose an option');empty.value='';n.append(empty);for(const v of options){const o=el('option',v.replaceAll('-',' '));o.value=v;n.append(o);}}
 else if(key.endsWith('age')){n.type='number';n.min=18;n.max=120;n.value=key==='min_age'?18:99;}else n.maxLength=key==='interests'?500:200;
 n.required=!['interests','children','smoking'].includes(key);l.append(n);$('match-fields').append(l);
}
async function api(path,data){const r=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const result=await r.json();if(!r.ok)throw Error(result.error);return result;}
function status(s){$('status').textContent=s;}
function symbolCards(o, privateDetails=false, subject='me'){
 const grid=el('div');grid.className='symbol-grid';
 for(const [icon,title,value] of [['✦','Sun sign',o.sun_sign],['♧','Chinese zodiac',o.chinese_zodiac],['◎','Life path',o.life_path],['♡','Name number',o.name_number??'Unavailable']]){
  const key={'Sun sign':'sun_sign','Chinese zodiac':'chinese_zodiac','Life path':'life_path','Name number':'name_number'}[title];
  const card=el('a');card.className='symbol-tile';card.href='/symbols/'+subject+'/'+key;card.setAttribute('aria-label',`${title}: ${value}. Read meaning and personality themes.`);card.append(el('span',icon),el('small',title),el('h3',String(value)),el('p',o.meanings[key]),el('strong','Explore meaning →'));grid.append(card);
 }
 if(privateDetails&&o.breakdown)grid.append(el('p',o.breakdown.method));return grid;
}
function showOverview(o){
 $('overview').replaceChildren(symbolCards(o,true),el('p',o.chinese_zodiac_note),el('p',o.birth_chart_status),el('p','Traditional symbolic associations for reflection and entertainment, not personality diagnoses.'));
}
function view(panel,button){
 for(const id of ['profile','matches','symbol-panel','privacy-panel'])$(id).hidden=id!==panel;
 for(const id of ['edit','discover','symbols','privacy'])$(id).setAttribute('aria-pressed',String(id===button));
 $(panel).scrollIntoView({block:'start'});
}
function authMode(register){
 $('confirm-label').hidden=!register;$('adult-label').hidden=!register;
 $('auth-form').confirm_password.required=register;
 $('auth-form').adult.required=register;
 $('auth-form').password.autocomplete=register?'new-password':'current-password';
 $('auth-submit').value=register?'register':'login';$('auth-submit').textContent=register?'Create account →':'Sign in →';
 $('join-mode').setAttribute('aria-pressed',String(register));$('login-mode').setAttribute('aria-pressed',String(!register));
}
$('join-mode').onclick=()=>authMode(true);$('login-mode').onclick=()=>authMode(false);
$('symbols').onclick=()=>view('symbol-panel','symbols');$('privacy').onclick=()=>view('privacy-panel','privacy');
$('visibility-edit').onclick=()=>{$('edit').click();$('profile-form').discoverable.focus();};
authMode(true);
async function load(){try{const me=await api('me');$('auth').hidden=true;$('account').hidden=false;if(me.profile){const f=$('profile-form');for(const [k,v] of Object.entries(me.profile)){if(k==='preferences'){for(const [name,value] of Object.entries(v))f.elements[name].value=value;}else if(k==='answers'){for(const [name,a] of Object.entries(v)){f.elements[name].value=a.choice;a.words.forEach((w,i)=>f.elements[name+i].value=w);}}else if(f.elements[k]){if(k==='discoverable')f.elements[k].checked=v;else f.elements[k].value=v;}}photoIds=[...new Set([...(me.profile.photos||[]),...(me.uploaded_photos||[])])];if(!me.profile.preferences.communication)f.elements.communication.value=me.profile.preferences.moods;renderPhotos();showOverview(me.overview);}else{photoIds=me.uploaded_photos||[];renderPhotos();}}catch(e){$('auth').hidden=false;$('account').hidden=true;}}
$('auth-form').onsubmit=async e=>{e.preventDefault();const f=e.target;try{if(e.submitter.value==='register'&&f.password.value!==f.confirm_password.value)throw Error('Passwords must match.');await api(e.submitter.value,{email:f.email.value,password:f.password.value,adult:f.adult.checked});f.password.value='';f.confirm_password.value='';status('Welcome. Build your story below.');await load();}catch(e){status(e.message);}};
$('profile-form').onsubmit=async e=>{e.preventDefault();const f=e.target,p={preferences:{},answers:{}};for(const k of ['first_name','last_name','birth_date','birth_time','birth_location','bio','birth_name',...Object.keys(profileFields)])p[k]=f.elements[k].value;p.min_age=Number(p.min_age);p.max_age=Number(p.max_age);p.discoverable=f.discoverable.checked;p.photos=[...photoIds];for(const k in categories)p.preferences[k]=f.elements[k].value;for(const k in questions)p.answers[k]={choice:f.elements[k].value||(k==='paradise'?'My own paradise':'White box'),words:[0,1,2].map(i=>f.elements[k+i].value)};try{const r=await api('profile',p);showOverview(r.overview);view('symbol-panel','symbols');status('Your story is saved. Reflections remain private.');}catch(e){status(e.message);}};
$('edit').onclick=()=>view('profile','edit');
$('discover').onclick=async()=>{try{const {matches}=await api('matches');view('matches','discover');$('results').replaceChildren();if(!matches.length){const empty=el('article');empty.className='empty-state';empty.append(el('h3','Your next connection is still ahead'),el('p','No profiles match your preferences yet. You can update your age range and preferences in My story.'));$('results').append(empty);}for(const m of matches){const card=el('article');card.append(el('h3',m.name),el('p',m.bio),el('strong',`${m.compatibility.score}% symbolic compatibility`),el('p',`${m.overview.sun_sign} · ${m.overview.chinese_zodiac} · Life path ${m.overview.life_path}`));for(const [k,v] of Object.entries(m.compatibility.categories))card.append(el('p',`${categories[k]||profileFields[k]?.[0]||k}: ${v}% preference alignment`));for(const id of m.photos||[]){const img=el('img');img.src='/api/photos/'+id;img.alt=m.name+' — profile photo';img.className='member-photo';card.append(img);}card.append(symbolCards(m.overview,false,m.id));for(const [label,domain] of Object.entries(m.compatibility.domains)){const d=el('details');d.append(el('summary',`${label}: ${domain.score}% preference alignment`),el('p',domain.basis));card.append(d);}card.append(el('p',m.compatibility.explanation));$('results').append(card);}status('Matches use entertainment rules and your stated preferences.');}catch(e){status(e.message);}};
$('logout').onclick=async()=>{try{await api('logout',{});location.reload();}catch(e){status(e.message);}};
$('delete').onclick=async()=>{if(confirm('Permanently delete your account and private answers?'))try{await api('delete',{});location.reload();}catch(e){status(e.message);}};
let photoIds=[];
function renderPhotos(){
 $('photo-list').replaceChildren();photoIds.forEach((id,i)=>{const card=el('article'),img=el('img');img.src='/api/photos/'+id;img.alt=i===0?'Your profile picture':'Your photo '+(i+1);img.className='member-photo';card.append(img,el('p',i===0?'Profile picture':'Gallery photo'));const primary=el('button','Set as profile picture');primary.type='button';primary.onclick=()=>{photoIds=[id,...photoIds.filter(x=>x!==id)];renderPhotos();status('Save your profile to apply the new order.');};const remove=el('button','Remove');remove.type='button';remove.onclick=async()=>{try{await api('photos/delete',{id});photoIds=photoIds.filter(x=>x!==id);renderPhotos();}catch(e){status(e.message);}};card.append(primary,remove);$('photo-list').append(card);});
}
async function preparePhoto(file){
 if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>10000000)throw Error('Choose a JPEG, PNG or WebP under 10 MB.');
 const bitmap=await createImageBitmap(file);try{const scale=Math.min(1,1200/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);let encoded;for(const quality of [.85,.65,.45,.25]){encoded=canvas.toDataURL('image/jpeg',quality).split(',')[1];if(encoded.length<=660000)return encoded;}throw Error('Photo is too complex. Choose a smaller image.');}finally{bitmap.close();}
}
$('photo-upload').onchange=async e=>{const input=e.target;input.disabled=true;try{if(photoIds.length+input.files.length>6)throw Error('Choose up to six photos total.');for(const file of input.files){const result=await api('photos',{image:await preparePhoto(file)});photoIds.push(result.id);renderPhotos();}status('Photos uploaded. Save your profile to share them with eligible matches.');}catch(e){status(e.message);}finally{input.value='';input.disabled=false;}};
load().then(()=>{if(!$('account').hidden){if(location.hash==='#matches')$('discover').click();else if(location.hash==='#symbols')$('symbols').click();}});
