(()=>{
const nav=document.querySelector('.member-nav');
const primary=['discovery-nav','standouts-nav','likes-nav','chat-nav','edit'];
const symbols=['⌂','☆','♡','▱','○'];
const menu=document.createElement('details');menu.className='account-menu';
const summary=document.createElement('summary');summary.textContent='Account & more';menu.append(summary);
for(const child of [...nav.children])if(!primary.includes(child.id))menu.append(child);
nav.before(menu);
primary.forEach((id,i)=>{const b=document.getElementById(id);const label=['Discover','Standouts','Likes','Chats','Profile'][i];b.textContent='';const icon=document.createElement('span');icon.textContent=symbols[i];icon.setAttribute('aria-hidden','true');const text=document.createElement('small');text.textContent=label;b.append(icon,text);b.setAttribute('aria-label',label);});
function edit(){document.getElementById('profile-form').hidden=false;document.getElementById('profile-preview').hidden=true;document.getElementById('profile-edit-tab').setAttribute('aria-selected','true');document.getElementById('preview-profile').setAttribute('aria-selected','false');}
document.getElementById('profile-edit-tab').onclick=edit;
document.getElementById('edit').addEventListener('click',edit);
let notificationState=null,badgeBusy=false;
const badges=[['likes-nav','likes','Likes'],['chat-nav','messages','Chats'],['discover','matches','My matches']];
for(const [id] of badges){const b=document.createElement('span');b.className='notification-badge';b.hidden=true;document.getElementById(id).append(b);}
async function updateBadges(){if(badgeBusy||document.hidden||account.hidden)return;badgeBusy=true;try{notificationState=await api('notifications/summary');for(const [id,key,label] of badges){const count=notificationState.counts[key]||0,node=document.getElementById(id),badge=node.querySelector('.notification-badge');badge.textContent=count>99?'99+':String(count);badge.hidden=!count;node.setAttribute('aria-label',label+(count?', '+count+' unread notifications':''));}const count=notificationState.counts.matches||0;summary.textContent='Account & more'+(count?' · '+count+' new match notifications':'');}catch(e){/* Preserve current badges during transient connection failures. */}finally{badgeBusy=false;}}
for(const [id,category] of badges)document.getElementById(id).addEventListener('click',async()=>{if(!notificationState)return;const through=notificationState.through_id;try{await api('notifications/read',{category,through_id:through});await updateBadges();}catch(e){status(e.message);}});
document.getElementById('read-notifications').addEventListener('click',()=>setTimeout(updateBadges,500));
const account=document.getElementById('account');
setInterval(updateBadges,10000);
document.addEventListener('visibilitychange',updateBadges);

new MutationObserver(()=>{document.body.classList.toggle('member-app',!account.hidden);updateBadges();}).observe(account,{attributes:true,attributeFilter:['hidden']});
document.body.classList.toggle('member-app',!account.hidden);updateBadges();
})();
