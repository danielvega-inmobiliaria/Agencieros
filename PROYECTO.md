# AGENCIEROS — Contexto del Proyecto

## Cómo usar este archivo
- **Al empezar un chat nuevo:** pegá → `Leé PROYECTO.md y continuá desde donde quedamos`
- **Al terminar un chat:** pedí → `Actualizá PROYECTO.md con lo que hicimos hoy`

---

_Última actualización: 14/09/2026 — 15:05 ART_

## Qué es este proyecto
**AGENCIEROS**: la plataforma más completa para agencias de automotores de Argentina. Unifica consulta de precios, gestión del negocio, tasación, rentabilidad y una red de colaboración entre agencieros.

**Gancho comercial:** hoy los agencieros pagan ~$16.800 solo para consultar precios (ej. InfoAuto). AGENCIEROS ofrece lo mismo (consulta marca/modelo/versión/año → precio) a un costo similar, pero con una app de gestión completa incluida. La consulta de precios es la **pantalla principal** de la app — desde ahí nacen las demás acciones (tasar, comprar, cargar a stock, publicar, vender, compartir con la Red).

**Nombre elegido:** Agencieros (de una lista de 10 opciones evaluadas: AutoRed, AutoGestión, DealerNet, AutoBroker, AutoBase, MotorHub, StockAuto, ValorAuto, Dealer360).

**Diferencial vs. la competencia** (que solo ofrece guía de precios): gestión completa + tasación inteligente + control financiero + seguimiento de clientes + red de agencieros + base de valuaciones propia + inteligencia de negocio.

**Visión a largo plazo:** que AGENCIEROS sea el estándar de agencias de autos en Argentina. Con masa crítica de usuarios, las operaciones cargadas por las agencias generan un "Valor de Mercado Agencieros" propio, potencialmente más representativo que una guía tradicional.

## Módulos (11)
1. **Consulta de precios** (gancho comercial) — marca/modelo/versión/año → precio de referencia. Base inicial con valores tipo InfoAuto (carga manual por ahora, sin integración por API).
2. **Stock de vehículos** — estados Disponible / Por ingresar / En reparación / Vendido. Ficha completa (características, equipamiento, km, combustible, caja, observaciones, documentación, historial) + galería de fotos propia (subida real de archivos, separada de la Inspección visual).
3. **Banco de pedidos** — clientes que buscan un vehículo. Aviso automático cuando ingresa una unidad que matchea.
4-6. **Toma y tasación** (un solo módulo/ítem de menú, flujo en 3 pasos secuenciales — unificado 13/09/2026): **Paso 1** Toma técnica (motor, caja, embrague, frenos, suspensión, dirección, interior, tapizados, cubiertas, electricidad, aire acondicionado, documentación — calificación Excelente/Bueno/Regular/Malo, y **costo estimado de reparación/limpieza cargable en cada punto individual**, ej. tapizados sucio o cubiertas gastadas); **Paso 2** Fotos + Inspección visual de chapa (subida real de foto por cada una de las 5 vistas — frente/trasera/lateral izq/lateral der/superior — con click sobre la imagen para ubicar marcadores de daño: golpe/rayón/vidrio roto/óptica/paragolpes/abolladura, con gravedad leve 🟢/moderado 🟡/grave 🔴 y **costo estimado de reparación por marcador**, con subtotal por vista); **Paso 3** Tasación (estado mecánico y estético pre-sugeridos automáticamente a partir de los pasos 1 y 2, editables; valor de referencia autocompletado desde `precios_base` con links de comparables reales en MercadoLibre/RosarioGarage/Facebook Marketplace; gastos estimados de reparación sugeridos = suma de los costos del Paso 1 + los del Paso 2, desglose visible; calcula el "Valor de toma" — precio máximo recomendado ya descontados reparación y margen — más riesgo y margen esperado). Las tomas pueden iniciarse sueltas o vinculadas a un vehículo puntual de Stock (botón "Hacer toma / tasación" en la ficha). Las rutas viejas `/inspeccion/` y `/tasacion/` quedaron como redirects de compatibilidad hacia este flujo.
7. **Control económico** — valor de compra, gastos, reparaciones, gastos administrativos, precio publicado/vendido → ganancia bruta/neta, rentabilidad, días en stock.
8. **Historial financiero** — tablero: ganancia mensual/anual, capital invertido, capital inmovilizado, vehículos más/menos rentables.
9. **Red de Agencieros** — marketplace privado entre agencias: publicar disponibles, pedir vehículos, compartir oportunidades, buscar unidades, contactar agencias, notificaciones, calificar operaciones.
10. **Base propia de valuaciones** — actualización mensual, inicialmente sobre InfoAuto; a futuro historial de precios y tendencias propias.
11. **Algoritmo de valuación** — extiende precios más allá del rango de InfoAuto (+5/10 años) considerando antigüedad, km, historial, marca, demanda y operaciones reales registradas en la plataforma.

## Stack / Tecnología
Igual patrón que `APP_PRESUPUESTOPRO` (ya probado y funcionando con Daniel):
- Flask + Python 3.11
- SQLite (`data/agencieros.db`)
- Server-side rendering con Jinja2 (sin framework JS pesado)
- Deploy futuro: Railway (a definir cuándo se despliegue)

## Archivos importantes
- `app.py` — factory de la app, registra todos los blueprints.
- `database.py` — conexión SQLite + schema completo (11 módulos) + seed de datos de ejemplo (precios_base, usuario admin).
- `routes/` — un blueprint por módulo: `auth`, `dashboard`, `precios`, `stock`, `pedidos`, `tomas`, `inspeccion`, `tasacion`, `finanzas`, `red`.
- `templates/` — Jinja2, layout `base.html` con sidebar (tema navy + dorado inspirado en el prototipo visual que Daniel subió).
- `static/css/style.css` — estilos.

## Credenciales admin (desarrollo local)
`admin@agencieros.com` / `admin1234`

---

## Competencia (investigado 15/07/2026)

El mercado argentino **no está vacío** — hay al menos dos jugadores directos, maduros y ya facturando, que hacen gran parte de lo que definimos para AGENCIEROS:

- **deConcesionarias** (deconcesionarias.com.ar) — el más fuerte. +90 agencias/concesionarios, 82.300 autos bajo gestión, 32.700 ventas/año, certificado oficial por Mercado Libre. Ya tiene: cotización por patente + análisis de mercado en vivo (= nuestro módulo 1 + parte del 6), peritaje digital (= módulo 4/5), multipublicador a 10+ portales, e-CRM con "lista de deseos" que **matchea cliente-stock y avisa automático** (= nuestro módulo 3, ya resuelto por ellos, hasta con el nombre "el Tinder automotor"), subastas privadas entre agencias (≈ módulo 9), WhatsApp con bot de IA, negocios digitales (seguros/garantías comisionables), app mobile. Precio: desde $80.000/mes (1 usuario, 15 autos) hasta $1.900.000/mes.
- **MOBU** (mobu.market) — ERP multimoneda genérico con vertical para agencias. Ya tiene: ganancia real por unidad con gastos imputados, **tasación asistida con IA usando comparables de MercadoLibre** (= nuestro módulo 6/11), permuta que auto-genera stock ya tasado, créditos/cuotas, comisiones de vendedores, panel "sobre/subvaluado vs. mercado".
- Otros con menor porte: AutoSite, DeAutos.io, Autosoft, Auto360, Octosis DMS, Nodum (ERP por VIN), PymeCar/FN Software.
- **InfoAuto ya tiene app propia** (InfoAuto Argentina, Google Play / App Store) con consultas ilimitadas, fichas técnicas y fotos — no es solo la revista impresa. Esto debilita el ángulo original de "ellos no tienen app, nosotros sí".

**Implicancia para el pitch de AGENCIEROS:** la idea de "consulta de precios + gestión completa en una sola app, más barata que la guía sola" sigue siendo válida como ángulo de entrada — deConcesionarias arranca en $80.000/mes, muy por encima de los ~$16.800 que hoy paga un agenciero chico solo por consultar precios. El diferencial real hoy no es "tener gestión + consulta" (eso ya existe y de forma más completa), sino: **precio de entrada mucho más bajo para el agenciero chico/independiente** que hoy no puede pagar deConcesionarias/MOBU, y una **Red de Agencieros abierta entre independientes** (no subastas cerradas de un solo grupo/marca como deConTerminal, sino colaboración horizontal entre agencias multimarca sueltas de todo el país). Vale la pena decidir esto con Daniel antes de seguir invirtiendo en funcionalidades que la competencia ya resolvió mejor (ej. multipublicador, peritaje con checklist, WhatsApp IA).

## Pendientes

### 🔴 CRÍTICO
- [ ] **Redefinir el diferencial real de AGENCIEROS a la luz de la competencia** (ver sección de arriba) antes de seguir construyendo funcionalidades — decidir si el foco es precio bajo para agencias chicas, red abierta entre independientes, o un nicho distinto.
- [ ] Definir fuente real de datos de precios (¿InfoAuto tiene API? ¿se carga a mano mes a mes?) — hoy `precios_base` tiene datos de ejemplo cargados a mano.
- [ ] Decidir modelo de negocio/planes de suscripción (no está definido en el código todavía) — mirar precios de deConcesionarias ($80k-$1,9M/mes) y MOBU como referencia de mercado.

### 🟡 IMPORTANTE
- [ ] Red de Agencieros (módulo 9) hoy es de un solo tenant/DB — para que sea red real entre agencias distintas hace falta multi-tenant (cada agencia con su login) y notificaciones.
- [ ] Algoritmo de valuación (módulo 11): la fórmula de Tasación es una primera versión simple (factores fijos), no aprende de operaciones reales todavía.
- [ ] Auth real (hoy es login simple tipo PresupuestoPRO, sin registro de agencias ni roles).
- [ ] **Bug mobile (Paso 1 · Toma técnica):** la tabla de puntos (Punto/Calificación/Costo/Comentario) se corta en pantallas chicas — las columnas Costo y Comentario quedan fuera de pantalla. Falta un diseño responsive (scroll horizontal contenido o layout apilado en mobile). Confirmado con capturas de Daniel 13/09/2026.
- [ ] **Imprimir informe de tasación:** agregar botón/vista de impresión del resultado de la Tasación.
- [ ] **Ampliar checklist de Toma técnica de 12 a 41 puntos:** Daniel compartió una foto de un checklist físico completo (ejemplo Peugeot 308) con 41 puntos de inspección — falta transcribir la lista completa y migrar `PUNTOS`/las columnas `comentario_<codigo>`/`costo_<codigo>` en `database.py` y `routes/tomas.py`.
- [ ] **Vínculo Toma→Stock al tomar un vehículo:** definir y programar qué pasa cuando se toma un vehículo — ¿se carga automático a Stock?, ¿se marca "En reparación"?, ¿se asigna fecha de entrega estimada? Hoy no hay ningún vínculo automático entre una Toma tasada y el módulo Stock.
- [ ] **Certificado HTTPS:** evaluar si conviene para evitar el cartel del navegador "Estás a punto de enviar información no segura" al cargar datos en la red local (hoy la app corre sin HTTPS).

### 🟢 IDEAS FUTURAS
- [ ] Comparables de mercado (MercadoLibre/RosarioGarage/Facebook Marketplace) en Tasación: hoy son links de búsqueda que abre el agenciero manualmente (decisión deliberada, para no depender de scraping frágil ni pisar los ToS de esos sitios). A futuro se podría evaluar una integración real (API o scraping propio) si hace falta traer el precio automáticamente.
- [ ] Base de Mercado Agencieros: una vez con operaciones reales cargadas, generar valores propios más allá de InfoAuto.
- [ ] Notificaciones push/WhatsApp para matches del Banco de pedidos y novedades de la Red.
- [ ] App mobile / PWA (el prototipo visual que subió Daniel está pensado como mobile-first).
- [ ] Bandeja unificada de contacto (tipo Kommo/CRM omnicanal): centralizar en una sola vista Mail, WhatsApp, Messenger, Instagram, Telegram, LinkedIn, etc. — leads y consultas de clientes en un solo lugar. (Pedido por Daniel 13/09/2026.)
- [ ] Generador automático de contenido para redes al tomar un vehículo: a partir de los datos ya cargados en Toma/Ficha, armar de una una historia de WhatsApp, un posteo para Facebook, uno para Instagram y la publicación para Marketplace. (Pedido por Daniel 13/09/2026.)

---

## Cambios recientes

### Sesión 14/09/2026 (continuación) — Rediseño del panel de Tasación (Paso 3)
Se implementaron los 5 pendientes 🟡 de la sesión anterior sobre Tasación (quedaron fuera de este bloque el bug mobile del Paso 1, imprimir informe, ampliar checklist a 41 puntos y el vínculo Toma→Stock — siguen en Pendientes):
- **Formulario simplificado:** sacados los textos "(sugerido: X)" de Estado mecánico/Estético. Eliminado el input de "Gastos estimados de reparación" — ahora ese valor se calcula siempre automático (suma de costos del Paso 1 + Paso 2, ya no es editable a mano) y se muestra como dato informativo arriba del panel "Qué hay que reparar".
- **"Qué hay que reparar" reagrupado por foto:** los daños del Paso 2 ahora se listan agrupados por vista (Frente/Trasera/Lateral izq/Lateral der/Superior), con subtotal por foto, en vez de una lista plana. Los puntos del Paso 1 quedaron con el mismo formato que ya tenían (calificación + comentario + costo).
- **Panel de Resultado rediseñado:** arriba, en chico, precio de tabla + fecha de tasación (el dato ya existía en `created_at`, solo faltaba mostrarlo). Después el monto grande de "Valor de toma". Después una fila de 3 datos: Gastos estimados totales, Margen esperado y **% de Beneficio** (nuevo cálculo: margen esperado / precio de toma). Se sacó "Riesgo" de la vista (se sigue calculando y guardando en la base por si sirve a futuro, pero no se muestra más).
- **Detalle de puntos en el Resultado:** debajo de los stats, listado de los puntos/daños tasados con su costo, y el comentario en una segunda línea con sangría — antes esta vista (al recargar una tasación ya guardada) solo mostraba los números finales sin el detalle.
- **Ficha de la Toma (`detalle.html`):** el resumen del Paso 3 también se actualizó — mismo criterio (sin Riesgo, con % de Beneficio y fecha de tasación).
- **Backend:** `routes/tomas.py` — nuevas funciones `_formatear_fecha`, `_tasacion_con_extra` (agrega `porcentaje_beneficio` y `fecha_fmt` a cualquier fila de `tasaciones`) y `_agrupar_danios_por_vista`. La vista `tasacion()` se simplificó: ya no arma un dict `resultado` aparte, siempre trabaja sobre `tasacion_previa` recién leída de la base (con un flag `es_nueva` para el texto del panel).
- **Archivos tocados:** `routes/tomas.py`, `templates/tomas/tasacion.html`, `templates/tomas/detalle.html`. Sin cambios de esquema en `database.py` (la columna `created_at` de `tasaciones` ya existía, solo faltaba mostrarla).
- **Pendiente:** probar el flujo completo en el navegador (cargar una toma con puntos/daños con costo, tasar, y revisar que el panel de Resultado y el de "Qué hay que reparar" se vean bien) y hacer el commit/push (bloque de Git Bash abajo, todavía no corrido).

### Sesión 14/09/2026 — Precios 0km/normalización InfoAuto, búsqueda por Año primero, autocompletar propio (adiós datalist), guía de precio + evaluador + comentarios en Toma, resumen de reparaciones en Tasación
- **Precios "0km" corregidos:** regla aplicada = año_0km es el máximo año cargado en esa fila de InfoAuto + 1 (antes estaba mal calculado). Se normalizó también la carga vieja de datos de ejemplo a mayúsculas, siguiendo la convención de InfoAuto.
- **Búsqueda por Año primero en toda la app:** se reordenaron los campos en Consulta de precios (`precios/index.html`) y en el selector compartido de Marca/Modelo/Versión (`static/js/catalogo.js`, usado en Toma, Stock, Pedidos y Red) para que el Año vaya primero y filtre Marca/Modelo/Versión a lo que corresponde a ese año — antes se podían elegir combinaciones que no existieron nunca. `obtener_catalogo()` en `database.py` ahora devuelve también los años por versión.
- **Autocompletar propio reemplaza el `<datalist>` nativo:** en iOS Safari el datalist mostraba las sugerencias en la barra de teclado (QuickType), confundiéndose con el autocorrector, en vez de desplegar una lista debajo del campo. Se creó `static/js/autocomplete.js` (dropdown propio, con teclado y mouse) y se reemplazó en los 5 lugares que usaban datalist: Consulta de precios, Toma, Stock, Pedidos (permuta) y Red.
- **Incidente técnico resuelto:** un paste largo en Git Bash se trabó a mitad de camino, y al recrear el archivo se generó un archivo duplicado (`catalogo-1.js`) por un conflicto de sincronización (OneDrive) sobre la carpeta del proyecto — se verificó el contenido byte a byte antes de restaurar `catalogo.js` en la ruta correcta.
- **Toma técnica (Paso 1) mejorada:**
  - Al elegir Marca+Modelo (y Año/Versión si están) aparece el precio de guía (InfoAuto) de ese vehículo, con aviso si se está usando el año más próximo cargado o si no hay precio cargado todavía.
  - El campo Evaluador ahora autocompleta con los nombres ya usados en tomas anteriores.
  - Cada uno de los 12 puntos de inspección tiene un campo de comentario para anotar en qué consiste la reparación necesaria (se ve también en el detalle de la toma).
- **Tasación (Paso 3):** nuevo panel "Qué hay que reparar" antes del botón "Calcular tasación", con el listado de puntos del Paso 1 (con calificación, comentario y costo) y de los daños marcados en las fotos del Paso 2 (con gravedad, descripción y costo) — para tener todo el detalle a la vista antes de tasar.
- **Pendiente para la próxima sesión (feedback de Daniel sobre este mismo panel y toda la Tasación):** ver el bloque nuevo en "Pendientes → 🟡 IMPORTANTE" — bug de tabla en mobile, simplificación del formulario de Tasación, reagrupar "Qué hay que reparar" por foto, formato de la vista de una tasación guardada, rediseño del panel de Resultado, fecha de tasación e impresión del informe.

### Sesión 13/09/2026 — Stock↔fotos/inspección, Toma+Inspección+Tasación unificadas, bandeja de mensajes (vista previa), acceso mobile, costos de reparación y comparables de mercado
- Sincronización de Stock con las fichas de `03_AUTOMOTOR/STOCK` (`sync_stock.py`), sin pisar campos financieros ya cargados a mano.
- Catálogo unificado de Marca/Modelo/Versión en toda la app (selects en cascada con "+ nueva/o..." como escape hatch) — evita duplicados por tipeo.
- Banco de pedidos: forma de pago desplegable (contado/cuotas/permuta), con campos de financiación y de vehículo en permuta + match automático contra pedidos propios y Red de Agencieros. Fecha y días transcurridos visibles en el listado.
- Dashboard: indicador de mensajes sin leer.
- Mensajes: maqueta de bandeja unificada (WhatsApp/Instagram/Facebook/Email) con datos de ejemplo — vista previa, todavía sin conexión real.
- **Toma de vehículos + Inspección visual + Tasación fusionadas en un solo ítem de menú ("Toma y tasación"), flujo de 3 pasos secuenciales**: Paso 1 datos técnicos, Paso 2 fotos reales de las 5 vistas + marcado interactivo de daños (click sobre la imagen), Paso 3 tasación con estado mecánico/estético sugeridos automáticamente (ajustables) y valor de referencia autocompletado desde `precios_base`. Las tomas pueden iniciarse desde un vehículo puntual de Stock. `/inspeccion/` y `/tasacion/` quedaron como redirects de compatibilidad.
- Stock: galería de fotos real del vehículo (subida múltiple, eliminar) — sistema separado de las fotos de Inspección visual.
- **Acceso desde el celular arreglado**: el server de Flask escuchaba solo en `127.0.0.1` (`app.run(host="0.0.0.0", ...)` agregado en `app.py`) + hacía falta reiniciar el proceso para que tome el cambio (bajar el archivo nuevo no alcanza, Flask no relee código de un proceso ya corriendo) + regla de Firewall de Windows para el puerto 5000. Confirmado funcionando desde el celu por Daniel.
- **Colores de los marcadores de daño** en la inspección visual: Grave = rojo, Moderado = amarillo, Leve = verde (antes Moderado y Leve eran difíciles de diferenciar).
- **Costo de reparación por daño marcado** (Paso 2): cada marcador de daño sobre la foto tiene su propio costo estimado de arreglo, con subtotal por vista.
- **Costo de reparación por punto técnico** (Paso 1): cada uno de los 12 puntos evaluados (motor, caja, embrague, frenos, suspensión, dirección, interior, tapizados, cubiertas, electricidad, aire acondicionado, documentación) tiene su propio campo de costo estimado de arreglo/limpieza — ej. tapizados en mal estado por suciedad o roturas. Se ve reflejado en el hub de la toma con el total del Paso 1.
- **Tasación (Paso 3) mejorada**: junto al valor de referencia (valor de tabla de `precios_base`) aparecen botones para abrir una búsqueda de ese vehículo en MercadoLibre, RosarioGarage y Facebook Marketplace (comparables reales — sin scraping, son links de búsqueda que abre el agenciero). Los "Gastos estimados de reparación" se sugieren automáticamente sumando el costo cargado en el Paso 1 (puntos técnicos) + el del Paso 2 (daños visuales), con el desglose de ambas fuentes a la vista. El resultado final quedó etiquetado como "Valor de toma" (precio máx. recomendado, ya descontados reparación y margen).

### Sesión 15/07/2026 — Arranque del proyecto
- Leído el brief completo (docx "Instrucciones Iniciales") con la definición de los 11 módulos, el naming (Agencieros) y la estrategia comercial (consulta de precios como gancho).
- Visto el prototipo visual de referencia (dashboard estilo navy + dorado, sidebar con Dashboard/Vehículos/Clientes/Ventas/Finanzas/Tareas/Agenda/Reportes/Marketing/Configuración).
- Creada la base del proyecto: Flask + SQLite, schema para los 11 módulos.
- Funcional: Consulta de precios, Stock de vehículos, Banco de pedidos (con alerta de match), Toma de vehículos, Tasación, Finanzas (tablero agregado), Red de Agencieros (CRUD básico).
- Stub (tabla lista, UI pendiente): Inspección visual de chapa.

---

## Notas / Decisiones tomadas
- La Consulta de precios es la pantalla de inicio (home) de la app — decisión explícita del brief original, no una elección técnica nuestra.
- Control económico (módulo 7) e Historial financiero (módulo 8) se resolvieron reusando los campos de `vehiculos` (valor_compra, gastos, valor_publicado, valor_vendido) en vez de una tabla de transacciones aparte — más simple para el MVP, se puede separar más adelante si hace falta trazabilidad más fina (pagos parciales, adelantos, etc.).
- Paleta visual tomada del prototipo subido por Daniel: fondo navy oscuro, acentos dorados, tarjetas navy más claro, texto blanco.
