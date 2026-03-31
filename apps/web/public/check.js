(function(){
  var m = document.getElementById('app-load-marker');
  if (m) {
    m.style.background = '#166534';
    m.style.color = '#dcfce7';
    m.textContent = 'Scripts loaded. If content still missing, Next.js chunks may have failed.';
  }
})();
