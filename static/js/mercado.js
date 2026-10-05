// Rango de precios de mercado (MercadoLibre API, 24/09/2026) -- ver mercado_ml.py.
// Uso: cargarRangoMercado({marca, modelo, version, anio}, contenedor, valorTabla?)
// Si la plataforma no tiene credenciales de ML, el contenedor queda vacío.
(function () {
  function pesos(n) { return '$ ' + Math.round(n).toLocaleString('es-AR'); }
  function esc(s) { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }

  window.cargarRangoMercado = async function (params, contenedor, valorTabla) {
    if (!contenedor) return;
    contenedor.innerHTML = '<div class="rm-cargando">Buscando publicaciones reales…</div>';
    // 04/10/2026: ML bloquea /sites/MLA/search (403, ver PROYECTO.md). Mientras tanto no
    // se llama a la API: se muestran solo las publicaciones de RosarioGarage.
    // Para reactivar: USAR_ML = true.
    const USAR_ML = false;
    if (!USAR_ML) { await cargarPublicacionesRG(params, contenedor, valorTabla); return; }
    let d;
    try {
      const r = await fetch('/precios/api/mercado?' + new URLSearchParams(params));
      d = await r.json();
    } catch (e) { d = { ok: false }; }
    // 28/09/2026: si MercadoLibre no da datos (hoy bloquea su buscador) no
    // se muestra ningún error: se prueba con publicaciones de RosarioGarage.
    if (!d.disponible || !d.ok) { await cargarPublicacionesRG(params, contenedor, valorTabla); return; }
    let comparacion = '';
    if (valorTabla) {
      const dif = (valorTabla - d.mediana) / d.mediana * 100;
      const txt = Math.abs(dif) < 3 ? 'en línea con el mercado'
        : `${Math.abs(dif).toFixed(0)}% ${dif > 0 ? 'por encima' : 'por debajo'} de la mediana de ML`;
      comparacion = `<div class="rm-nota">Valor de tabla ${pesos(valorTabla)}: ${txt}.</div>`;
    }
    const alcance = d.alcance === 'version' ? 'misma versión' : 'todas las versiones del modelo';
    const extras = [];
    if (d.km_promedio) extras.push(`${d.km_promedio.toLocaleString('es-AR')} km promedio`);
    if (d.n_usd) extras.push(`${d.n_usd} en dólares no incluidos`);
    if (d.descartados) extras.push(`${d.descartados} descartados por precio fuera de rango (anticipos/cuotas)`);
    const muestras = (d.muestras || []).map(m =>
      `<a class="rm-aviso" href="${esc(m.url)}" target="_blank" rel="noopener">
         <span>${esc(m.titulo)}${m.km ? ' · ' + m.km.toLocaleString('es-AR') + ' km' : ''}</span>
         <strong>${pesos(m.precio)}</strong></a>`).join('');
    contenedor.innerHTML = `
      <div class="rango-mercado">
        <div class="rm-titulo">Precio de mercado · MercadoLibre</div>
        <div class="rm-rango">${pesos(d.p25)} – ${pesos(d.p75)}</div>
        <div class="rm-nota">Rango típico (la mitad de los avisos está en esta franja) · mediana <strong>${pesos(d.mediana)}</strong></div>
        <div class="rm-grid">
          <div><span>Mínimo</span><strong>${pesos(d.minimo)}</strong></div>
          <div><span>Promedio</span><strong>${pesos(d.promedio)}</strong></div>
          <div><span>Máximo</span><strong>${pesos(d.maximo)}</strong></div>
        </div>
        ${comparacion}
        <div class="rm-nota">${d.n} avisos en pesos${d.anio ? ' del ' + esc(d.anio) : ''} · ${alcance}${extras.length ? ' · ' + extras.join(' · ') : ''}. Precios publicados (pedidos), no de venta cerrada.</div>
        ${muestras ? `<details class="rm-muestras"><summary>Ver avisos cercanos a la mediana</summary>${muestras}</details>` : ''}
      </div>`;
  };

  async function cargarPublicacionesRG(params, contenedor, valorTabla) {
    let d;
    try {
      const q = new URLSearchParams({ ...params, valor_tabla: valorTabla || '' });
      const r = await fetch('/precios/api/publicaciones?' + q);
      d = await r.json();
    } catch (e) { contenedor.innerHTML = ''; return; }
    if (!d.ok || !d.avisos || !d.avisos.length) { contenedor.innerHTML = ''; return; }
    const tarjetas = d.avisos.map(a => `
      <a class="pub-rg" href="${esc(a.url)}">
        ${a.foto ? `<img src="${esc(a.foto)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'pub-rg-sinfoto'}))">` : '<div class="pub-rg-sinfoto"></div>'}
        <div class="pub-rg-info">
          <div class="pub-rg-tit">${esc(a.titulo)}</div>
          <div class="pub-rg-det">${esc(a.detalle)}</div>
          <div class="pub-rg-precio">${pesos(a.precio)}</div>
        </div>
      </a>`).join('');
    contenedor.innerHTML = `
      <div class="rango-mercado">
        <div class="rm-titulo">Publicaciones reales · RosarioGarage</div>
        ${tarjetas}
        <div class="rm-nota">Precios publicados (pedidos), no de venta cerrada. <a href="${esc(d.url_busqueda)}">Ver todas</a></div>
      </div>`;
  }

  // ---- Publicaciones por zona (DeAutos) -- prueba 05/10/2026, solo agencia 1 ----
  let _localidades = null;
  function guardado() { try { return JSON.parse(localStorage.getItem('agencieros_zona') || '{}'); } catch (e) { return {}; } }
  function guardar(o) { try { localStorage.setItem('agencieros_zona', JSON.stringify(o)); } catch (e) {} }

  async function cargarZona(params, contenedor) {
    let cont = contenedor.nextElementSibling;
    if (!cont || !cont.classList.contains('zona-deautos')) {
      cont = document.createElement('div');
      cont.className = 'zona-deautos';
      contenedor.insertAdjacentElement('afterend', cont);
    }
    if (_localidades === null) {
      try {
        const r = await (await fetch('/precios/api/localidades')).json();
        _localidades = { localidades: r.localidades || [], regiones: r.regiones || [] };
      } catch (e) { _localidades = { localidades: [], regiones: [] }; }
    }
    const g = guardado();
    const radios = [25, 50, 100, 200, 300, 500, 1000];
    const regSel = g.region || 'Centro';
    const opcReg = _localidades.regiones.map(r => `<option value="${esc(r)}"${r === regSel ? ' selected' : ''}>${esc(r)}</option>`).join('')
      + `<option value="todo"${regSel === 'todo' ? ' selected' : ''}>Todo el país</option>`
      + `<option value="radio"${regSel === 'radio' ? ' selected' : ''}>Cerca de una localidad…</option>`;
    cont.innerHTML = `
      <div class="rango-mercado">
        <div class="rm-titulo">Publicaciones por zona · DeAutos + Autocosmos (prueba)</div>
        <div class="zona-bar">
          <label class="zona-pill"><span>Región</span><select class="zona-reg">${opcReg}</select></label>
          <label class="zona-pill zona-solo-radio"><span>Localidad</span>
            <input type="text" class="zona-loc" list="zona-lista" placeholder="Ej.: Rosario, Santa Fe" value="${esc(g.localidad || '')}" autocomplete="off"></label>
          <label class="zona-pill zona-solo-radio"><span>Radio (km)</span>
            <select class="zona-radio">${radios.map(r => `<option value="${r}"${String(r) === String(g.radio || 100) ? ' selected' : ''}>${r} km</option>`).join('')}</select></label>
          <button type="button" class="btn btn-secondary btn-sm zona-ir">Buscar</button>
        </div>
        <datalist id="zona-lista">${_localidades.localidades.map(l => `<option value="${esc(l)}">`).join('')}</datalist>
        <div class="zona-res"></div>
      </div>`;
    const selReg = cont.querySelector('.zona-reg'), inLoc = cont.querySelector('.zona-loc'),
      selR = cont.querySelector('.zona-radio'), res = cont.querySelector('.zona-res');
    const soloRadio = cont.querySelectorAll('.zona-solo-radio');
    const dormir = ms => new Promise(ok => setTimeout(ok, ms));
    let ticket = 0;

    function pintar(d, avisos, estado) {
      const tarjetas = avisos.map(a => `
        <a class="pub-rg" href="${esc(a.url)}" target="_blank" rel="noopener">
          ${a.foto ? `<img src="${esc(a.foto)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'pub-rg-sinfoto'}))">` : '<div class="pub-rg-sinfoto"></div>'}
          <div class="pub-rg-info">
            <div class="pub-rg-tit">${esc(a.titulo)}${a.version ? ' · ' + esc(a.version) : ''}</div>
            <div class="pub-rg-det">${a.anio || ''}${a.km ? ' · ' + a.km.toLocaleString('es-AR') + ' km' : ''} · ${esc(a.fuente || '')} · ${esc(a.ciudad || a.loc || '')}${a.provincia && a.distancia_km == null ? ', ' + esc(a.provincia) : ''}${a.aprox ? ' (zona aprox.)' : ''}${a.distancia_km != null ? ' · a ' + a.distancia_km + ' km' : ''}</div>
            <div class="pub-rg-precio">${a.moneda === 'USD' ? 'USD ' : '$ '}${Math.round(a.precio).toLocaleString('es-AR')}</div>
          </div>
        </a>`).join('');
      const ars = avisos.filter(a => a.moneda === 'ARS' && !a.dif_anio).map(a => a.precio).sort((x, y) => x - y);
      const mediana = ars.length >= 3 ? ars[Math.floor(ars.length / 2)] : null;
      const nota = [`${d.leidos} avisos leídos en DeAutos`];
      if (d.fuera_de_radio) nota.push(`${d.fuera_de_radio} de otras zonas`);
      if (d.sin_ubicar) nota.push(`${d.sin_ubicar} sin ubicación reconocida`);
      res.innerHTML = `${avisos.length ? tarjetas : `<div class="rm-nota">${esc(estado.fin ? (d.motivo || 'Sin resultados.') : 'Sin resultados todavía…')}</div>`}
        ${mediana ? `<div class="rm-nota">Mediana de los avisos en pesos del mismo año: <strong>${pesos(mediana)}</strong></div>` : ''}
        ${estado.msg ? `<div class="rm-cargando">${esc(estado.msg)}</div>` : ''}
        <div class="rm-nota">${nota.join(' · ')}${estado.ac ? ' · ' + esc(estado.ac) : ''}. Precio que pide cada vendedor; se incluyen años ±1. Autocosmos: solo la primera página de la marca por provincia.
          ${d.url_busqueda ? `<a href="${esc(d.url_busqueda)}" target="_blank" rel="noopener">Ver en DeAutos</a>` : ''}</div>`;
    }

    async function buscar() {
      const mi = ++ticket;
      const radioModo = selReg.value === 'radio';
      soloRadio.forEach(el => { el.style.display = radioModo ? '' : 'none'; });
      res.innerHTML = '<div class="rm-cargando">Buscando por zona…</div>';
      const base = { ...params, modo: radioModo ? 'radio' : 'region', region: radioModo ? '' : selReg.value, localidad: inLoc.value.trim(), radio: selR.value };
      let d;
      try { d = await (await fetch('/precios/api/zona?' + new URLSearchParams(base))).json(); } catch (e) { d = { ok: false, motivo: 'No se pudo consultar.' }; }
      if (mi !== ticket) return;
      if (!d.habilitado) { cont.innerHTML = ''; return; }
      if (d.origen && !inLoc.value.trim()) inLoc.value = `${d.origen.nombre}, ${d.origen.provincia}`;
      guardar({ region: selReg.value, localidad: inLoc.value.trim(), radio: selR.value });
      const mapa = new Map();
      const sumar = lista => (lista || []).forEach(a => {
        const k = [a.anio, a.km, a.precio].join('|');
        if (!mapa.has(k) || a.fuente === 'Autocosmos' && a.url.indexOf('autocosmos.com') >= 0) mapa.set(k, a);
      });
      const lista = () => [...mapa.values()].sort((a, b) => (a.dif_anio - b.dif_anio) || (a.precio - b.precio));
      sumar(d.avisos);
      const pedidos = d.ac_pedidos || [];
      let hechos = 0;
      pintar(d, lista(), { fin: !pedidos.length, msg: pedidos.length ? `Consultando Autocosmos (0/${pedidos.length})…` : '' });
      for (const p of pedidos) {
        let r = null;
        for (let intento = 0; intento < 4; intento++) {
          try { r = await (await fetch('/precios/api/zona_autocosmos?' + new URLSearchParams({ ...base, cod: p.cod }))).json(); } catch (e) { r = null; break; }
          if (mi !== ticket) return;
          if (r && r.espera > 0) {
            pintar(d, lista(), { fin: false, msg: `Autocosmos ${hechos}/${pedidos.length}: esperando ${r.espera} s para respetar al sitio…` });
            await dormir((r.espera + 1) * 1000);
            if (mi !== ticket) return;
            r = null;
            continue;
          }
          break;
        }
        if (mi !== ticket) return;
        hechos++;
        if (r && r.avisos) sumar(r.avisos);
        d.leidos += (r && r.leidos) || 0;
        d.fuera_de_radio += (r && r.fuera_de_radio) || 0;
        d.sin_ubicar += (r && r.sin_ubicar) || 0;
        pintar(d, lista(), { fin: hechos >= pedidos.length, msg: hechos < pedidos.length ? `Consultando Autocosmos (${hechos}/${pedidos.length})…` : '' });
      }
      if (pedidos.length) pintar(d, lista(), { fin: true, ac: `Autocosmos: ${pedidos.map(p => p.nombre).join(', ')}` });
    }
    cont.querySelector('.zona-ir').addEventListener('click', buscar);
    selReg.addEventListener('change', buscar);
    selR.addEventListener('change', buscar);
    inLoc.addEventListener('change', buscar);
    buscar();
  }

  const _cargarOriginal = window.cargarRangoMercado;
  window.cargarRangoMercado = async function (params, contenedor, valorTabla) {
    await _cargarOriginal(params, contenedor, valorTabla);
    if (window.ZONA_DEAUTOS && contenedor && params && params.modelo) { cargarZona(params, contenedor); }
  };

  // Auto-carga para elementos server-side: <div data-rango-mercado data-marca=.. data-modelo=.. data-version=.. data-anio=.. data-valor-tabla=..>
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-rango-mercado]').forEach(el => {
      const ds = el.dataset;
      window.cargarRangoMercado({ marca: ds.marca || '', modelo: ds.modelo || '', version: ds.version || '', anio: ds.anio || '' },
        el, ds.valorTabla ? Number(ds.valorTabla) : null);
    });
  });
})();
