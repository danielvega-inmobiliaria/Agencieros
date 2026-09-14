/**
 * Campos de Año / Marca / Modelo / Versión con autocompletar, armados a
 * partir del catálogo unificado de toda la app (ver `obtener_catalogo()`
 * en database.py, inyectado como `catalogo_json` en cada página).
 *
 * Convierte los <select id="..."> vacíos de Marca/Modelo/Versión en
 * <input type="text" list="..."> con su <datalist> de sugerencias: se
 * escribe directo en vez de revolver un desplegable larguísimo. Cargar
 * algo que todavía no está en el catálogo es simplemente escribirlo: no
 * hace falta un paso aparte de "+ nueva/o...".
 *
 * Modelo funciona sin elegir Marca antes: si el modelo tipeado existe en
 * una sola marca del catálogo, esa marca se completa sola.
 *
 * Año primero (13-14/09/2026): si se pasa `anioId`, ese campo (un input
 * numérico ya existente en el HTML, no se convierte) pasa a filtrar todo
 * lo demás — Marca, Modelo y Versión solo sugieren lo que el catálogo
 * tiene efectivamente cargado para ese año puntual. Una versión sin año
 * conocido en ninguna fuente (ej. un pedido de cliente sin permuta) se
 * sigue mostrando igual, para no ocultar datos por esa falta.
 *
 * Uso:
 *   // Con Año primero (Toma, Stock, Red, permuta de Pedidos):
 *   initCatalogoSelects(catalogo, 'anio', 'marca', 'modelo', 'version');
 *   initCatalogoSelects(catalogo, 'anio', 'marca', 'modelo', 'version', {anio: v.anio, marca: v.marca, modelo: v.modelo, version: v.version});
 *
 *   // Sin Año (ej. pedido de cliente: busca por Año desde/hasta, un rango,
 *   // no un año puntual — se pasa null y el campo queda como antes):
 *   initCatalogoSelects(catalogo, null, 'marca', 'modelo', 'version');
 */
function initCatalogoSelects(catalogo, anioId, marcaId, modeloId, versionId, valoresIniciales) {
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
    input.placeholder = placeholderDe(id);

    el.replaceWith(input);
    input.insertAdjacentElement("afterend", datalist);
    return input;
  }

  // El campo Año ya existe en el HTML como <input type="number">: no lo
  // convertimos, solo le sumamos un datalist con los años que aparecen en
  // el catálogo, para que también se pueda tipear con sugerencias.
  function prepararAnio(id) {
    if (!id) return null;
    var el = document.getElementById(id);
    if (!el) return null;
    var datalistId = id + "-datalist";
    var datalist = document.getElementById(datalistId);
    if (!datalist) {
      datalist = document.createElement("datalist");
      datalist.id = datalistId;
      el.insertAdjacentElement("afterend", datalist);
    }
    el.setAttribute("list", datalistId);
    return el;
  }

  var anioEl = prepararAnio(anioId);
  var marcaEl = convertirAInput(marcaId);
  if (!marcaEl) return;
  var modeloEl = modeloId ? convertirAInput(modeloId) : null;
  var versionEl = versionId ? convertirAInput(versionId) : null;

  function anioActual() {
    if (!anioEl) return null;
    var v = parseInt(anioEl.value, 10);
    return isNaN(v) ? null : v;
  }

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

  // Una versión "calza" con el año pedido si no hay año pedido, si esa
  // versión no tiene ningún año conocido (no se filtra por falta de dato),
  // o si el año pedido está entre los suyos.
  function versionCalzaConAnio(anios, anio) {
    return !anio || !anios || anios.length === 0 || anios.indexOf(anio) !== -1;
  }

  function modeloTieneAnio(marca, modelo, anio) {
    var versiones = (catalogo[marca] && catalogo[marca][modelo]) || {};
    return Object.keys(versiones).some(function (v) { return versionCalzaConAnio(versiones[v], anio); });
  }

  function marcaTieneAnio(marca, anio) {
    var modelos = catalogo[marca] || {};
    return Object.keys(modelos).some(function (modelo) { return modeloTieneAnio(marca, modelo, anio); });
  }

  function todosLosAnios() {
    var vistos = {};
    var out = [];
    Object.keys(catalogo).forEach(function (marca) {
      Object.keys(catalogo[marca]).forEach(function (modelo) {
        var versiones = catalogo[marca][modelo];
        Object.keys(versiones).forEach(function (v) {
          versiones[v].forEach(function (a) {
            if (!vistos[a]) { vistos[a] = true; out.push(String(a)); }
          });
        });
      });
    });
    return out;
  }

  function marcasParaAnio(anio) {
    return Object.keys(catalogo).filter(function (marca) { return marcaTieneAnio(marca, anio); });
  }

  function modelosDe(marca, anio) {
    if (!catalogo[marca]) return [];
    return Object.keys(catalogo[marca]).filter(function (modelo) { return modeloTieneAnio(marca, modelo, anio); });
  }

  function todosLosModelos(anio) {
    var vistos = {};
    var out = [];
    Object.keys(catalogo).forEach(function (marca) {
      modelosDe(marca, anio).forEach(function (modelo) {
        if (!vistos[modelo]) { vistos[modelo] = true; out.push(modelo); }
      });
    });
    return out;
  }

  function marcasDeModelo(modelo, anio) {
    return Object.keys(catalogo).filter(function (marca) {
      return Object.prototype.hasOwnProperty.call(catalogo[marca] || {}, modelo) && modeloTieneAnio(marca, modelo, anio);
    });
  }

  function versionesDe(marca, modelo, anio) {
    var out = [];
    if (marca) {
      var versiones = (catalogo[marca] && catalogo[marca][modelo]) || {};
      Object.keys(versiones).forEach(function (v) {
        if (versionCalzaConAnio(versiones[v], anio)) out.push(v);
      });
      return out;
    }
    // Sin marca elegida: versiones de ese modelo en cualquier marca que lo tenga.
    var vistos = {};
    marcasDeModelo(modelo, anio).forEach(function (m) {
      var versiones = catalogo[m][modelo] || {};
      Object.keys(versiones).forEach(function (v) {
        if (versionCalzaConAnio(versiones[v], anio) && !vistos[v]) { vistos[v] = true; out.push(v); }
      });
    });
    return out;
  }

  function refrescarMarcas() {
    if (!anioEl) return; // sin campo Año, la lista de marcas es fija (armada al inicio)
    llenarDatalist(marcaEl, marcasParaAnio(anioActual()));
  }

  function refrescarModelos() {
    if (!modeloEl) return;
    var marca = marcaEl.value.trim();
    var anio = anioActual();
    llenarDatalist(modeloEl, marca ? modelosDe(marca, anio) : todosLosModelos(anio));
  }

  function refrescarVersiones() {
    if (!versionEl) return;
    var marca = marcaEl.value.trim();
    var modelo = modeloEl ? modeloEl.value.trim() : "";
    llenarDatalist(versionEl, modelo ? versionesDe(marca, modelo, anioActual()) : []);
  }

  if (anioEl) {
    llenarDatalist(anioEl, todosLosAnios());
    anioEl.addEventListener("input", function () {
      refrescarMarcas();
      refrescarModelos();
      refrescarVersiones();
    });
  }

  marcaEl.addEventListener("input", function () {
    refrescarModelos();
    refrescarVersiones();
  });

  if (modeloEl) {
    modeloEl.addEventListener("input", function () {
      // Si todavía no eligieron marca y el modelo tipeado existe en una
      // sola marca del catálogo (para el año elegido, si hay), la
      // completamos sola.
      if (!marcaEl.value.trim()) {
        var marcas = marcasDeModelo(modeloEl.value.trim(), anioActual());
        if (marcas.length === 1) {
          marcaEl.value = marcas[0];
          refrescarModelos();
        }
      }
      refrescarVersiones();
    });
  }

  // --- Armado inicial ---
  llenarDatalist(marcaEl, anioEl ? marcasParaAnio(anioActual()) : Object.keys(catalogo));
  refrescarModelos();
  refrescarVersiones();

  // --- Pre-selección (editar un registro existente, o venir con datos ya sabidos) ---
  var vi = valoresIniciales || {};
  if (vi.anio && anioEl) { anioEl.value = vi.anio; refrescarMarcas(); }
  if (vi.marca) { marcaEl.value = vi.marca; refrescarModelos(); }
  if (vi.modelo && modeloEl) { modeloEl.value = vi.modelo; }
  refrescarVersiones();
  if (vi.version && versionEl) versionEl.value = vi.version;
}
