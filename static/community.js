// All navigation stays on this site. Published member stories require operator approval.
fetch('/api/public/stories').then(r=>r.ok?r.json():{stories:[]}).then(r=>{const box=document.getElementById('stories');for(const story of r.stories||[]){const p=document.createElement('p');p.textContent=story.story;box.append(p);}}).catch(()=>{});
