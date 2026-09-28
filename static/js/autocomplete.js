/**
 * Autocompletar propio (dropdown armado a mano, sin <input list> +
 * <datalist> nativo).
 *
 * Por qué: en iOS Safari, un <input list="..."> muestra las sugerencias
 * del datalist arriba del teclado, en la misma barra de QuickType donde
 * aparecen las sugerencias de palabras al escribir — se ve exactamente
 * igual que el autocorrector y confunde (ver charla 13-14/09/2026,
 * capturas del formulario de Toma en el celular). Este helper arma un
 * desplegable propio, debajo del campo, igual en cualquier navegador.
 *
 * Uso:
 *   attachAutocomplete(inputEl, function() { return ["A", "B", "C"]; });
 *   attachAutocomplete(inputEl, obtenerValores, function(valorElegido) { ... });
 *
 * - `obtenerValores()` se llama cada vez que hay que mostrar el
 *   desplegable (al enfocar el campo o al tipear) y devuelve la lista
 *   completa de opciones válidas EN ESE MOMENTO — el filtrado por lo ya
 *   tipeado lo hace este helper. Que sea una función (no una lista fija)
 *   es lo que permite que options dependan de otros campos (ej. Modelo
 *   depende de la Marca y el Año ya elegidos) sin tener que estar
 *   recalculando datalists a mano en cada cambio.
 * - `onSeleccionar(valor)` (opcional) se llama después de elegir una
 *   opción tocándola/cliqueándola, además del evento 'input' normal que
 *   ya se dispara sobre el campo (así el resto del código reacciona igual
 *   que si lo hubiera tipeado).
 */
function attachAutocomplete(input, obtenerValores, onSeleccionar, opciones) {
  // `opciones.detalle(valor)` (opcional, 24/09/2026): texto chico que se
  // muestra a la derecha de cada ítem sin formar parte del valor elegido
  // -- ej. el precio de cada versión en Consulta de precios.
  var detalle = opciones && opciones.detalle;
  // Opciones de Consulta de precios (28/09/2026, pedido de Daniel):
  // - minCaracteres: no mostrar nada hasta que se tipeen N letras (antes, al
  //   elegir el año aparecía la lista entera de versiones).
  // - mantenerAbierto: la lista NO se cierra al bajar el teclado (blur); se
  //   cierra al elegir una opción o al tocar fuera del buscador, así se
  //   puede scrollear la lista con el teclado guardado.
  // - subirAlMostrar: en celu, sube la pantalla para que el campo quede
  //   arriba y la lista tenga más lugar.
  // - enLinea: la lista ocupa lugar en la página (no flota) y es más alta.
  var minCaracteres = (opciones && opciones.minCaracteres) || 0;
  var mantenerAbierto = !!(opciones && opciones.mantenerAbierto);
  var subirAlMostrar = !!(opciones && opciones.subirAlMostrar);
  var enLinea = !!(opciones && opciones.enLinea);
  var yaSubio = false;
  var wrap = document.createElement("div");
  wrap.className = "autocomplete-wrap";
  input.parentNode.insertBefore(wrap, input);
  wrap.appendChild(input);

  var dd = document.createElement("div");
  dd.className = "autocomplete-dropdown" + (enLinea ? " en-linea" : "");
  dd.style.display = "none";
  wrap.appendChild(dd);

  var activo = -1;

  function seleccionar(valor) {
    input.value = valor;
    // Ojo con el orden: el 'input' que disparamos acá abajo también lo
    // escucha este mismo helper (para refrescar sugerencias mientras se
    // tipea) y puede reabrir el desplegable con la única opción que ya
    // quedó elegida. Por eso cerramos DESPUÉS de disparar el evento, no
    // antes — así gana el cierre.
    input.dispatchEvent(new Event("input", { bubbles: true }));
    cerrar();
    if (onSeleccionar) onSeleccionar(valor);
  }

  function cerrar() {
    dd.style.display = "none";
    activo = -1;
    yaSubio = false;
  }

  function subir() {
    if (!subirAlMostrar || yaSubio || window.innerWidth > 700) return;
    yaSubio = true;
    var barra = document.querySelector(".mobile-topbar");
    var margen = (barra ? barra.offsetHeight : 0) + 8;
    var etiqueta = input.closest(".bp-campo") || wrap;
    var y = etiqueta.getBoundingClientRect().top + window.pageYOffset - margen;
    setTimeout(function () { window.scrollTo({ top: y, behavior: "smooth" }); }, 50);
  }

  function marcarActivo(items) {
    for (var i = 0; i < items.length; i++) items[i].classList.toggle("active", i === activo);
    if (items[activo] && items[activo].scrollIntoView) items[activo].scrollIntoView({ block: "nearest" });
  }

  function mostrar() {
    var texto = input.value.trim().toLowerCase();
    var todas = obtenerValores() || [];
    // Cada palabra tipeada tiene que aparecer en la opción, en cualquier
    // orden (24/09/2026, buscador estilo Decreditos): "etios plat" encuentra
    // "TOYOTA - ETIOS 1.5 4 PTAS PLATINUM". Con una sola palabra es igual
    // que antes (contiene el texto).
    var palabras = texto.split(/\s+/).filter(Boolean);
    var filtradas = palabras.length
      ? todas.filter(function (v) {
          var s = String(v).toLowerCase();
          return palabras.every(function (p) { return s.indexOf(p) !== -1; });
        })
      : todas;

    dd.innerHTML = "";
    activo = -1;
    if (texto.length < minCaracteres) { dd.style.display = "none"; return; }
    if (!filtradas.length) { dd.style.display = "none"; return; }

    filtradas.forEach(function (valor) {
      var item = document.createElement("div");
      item.className = "autocomplete-item";
      item.setAttribute("data-valor", valor);
      var extra = detalle ? detalle(valor) : "";
      if (extra) {
        var txt = document.createElement("span");
        txt.className = "autocomplete-texto";
        txt.textContent = valor;
        var det = document.createElement("span");
        det.className = "autocomplete-detalle";
        det.textContent = extra;
        item.appendChild(txt);
        item.appendChild(det);
      } else {
        item.textContent = valor;
      }
      // mousedown (no click): dispara antes que el blur del input, así el
      // toque en el ítem no se pierde cuando el campo pierde el foco.
      item.addEventListener("mousedown", function (e) {
        e.preventDefault();
        seleccionar(valor);
      });
      dd.appendChild(item);
    });
    dd.scrollTop = 0;
    dd.style.display = "block";
    subir();
  }

  input.addEventListener("focus", mostrar);
  input.addEventListener("input", mostrar);
  input.addEventListener("blur", function () {
    if (!mantenerAbierto) setTimeout(cerrar, 120);
  });
  if (mantenerAbierto) {
    document.addEventListener("pointerdown", function (e) {
      if (!wrap.contains(e.target)) cerrar();
    });
  }
  input.addEventListener("keydown", function (e) {
    if (dd.style.display === "none") return;
    var items = dd.querySelectorAll(".autocomplete-item");
    if (!items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activo = Math.min(activo + 1, items.length - 1);
      marcarActivo(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activo = Math.max(activo - 1, 0);
      marcarActivo(items);
    } else if (e.key === "Enter") {
      if (activo >= 0) { e.preventDefault(); seleccionar(items[activo].getAttribute("data-valor")); }
    } else if (e.key === "Escape") {
      cerrar();
    }
  });

  return { refrescar: mostrar, cerrar: cerrar };
}
