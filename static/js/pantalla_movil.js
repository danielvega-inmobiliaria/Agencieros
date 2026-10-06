// Celu (06/10/2026): 1) al scrollear, el título de la pantalla pasa a la barra
// de arriba (más chico); 2) las filas marcadas .sticky-movil quedan fijas
// debajo de esa barra; 3) botón flotante "volver arriba" solo si la pantalla
// es larga y ya se scrolleó.
(function () {
  var mq = window.matchMedia('(max-width: 700px)');
  var barra = document.querySelector('.mobile-topbar');
  var texto = document.getElementById('mobile-brand-texto');
  var h1 = document.querySelector('.topbar h1');
  var titulo = h1 ? h1.textContent.trim() : '';
  var marca = texto ? texto.textContent : '';
  var fijas = Array.prototype.slice.call(document.querySelectorAll('.sticky-movil'));

  var btn = document.createElement('button');
  btn.type = 'button'; btn.id = 'btn-arriba'; btn.setAttribute('aria-label', 'Volver arriba');
  btn.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>';
  btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  document.body.appendChild(btn);

  function apilar() {
    var off = mq.matches && barra ? barra.offsetHeight : 0;
    fijas.forEach(function (el) {
      if (!mq.matches) { el.style.top = ''; return; }
      el.style.top = off + 'px';
      off += el.offsetHeight;
    });
    return off;
  }

  var pendiente = false;
  function actualizar() {
    pendiente = false;
    if (!mq.matches) { btn.classList.remove('visible'); if (texto) { texto.textContent = marca; texto.classList.remove('es-titulo'); } return; }
    var alto = barra ? barra.offsetHeight : 0;
    if (texto && titulo && h1) {
      var oculto = h1.getBoundingClientRect().bottom < alto + 4;
      texto.textContent = oculto ? titulo : marca;
      texto.classList.toggle('es-titulo', oculto);
    }
    var largo = document.documentElement.scrollHeight > window.innerHeight * 1.6;
    btn.classList.toggle('visible', largo && window.scrollY > 350);
  }
  function pedir() { if (!pendiente) { pendiente = true; window.requestAnimationFrame(actualizar); } }

  window.addEventListener('scroll', pedir, { passive: true });
  window.addEventListener('resize', function () { apilar(); pedir(); });
  window.addEventListener('load', function () { apilar(); pedir(); });
  apilar(); actualizar();
})();
