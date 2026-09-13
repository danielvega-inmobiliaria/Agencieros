# AGENCIEROS — Contexto del Proyecto

## Cómo usar este archivo
- **Al empezar un chat nuevo:** pegá → `Leé PROYECTO.md y continuá desde donde quedamos`
- **Al terminar un chat:** pedí → `Actualizá PROYECTO.md con lo que hicimos hoy`

---

_Última actualización: 15/07/2026 — 20:45 ART_

## Qué es este proyecto
**AGENCIEROS**: la plataforma más completa para agencias de automotores de Argentina. Unifica consulta de precios, gestión del negocio, tasación, rentabilidad y una red de colaboración entre agencieros.

**Gancho comercial:** hoy los agencieros pagan ~$16.800 solo para consultar precios (ej. InfoAuto). AGENCIEROS ofrece lo mismo (consulta marca/modelo/versión/año → precio) a un costo similar, pero con una app de gestión completa incluida. La consulta de precios es la **pantalla principal** de la app — desde ahí nacen las demás acciones (tasar, comprar, cargar a stock, publicar, vender, compartir con la Red).

**Nombre elegido:** Agencieros (de una lista de 10 opciones evaluadas: AutoRed, AutoGestión, DealerNet, AutoBroker, AutoBase, MotorHub, StockAuto, ValorAuto, Dealer360).

**Diferencial vs. la competencia** (que solo ofrece guía de precios): gestión completa + tasación inteligente + control financiero + seguimiento de clientes + red de agencieros + base de valuaciones propia + inteligencia de negocio.

**Visión a largo plazo:** que AGENCIEROS sea el estándar de agencias de autos en Argentina. Con masa crítica de usuarios, las operaciones cargadas por las agencias generan un "Valor de Mercado Agencieros" propio, potencialmente más representativo que una guía tradicional.

## Módulos (11)
1. **Consulta de precios** (gancho comercial) — marca/modelo/versión/año → precio de referencia. Base inicial con valores tipo InfoAuto (carga manual por ahora, sin integración por API).
2. **Stock de vehículos** — estados Disponible / Por ingresar / En reparación / Vendido. Ficha completa (fotos, características, equipamiento, km, combustible, caja, observaciones, documentación, historial).
3. **Banco de pedidos** — clientes que buscan un vehículo. Aviso automático cuando ingresa una unidad que matchea.
4. **Toma de vehículos** — ficha de inspección técnica: motor, caja, embrague, frenos, suspensión, dirección, interior, tapizados, cubiertas, electricidad, aire acondicionado, documentación. Calificación Excelente/Bueno/Regular/Malo.
5. **Inspección visual de chapa** — 5 vistas (frente, trasera, lateral izq/der, superior) con marcadores arrastrables sobre la imagen (golpes, rayones, vidrios rotos, ópticas, paragolpes, abolladuras), cada uno con gravedad, descripción y foto opcional.
6. **Tasación inteligente** — a partir de valor de referencia + estado mecánico + estado estético + gastos estimados, calcula precio máximo recomendado de compra, riesgo y margen esperado.
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
- [ ] Inspección visual de chapa (módulo 5): hoy es un stub — falta el canvas interactivo para arrastrar marcadores sobre las 5 vistas del auto. Requiere JS más elaborado (ej. Fabric.js o similar).
- [ ] Subida real de fotos de vehículos (hoy `vehiculo_fotos` existe en el schema pero no hay UI de carga de archivos).
- [ ] Red de Agencieros (módulo 9) hoy es de un solo tenant/DB — para que sea red real entre agencias distintas hace falta multi-tenant (cada agencia con su login) y notificaciones.
- [ ] Algoritmo de valuación (módulo 11): la fórmula de Tasación es una primera versión simple (factores fijos), no aprende de operaciones reales todavía.
- [ ] Auth real (hoy es login simple tipo PresupuestoPRO, sin registro de agencias ni roles).

### 🟢 IDEAS FUTURAS
- [ ] Base de Mercado Agencieros: una vez con operaciones reales cargadas, generar valores propios más allá de InfoAuto.
- [ ] Notificaciones push/WhatsApp para matches del Banco de pedidos y novedades de la Red.
- [ ] App mobile / PWA (el prototipo visual que subió Daniel está pensado como mobile-first).
- [ ] Bandeja unificada de contacto (tipo Kommo/CRM omnicanal): centralizar en una sola vista Mail, WhatsApp, Messenger, Instagram, Telegram, LinkedIn, etc. — leads y consultas de clientes en un solo lugar. (Pedido por Daniel 13/09/2026.)
- [ ] Generador automático de contenido para redes al tomar un vehículo: a partir de los datos ya cargados en Toma/Ficha, armar de una una historia de WhatsApp, un posteo para Facebook, uno para Instagram y la publicación para Marketplace. (Pedido por Daniel 13/09/2026.)

---

## Cambios recientes

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
