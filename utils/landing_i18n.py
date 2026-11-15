"""Textos de la landing pública (agencieros.net.ar) en español e inglés.

La landing se renderiza en el servidor según el idioma: ?lang=es|en (se guarda
en una cookie), luego la cookie y, si no hay nada, el Accept-Language del
navegador. Por defecto, español. Para cambiar un texto se edita acá.
"""

IDIOMAS = ("es", "en")


def elegir_idioma(args, cookies, accept_language=""):
    """Devuelve (idioma, guardar_cookie)."""
    pedido = (args.get("lang") or "").strip().lower()[:2]
    if pedido in IDIOMAS:
        return pedido, True
    previo = (cookies.get("lang") or "").strip().lower()[:2]
    if previo in IDIOMAS:
        return previo, False
    for parte in (accept_language or "").split(","):
        cod = parte.split(";")[0].strip().lower()[:2]
        if cod in IDIOMAS:
            return cod, False
    return "es", False


ES = {
    "html_lang": "es",
    "og_locale": "es_AR",
    "title": "AGENCIEROS — La app para agencias de autos usados de Rosario",
    "meta_desc": "La app para agencias de autos usados de Rosario y zona: precios de referencia con avisos reales, stock, toma y tasación con checklist de 44 puntos, web propia de tu agencia, compartir en redes, financiación y red de agencias. Probala gratis 30 días.",
    "og_title": "AGENCIEROS — La plataforma para agencias de autos",
    "og_desc": "Precios, stock, toma y tasación, web propia, compartir en redes y una red de agencias.",
    "nav_funciones": "Funciones",
    "nav_como": "Cómo funciona",
    "nav_modulos": "Módulos",
    "btn_ingresar": "Ingresar",
    "btn_registro": "Registrá tu agencia",
    "btn_gratis": "Probala gratis 30 días",
    "btn_tengo": "Ya tengo cuenta",
    "btn_demo": "Ver la demo",
    "idioma_label": "Idioma",
    "eyebrow_hero": "Para agencias de autos usados de Rosario y zona",
    "h1_a": "Todo el negocio de tu agencia, ",
    "h1_b": "en el celular.",
    "lead": "Consultá el precio de referencia con avisos reales de Rosario, cargá tu stock, tasá cada toma con checklist de 44 puntos y las deudas del auto, armá la web de tu agencia, compartí en redes y trabajá en red con otras agencias de la zona.",
    "hero_note": "30 días gratis, sin tarjeta. Se usa desde el celular o la compu, y se puede instalar como app.",
    "aria_pantallas": "Pantallas de la app",
    "hint": "Deslizá para ver más",
    "sc": [
        ("Precios al instante", "Valor de referencia e historial por año"),
        ("Banco de pedidos", "Lo que busca cada cliente"),
        ("Toma y tasación", "Inspección de 44 puntos"),
        ("Dashboard", "Tu agencia de un vistazo"),
        ("Red de Agencieros", "Ofrecé y buscá entre agencias de Rosario"),
    ],
    "alt_precios": "Consulta de precios: resultado y historial de valores de referencia",
    "alt_pedidos": "Banco de pedidos: lo que busca cada cliente",
    "alt_tasacion": "Tasación de una toma con qué hay que reparar y resultado",
    "alt_dashboard": "Dashboard con stock por estado, ventas y gastos",
    "alt_red": "Red de Agencieros: ofertas y búsquedas de otras agencias",
    "alt_tasacion2": "Pantalla de tasación con resultado",
    "alt_stock": "Stock de vehículos con fotos, precio y estado",
    "alt_ficha": "Ficha comercial de una Toyota Hilux con foto, precio y equipamiento",
    "alt_fin": "Simulador de financiación propia con cuota calculada",
    "chips": [
        ("i-price", "Consulta de precios", "Referencia en segundos"),
        ("i-car", "Stock y ventas", "Con seña, permuta o crédito"),
        ("i-check", "Toma y tasación", "Inspección y deudas"),
        ("i-globe", "Web y redes", "Tu web y tus imágenes"),
        ("i-users", "Red de agencias", "Pedidos y ofertas"),
    ],
    # --- 01 Tasación
    "s1_eyebrow": "01  Toma y tasación",
    "s1_title": "Tomá el auto sabiendo cuánto vale y qué le falta.",
    "s1_lead": "Cuando un cliente te trae su auto, la app te guía por toda la toma y te devuelve un número para negociar con respaldo.",
    "s1_ticks": [
        "Datos del vehículo, service y códigos de falla en un solo lugar.",
        "Fotos de cada vista del auto, con los golpes y rayones marcados sobre la imagen.",
        "Inspección de 44 puntos: cada punto en bueno, regular o malo, con su costo estimado.",
        "Deudas de patentes y multas: la app abre cada portal oficial, cargás el resultado y se descuenta del valor de toma.",
        "Tasación con el precio de referencia, los gastos de reparación, las deudas y el margen que querés ganar.",
        "Con un toque, la toma pasa a tu stock.",
    ],
    # --- 02 Stock
    "s2_eyebrow": "02  Stock y ficha comercial",
    "s2_title": "Tu stock, listo para mostrar y vender.",
    "s2_lead": "Cargá cada vehículo con sus fotos y su precio. Cada uno tiene su ficha pública para mandar por WhatsApp.",
    "s2_ticks": [
        "Fotos, precio, kilometraje y equipamiento de cada vehículo.",
        "Estado de cada unidad: disponible, por ingresar, en reparación, señado o vendido.",
        "Ventas con seña, permuta o crédito, registradas desde el mismo stock.",
        "Ficha comercial con botón de WhatsApp para compartir con el cliente.",
    ],
    # --- 03 Web y redes
    "s3_eyebrow": "03  Tu web y tus redes",
    "s3_title": "Una web para tu agencia, sin diseñador ni programador.",
    "s3_lead": "Elegís qué autos se muestran y la app arma tu web pública con el link de tu agencia. Después, convertís cada auto en una imagen lista para tus redes.",
    "s3_web_h": "Web propia de tu agencia",
    "s3_web": [
        "Link propio con el nombre de tu agencia y tu logo.",
        "Usados, 0 Km y «Compramos tu auto», con menú fijo en el celular.",
        "Buscador con filtros y formulario de contacto: te llega el pedido con forma de pago y valor del auto que busca.",
        "Elegís qué unidades se muestran en tu web.",
    ],
    "s3_red_h": "Compartir en redes",
    "s3_red": [
        "5 plantillas de imagen: Historia, Post cuadrado, Post 4:5, Facebook/Marketplace y collage de 3 fotos.",
        "Elegís las fotos y editás el texto, el precio y la llamada a la acción.",
        "Sumás el logo de tu agencia y descargás la imagen lista para publicar.",
    ],
    # --- 04 Financiación
    "s4_eyebrow": "04  Financiación propia",
    "s4_title": "El simulador de cuotas, a mano en el momento de la venta.",
    "s4_lead": "Armá el plan con tu cliente: monto, cantidad de cuotas, periodicidad y tasa. La app calcula la cuota, el total y el interés.",
    "s4_ticks": [
        "Cuota calculada y cuota aplicada redondeada.",
        "Cobro mensual o semanal, con la fecha de la primera cuota.",
        "Seguimiento de cuotas cobradas, por cobrar y vencidas.",
    ],
    "disponible": "Disponible",
    # --- 05 Red
    "s5_eyebrow": "05  Red de Agencieros",
    "s5_title": "Trabajá en red, con quién vos elijas.",
    "s5_lead": "Ofrecé tus unidades y encontrá lo que te piden tus clientes entre las agencias de Rosario y zona, con contacto directo.",
    "s5_ticks": [
        "Publicá a toda la Red o solo a las agencias que vos tildes.",
        "«No compartir con»: dejás afuera a las agencias que no querés que vean lo tuyo.",
        "Matches automáticos entre lo que buscan tus clientes, tu stock y la Red.",
        "Ranking para ver cómo viene cada vendedor.",
    ],
    # --- 06 Dashboard
    "s6_eyebrow": "06  Dashboard",
    "s6_title": "Tu agencia de un vistazo.",
    "s6_lead": "Un tablero con lo que importa cada día, sin planillas ni cuentas a mano.",
    "s6_ticks": [
        "Stock por estado: disponible, por ingresar, en reparación, señado.",
        "Pedidos activos y ventas del mes.",
        "Gastos en reparación y ganancia del mes.",
    ],
    # --- Cómo funciona
    "como_eyebrow": "Cómo funciona",
    "como_title": "Empezá en tres pasos.",
    "como_lead": "Sin instalar nada y sin cargar todo de golpe.",
    "pasos": [
        ("Registrá tu agencia", "30 días gratis, sin tarjeta. Nombre, teléfono, dirección y un email. Te mandamos un código para verificarlo."),
        ("Cargá tu stock", "Sumá tus vehículos con fotos y precio. Tu ficha, tu web y tu WhatsApp quedan listos para compartir."),
        ("Tasá, vendé y conectate", "Hacé tomas con inspección, seguí tus ventas y publicá lo que ofrecés o buscás en la Red."),
    ],
    # --- Módulos
    "mod_eyebrow": "Módulos",
    "mod_title": "Lo que trae AGENCIEROS.",
    "mod_lead": "Un sistema hecho por y para agencieros. Todos los módulos están disponibles desde el primer día.",
    "mods": [
        ("i-price", "Consulta de precios", "Valor de referencia e historial por año, con la fecha del dato y avisos reales publicados en Rosario."),
        ("i-car", "Stock", "Tus vehículos con fotos, estado y precio. Ventas con seña, permuta o crédito."),
        ("i-check", "Toma, inspección y tasación", "Inspección de 44 puntos, deudas de patentes y multas, y tasación con gastos y margen."),
        ("i-chat", "Ficha comercial", "Página pública de cada auto para mandar por WhatsApp."),
        ("i-globe", "Web de tu agencia", "Tu web pública con Usados, 0 Km, Buscador, «Compramos tu auto» y formulario de contacto."),
        ("i-image", "Compartir en redes", "Imágenes listas para Historias, Instagram, Facebook y Marketplace, con tu logo."),
        ("i-list", "Banco de pedidos", "Anotá lo que busca cada cliente, con marca, modelo y presupuesto. Cuando entra un auto que coincide, la app te avisa."),
        ("i-users", "Red de Agencieros", "Ofrecé tus unidades y encontrá lo que te piden, con contacto directo. Elegís quién ve cada publicación."),
        ("i-target", "Matches", "Cruce automático entre lo que buscan tus clientes y lo que hay en tu stock, por ingresar o en la Red."),
        ("i-chart", "Dashboard y Ranking", "Stock, pedidos, ventas, gastos y ganancia del mes, y el ranking de tus vendedores."),
        ("i-bank", "Financiación propia", "Simulador de cuotas y seguimiento de cobros de tus planes."),
        ("i-phone", "App instalable", "Se instala en el celular desde el navegador y se abre como una app más."),
    ],
    # --- CTA final
    "fin_a": "Probá ",
    "fin_b": " en tu negocio.",
    "fin_p": "Probala gratis 30 días, sin tarjeta. Te registrás en un minuto y empezás a cargar tu stock hoy.",
    "seguinos_h": "Seguinos en redes",
    "seguinos_p": "Novedades de la app, tips para tu agencia y nuevas funciones.",
    "pie_lema": "Consultá, tasá, comprá, vendé.",
    "pie_alt": "Desarrollado por DanguiApps",
}

EN = {
    "html_lang": "en",
    "og_locale": "en_US",
    "title": "AGENCIEROS — The app for used-car dealerships in Rosario, Argentina",
    "meta_desc": "The app for used-car dealerships in Rosario and nearby: reference prices backed by real listings, inventory, trade-in appraisal with a 44-point checklist, your own dealership website, social media sharing, financing and a network of dealerships. Try it free for 30 days.",
    "og_title": "AGENCIEROS — The platform for car dealerships",
    "og_desc": "Prices, inventory, trade-in appraisal, your own website, social media sharing and a dealership network.",
    "nav_funciones": "Features",
    "nav_como": "How it works",
    "nav_modulos": "Modules",
    "btn_ingresar": "Log in",
    "btn_registro": "Sign up your dealership",
    "btn_gratis": "Try it free for 30 days",
    "btn_tengo": "I already have an account",
    "btn_demo": "See the demo",
    "idioma_label": "Language",
    "eyebrow_hero": "For used-car dealerships in Rosario and the surrounding area",
    "h1_a": "Your whole dealership, ",
    "h1_b": "in your pocket.",
    "lead": "Check reference prices backed by real Rosario listings, load your inventory, appraise every trade-in with a 44-point checklist and the vehicle's debts, build your dealership's website, share on social media and work with other dealerships nearby.",
    "hero_note": "30 days free, no card required. Works on your phone or computer, and can be installed as an app.",
    "aria_pantallas": "App screens",
    "hint": "Swipe to see more",
    "sc": [
        ("Instant prices", "Reference value and history by year"),
        ("Request board", "What each customer is looking for"),
        ("Trade-in appraisal", "44-point inspection"),
        ("Dashboard", "Your dealership at a glance"),
        ("Agencieros Network", "Offer and search among Rosario dealerships"),
    ],
    "alt_precios": "Price lookup: result and history of reference values",
    "alt_pedidos": "Request board: what each customer is looking for",
    "alt_tasacion": "Trade-in appraisal showing what needs repair and the result",
    "alt_dashboard": "Dashboard with inventory by status, sales and expenses",
    "alt_red": "Agencieros Network: offers and searches from other dealerships",
    "alt_tasacion2": "Appraisal screen with result",
    "alt_stock": "Vehicle inventory with photos, price and status",
    "alt_ficha": "Sales sheet for a Toyota Hilux with photo, price and equipment",
    "alt_fin": "In-house financing simulator with calculated installment",
    "chips": [
        ("i-price", "Price lookup", "Reference in seconds"),
        ("i-car", "Inventory & sales", "Deposit, trade-in or credit"),
        ("i-check", "Trade-in & appraisal", "Inspection and debts"),
        ("i-globe", "Website & social", "Your site and your images"),
        ("i-users", "Dealer network", "Requests and offers"),
    ],
    "s1_eyebrow": "01  Trade-in & appraisal",
    "s1_title": "Take in a car knowing what it's worth and what it needs.",
    "s1_lead": "When a customer brings in their car, the app walks you through the whole intake and gives you a number you can negotiate with.",
    "s1_ticks": [
        "Vehicle data, service history and fault codes in one place.",
        "Photos of every side of the car, with dents and scratches marked on the image.",
        "44-point inspection: each point rated good, fair or poor, with its estimated cost.",
        "Unpaid vehicle tax and fines: the app opens each official portal, you enter the result and it is deducted from the trade-in value.",
        "Appraisal with the reference price, repair costs, debts and the margin you want to earn.",
        "One tap moves the trade-in to your inventory.",
    ],
    "s2_eyebrow": "02  Inventory & sales sheet",
    "s2_title": "Your inventory, ready to show and sell.",
    "s2_lead": "Load each vehicle with its photos and price. Each one gets a public sales sheet you can send by WhatsApp.",
    "s2_ticks": [
        "Photos, price, mileage and equipment for every vehicle.",
        "Status of each unit: available, incoming, in repair, reserved or sold.",
        "Sales with deposit, trade-in or credit, recorded right from the inventory.",
        "Sales sheet with a WhatsApp button to share with the customer.",
    ],
    "s3_eyebrow": "03  Your website & social media",
    "s3_title": "A website for your dealership, no designer or developer needed.",
    "s3_lead": "You choose which cars are shown and the app builds your public website with your own dealership link. Then you turn each car into an image ready for social media.",
    "s3_web_h": "Your dealership's own website",
    "s3_web": [
        "Your own link, with your dealership's name and logo.",
        "Used cars, new cars and «We buy your car», with a fixed menu on mobile.",
        "Search with filters and a contact form: requests arrive with payment method and the value of the car they want.",
        "You pick which units appear on your website.",
    ],
    "s3_red_h": "Share on social media",
    "s3_red": [
        "5 image templates: Story, square Post, 4:5 Post, Facebook/Marketplace and a 3-photo collage.",
        "Pick the photos and edit the text, price and call to action.",
        "Add your dealership's logo and download the image ready to post.",
    ],
    "s4_eyebrow": "04  In-house financing",
    "s4_title": "The installment simulator, at hand when you close the sale.",
    "s4_lead": "Build the plan with your customer: amount, number of installments, frequency and rate. The app calculates the installment, the total and the interest.",
    "s4_ticks": [
        "Calculated installment and a rounded applied installment.",
        "Monthly or weekly collection, with the date of the first installment.",
        "Tracking of installments collected, due and overdue.",
    ],
    "disponible": "Available",
    "s5_eyebrow": "05  Agencieros Network",
    "s5_title": "Work as a network, with whoever you choose.",
    "s5_lead": "Offer your units and find what your customers are asking for among the dealerships of Rosario and the surrounding area, with direct contact.",
    "s5_ticks": [
        "Publish to the whole Network or only to the dealerships you tick.",
        "«Don't share with»: leave out the dealerships you don't want to see your listings.",
        "Automatic matches between what your customers want, your inventory and the Network.",
        "Ranking to see how each salesperson is doing.",
    ],
    "s6_eyebrow": "06  Dashboard",
    "s6_title": "Your dealership at a glance.",
    "s6_lead": "A board with what matters each day, no spreadsheets or manual math.",
    "s6_ticks": [
        "Inventory by status: available, incoming, in repair, reserved.",
        "Active requests and sales for the month.",
        "Repair expenses and profit for the month.",
    ],
    "como_eyebrow": "How it works",
    "como_title": "Get started in three steps.",
    "como_lead": "Nothing to install, and no need to load everything at once.",
    "pasos": [
        ("Sign up your dealership", "30 days free, no card required. Name, phone, address and an email. We send you a code to verify it."),
        ("Load your inventory", "Add your vehicles with photos and price. Your sales sheets, your website and your WhatsApp are ready to share."),
        ("Appraise, sell and connect", "Take in trade-ins with inspection, track your sales and publish what you offer or look for in the Network."),
    ],
    "mod_eyebrow": "Modules",
    "mod_title": "What AGENCIEROS includes.",
    "mod_lead": "A system built by and for car dealers. Every module is available from day one.",
    "mods": [
        ("i-price", "Price lookup", "Reference value and history by year, with the data's date and real listings published in Rosario."),
        ("i-car", "Inventory", "Your vehicles with photos, status and price. Sales with deposit, trade-in or credit."),
        ("i-check", "Trade-in, inspection & appraisal", "44-point inspection, unpaid tax and fines, and appraisal with costs and margin."),
        ("i-chat", "Sales sheet", "A public page for each car to send by WhatsApp."),
        ("i-globe", "Your dealership website", "Your public site with Used, New, Search, «We buy your car» and a contact form."),
        ("i-image", "Social media sharing", "Images ready for Stories, Instagram, Facebook and Marketplace, with your logo."),
        ("i-list", "Request board", "Note what each customer is looking for, with make, model and budget. When a matching car comes in, the app lets you know."),
        ("i-users", "Agencieros Network", "Offer your units and find what others ask for, with direct contact. You choose who sees each listing."),
        ("i-target", "Matches", "Automatic cross-matching between what your customers want and what you have in stock, incoming or in the Network."),
        ("i-chart", "Dashboard & Ranking", "Inventory, requests, sales, expenses and monthly profit on one screen, plus your salespeople's ranking."),
        ("i-bank", "In-house financing", "Installment simulator and collection tracking for your plans."),
        ("i-phone", "Installable app", "Install it on your phone from the browser and open it like any other app."),
    ],
    "fin_a": "Try ",
    "fin_b": " in your business.",
    "fin_p": "Try it free for 30 days, no card required. Sign up in a minute and start loading your inventory today.",
    "seguinos_h": "Follow us",
    "seguinos_p": "App news, tips for your dealership and new features.",
    "pie_lema": "Check, appraise, buy, sell.",
    "pie_alt": "Developed by DanguiApps",
}

TEXTOS = {"es": ES, "en": EN}
