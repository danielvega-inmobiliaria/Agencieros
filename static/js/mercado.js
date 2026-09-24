// Rango de precios de mercado (MercadoLibre API, 24/09/2026) -- ver mercado_ml.py.
// Uso: cargarRangoMercado({marca, modelo, version, anio}, contenedor, valorTabla?)
// Si la plataforma no tiene credenciales de ML, el contenedor queda vacío.
(function () {
  function pesos(n) { return '$ ' + Math.round(n).toLocaleString('es-AR'); }
  function esc(s) { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }

  window.cargarRangoMercado = async function (params, contenedor, valorTabla) {
    if (!contenedor) return;
    contenedor.innerHTML = '<div class="rm-cargando">Buscando precios de mercado en MercadoLibre…</div>';
    let d;
    try {
      const r = await fetch('/precios/api/mercado?' + new URLSearchParams(params));
      d = await r.json();
    } catch (e) { contenedor.innerHTML = ''; return; }
    if (!d.disponible) { contenedor.innerHTML = ''; return; }
    if (!d.ok) {
      contenedor.innerHTML = `<div class="rango-mercado"><div class="rm-titulo">Precio de mercado (MercadoLibre)</div>
        <div class="rm-nota">${esc(d.motivo || 'Sin datos.')}</div></div>`;
      return;
    }
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

  // Auto-carga para elementos server-side: <div data-rango-mercado data-marca=.. data-modelo=.. data-version=.. data-anio=.. data-valor-tabla=..>
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-rango-mercado]').forEach(el => {
      const ds = el.dataset;
      window.cargarRangoMercado({ marca: ds.marca || '', modelo: ds.modelo || '', version: ds.version || '', anio: ds.anio || '' },
        el, ds.valorTabla ? Number(ds.valorTabla) : null);
    });
  });
})();
