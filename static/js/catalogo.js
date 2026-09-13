/**
 * Selects en cascada Marca -> Modelo -> Versión, armados a partir del
 * catálogo unificado de toda la app (ver `obtener_catalogo()` en
 * database.py, inyectado como `catalogo_json` en cada página).
 *
 * Objetivo: que Marca/Modelo/Versión se elijan siempre de la misma lista
 * en Stock, Banco de pedidos, Red de Agencieros, Tomas y Tasación, para no
 * terminar con "Corolla" / "corolla " / "COROLLA" como si fueran distintos.
 *
 * Si el vehículo es de una marca/modelo/versión que todavía no está en el
 * catálogo, el último ítem de cada select es "+ nueva/o...": al elegirlo,
 * ese campo se convierte en un input de texto libre. Lo que se cargue ahí
 * pasa a formar parte del catálogo para el resto de la app la próxima vez
 * que se abra un formulario (el catálogo se recalcula en cada request).
 *
 * Uso:
 *   initCatalogoSelects(catalogo, 'marca', 'modelo', 'version');
 *   initCatalogoSelects(catalogo, 'marca', 'modelo', 'version', {marca: v.marca, modelo: v.modelo, version: v.version});
 */
function initCatalogoSelects(catalogo, marcaId, modeloId, versionId, valoresIniciales) {
  var NUEVA = "__nueva__";
  var marcaSel = document.getElementById(marcaId);
  if (!marcaSel) return;
  var modeloSel = modeloId ? document.getElementById(modeloId) : null;
  var versionSel = versionId ? document.getElementById(versionId) : null;

  function ordenar(lista) {
    return lista.slice().sort(function (a, b) { return a.localeCompare(b, "es"); });
  }

  function llenarSelect(sel, valores, placeholder, opcionNueva) {
    if (!sel) return;
    sel.innerHTML = "";
    var optPlaceholder = document.createElement("option");
    optPlaceholder.value = "";
    optPlaceholder.textContent = placeholder;
    sel.appendChild(optPlaceholder);
    ordenar(valores).forEach(function (v) {
      var opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    });
    var optNueva = document.createElement("option");
    optNueva.value = NUEVA;
    optNueva.textContent = opcionNueva;
    sel.appendChild(optNueva);
  }

  function convertirATexto(sel, valorInicial) {
    if (!sel || sel.tagName !== "SELECT") return sel;
    var input = document.createElement("input");
    input.type = "text";
    input.name = sel.name;
    input.id = sel.id;
    input.className = sel.className;
    if (sel.required) input.required = true;
    input.value = valorInicial || "";
    input.placeholder = sel.getAttribute("data-placeholder-libre") || "";
    sel.replaceWith(input);
    return input;
  }

  function seleccionarSiExiste(sel, valor) {
    if (!sel || !valor) return false;
    var existe = Array.prototype.some.call(sel.options, function (o) { return o.value === valor; });
    if (existe) sel.value = valor;
    return existe;
  }

  function modelosDe(marca) {
    return (catalogo[marca]) ? Object.keys(catalogo[marca]) : [];
  }

  function versionesDe(marca, modelo) {
    return (catalogo[marca] && catalogo[marca][modelo]) ? catalogo[marca][modelo] : [];
  }

  function alCambiarMarca() {
    if (marcaSel.value === NUEVA) {
      convertirATexto(marcaSel, "");
      if (modeloSel) convertirATexto(modeloSel, "");
      if (versionSel) convertirATexto(versionSel, "");
      return;
    }
    if (modeloSel) {
      llenarSelect(modeloSel, modelosDe(marcaSel.value), "Modelo", "+ Modelo nuevo...");
      modeloSel.disabled = !marcaSel.value;
    }
    if (versionSel) {
      llenarSelect(versionSel, [], "Versión", "+ Versión nueva...");
      versionSel.disabled = true;
    }
  }

  function alCambiarModelo() {
    if (modeloSel.value === NUEVA) {
      convertirATexto(modeloSel, "");
      if (versionSel) convertirATexto(versionSel, "");
      return;
    }
    if (versionSel) {
      llenarSelect(versionSel, versionesDe(marcaSel.value, modeloSel.value), "Versión", "+ Versión nueva...");
      versionSel.disabled = !modeloSel.value;
    }
  }

  function alCambiarVersion() {
    if (versionSel.value === NUEVA) {
      convertirATexto(versionSel, "");
    }
  }

  // --- Armado inicial ---
  llenarSelect(marcaSel, Object.keys(catalogo), "Marca", "+ Marca nueva...");
  marcaSel.addEventListener("change", alCambiarMarca);

  if (modeloSel) {
    llenarSelect(modeloSel, [], "Modelo", "+ Modelo nuevo...");
    modeloSel.disabled = true;
    modeloSel.addEventListener("change", alCambiarModelo);
  }
  if (versionSel) {
    llenarSelect(versionSel, [], "Versión", "+ Versión nueva...");
    versionSel.disabled = true;
    versionSel.addEventListener("change", alCambiarVersion);
  }

  // --- Pre-selección (editar un registro existente, o venir con datos ya sabidos) ---
  var vi = valoresIniciales || {};
  if (vi.marca) {
    if (seleccionarSiExiste(marcaSel, vi.marca)) {
      if (modeloSel) {
        llenarSelect(modeloSel, modelosDe(vi.marca), "Modelo", "+ Modelo nuevo...");
        modeloSel.disabled = false;
        if (vi.modelo) {
          if (seleccionarSiExiste(modeloSel, vi.modelo)) {
            if (versionSel) {
              llenarSelect(versionSel, versionesDe(vi.marca, vi.modelo), "Versión", "+ Versión nueva...");
              versionSel.disabled = false;
              if (vi.version && !seleccionarSiExiste(versionSel, vi.version)) {
                convertirATexto(versionSel, vi.version);
              }
            }
          } else {
            convertirATexto(modeloSel, vi.modelo);
            if (versionSel) convertirATexto(versionSel, vi.version || "");
          }
        }
      }
    } else {
      convertirATexto(marcaSel, vi.marca);
      if (modeloSel) convertirATexto(modeloSel, vi.modelo || "");
      if (versionSel) convertirATexto(versionSel, vi.version || "");
    }
  }
}
