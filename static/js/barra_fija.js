// Barra fija arriba (toma / inspección, 29/09/2026): queda pegada debajo de
// la barra AGENCIEROS del celu, y los títulos de sección quedan pegados
// debajo de ella. Se miden las alturas reales para no tapar nada.
(function () {
  var barra = document.getElementById('barra-fija');
  if (!barra) return;
  function medir() {
    var top = document.querySelector('.mobile-topbar');
    var altoTop = top && getComputedStyle(top).display !== 'none' ? top.offsetHeight : 0;
    document.documentElement.style.setProperty('--alto-topbar', altoTop + 'px');
    document.documentElement.style.setProperty('--alto-barra-fija', barra.offsetHeight + 'px');
  }
  medir();
  window.addEventListener('resize', medir);
})();
