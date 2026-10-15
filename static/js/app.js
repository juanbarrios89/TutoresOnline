document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.alert').forEach(x=>setTimeout(()=>{x.style.opacity='0';x.style.transition='.5s'},4000));});
function toggleFavorite(id,el){fetch('/favorito/'+id,{method:'POST'}).then(r=>r.json()).then(d=>{el.textContent=d.favorito?'❤️':'♡'});}
