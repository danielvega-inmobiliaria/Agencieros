// Carrusel de fotos de la ficha comercial. Sirve para una ficha suelta y para
// el visor "Ver Fichas" (varias fichas en la misma página): cada .carrusel-wrap
// se maneja por separado. En el visor (body.modo-visor) las fotos no se
// deslizan con el dedo -- ese gesto lo usa el visor para cambiar de vehículo --
// y se pasan con las flechas, los puntos o tocando la foto.
(function () {
  function iniciar(wrap) {
    var carrusel = wrap.querySelector('.carrusel');
    if (!carrusel) return;
    var dots = wrap.querySelector('.dots');
    var contador = wrap.querySelector('.foto-contador');
    var izq = wrap.querySelector('.carrusel-flecha.izq');
    var der = wrap.querySelector('.carrusel-flecha.der');
    var total = carrusel.children.length;

    function actual() {
      return carrusel.clientWidth ? Math.round(carrusel.scrollLeft / carrusel.clientWidth) : 0;
    }
    function marcar(idx) {
      if (dots) {
        Array.prototype.forEach.call(dots.children, function (dot, i) {
          dot.classList.toggle('activo', i === idx);
        });
      }
      if (contador) { contador.textContent = (idx + 1) + '/' + total; }
    }
    function irAFoto(idx) {
      carrusel.scrollTo({ left: idx * carrusel.clientWidth, behavior: 'smooth' });
      marcar(idx);
    }

    carrusel.addEventListener('scroll', function () { marcar(actual()); });
    if (dots) {
      Array.prototype.forEach.call(dots.children, function (dot) {
        dot.addEventListener('click', function () { irAFoto(parseInt(dot.dataset.idx, 10)); });
      });
    }
    if (izq) izq.addEventListener('click', function () { irAFoto((actual() - 1 + total) % total); });
    if (der) der.addEventListener('click', function () { irAFoto((actual() + 1) % total); });
    if (total > 1 && document.body.classList.contains('modo-visor')) {
      carrusel.addEventListener('click', function () { irAFoto((actual() + 1) % total); });
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.carrusel-wrap'), iniciar);
})();
