let comparacionData = null; // JSON de comparación que contiene ley + metadatos de cambios

async function init() {
    try {
        const lawSelect = document.getElementById('law-select');
        if (lawSelect) {
            lawSelect.addEventListener('change', (e) => {
                loadLaw(e.target.value);
            });
            // Cargar ley inicial
            await loadLaw(lawSelect.value);
        } else {
            await loadLaw('20744');
        }

        setupEventListeners();
    } catch (error) {
        console.error('Error inicializando aplicación:', error);
    }
}

async function loadLaw(numeroLey) {
    const container = document.getElementById('split-content');
    const tocContainer = document.getElementById('toc-container');
    
    container.innerHTML = '<p class="placeholder">Cargando artículos...</p>';
    if (tocContainer) tocContainer.innerHTML = '';
    
    try {
        const url = `data/comparacion_global_ley_${numeroLey}.json`;
        const comparacionResponse = await fetch(url);
        if (!comparacionResponse.ok) {
            throw new Error(`No se pudo cargar la ley ${numeroLey}`);
        }
        comparacionData = await comparacionResponse.json();

        renderTOC();
        renderSplitView();
        
        // Scroll to top
        window.scrollTo(0, 0);
    } catch (error) {
        console.error('Error cargando datos:', error);
        container.innerHTML = 
            `<p class="error">Error al cargar los datos de la ley ${numeroLey}. Asegúrese de que el archivo JSON esté disponible.</p>`;
    }
}

// Funciones de procesamiento del dictamen ya no son necesarias
// El JSON de comparación ya tiene toda la información procesada

function setupEventListeners() {
    // TOC toggle button
    const tocToggle = document.getElementById('toc-toggle');
    const tocSidebar = document.getElementById('toc-sidebar');
    const mainLayout = document.querySelector('.main-split-layout');

    if (tocToggle && tocSidebar) {
        tocToggle.addEventListener('click', () => {
            if (window.innerWidth <= 1024) {
                tocSidebar.classList.toggle('toc-visible');
            } else if (mainLayout) {
                mainLayout.classList.toggle('collapsed');
            }
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
    
    // Obtener todos los títulos de la comparación
    const allTitulos = comparacionData.ley.titulos || [];
    
    // Generar HTML plano sin anidamiento
    let html = '';
    
    // Renderizar todos los títulos
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
    // Usar el estado directamente del JSON de comparación
    const estado = articulo.estado || 'sin_cambios';
    const isIncorporated = estado === 'incorporado';
    const isDerogated = estado === 'derogado';
    const hasChange = estado === 'sustituido' || isDerogated || isIncorporated;
    const isSynthetic = String(articulo.numero).startsWith('CAP_');
    
    const classes = [];
    if (isIncorporated) {
        classes.push('is-incorporated');
    } else if (hasChange) {
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

// Función ya no es necesaria - los artículos derogados ya están en el JSON de comparación

function getAllArticles() {
    const allArticles = [];
    const titulos = comparacionData.ley.titulos;
    
    // Obtener artículos de la estructura de comparación
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
    
    // Ordenar considerando sufijos (bis, ter, etc.)
    return allArticles.sort(compareArticleNumbers);
}

// Funciones de procesamiento del dictamen ya no son necesarias
// El JSON de comparación ya tiene toda la información procesada

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
    
    // Obtener todos los títulos de la comparación, incluso los que no tienen artículos
    const allTitulos = comparacionData.ley.titulos || [];
    
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
        
        // Renderizar capítulos si existen
        if (titulo.capitulos) {
            titulo.capitulos.forEach(capitulo => {
                const capituloNumero = String(capitulo.numero);
                
                // Renderizar header del capítulo
                html += `
                    <div class="split-section-header" id="capitulo-${capituloNumero}">
                        <div class="split-section-left">
                            <h4 class="section-subtitle">Capítulo ${capitulo.numero}: ${capitulo.nombre}</h4>
                        </div>
                        <div class="split-section-right">
                            <h4 class="section-subtitle">Capítulo ${capitulo.numero}: ${capitulo.nombre}</h4>
                        </div>
                    </div>
                `;
                
                // Renderizar artículos del capítulo
                if (capitulo.articulos) {
                    capitulo.articulos.forEach(articulo => {
                        html += renderArticleRow(articulo, titulo, capitulo);
                    });
                }
            });
        }
        
        // Renderizar artículos directos del título (sin capítulo)
        if (titulo.articulos) {
            titulo.articulos.forEach(articulo => {
                html += renderArticleRow(articulo, titulo, null);
            });
        }
        
        // Si no hay artículos ni capítulos para este título, mostrar un mensaje
        if (tituloArticles.length === 0 && (!titulo.capitulos || titulo.capitulos.length === 0) && (!titulo.articulos || titulo.articulos.length === 0)) {
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
        }
    });
    
    container.innerHTML = html;
}

function renderArticleRow(articulo, titulo, capitulo) {
    // Usar el estado directamente del JSON de comparación
    const estado = articulo.estado || 'sin_cambios';
    const isIncorporated = estado === 'incorporado';
    const isDerogated = estado === 'derogado';
    const isSustituido = estado === 'sustituido';
    const hasChange = isSustituido || isDerogated || isIncorporated;
    const isSynthetic = String(articulo.numero).startsWith('CAP_');
    
    // Para incorporaciones, no usar la clase has-change (que aplica fondo rojo)
    const rowClasses = [];
    if (isIncorporated) {
        rowClasses.push('is-incorporated');
    } else if (hasChange) {
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
    
    // Determinar títulos a mostrar
    const tituloOriginal = articulo.titulo || '';
    const tituloNuevo = articulo.titulo_nuevo || articulo.titulo || '';
    
    // Determinar texto a mostrar en el lado izquierdo (original)
    let textoIzquierdo = '';
    if (isIncorporated) {
        textoIzquierdo = '<p class="placeholder" style="color: #999; font-style: italic;">Artículo nuevo (no existe en ley actual)</p>';
    } else if (isSustituido && articulo.texto_original) {
        // Para sustituciones, mostrar el texto original en el lado izquierdo
        textoIzquierdo = renderArticleContent({
            ...articulo,
            texto: articulo.texto_original,
            titulo: tituloOriginal,
            incisos: articulo.incisos_originales || articulo.incisos
        });
    } else {
        textoIzquierdo = renderArticleContent(articulo);
    }
    
    // Determinar contenido del lado derecho (nuevo/modificado)
    let contenidoDerecho = '';
    if (isDerogated) {
        contenidoDerecho = `
            <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                <span class="split-article-number">Art. ${displayNumber}</span>
                <span class="split-change-badge" style="background: #e74c3c;">DERÓGASE</span>
            </div>
            <div class="split-article-content changed" style="background: #ffe6e6;">
                <p class="placeholder" style="color: #c0392b; font-weight: bold; font-style: italic;">Artículo eliminado</p>
            </div>
        `;
    } else if (isSustituido) {
        // Mostrar texto nuevo
        const textoNuevo = articulo.texto_nuevo || '';
        const incisosNuevos = articulo.incisos_nuevos || articulo.incisos;
        
        contenidoDerecho = `
            <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                <span class="split-article-number">Art. ${displayNumber}</span>
                ${tituloNuevo ? `<span class="split-article-title">${tituloNuevo}</span>` : ''}
                <span class="split-change-badge">${articulo.accion || 'Modificación'}</span>
            </div>
            <div class="split-article-content changed">
                ${textoNuevo ? 
                    renderArticleContent({
                        ...articulo,
                        texto: textoNuevo,
                        titulo: tituloNuevo,
                        incisos: incisosNuevos
                    }) : 
                    '<p class="placeholder" style="color: #999; font-style: italic;">Texto no disponible</p>'
                }
            </div>
        `;
    } else if (isIncorporated) {
        // Mostrar texto del artículo incorporado
        contenidoDerecho = `
            <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                <span class="split-article-number">Art. ${displayNumber}</span>
                ${tituloNuevo ? `<span class="split-article-title">${tituloNuevo}</span>` : ''}
                <span class="split-change-badge" style="background: #27ae60;">INCORPÓRASE</span>
            </div>
            <div class="split-article-content changed" style="background: #e8f5e9;">
                ${renderArticleContent(articulo)}
            </div>
        `;
    } else {
        // Sin cambios
        contenidoDerecho = `
            <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                <span class="split-article-number">Art. ${displayNumber}</span>
                ${tituloNuevo ? `<span class="split-article-title">${tituloNuevo}</span>` : ''}
            </div>
            <div class="split-article-content unchanged">
                ${renderArticleContent(articulo)}
            </div>
        `;
    }
    
    return `
        <div class="split-article-row ${rowClasses.join(' ')}" id="article-${articulo.numero}">
            <div class="split-article-left">
                <div class="split-article-header" onclick="toggleArticle('${articulo.numero}')">
                    <span class="split-article-number">Art. ${displayNumber}</span>
                    ${tituloOriginal ? `<span class="split-article-title">${tituloOriginal}</span>` : ''}
                </div>
                <div class="split-article-content">
                    ${textoIzquierdo}
                </div>
            </div>
            <div class="split-article-right">
                ${contenidoDerecho}
            </div>
        </div>
    `;
}

function renderArticleContent(articulo) {
    let html = '';
    
    // Si hay un título, mostrarlo como primer párrafo en negrita
    if (articulo.titulo) {
        html += `<p class="article-body-title"><strong>${articulo.titulo}</strong></p>`;
    }
    
    html += formatText(articulo.texto || '');
    
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
