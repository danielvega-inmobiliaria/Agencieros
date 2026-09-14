/**
 * Campos de Marca / Modelo / Versión con autocompletar, armados a partir
 * del catálogo unificado de toda la app (ver `obtener_catalogo()` en
 * database.py, inyectado como `catalogo_json` en cada página).
 *
 * Convierte los <select id="..."> vacíos del HTML en <input type="text"
 * list="..."> con su <datalist> de sugerencias: se escribe directo en vez
 * de revolver un desplegable larguísimo (antes, con varias marcas
 * cargadas, en el celular se volvía una lista interminable — ver charla
 * 13/09/2026). Cargar algo que todavía no está en el catálogo es
 * simplemente escribirlo: no hace falta un paso aparte de "+ nueva/o...".
 *
 * Modelo funciona sin elegir Marca antes: con Marca vacía, sugiere TODOS
 * los modelos de cualquier marca; si el modelo tipeado existe en una sola
 * marca del catálogo, esa marca se completa sola (si existe en varias, se
 * deja para que la escriban — ya es un campo de texto, no un desplegable
 * gigante).
 *
 * Uso (misma firma que antes):
 *   initCatalogoSelects(catalogo, 'marca', 'modelo', 'version');
 *   initCatalogoSelects(catalogo, 'marca', 'modelo', 'version', {marca: v.marca, modelo: v.modelo, version: v.version});
 */
function initCatalogoSelects(catalogo, marcaId, modeloId, versionId, valoresIniciales) {
  var ETIQUETAS = { marca: "Marca", modelo: "Modelo", version: "Versión" };
  function capitalizar(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function placeholderDe(id) {
    var partes = id.split("_");
    var ultimo = partes[partes.length - 1];
    var base = ETIQUETAS[ultimo] || capitalizar(ultimo);
    if (partes.length === 1) return base;
    return capitalizar(partes.slice(0, -1).join(" ")) + " · " + base;
  }

  function convertirAInput(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    if (el.tagName !== "SELECT") return el; // ya convertido antes (no debería pasar)

    var datalistId = id + "-datalist";
    var datalist = document.createElement("datalist");
    datalist.id = datalistId;

    var input = document.createElement("input");
    input.type = "text";
    input.name = el.name;
    input.id = el.id;
    input.className = el.className;
    if (el.required) input.required = true;
    input.autocomplete = "off";
    input.setAttribute("list", datalistId);
    // El data-placeholder-libre de los templates viejos decía "Marca nueva",
    // pensado para cuando el campo recién se volvía editable a mano. Ahora
    // el campo es de texto desde el arranque, así que el placeholder neutro
    // (id capitalizado) queda mejor para cualquiera, no solo para carga nueva.
    input.placeholder = placeholderDe(id);

    el.replaceWith(input);
    input.insertAdjacentElement("afterend", datalist);
    return input;
  }

  var marcaEl = convertirAInput(marcaId);
  if (!marcaEl) return;
  var modeloEl = modeloId ? convertirAInput(modeloId) : null;
  var versionEl = versionId ? convertirAInput(versionId) : null;

  function ordenar(lista) {
    return lista.slice().sort(function (a, b) { return a.localeCompare(b, "es"); });
  }

  function llenarDatalist(input, valores) {
    var dl = document.getElementById(input.getAttribute("list"));
    if (!dl) return;
    dl.innerHTML = "";
    ordenar(valores).forEach(function (v) {
      var opt = document.createElement("option");
      opt.value = v;
      dl.appendChild(opt);
    });
  }

  function todosLosModelos() {
    var vistos = {};
    var out = [];
    Object.keys(catalogo).forEach(function (marca) {
      Object.keys(catalogo[marca]).forEach(function (modelo) {
        if (!vistos[modelo]) { vistos[modelo] = true; out.push(modelo); }
      });
    });
    return out;
  }

  function marcasDeModelo(modelo) {
    return Object.keys(catalogo).filter(function (marca) {
      return Object.prototype.hasOwnProperty.call(catalogo[marca] || {}, modelo);
    });
  }

  function modelosDe(marca) {
    return catalogo[marca] ? Object.keys(catalogo[marca]) : [];
  }

  function versionesDe(marca, modelo) {
    if (marca) {
      return (catalogo[marca] && catalogo[marca][modelo]) ? catalogo[marca][modelo] : [];
    }
    // Sin marca elegida: versiones de ese modelo en cualquier marca que lo tenga.
    var vistos = {};
    var out = [];
    marcasDeModelo(modelo).forEach(function (m) {
      (catalogo[m][modelo] || []).forEach(function (v) {
        if (!vistos[v]) { vistos[v] = true; out.push(v); }
      });
    });
    return out;
  }

  function refrescarModelos() {
    if (!modeloEl) return;
    var marca = marcaEl.value.trim();
    llenarDatalist(modeloEl, marca ? modelosDe(marca) : todosLosModelos());
  }

  function refrescarVersiones() {
    if (!versionEl) return;
    var marca = marcaEl.value.trim();
    var modelo = modeloEl ? modeloEl.value.trim() : "";
    llenarDatalist(versionEl, modelo ? versionesDe(marca, modelo) : []);
  }

  marcaEl.addEventListener("input", function () {
    refrescarModelos();
    refrescarVersiones();
  });

  if (modeloEl) {
    modeloEl.addEventListener("input", function () {
      // Si todavía no eligieron marca y el modelo tipeado existe en una
      // sola marca del catálogo, la completamos sola.
      if (!marcaEl.value.trim()) {
        var marcas = marcasDeModelo(modeloEl.value.trim());
        if (marcas.length === 1) {
          marcaEl.value = marcas[0];
          refrescarModelos();
        }
      }
      refrescarVersiones();
    });
  }

  // --- Armado inicial ---
  llenarDatalist(marcaEl, Object.keys(catalogo));
  refrescarModelos();
  refrescarVersiones();

  // --- Pre-selección (editar un registro existente, o venir con datos ya sabidos) ---
  var vi = valoresIniciales || {};
  if (vi.marca) { marcaEl.value = vi.marca; refrescarModelos(); }
  if (vi.modelo && modeloEl) { modeloEl.value = vi.modelo; }
  refrescarVersiones();
  if (vi.version && versionEl) versionEl.value = vi.version;
}
