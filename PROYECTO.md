# AGENCIEROS — Contexto del Proyecto

## Cómo usar este archivo
- **Al empezar un chat nuevo:** pegá → `Leé PROYECTO.md y continuá desde donde quedamos`
- **Al terminar un chat:** pedí → `Actualizá PROYECTO.md con lo que hicimos hoy`

---

_Última actualización: 14/09/2026 — 19:00 ART_

## Qué es este proyecto
**AGENCIEROS**: la plataforma más completa para agencias de automotores de Argentina. Unifica consulta de precios, gestión del negocio, tasación, rentabilidad y una red de colaboración entre agencieros.

**Gancho comercial:** hoy los agencieros pagan ~$16.800 solo para consultar precios (ej. InfoAuto). AGENCIEROS ofrece lo mismo (consulta marca/modelo/versión/año → precio) a un costo similar, pero con una app de gestión completa incluida. La consulta de precios es la **pantalla principal** de la app — desde ahí nacen las demás acciones (tasar, comprar, cargar a stock, publicar, vender, compartir con la Red).

**Nombre elegido:** Agencieros (de una lista de 10 opciones evaluadas: AutoRed, AutoGestión, DealerNet, AutoBroker, AutoBase, MotorHub, StockAuto, ValorAuto, Dealer360).

**Diferencial vs. la competencia** (que solo ofrece guía de precios): gestión completa + tasación inteligente + control financiero + seguimiento de clientes + red de agencieros + base de valuaciones propia + inteligencia de negocio.

**Visión a largo plazo:** que AGENCIEROS sea el estándar de agencias de autos en Argentina. Con masa crítica de usuarios, las operaciones cargadas por las agencias generan un "Valor de Mercado Agencieros" propio, potencialmente más representativo que una guía tradicional.

## Módulos (12)
1. **Consulta de precios** (gancho comercial) — marca/modelo/versión/año → precio de referencia. Base inicial con valores tipo InfoAuto (carga manual por ahora, sin integración por API).
2. **Stock de vehículos** — estados Disponible / Por ingresar / En reparación / Vendido. Ficha completa (características, equipamiento, km, combustible, caja, observaciones, documentación, historial) + galería de fotos propia (subida real de archivos, separada de la Inspección visual).
3. **Banco de pedidos** — clientes que buscan un vehículo. Aviso automático cuando ingresa una unidad que matchea.
4-6. **Toma y tasación** (un solo módulo/ítem de menú, flujo en 3 pasos secuenciales — unificado 13/09/2026): **Paso 1** Toma técnica (motor, caja, embrague, frenos, suspensión, dirección, interior, tapizados, cubiertas, electricidad, aire acondicionado, documentación — calificación Excelente/Bueno/Regular/Malo, y **costo estimado de reparación/limpieza cargable en cada punto individual**, ej. tapizados sucio o cubiertas gastadas); **Paso 2** Fotos + Inspección visual de chapa (subida real de foto por cada una de las 5 vistas — frente/trasera/lateral izq/lateral der/superior — con click sobre la imagen para ubicar marcadores de daño: golpe/rayón/vidrio roto/óptica/paragolpes/abolladura, con gravedad leve 🟢/moderado 🟡/grave 🔴 y **costo estimado de reparación por marcador**, con subtotal por vista); **Paso 3** Tasación (estado mecánico y estético pre-sugeridos automáticamente a partir de los pasos 1 y 2, editables; valor de referencia autocompletado desde `precios_base` con links de comparables reales en MercadoLibre/RosarioGarage/Facebook Marketplace; gastos estimados de reparación sugeridos = suma de los costos del Paso 1 + los del Paso 2, desglose visible; calcula el "Valor de toma" — precio máximo recomendado ya descontados reparación y margen — más riesgo y margen esperado). Las tomas pueden iniciarse sueltas o vinculadas a un vehículo puntual de Stock (botón "Hacer toma / tasación" en la ficha). Las rutas viejas `/inspeccion/` y `/tasacion/` quedaron como redirects de compatibilidad hacia este flujo.
7. **Control económico** — valor de compra, gastos, reparaciones, gastos administrativos, precio publicado/vendido → ganancia bruta/neta, rentabilidad, días en stock.
8. **Historial financiero** — tablero: ganancia mensual/anual, capital invertido, capital inmovilizado, vehículos más/menos rentables.
9. **Red de Agencieros** — marketplace privado entre agencias: publicar disponibles, pedir vehículos, compartir oportunidades, buscar unidades, contactar agencias, notificaciones, calificar operaciones.
10. **Base propia de valuaciones** — actualización mensual, inicialmente sobre InfoAuto; a futuro historial de precios y tendencias propias.
11. **Algoritmo de valuación** — extiende precios más allá del rango de InfoAuto (+5/10 años) considerando antigüedad, km, historial, marca, demanda y operaciones reales registradas en la plataforma.
12. **Financiación** (nuevo 14/09/2026) — la agencia financia directo al comprador (no es un simulador de crédito bancario externo). Simulador de cuotas por sistema francés (cuota fija) disponible libremente para cualquier consulta antes de cerrar una venta (sin necesidad de tener el vehículo marcado como vendido todavía); al confirmar la venta, el plan se guarda como real (opcionalmente atado a un vehículo de Stock) y genera el cronograma de cuotas con fecha de vencimiento. Panel de control por plan: cobrado vs. adeudado, cuotas vencidas, registro de pagos (totales o parciales), cierre automático a "Finalizado" cuando se cobran todas las cuotas.

## Stack / Tecnología
Igual patrón que `APP_PRESUPUESTOPRO` (ya probado y funcionando con Daniel):
- Flask + Python 3.11
- SQLite (`data/agencieros.db`)
- Server-side rendering con Jinja2 (sin framework JS pesado)
- Deploy futuro: Railway (a definir cuándo se despliegue)

## Archivos importantes
- `app.py` — factory de la app, registra todos los blueprints.
- `database.py` — conexión SQLite + schema completo (12 módulos) + seed de datos de ejemplo (precios_base, usuario admin).
- `routes/` — un blueprint por módulo: `auth`, `dashboard`, `precios`, `stock`, `pedidos`, `tomas`, `inspeccion`, `tasacion`, `finanzas`, `red`, `financiacion`.
- `templates/` — Jinja2, layout `base.html` con sidebar (tema navy + dorado inspirado en el prototipo visual que Daniel subió).
- `static/css/style.css` — estilos.

## Credenciales admin (desarrollo local)
`admin@agencieros.com` / `admin1234`

---

## Competencia (investigado 15/07/2026)

El mercado argentino **no está vacío** — hay al menos dos jugadores directos, maduros y ya facturando, que hacen gran parte de lo que definimos para AGENCIEROS:

- **deConcesionarias** (deconcesionarias.com.ar) — el más fuerte. +90 agencias/concesionarios, 82.300 autos bajo gestión, 32.700 ventas/año, certificado oficial por Mercado Libre. Ya tiene: cotización por patente + análisis de mercado en vivo (= nuestro módulo 1 + parte del 6), peritaje digital (= módulo 4/5), multipublicador a 10+ portales, e-CRM con "lista de deseos" que **matchea cliente-stock y avisa automático** (= nuestro módulo 3, ya resuelto por ellos, hasta con el nombre "el Tinder automotor"), subastas privadas entre agencias (≈ módulo 9), WhatsApp con bot de IA, negocios digitales (seguros/garantías comisionables), app mobile. Precio: desde $80.000/mes (1 usuario, 15 autos) hasta $1.900.000/mes.
- **MOBU** (mobu.market) — ERP multimoneda genérico con vertical para agencias. Ya tiene: ganancia real por unidad con gastos imputados, **tasación asistida con IA usando comparables de MercadoLibre** (= nuestro módulo 6/11), permuta que auto-genera stock ya tasado, créditos/cuotas, comisiones de vendedores, panel "sobre/subvaluado vs. mercado".
- **LUCY.CRM** (crm.lucy.ar) — agregado por Daniel 14/09/2026, producto 100% nacional. CRM especializado organizado en 4 áreas: Comercial (leads, ventas, inventario — se solapa con nuestros módulos 1-3), Contable (gastos, pagos, movimientos — ≈ módulo 7/8), Gestoría (transferencias, patentes, multas — no tenemos nada parecido hoy) y Servicios (seguimiento de unidades en taller). Publica directo a MercadoLibre y a ComunidAuto (una red/comunidad de agencias — vale la pena mirarla también como referencia para nuestro módulo 9 de Red), genera placas para historias de redes, multi-sucursal. Precio: 4 planes mensuales — Starter $250.000 (3 usuarios/20 unidades), Standar $320.000 (5 usuarios/50 unidades), Pro $390.000 (10 usuarios/100 unidades), Enterprise $435.600 (ilimitado) — más un add-on "Lucy × REM" con bot conversacional 24/7 para captar leads (precio a consultar). Al igual que deConcesionarias, el precio de entrada de Lucy sigue muy por encima de lo que hoy paga un agenciero chico solo por la guía de precios — refuerza el ángulo de "precio de entrada bajo" como diferencial de AGENCIEROS.
- Otros con menor porte: AutoSite, DeAutos.io, Autosoft, Auto360, Octosis DMS, Nodum (ERP por VIN), PymeCar/FN Software.
- **InfoAuto ya tiene app propia** (InfoAuto Argentina, Google Play / App Store) con consultas ilimitadas, fichas técnicas y fotos — no es solo la revista impresa. Esto debilita el ángulo original de "ellos no tienen app, nosotros sí".

**Implicancia para el pitch de AGENCIEROS:** la idea de "consulta de precios + gestión completa en una sola app, más barata que la guía sola" sigue siendo válida como ángulo de entrada — deConcesionarias arranca en $80.000/mes, muy por encima de los ~$16.800 que hoy paga un agenciero chico solo por consultar precios. El diferencial real hoy no es "tener gestión + consulta" (eso ya existe y de forma más completa), sino: **precio de entrada mucho más bajo para el agenciero chico/independiente** que hoy no puede pagar deConcesionarias/MOBU, y una **Red de Agencieros abierta entre independientes** (no subastas cerradas de un solo grupo/marca como deConTerminal, sino colaboración horizontal entre agencias multimarca sueltas de todo el país). Vale la pena decidir esto con Daniel antes de seguir invirtiendo en funcionalidades que la competencia ya resolvió mejor (ej. multipublicador, peritaje con checklist, WhatsApp IA).

## Pendientes

### 🔴 CRÍTICO
- [ ] **Redefinir el diferencial real de AGENCIEROS a la luz de la competencia** (deConcesionarias, MOBU y ahora también **LUCY.CRM** — ver sección de arriba) antes de seguir construyendo funcionalidades — decidir si el foco es precio bajo para agencias chicas, red abierta entre independientes, o un nicho distinto.
- [x] ~~Definir fuente real de datos de precios~~ → **Decidido 14/09/2026: carga manual por ahora** (no se va a integrar API de InfoAuto en esta etapa). Sigue pendiente como tarea operativa, no de producto: mantener `precios_base` actualizado a mano.
- [ ] **Decidir modelo de negocio/planes de suscripción** — Decidido 14/09/2026: va a ser **con planes de suscripción** (no freemium, no por transacción). Falta definir: cantidad de planes, qué incluye cada uno (usuarios, vehículos en stock, módulos), y precios — usar como referencia de mercado a deConcesionarias ($80k-$1,9M/mes), MOBU y ahora LUCY.CRM (Starter $250k → Enterprise $435,6k/mes), todos muy por encima de los ~$16.800 que hoy paga un agenciero chico solo por la guía de precios — ahí está el hueco de precio de entrada que definimos como diferencial.

### 🟡 IMPORTANTE
- [ ] **Financiación (módulo 12, nuevo 14/09/2026):** falta que Daniel pruebe el flujo real desde el navegador/celu (simulador → guardar plan → registrar pagos) y confirme que el cálculo de cuotas (sistema francés) da los números esperados. Pendiente de decidir a futuro: ¿agregar un botón directo "Simular financiación" desde `stock/detalle.html` cuando el vehículo está vendido (hoy se llega solo entrando a Financiación → Simulador y eligiendo el vehículo de una lista)? ¿Enviar recordatorio automático (push/WhatsApp, ver pendiente relacionado abajo) cuando una cuota está por vencer o ya venció?
- [ ] Red de Agencieros (módulo 9) hoy es de un solo tenant/DB — para que sea red real entre agencias distintas hace falta multi-tenant (cada agencia con su login) y notificaciones. **Decidido 14/09/2026: se implementa recién cuando cerremos la funcionalidad core de la app — no es prioridad ahora, queda deliberadamente después en la cola.**
- [ ] Algoritmo de valuación (módulo 11): la fórmula de Tasación es una primera versión simple (factores fijos), no aprende de operaciones reales todavía. **Agregado 14/09/2026: hacer configurable el % de utilidad** — hoy está hardcodeado en `MARGEN_OBJETIVO = 0.15` (`routes/tasacion.py` línea 11, comentario "15% de ganancia esperada sobre el valor de referencia"), fijo para todas las tasaciones y no editable desde ningún lado de la app. Falta decidir cómo se vuelve ajustable (¿un campo en el formulario de Tasación por cada toma? ¿una configuración general de la agencia? ¿ambas, con la general como default?).
- [ ] **Auth real** (hoy es login simple tipo PresupuestoPRO, sin registro de agencias ni roles). **Alcance confirmado 14/09/2026:** registro de agencia + validación por mail, y cobro por Mercado Pago (mismo patrón ya resuelto en PresupuestoPRO) — esto conecta directo con el pendiente 🔴 de modelo de negocio/planes de suscripción: la suscripción paga por Mercado Pago va a depender de que Auth real ya esté armado.
- [x] ~~Imprimir informe de tasación~~ → **Confirmado 14/09/2026: sí, hay que hacerlo.** Falta diseñar el formato de salida (queda como tarea de diseño antes de programarlo).
- [ ] **Ampliar checklist de Toma técnica de 12 a 41 puntos:** Daniel compartió una foto de un checklist físico completo (ejemplo Peugeot 308) con 41 puntos de inspección — falta transcribir la lista completa y migrar `PUNTOS`/las columnas `comentario_<codigo>`/`costo_<codigo>` en `database.py` y `routes/tomas.py`. **14/09/2026: Daniel pasa la lista cuando se la pidamos — mencionó que hay otra versión de checklist con 2 o 3 ítems más, confirmar cuál usar antes de transcribir.**
- [ ] **Vínculo Toma→Stock al tomar un vehículo:** **Confirmado 14/09/2026: sí** — se carga automático a Stock (a definir si queda "En reparación" u otro estado) **y/o fecha de entrega programada** si la carga automática completa a Stock no se puede resolver de una. Hoy no hay ningún vínculo automático entre una Toma tasada y el módulo Stock.
- [x] ~~Certificado HTTPS~~ → **Descartado 14/09/2026: no hace falta por ahora** — el cartel de "sitio no seguro" es un problema de correr en red local sin HTTPS; una vez que se despliegue en web (ej. Railway) va a andar con HTTPS de forma nativa y este problema deja de existir solo.

### 🟢 IDEAS FUTURAS
- [ ] **Comparables de mercado — integración real:** hoy son links de búsqueda manuales. Daniel preguntó 14/09/2026 cómo se implementaría — propuesta técnica:
  - **MercadoLibre: sí es viable.** Tiene una API pública oficial y gratuita (`api.mercadolibre.com/sites/MLA/search?q=...`), sin necesidad de aprobación para búsquedas básicas, devuelve JSON con precio/título/link/miniatura de cada aviso. Se podría traer los N avisos más relevantes de marca+modelo+versión+año y mostrar un rango (mín/promedio/máx) al lado del valor de tabla en Tasación, en vez de solo el link de búsqueda — sin scraping, 100% dentro de sus términos de uso.
  - **RosarioGarage y Facebook Marketplace: no conviene.** Ninguno tiene una API pública real para esto (Facebook Marketplace requiere acuerdo comercial con Meta, fuera de alcance para una app chica) — scrapearlos sería exactamente lo que decidimos evitar desde el principio (frágil, pisa ToS). Recomendación: dejarlos como link de búsqueda manual como están hoy, e invertir el esfuerzo de integración solo en MercadoLibre.
  - Detalles a resolver si se encara: cachear resultados (no pegarle a la API en cada tecleo), límites de uso de la API gratuita, y qué mostrar cuando no hay resultados para ese modelo/año exacto.
- [ ] **Base de "Mercado Agencieros" propia — cómo se configuraría:** Daniel preguntó 14/09/2026. Depende de tener volumen real de operaciones cargadas en la plataforma entre varias agencias — o sea, depende de que la Red de Agencieros ya sea multi-tenant (ver pendiente 🟡), no solo de "esperar datos". Propuesta cuando llegue el momento: agregar por marca+modelo+versión+año los `valor_vendido` reales de `vehiculos` con estado 'vendido' (la señal más confiable, más que `valor_referencia` de tasaciones que es solo una estimación), calculando un promedio o mediana, con más peso a las ventas más recientes y descartando outliers. Definir un mínimo de operaciones cargadas por modelo antes de mostrar un "Valor de Mercado Agencieros" (con 1 o 2 ventas no alcanza para confiar en el número). No hay nada para construir todavía — es un plan a futuro, condicionado al multi-tenant.
- [x] Notificaciones push/WhatsApp para matches del Banco de pedidos y novedades de la Red. **Confirmado 14/09/2026: sí, hay que implementarlo.**
- [ ] App mobile / PWA (el prototipo visual que subió Daniel está pensado como mobile-first). **14/09/2026: Daniel confirmó que es el paso siguiente, una vez verificado el funcionamiento de la app web.**
- [ ] Bandeja unificada de contacto (tipo Kommo/CRM omnicanal): centralizar en una sola vista Mail, WhatsApp, Messenger, Instagram, Telegram, LinkedIn, etc. — leads y consultas de clientes en un solo lugar. (Pedido por Daniel 13/09/2026. **Reconfirmado 14/09/2026: "me interesa mucho" — alto interés de Daniel, aunque sigue en Ideas futuras por orden de implementación.**)
- [ ] Generador automático de contenido para redes al tomar un vehículo: a partir de los datos ya cargados en Toma/Ficha, armar de una una historia de WhatsApp, un posteo para Facebook, uno para Instagram y la publicación para Marketplace. (Pedido por Daniel 13/09/2026. **Reconfirmado 14/09/2026 con mucho entusiasmo — "sería un golazo!!".**)

---

## Cambios recientes

### Sesión 14/09/2026 (continuación 8) — Nuevo módulo: Financiación (crédito propio, cuotas, cobro/deuda)
Daniel pidió una sección de financiación donde calcular crédito y cuotas, con control de lo cobrado y adeudado. Antes de programar se confirmaron 3 decisiones con Daniel (AskUserQuestion):
- **Es financiación propia de la agencia** (no un simulador de crédito bancario externo) — la agencia le vende en cuotas al cliente y cobra ella misma, con ledger real de cobro/deuda.
- **El simulador de cuotas está disponible libre, para cualquier consulta antes de cerrar una venta** (no depende de tener el vehículo ya marcado como vendido en Stock) — recién al guardar el plan queda un registro real, opcionalmente atado a un vehículo de Stock.
- **Sistema francés (cuota fija)** para el cálculo de cuotas.

**Qué se construyó:**
- `database.py`: 2 tablas nuevas — `financiaciones` (cliente, vehículo opcional, monto financiado, tasa mensual, cantidad de cuotas, valor de cuota, estado activo/finalizado/cancelado) y `financiacion_cuotas` (una fila por cuota: número, vencimiento, monto, monto pagado, fecha de pago, estado).
- `routes/financiacion.py` (blueprint nuevo, registrado en `app.py`): cálculo de cuota por sistema francés (`_calcular_cuota_frances`) y del cronograma completo mes a mes con interés/amortización/saldo (`_generar_cronograma`, con ajuste de centavos en la última cuota para que el saldo cierre en $0 exacto). Rutas: `/financiacion/` (listado + resumen de cobrado/adeudado/vencidas), `/financiacion/simulador` (calculadora libre, GET/POST, sin persistir hasta que se guarda), `/financiacion/nuevo` (persiste el plan + genera las cuotas), `/financiacion/<id>` (detalle con cronograma y botón "Registrar pago" por cuota, admite pago parcial), `/financiacion/<id>/cuota/<id>/pagar`, `/financiacion/<id>/cancelar`. Al cobrarse la última cuota pendiente el plan pasa solo a "Finalizado".
- Templates nuevos: `templates/financiacion/index.html`, `simulador.html`, `detalle.html` — mismo estilo navy/dorado y mismas clases (`.tabla-responsive`, `.badge`, `.card`) que el resto de la app, sin CSS nuevo.
- Ítem de menú nuevo en `templates/base.html`: "🏦 Financiación".
- **Verificación:** copiado todo al entorno de prueba con la base de datos real de Daniel y corrido con el cliente de test de Flask — simulación de cuotas, guardado de un plan real, y registro de un pago, los tres devolvieron 200 y el HTML esperado (cronograma, plan creado, cuota marcada "Pagada"). También se re-probaron de paso `/dashboard`, `/stock/`, `/finanzas/`, `/precios/`, `/tomas/`, `/red/`, `/pedidos/` para confirmar que el cambio en `database.py`/`app.py` no rompió nada existente — todas 200.
- Escritos en la compu de Daniel y confirmado el tamaño de cada archivo contra lo esperado (mismo protocolo desde el incidente del hardlink).
- **Archivos tocados:** `app.py`, `database.py`, `templates/base.html` (modificados), `routes/financiacion.py`, `templates/financiacion/index.html`, `templates/financiacion/simulador.html`, `templates/financiacion/detalle.html` (nuevos).
- **Pendiente:** que Daniel pruebe el flujo real desde el navegador/celu y confirme que los números de cuota le cierran (queda anotado en Pendientes → 🟡 IMPORTANTE). Falta también el commit/push (bloque de Git Bash de esta respuesta).

### Sesión 14/09/2026 (continuación 7) — Repaso de pendientes 🟢 IDEAS FUTURAS con decisiones de Daniel
- **Comparables de mercado — cómo implementarlo:** propuesta técnica agregada — usar la API pública gratuita de MercadoLibre (`api.mercadolibre.com/sites/MLA/search`) para traer precios reales sin scraping; RosarioGarage y Facebook Marketplace quedan como link manual (no tienen API viable para esto, scrapearlos violaría lo que ya habíamos decidido evitar).
- **Base de Mercado Agencieros — cómo se configuraría:** depende de que la Red sea multi-tenant primero (no es solo "esperar datos"). Plan cuando llegue el momento: promediar `valor_vendido` real por marca/modelo/versión/año, con mínimo de operaciones antes de mostrar el número.
- **Notificaciones push/WhatsApp:** confirmado que sí, a implementar.
- **App mobile/PWA:** confirmado como paso siguiente, una vez verificado el funcionamiento de la app web.
- **Bandeja unificada de contacto:** Daniel reconfirmó mucho interés ("me interesa mucho").
- **Generador de contenido para redes:** Daniel reconfirmó con mucho entusiasmo ("sería un golazo!!").
- **Archivos tocados:** `PROYECTO.md` únicamente (decisiones/scoping de producto, no hay código nuevo).

### Sesión 14/09/2026 (continuación 6) — Repaso completo de pendientes 🟡 IMPORTANTE con decisiones de Daniel
- **Red de Agencieros multi-tenant:** confirmado que se implementa recién al cerrar la funcionalidad core — deliberadamente después en la cola, no ahora.
- **Algoritmo de valuación — % de utilidad:** Daniel preguntó de dónde sale hoy. Respuesta: está hardcodeado en `MARGEN_OBJETIVO = 0.15` en `routes/tasacion.py` (15% fijo, no editable desde la UI). Se agrega como pendiente hacerlo configurable — falta decidir si es por toma, por agencia (configuración general), o ambas.
- **Auth real:** alcance confirmado — registro de agencia + validación por mail + cobro por Mercado Pago (mismo patrón que PresupuestoPRO). Queda enganchado con el pendiente 🔴 de modelo de negocio (la suscripción paga depende de esto).
- **Imprimir informe de tasación:** confirmado que sí. Falta diseñar el formato de salida antes de programarlo.
- **Checklist 41 puntos:** Daniel lo pasa cuando se lo pidamos — ojo que mencionó que hay otra versión del checklist con 2-3 ítems más, hay que confirmar cuál usar.
- **Vínculo Toma→Stock:** confirmado que sí — carga automática a Stock y/o fecha de entrega programada si la carga completa no se puede resolver de entrada.
- **Certificado HTTPS:** descartado — no hace falta en local, se resuelve solo al desplegar en web.
- **Archivos tocados:** `PROYECTO.md` únicamente (decisiones de producto).

### Sesión 14/09/2026 (continuación 5) — Decisiones de negocio + nuevo competidor (LUCY.CRM)
- **Nuevo competidor sumado:** LUCY.CRM (crm.lucy.ar), producto nacional — investigado y agregado a la sección Competencia con sus 4 áreas (Comercial/Contable/Gestoría/Servicios), publicación a MercadoLibre y ComunidAuto, y sus 4 planes de precio ($250k-$435,6k/mes). Refuerza el mismo patrón que deConcesionarias y MOBU: todos arriba de $250k/mes, muy lejos de los ~$16.800 que paga hoy un agenciero chico solo por la guía de precios.
- **Decidido: fuente de precios** — carga manual de `precios_base`, no se integra API de InfoAuto por ahora.
- **Decidido: modelo de negocio** — va a ser con planes de suscripción. Falta definir cantidad de planes, qué incluye cada uno y los precios (queda como pendiente 🔴, ahora con LUCY.CRM sumado como referencia de mercado además de deConcesionarias y MOBU).
- **Archivos tocados:** `PROYECTO.md` únicamente (decisiones de producto, no hay código involucrado).

### Sesión 14/09/2026 (continuación 4) — Tabla responsive aplicada a TODOS los listados de la app (no solo Toma técnica)
Daniel reportó el mismo problema de mobile (columnas cortadas, sin forma cómoda de ver todo) pero en el Dashboard ("Últimos vehículos cargados"). Al revisar, era el mismo patrón sin arreglar en TODAS las tablas de listado de la app — el fix de la sesión anterior solo había cubierto la tabla de Paso 1 de Toma técnica.
- Aplicada la misma clase `.tabla-responsive` (tarjetas apiladas en mobile, ya probada) a las tablas de: **Dashboard** (últimos vehículos), **Toma y tasación** (listado de tomas), **Stock** (listado de vehículos), **Red de Agencieros** (publicaciones), **Banco de pedidos** (listado de pedidos) y **Finanzas** (las 3 tablas: ganancia por mes, por año, y ranking de rentabilidad).
- No se tocaron: la ficha de un vehículo en Stock (`stock/detalle.html`, tabla de 2 columnas dato/valor — no se corta) ni el historial de precios en Consulta (`precios/resultado.html`, también 2 columnas) — esas no tienen el problema.
- **Verificación:** esta vez, antes de avisar que estaba resuelto, corrí el flujo real contra la base de datos de Daniel para las 6 páginas tocadas (`/dashboard/`, `/tomas/`, `/stock/`, `/red/`, `/pedidos/`, `/finanzas/`) — todas 200 OK. Además, después de escribir los archivos en su compu, releí el tamaño de cada uno para confirmar que quedaron guardados de verdad (por el susto de la vez pasada con `tasacion.html`).
- **Archivos tocados:** `templates/dashboard.html`, `templates/tomas/index.html`, `templates/stock/index.html`, `templates/red/index.html`, `templates/pedidos/index.html`, `templates/finanzas/index.html`.
- **Pendiente:** que Daniel confirme desde el celu que ahora se ve bien en estas 6 pantallas.

### Sesión 14/09/2026 (continuación 3) — Bug crítico: TypeError al calcular la Tasación (rompía toda la pantalla)
Daniel reportó `TypeError: 'builtin_function_or_method' object is not iterable` al llegar al Paso 3 desde el Paso 2, tanto en la compu como en el celu — la pantalla de Tasación no cargaba directamente. Era una regresión introducida en el rediseño de este mismo día (sesión "continuación").
- **Causa:** en `_agrupar_danios_por_vista` (routes/tomas.py), cada grupo se armaba con una clave `"items"`. En el template, `{% for d in g.items %}` — en Jinja, `g.items` sobre un diccionario resuelve primero al **método** `dict.items()` (built-in de Python) antes que a la clave `"items"` que yo había puesto. Al no llamarlo (sin paréntesis) e intentar iterarlo, explotaba con exactamente ese error. Pasaba siempre que la toma tenía algún daño con costo cargado en el Paso 2 (la toma #7 del ejemplo de Daniel los tenía).
- **Fix:** renombrada la clave a `"danios"` en `_agrupar_danios_por_vista` y actualizados los dos lugares de `templates/tomas/tasacion.html` que la usaban (`g.items` → `g.danios`).
- **Verificación:** esta vez, además de compilar el Python y parsear el Jinja (que no detectan este tipo de error — el chequeo de sintaxis pasa igual), armé una copia funcional de la app completa en un entorno de prueba con la base de datos real de Daniel y corrí el flujo real con el cliente de test de Flask: `GET /tomas/7/tasacion`, `POST` calculando la tasación (con los daños con costo reales de esa toma, el mismo caso que rompía), y de nuevo `GET` para ver la tasación ya guardada — los tres devolvieron 200 y el HTML generado incluye el panel agrupado por foto correctamente. También se probaron `/tomas/7` (ficha), `/tomas/nueva` (Paso 1) y `/tomas/` (listado) por las dudas, todas 200.
- **Aprendizaje para mí:** de acá en más, cuando arme un diccionario para pasarlo a un template Jinja, evito nombres de clave que choquen con métodos de dict (`items`, `keys`, `values`, `get`, `update`, etc.) — y para cambios en la lógica de Tasación en particular, corro el flujo real (no solo compilar/parsear) antes de darlo por terminado.
- **Archivos tocados:** `routes/tomas.py`, `templates/tomas/tasacion.html`.
- **⚠️ Nota importante descubierta después:** el primer intento de guardar el fix de `templates/tomas/tasacion.html` reportó éxito pero el archivo en la compu de Daniel **no quedó con el cambio** (Daniel siguió viendo el mismo error). Al revisar, la herramienta que lee archivos de la compu de Daniel devolvió un error puntual: *"file is hardlinked (nlink > 1)"* — es decir, ese archivo específico tiene más de un nombre apuntando a los mismos datos en el disco (un hard link), algo nada común para un archivo de proyecto suelto. Sospecha: podría estar relacionado con el mismo tipo de conflicto de sincronización de OneDrive que ya había dado problemas antes (ver incidente de `catalogo-1.js`, sesión 14/09 anterior), o con algún backup/versionado que Daniel tenga corriendo sobre esa carpeta. Se volvió a escribir el archivo y esta vez el tamaño en disco quedó igual al esperado (7487 bytes), pero **queda pendiente confirmar con Daniel** si el problema aparece de nuevo — si es así, correr `fsutil hardlink list "D:\ESCRITORIO\CLAUDE\03_AUTOMOTOR\APP_AGENCIEROS\templates\tomas\tasacion.html"` en Git Bash para ver qué otro archivo comparte los mismos datos.

### Sesión 14/09/2026 (continuación 2) — Bug mobile: tabla de Paso 1 se cortaba (Costo/Comentario invisibles)
Daniel reportó que en el celu seguía sin verse Costo y Comentario en la tabla de puntos técnicos (la vista de una Toma ya guardada, `tomas/detalle.html`, que muestra el resumen del Paso 1 justo arriba del Paso 3 · Tasación — de ahí que lo describiera como "en la tasación"). Era el bug mobile que había quedado anotado en Pendientes.
- **Causa:** la tabla de 4 columnas (Punto/Calificación/Costo/Comentario) no tenía ningún tratamiento responsive — en pantallas chicas el navegador la angostaba hasta hacer imposible leer Costo y Comentario, sin un scroll evidente para el usuario.
- **Solución:** en vez de agregar solo scroll horizontal (poco notorio en el celu), se armó un layout de tarjetas apiladas para pantallas ≤700px: cada fila pasa a ser una tarjeta con el nombre de cada columna arriba de su valor (clase `.tabla-responsive` + `data-label` en cada `<td>`, con la regla en `static/css/style.css`). Se aplicó tanto en el formulario de carga (Paso 1, `tomas/form.html`) como en la vista de una toma ya guardada (`tomas/detalle.html`).
- **De paso:** en `detalle.html` se sacó la fila "Total reparación/limpieza (Paso 1)" de adentro de la tabla (quedaba con celdas vacías raras en el layout apilado) y pasó a ser un párrafo aparte debajo.
- **Archivos tocados:** `static/css/style.css`, `templates/tomas/form.html`, `templates/tomas/detalle.html`.
- **Pendiente:** Daniel probar de nuevo desde el celu que ahora sí se vean Costo y Comentario, y confirmar que el layout de tarjetas se vea bien (no solo "arreglado").

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
- **(14/09/2026) Fuente de precios:** carga manual de `precios_base` por ahora, sin integración por API con InfoAuto.
- **(14/09/2026) Modelo de negocio:** va a ser con planes de suscripción (no definidos todavía en cantidad/contenido/precio — ver pendiente 🔴).
