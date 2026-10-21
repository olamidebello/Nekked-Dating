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
const account=document.getElementById('account');
new MutationObserver(()=>{document.body.classList.toggle('member-app',!account.hidden);}).observe(account,{attributes:true,attributeFilter:['hidden']});
document.body.classList.toggle('member-app',!account.hidden);
})();
