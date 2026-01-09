let leyData = null;
let dictamenData = null;
let modifiedArticles = new Set();
let derogatedArticles = new Set(); // Artículos derogados individualmente
let derogatedChapters = new Map(); // Mapa de capítulo -> Set de artículos derogados

function extractArticleNumberFromHeader(encabezado) {
    if (!encabezado) return null;
    
    // Para incorporaciones, buscar "como artículo X" o "artículo X" después de incorpórase
    const incorporacionMatch = encabezado.match(/incorp[óo]rase\s+como\s+art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)/i);
    if (incorporacionMatch) {
        return incorporacionMatch[1].trim();
    }
    
    // Fallback: buscar cualquier "artículo X" con sufijos
    const match = encabezado.match(/art[íi]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)/i);
    if (match) {
        return match[1].trim();
    }
    
    return null;
}

function getDestinoArticulo(cambio) {
    // Prioridad 1: destino_articulo explícito
    if (cambio.destino_articulo) {
        return String(cambio.destino_articulo);
    }
    
    // Prioridad 2: extraer desde texto_nuevo (más confiable)
    if (cambio.texto_nuevo) {
        const match = cambio.texto_nuevo.match(/ART[ÍI]CULO\s+(\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?)\s*[°º]?-/i);
        if (match) {
            return match[1].trim();
        }
    }
    
    // Prioridad 3: extraer desde encabezado
    const fromHeader = extractArticleNumberFromHeader(cambio.encabezado);
    return fromHeader ? String(fromHeader) : null;
}

async function init() {
    try {
        const [leyResponse, dictamenResponse] = await Promise.all([
            fetch('../data/ley_contrato_trabajo_oficial_completa.json'),
            fetch('../data/dictamen_modernizacion_laboral_titulo_I.json')
        ]);

        leyData = await leyResponse.json();
        dictamenData = await dictamenResponse.json();

        processDictamenData();
        setupEventListeners();
        renderTOC();
        renderSplitView();
    } catch (error) {
        console.error('Error cargando datos:', error);
        document.getElementById('split-content').innerHTML = 
            '<p class="error">Error al cargar los datos. Asegúrese de que los archivos JSON estén disponibles.</p>';
    }
}

function findArticlesInChapter(capituloNumero) {
    const articles = [];
    const titulos = leyData.ley.titulos;
    
    for (const titulo of titulos) {
        if (titulo.capitulos) {
            for (const capitulo of titulo.capitulos) {
                const capNum = String(capitulo.numero).toUpperCase();
                const targetCapNum = String(capituloNumero).toUpperCase();
                
                if (capNum === targetCapNum && capitulo.articulos) {
                    for (let i = 0; i < capitulo.articulos.length; i++) {
                        const articulo = capitulo.articulos[i];
                        // Si el artículo no tiene número o es "S/N", usar un identificador basado en índice
                        const numero = String(articulo.numero || '').trim();
                        if (numero === '' || numero.toUpperCase() === 'S/N' || numero === 'null') {
                            // Crear identificador único: "CAP_VIII_ART_1", "CAP_VIII_ART_2", etc.
                            articles.push(`CAP_${capituloNumero}_ART_${i + 1}`);
                        } else {
                            articles.push(numero);
                        }
                    }
                }
            }
        }
    }
    
    return articles;
}

function processDictamenData() {
    dictamenData.forEach(cambio => {
        // Detectar derogaciones de capítulos completos
        if (cambio.destino_capitulo) {
            const capituloNumero = cambio.destino_capitulo;
            const articlesInChapter = findArticlesInChapter(capituloNumero);
            derogatedChapters.set(capituloNumero, new Set(articlesInChapter));
            // Marcar todos los artículos del capítulo como modificados
            articlesInChapter.forEach(artNum => {
                modifiedArticles.add(artNum);
                derogatedArticles.add(artNum);
            });
            
            // Si no se encontraron artículos (capítulo no existe o tiene artículos sin número),
            // crear artículos sintéticos para mostrar la derogación
            if (articlesInChapter.length === 0) {
                // Para el Capítulo VIII de Formación Profesional, crear artículos sintéticos
                // basados en la información proporcionada por el usuario (7 artículos sin número)
                if (capituloNumero.toUpperCase() === 'VIII') {
                    // Crear identificadores para los 7 artículos sin número del Capítulo VIII
                    for (let i = 1; i <= 7; i++) {
                        const artId = `CAP_VIII_ART_${i}`;
                        modifiedArticles.add(artId);
                        derogatedArticles.add(artId);
                    }
                    derogatedChapters.set(capituloNumero, new Set(Array.from({length: 7}, (_, i) => `CAP_VIII_ART_${i + 1}`)));
                }
            }
        } else {
            // Otras modificaciones (incorporaciones, sustituciones, etc.)
            const destinoArticulo = getDestinoArticulo(cambio);
            if (destinoArticulo) {
                modifiedArticles.add(destinoArticulo);
                // Si es una derogación individual, marcarla
                if (cambio.accion === "derógase" || cambio.accion === "derogase") {
                    derogatedArticles.add(destinoArticulo);
                }
            }
        }
    });
}

function setupEventListeners() {
    // TOC toggle button
    const tocToggle = document.getElementById('toc-toggle');
    const tocSidebar = document.getElementById('toc-sidebar');
    if (tocToggle && tocSidebar) {
        tocToggle.addEventListener('click', () => {
            tocSidebar.classList.toggle('toc-visible');
        });
    }
    
    // Close TOC when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 1024 && tocSidebar && tocSidebar.classList.contains('toc-visible')) {
            if (!tocSidebar.contains(e.target) && tocToggle && !tocToggle.contains(e.target)) {
                tocSidebar.classList.remove('toc-visible');
            }
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (window.innerWidth > 1024 && tocSidebar) {
            // On desktop, always show TOC (remove hidden class)
            tocSidebar.classList.remove('toc-visible');
        }
    });
    
    // Scroll tracking - now on window instead of split-content
    window.addEventListener('scroll', updateActiveTOCItem);
}

function updateActiveTOCItem() {
    const scrollableElements = document.querySelectorAll('.split-article-row[id], .split-section-header[id]');
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const offset = 200;
    
    let activeElement = null;
    let activeType = null;
    
    for (let i = scrollableElements.length - 1; i >= 0; i--) {
        const element = scrollableElements[i];
        const elementTop = element.getBoundingClientRect().top + scrollTop;
        
        if (scrollTop + offset >= elementTop) {
            const id = element.id;
            if (id.startsWith('article-')) {
                activeElement = id.replace('article-', '');
                activeType = 'article';
            } else if (id.startsWith('titulo-')) {
                activeElement = id.replace('titulo-', '');
                activeType = 'titulo';
            } else if (id.startsWith('capitulo-')) {
                activeElement = id.replace('capitulo-', '');
                activeType = 'capitulo';
            }
            break;
        }
    }
    
    if (activeElement) {
        document.querySelectorAll('.toc-item, .toc-titulo-header, .toc-capitulo-header').forEach(item => {
            item.classList.remove('active');
        });
        
        if (activeType === 'article') {
            const tocItem = document.querySelector(`[data-article="${activeElement}"]`);
            if (tocItem) {
                tocItem.classList.add('active');
            }
        } else if (activeType === 'titulo') {
            const tocTitulo = document.querySelector(`.toc-titulo-header[data-titulo="${activeElement}"]`);
            if (tocTitulo) {
                tocTitulo.classList.add('active');
            }
        } else if (activeType === 'capitulo') {
            const tocCapitulo = document.querySelector(`.toc-capitulo-header[data-capitulo="${activeElement}"]`);
            if (tocCapitulo) {
                tocCapitulo.classList.add('active');
            }
        }
    }
}

function renderTOC() {
    const tocContainer = document.getElementById('toc-container');
    const allArticles = getAllArticles();
    
    if (!allArticles || allArticles.length === 0) {
        tocContainer.innerHTML = '<p class="placeholder">No se encontraron artículos.</p>';
        return;
    }
    
    // Agrupar artículos por título y capítulo, manteniendo el orden original
    const structure = {};
    const tituloOrder = []; // Mantener orden de aparición de títulos
    
    allArticles.forEach(articulo => {
        const tituloKey = `titulo-${articulo.tituloNumero}`;
        if (!structure[tituloKey]) {
            structure[tituloKey] = {
                tituloNumero: articulo.tituloNumero,
                tituloNombre: articulo.tituloNombre,
                capitulos: {},
                capituloOrder: [] // Mantener orden de aparición de capítulos
            };
            tituloOrder.push(tituloKey);
        }
        
        if (articulo.capituloNumero) {
            const capituloKey = `capitulo-${articulo.capituloNumero}`;
            if (!structure[tituloKey].capitulos[capituloKey]) {
                structure[tituloKey].capitulos[capituloKey] = {
                    capituloNumero: articulo.capituloNumero,
                    capituloNombre: articulo.capituloNombre,
                    articulos: []
                };
                structure[tituloKey].capituloOrder.push(capituloKey);
            }
            structure[tituloKey].capitulos[capituloKey].articulos.push(articulo);
        } else {
            // Artículos sin capítulo (directamente en el título)
            if (!structure[tituloKey].articulos) {
                structure[tituloKey].articulos = [];
            }
            structure[tituloKey].articulos.push(articulo);
        }
    });
    
    // Obtener todos los títulos de la ley para incluir los que no tienen artículos
    const allTitulos = leyData.ley.titulos || [];
    const titulosMap = {};
    allTitulos.forEach(titulo => {
        titulosMap[String(titulo.numero)] = titulo;
    });
    
    // Generar HTML plano sin anidamiento
    let html = '';
    
    // Renderizar todos los títulos de la ley
    allTitulos.forEach(titulo => {
        const tituloKey = `titulo-${titulo.numero}`;
        const tituloData = structure[tituloKey];
        const tituloNumeroEscaped = String(titulo.numero).replace(/'/g, "\\'").replace(/"/g, "&quot;");
        const tituloNumeroForAttr = String(titulo.numero).replace(/"/g, "&quot;");
        
        // Título (siempre visible, sin anidamiento)
        html += `
            <div class="toc-titulo-header toc-item" 
                 data-titulo="${tituloNumeroForAttr}" 
                 onclick="scrollToTitulo('${tituloNumeroEscaped}')"
                 style="padding: 8px 12px; cursor: pointer; font-weight: bold;">
                Título ${titulo.numero}: ${titulo.nombre}
            </div>
        `;
        
        // Si hay estructura de datos para este título, mostrar capítulos y artículos
        if (tituloData) {
            // Mostrar capítulos si existen
            if (tituloData.capituloOrder && tituloData.capituloOrder.length > 0) {
                tituloData.capituloOrder.forEach(capituloKey => {
                    const capitulo = tituloData.capitulos[capituloKey];
                    const capituloNumeroEscaped = String(capitulo.capituloNumero).replace(/'/g, "\\'").replace(/"/g, "&quot;");
                    
                    html += `
                        <div class="toc-capitulo-header toc-item" 
                             data-capitulo="${capitulo.capituloNumero}" 
                             onclick="scrollToCapitulo('${capituloNumeroEscaped}')"
                             style="padding: 6px 12px 6px 24px; cursor: pointer; font-weight: 600;">
                            Capítulo ${capitulo.capituloNumero}: ${capitulo.capituloNombre}
                        </div>
                    `;
                    
                    // Artículos del capítulo
                    capitulo.articulos.forEach(articulo => {
                        html += renderTOCItem(articulo, true); // true = con indentación
                    });
                });
            }
            
            // Mostrar artículos sin capítulo si existen
            if (tituloData.articulos && tituloData.articulos.length > 0) {
                tituloData.articulos.forEach(articulo => {
                    html += renderTOCItem(articulo, true); // true = con indentación
                });
            }
        }
    });
    
    tocContainer.innerHTML = html;
}

function renderTOCItem(articulo, indented = false) {
    const hasChange = modifiedArticles.has(String(articulo.numero));
    const isIncorporated = articulo.isIncorporated === true;
    const isDerogated = derogatedArticles.has(String(articulo.numero));
    const isSynthetic = String(articulo.numero).startsWith('CAP_');
    const classes = [];
    if (isIncorporated) {
        classes.push('is-incorporated');
    } else if (hasChange || isDerogated) {
        classes.push('has-change');
    }
    
    // Determinar el número de artículo a mostrar en el TOC
    let displayNumber = articulo.numero;
    if (isSynthetic) {
        const match = articulo.numero.match(/CAP_VIII_ART_(\d+)/);
        if (match) {
            displayNumber = `S/N (${match[1]})`;
        }
    }
    
    const indentStyle = indented ? 'padding-left: 36px;' : 'padding-left: 24px;';
    
    return `
        <div class="toc-item ${classes.join(' ')}" 
             data-article="${articulo.numero}"
             onclick="scrollToArticle('${articulo.numero}')"
             style="${indentStyle} padding: 4px 12px; cursor: pointer;">
            Art. ${displayNumber}
        </div>
    `;
}

function scrollToArticle(numero) {
    const articleElement = document.getElementById(`article-${numero}`);
    if (articleElement) {
        const headerOffset = 150;
        const elementPosition = articleElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
        
        // Close TOC on mobile after clicking
        if (window.innerWidth <= 1024) {
            const tocSidebar = document.getElementById('toc-sidebar');
            if (tocSidebar) {
                tocSidebar.classList.remove('toc-visible');
            }
        }
        
        document.querySelectorAll('.toc-item, .toc-titulo-header, .toc-capitulo-header').forEach(item => {
            item.classList.remove('active');
        });
        const tocItem = document.querySelector(`[data-article="${numero}"]`);
        if (tocItem) {
            tocItem.classList.add('active');
        }
    }
}

function handleTituloClick(tituloNumero) {
    // Normalizar el número del título para la búsqueda
    const tituloNumeroNormalized = String(tituloNumero).trim();
    // Buscar el elemento usando el atributo data-titulo
    // Intentar primero con selector de atributo, luego buscar manualmente si falla
    let tituloElement = document.querySelector(`.toc-titulo[data-titulo="${tituloNumeroNormalized}"]`);
    if (!tituloElement) {
        // Fallback: buscar manualmente en todos los elementos
        const allTitulos = document.querySelectorAll('.toc-titulo');
        for (const el of allTitulos) {
            if (String(el.getAttribute('data-titulo')).trim() === tituloNumeroNormalized) {
                tituloElement = el;
                break;
            }
        }
    }
    if (!tituloElement) {
        console.warn(`No se encontró el título ${tituloNumeroNormalized}`);
        return;
    }
    
    const content = tituloElement.querySelector('.toc-titulo-content');
    const header = tituloElement.querySelector('.toc-titulo-header');
    if (!header) {
        console.warn(`No se encontró el header para el título ${tituloNumero}`);
        return;
    }
    
    if (!content) {
        console.warn(`No se encontró el contenido para el título ${tituloNumero}`);
        return;
    }
    
    const icon = header.querySelector('.toc-toggle-icon');
    const isExpanded = content.classList.contains('toc-expanded');
    
    if (isExpanded) {
        content.classList.remove('toc-expanded');
        if (icon) {
            icon.textContent = '▶';
        } else {
            // Si no hay icono, crearlo
            const newIcon = document.createElement('span');
            newIcon.className = 'toc-toggle-icon';
            newIcon.textContent = '▶';
            header.insertBefore(newIcon, header.firstChild);
        }
    } else {
        content.classList.add('toc-expanded');
        if (icon) {
            icon.textContent = '▼';
        } else {
            // Si no hay icono, crearlo
            const newIcon = document.createElement('span');
            newIcon.className = 'toc-toggle-icon';
            newIcon.textContent = '▼';
            header.insertBefore(newIcon, header.firstChild);
        }
    }
}

function handleCapituloClick(capituloNumero) {
    const capituloElement = document.querySelector(`.toc-capitulo[data-capitulo="${capituloNumero}"]`);
    if (!capituloElement) return;
    
    const content = capituloElement.querySelector('.toc-articulos');
    const header = capituloElement.querySelector('.toc-capitulo-header');
    const icon = header.querySelector('.toc-toggle-icon');
    
    if (content) {
        const isExpanded = content.classList.contains('toc-expanded');
        if (isExpanded) {
            content.classList.remove('toc-expanded');
            if (icon) icon.textContent = '▶';
        } else {
            content.classList.add('toc-expanded');
            if (icon) icon.textContent = '▼';
        }
    }
}

function scrollToTitulo(tituloNumero) {
    // Normalizar el número del título para la búsqueda
    const tituloNumeroNormalized = String(tituloNumero).trim();
    const tituloElement = document.getElementById(`titulo-${tituloNumeroNormalized}`);
    if (tituloElement) {
        const headerOffset = 150;
        const elementPosition = tituloElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
        
        // Close TOC on mobile after clicking
        if (window.innerWidth <= 1024) {
            const tocSidebar = document.getElementById('toc-sidebar');
            if (tocSidebar) {
                tocSidebar.classList.remove('toc-visible');
            }
        }
        
        // Marcar como activo en el TOC
        document.querySelectorAll('.toc-item, .toc-titulo-header, .toc-capitulo-header').forEach(item => {
            item.classList.remove('active');
        });
        let tocHeader = document.querySelector(`.toc-titulo-header[data-titulo="${tituloNumeroNormalized}"]`);
        if (!tocHeader) {
            // Fallback: buscar manualmente
            const allHeaders = document.querySelectorAll('.toc-titulo-header');
            for (const el of allHeaders) {
                if (String(el.getAttribute('data-titulo')).trim() === tituloNumeroNormalized) {
                    tocHeader = el;
                    break;
                }
            }
        }
        if (tocHeader) {
            tocHeader.classList.add('active');
        }
    }
}

function scrollToCapitulo(capituloNumero) {
    const capituloElement = document.getElementById(`capitulo-${capituloNumero}`);
    if (capituloElement) {
        const headerOffset = 150;
        const elementPosition = capituloElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
        
        // Close TOC on mobile after clicking
        if (window.innerWidth <= 1024) {
            const tocSidebar = document.getElementById('toc-sidebar');
            if (tocSidebar) {
                tocSidebar.classList.remove('toc-visible');
            }
        }
        
        // Marcar como activo en el TOC
        document.querySelectorAll('.toc-item, .toc-titulo-header, .toc-capitulo-header').forEach(item => {
            item.classList.remove('active');
        });
        let tocHeader = document.querySelector(`.toc-capitulo-header[data-capitulo="${capituloNumero}"]`);
        if (!tocHeader) {
            // Fallback: buscar manualmente
            const allHeaders = document.querySelectorAll('.toc-capitulo-header');
            for (const el of allHeaders) {
                if (String(el.getAttribute('data-capitulo')).trim() === String(capituloNumero).trim()) {
                    tocHeader = el;
                    break;
                }
            }
        }
        if (tocHeader) {
            tocHeader.classList.add('active');
        }
    }
}

function compareArticleNumbers(a, b) {
    // Función de comparación que maneja números con sufijos
    // Ej: "11" < "11 bis" < "12"
    const numA = String(a.numero || '');
    const numB = String(b.numero || '');
    
    // Manejar artículos sintéticos (CAP_VIII_ART_X) - van al final
    const isSyntheticA = numA.startsWith('CAP_');
    const isSyntheticB = numB.startsWith('CAP_');
    
    if (isSyntheticA && !isSyntheticB) return 1; // Sintéticos al final
    if (!isSyntheticA && isSyntheticB) return -1;
    if (isSyntheticA && isSyntheticB) {
        // Ordenar sintéticos por su índice
        const matchA = numA.match(/ART_(\d+)/);
        const matchB = numB.match(/ART_(\d+)/);
        const idxA = matchA ? parseInt(matchA[1]) : 0;
        const idxB = matchB ? parseInt(matchB[1]) : 0;
        return idxA - idxB;
    }
    
    // Extraer número base y sufijo
    const parseArticleNumber = (numStr) => {
        const match = numStr.match(/^(\d+)(?:\s*(bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?$/i);
        if (match) {
            const base = parseInt(match[1]) || 0;
            const suffix = match[2] ? match[2].toLowerCase() : '';
            // Asignar valores numéricos a sufijos para comparación
            const suffixOrder = {
                '': 0,
                'bis': 1,
                'ter': 2,
                'quater': 3,
                'quinquies': 4,
                'sexies': 5,
                'septies': 6,
                'octies': 7,
                'nonies': 8,
                'decies': 9
            };
            return { base, suffixValue: suffixOrder[suffix] || 0 };
        }
        // Fallback: intentar parsear como número simple
        return { base: parseInt(numStr) || 0, suffixValue: 0 };
    };
    
    const parsedA = parseArticleNumber(numA);
    const parsedB = parseArticleNumber(numB);
    
    // Comparar primero por número base
    if (parsedA.base !== parsedB.base) {
        return parsedA.base - parsedB.base;
    }
    
    // Si el número base es igual, comparar por sufijo
    return parsedA.suffixValue - parsedB.suffixValue;
}

function getDerogatedChapterArticles() {
    const derogatedArticlesList = [];
    
    // Buscar capítulos derogados y crear artículos sintéticos si es necesario
    derogatedChapters.forEach((articlesSet, capituloNumero) => {
        articlesSet.forEach(artId => {
            // Si es un artículo sintético (formato CAP_VIII_ART_X)
            if (artId.startsWith('CAP_')) {
                const match = artId.match(/CAP_(\w+)_ART_(\d+)/);
                if (match) {
                    const capNum = match[1];
                    const artIndex = parseInt(match[2]);
                    
                    // Solo crear artículos sintéticos para Capítulo VIII de Formación Profesional
                    if (capNum === 'VIII') {
                        // Textos de los artículos del Capítulo VIII según el usuario
                        const textos = [
                            "La promoción profesional y la formación en el trabajo, en condiciones igualitarias de acceso y trato será un derecho fundamental para todos los trabajadores y trabajadoras.",
                            "El empleador implementará acciones de formación profesional profesional y/o capacitación con la participación de los trabajadores y con la asistencia de los organismos competentes al Estado.",
                            "La capacitación del trabajador se efectuará de acuerdo a los requerimientos del empleador, a las características de las tareas, a las exigencias de la organización del trabajo y a los medios que le provea el empleador para dicha capacitación.",
                            "La organización sindical que represente a los trabajadores de conformidad a la legislación vigente tendrá derecho a recibir información sobre la evolución de la empresa, sobre innovaciones tecnológicas y organizativas y toda otra que tenga relación con la planificación de acciones de formación y capacitación profesional.",
                            "La organización sindical que represente a los trabajadores de conformidad a la legislación vigente ante innovaciones de base tecnológica y organizativa de la empresa, podrá solicitar al empleador la implementación de acciones de formación profesional para la mejor adecuación del personal al nuevo sistema.",
                            "En el certificado de trabajo que el empleador está obligado a entregar a la extinción del contrato de trabajo deberá constar además de lo prescripto en el artículo 80, la calificación profesional obtenida en el o los puestos de trabajo desempeñados, hubiere o no realizado el trabajador acciones regulares de capacitación.",
                            "El trabajador tendrá derecho a una cantidad de horas del tiempo total anual del trabajo, de acuerdo a lo que se establezca en el convenio colectivo, para realizar, fuera de su lugar de trabajo actividades de formación y/o capacitación que él juzgue de su propio interés."
                        ];
                        
                        if (artIndex <= textos.length) {
                            derogatedArticlesList.push({
                                numero: artId,
                                titulo: "",
                                texto: textos[artIndex - 1] || "",
                                isDerogated: true,
                                tituloNumero: "III", // El Capítulo VIII está en el Título III
                                tituloNombre: "De los derechos y obligaciones de las partes",
                                capituloNumero: "VIII",
                                capituloNombre: "DE LA FORMACIÓN PROFESIONAL"
                            });
                        }
                    }
                }
            }
        });
    });
    
    return derogatedArticlesList;
}

function getAllArticles() {
    const allArticles = [];
    const titulos = leyData.ley.titulos;
    
    // Obtener artículos de la ley original
    for (const titulo of titulos) {
        if (titulo.articulos) {
            for (const articulo of titulo.articulos) {
                allArticles.push({
                    ...articulo,
                    tituloNombre: titulo.nombre,
                    tituloNumero: titulo.numero
                });
            }
        }
        
        if (titulo.capitulos) {
            for (const capitulo of titulo.capitulos) {
                if (capitulo.articulos) {
                    for (const articulo of capitulo.articulos) {
                        allArticles.push({
                            ...articulo,
                            tituloNombre: titulo.nombre,
                            tituloNumero: titulo.numero,
                            capituloNombre: capitulo.nombre,
                            capituloNumero: capitulo.numero
                        });
                    }
                }
            }
        }
    }
    
    // Agregar artículos incorporados
    const incorporatedArticles = getIncorporatedArticles();
    allArticles.push(...incorporatedArticles);
    
    // Agregar artículos derogados de capítulos (artículos sintéticos)
    const derogatedChapterArticles = getDerogatedChapterArticles();
    allArticles.push(...derogatedChapterArticles);
    
    // Ordenar considerando sufijos (bis, ter, etc.)
    return allArticles.sort(compareArticleNumbers);
}

function getCambioForArticulo(numero) {
    const numeroStr = String(numero);
    return dictamenData.find(c => {
        const destinoArticulo = getDestinoArticulo(c);
        return destinoArticulo === numeroStr;
    });
}

function getIncorporatedArticles() {
    const incorporatedArticles = [];
    
    dictamenData.forEach(cambio => {
        if (cambio.accion === "incorpórase" || cambio.accion === "incorporase") {
            const destinoArticulo = getDestinoArticulo(cambio);
            if (!destinoArticulo) return;
            
            // Verificar si el artículo ya existe en la ley original
            const existsInLaw = leyData.ley.titulos.some(titulo => {
                if (titulo.articulos) {
                    if (titulo.articulos.some(art => String(art.numero) === destinoArticulo)) {
                        return true;
                    }
                }
                if (titulo.capitulos) {
                    for (const capitulo of titulo.capitulos) {
                        if (capitulo.articulos) {
                            if (capitulo.articulos.some(art => String(art.numero) === destinoArticulo)) {
                                return true;
                            }
                        }
                    }
                }
                return false;
            });
            
            // Solo agregar si no existe en la ley original
            if (!existsInLaw) {
                // Extraer título del texto_nuevo si está disponible
                let titulo = "";
                if (cambio.texto_nuevo) {
                    const tituloMatch = cambio.texto_nuevo.match(/ART[ÍI]CULO\s+\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[°º]?-\s*(.+?)(?:\n|$)/i);
                    if (tituloMatch && tituloMatch[1]) {
                        titulo = tituloMatch[1].trim();
                        // Limpiar el título (puede tener más texto después)
                        titulo = titulo.split('\n')[0].trim();
                    }
                }
                
                incorporatedArticles.push({
                    numero: destinoArticulo,
                    titulo: titulo,
                    texto: cambio.texto_nuevo || "",
                    isIncorporated: true,
                    tituloNumero: "I", // Por defecto, se puede inferir mejor después
                    tituloNombre: "Disposiciones Generales" // Por defecto
                });
            }
        }
    });
    
    return incorporatedArticles;
}

function renderSplitView() {
    const container = document.getElementById('split-content');
    const allArticles = getAllArticles();
    
    // Crear un mapa de artículos por título para facilitar el acceso
    const articlesByTitulo = {};
    allArticles.forEach(articulo => {
        const tituloKey = String(articulo.tituloNumero);
        if (!articlesByTitulo[tituloKey]) {
            articlesByTitulo[tituloKey] = [];
        }
        articlesByTitulo[tituloKey].push(articulo);
    });
    
    // Obtener todos los títulos de la ley, incluso los que no tienen artículos
    const allTitulos = leyData.ley.titulos || [];
    
    if (allTitulos.length === 0 && allArticles.length === 0) {
        container.innerHTML = '<p class="placeholder">No se encontraron artículos.</p>';
        return;
    }
    
    let html = '';
    
    // Renderizar todos los títulos, incluso los que no tienen artículos
    allTitulos.forEach(titulo => {
        const tituloNumero = String(titulo.numero);
        const tituloArticles = articlesByTitulo[tituloNumero] || [];
        
        // Renderizar el header del título
        html += `
            <div class="split-section-header" id="titulo-${tituloNumero}">
                <div class="split-section-left">
                    <h3 class="section-title">Título ${titulo.numero}: ${titulo.nombre}</h3>
                </div>
                <div class="split-section-right">
                    <h3 class="section-title">Título ${titulo.numero}: ${titulo.nombre}</h3>
                </div>
            </div>
        `;
        
        // Si no hay artículos para este título, mostrar un mensaje
        if (tituloArticles.length === 0) {
            html += `
                <div class="split-article-row">
                    <div class="split-article-left">
                        <p class="placeholder" style="padding: 20px; text-align: center; color: #999;">
                            Este título no contiene artículos.
                        </p>
                    </div>
                    <div class="split-article-right">
                        <p class="placeholder" style="padding: 20px; text-align: center; color: #999;">
                            Este título no contiene artículos.
                        </p>
                    </div>
                </div>
            `;
        } else {
            // Renderizar los artículos de este título
            let currentCapitulo = null;
            
            tituloArticles.forEach(articulo => {
                const cambio = getCambioForArticulo(articulo.numero);
                const hasChange = cambio !== undefined;
                
                if (articulo.capituloNumero && currentCapitulo !== articulo.capituloNumero) {
                    currentCapitulo = articulo.capituloNumero;
                    html += `
                        <div class="split-section-header" id="capitulo-${articulo.capituloNumero}">
                            <div class="split-section-left">
                                <h4 class="section-subtitle">Capítulo ${articulo.capituloNumero}: ${articulo.capituloNombre}</h4>
                            </div>
                            <div class="split-section-right">
                                <h4 class="section-subtitle">Capítulo ${articulo.capituloNumero}: ${articulo.capituloNombre}</h4>
                            </div>
                        </div>
                    `;
                }
                
                const isIncorporated = articulo.isIncorporated === true;
                const isDerogated = derogatedArticles.has(String(articulo.numero));
                const isSynthetic = String(articulo.numero).startsWith('CAP_');
                
                // Para incorporaciones, no usar la clase has-change (que aplica fondo rojo)
                const rowClasses = [];
                if (isIncorporated) {
                    rowClasses.push('is-incorporated');
                } else if (hasChange || isDerogated) {
                    rowClasses.push('has-change');
                }
                
                // Determinar el número de artículo a mostrar
                let displayNumber = articulo.numero;
                if (isSynthetic) {
                    const match = articulo.numero.match(/CAP_VIII_ART_(\d+)/);
                    if (match) {
                        displayNumber = `S/N (${match[1]})`;
                    }
                }
                
                html += `
                    <div class="split-article-row ${rowClasses.join(' ')}" id="article-${articulo.numero}">
                        <div class="split-article-left">
                            <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                                <span class="split-article-number">Art. ${displayNumber}</span>
                                ${articulo.titulo ? `<span class="split-article-title">${articulo.titulo}</span>` : ''}
                            </div>
                            <div class="split-article-content">
                                ${isIncorporated ? 
                                    '<p class="placeholder" style="color: #999; font-style: italic;">Artículo nuevo (no existe en ley actual)</p>' : 
                                    renderArticleContent(articulo)
                                }
                            </div>
                        </div>
                        <div class="split-article-right">
                            ${isDerogated ? `
                                <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                                    <span class="split-article-number">Art. ${displayNumber}</span>
                                    <span class="split-change-badge" style="background: #e74c3c;">DERÓGASE</span>
                                </div>
                                <div class="split-article-content changed" style="background: #ffe6e6;">
                                    <p class="placeholder" style="color: #c0392b; font-weight: bold; font-style: italic;">Artículo eliminado</p>
                                </div>
                            ` : hasChange ? `
                                <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                                    <span class="split-article-number">Art. ${displayNumber}</span>
                                    <span class="split-change-badge">${cambio.accion || 'Modificación'}</span>
                                </div>
                                <div class="split-article-content changed">
                                    ${cambio.texto_nuevo ? 
                                        formatText(cambio.texto_nuevo) : 
                                        '<p class="placeholder" style="color: #999; font-style: italic;">Texto no disponible</p>'
                                    }
                                </div>
                            ` : `
                                <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                                    <span class="split-article-number">Art. ${displayNumber}</span>
                                </div>
                                <div class="split-article-content unchanged">
                                    ${renderArticleContent(articulo)}
                                </div>
                            `}
                        </div>
                    </div>
                `;
            });
        }
    });
    
    container.innerHTML = html;
}

function renderArticleContent(articulo) {
    let html = formatText(articulo.texto || '');
    
    if (articulo.incisos && articulo.incisos.length > 0) {
        html += '<div class="split-incisos">';
        articulo.incisos.forEach(inciso => {
            html += `
                <div class="split-inciso">
                    <span class="inciso-letra">${inciso.letra})</span> ${formatText(inciso.texto)}
                </div>
            `;
        });
        html += '</div>';
    }
    
    return html;
}

function formatText(text) {
    if (!text) return '';
    return text
        .replace(/ARTICULO\s+(\d+)[\.-]/gi, '<strong>ARTÍCULO $1</strong>')
        .replace(/\n/g, '<br>');
}

function toggleArticle(numero) {
    const articleRow = document.getElementById(`article-${numero}`);
    if (articleRow) {
        articleRow.classList.toggle('collapsed');
    }
}

window.scrollToArticle = scrollToArticle;
window.scrollToTitulo = scrollToTitulo;
window.scrollToCapitulo = scrollToCapitulo;
window.handleTituloClick = handleTituloClick;
window.handleCapituloClick = handleCapituloClick;
window.toggleArticle = toggleArticle;

init();
