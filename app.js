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
            fetch('ley_contrato_trabajo_oficial_completa.json'),
            fetch('dictamen_modernizacion_laboral_titulo_I.json')
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
    document.getElementById('export-pdf-btn').addEventListener('click', exportToPDF);
    
    const splitContent = document.getElementById('split-content');
    splitContent.addEventListener('scroll', updateActiveTOCItem);
}

function updateActiveTOCItem() {
    const splitContent = document.getElementById('split-content');
    const articles = document.querySelectorAll('.split-article-row[id]');
    const scrollTop = splitContent.scrollTop;
    const offset = 150;
    
    let activeArticle = null;
    
    for (let i = articles.length - 1; i >= 0; i--) {
        const article = articles[i];
        const articleTop = article.offsetTop - splitContent.offsetTop;
        
        if (scrollTop + offset >= articleTop) {
            activeArticle = article.id.replace('article-', '');
            break;
        }
    }
    
    if (activeArticle) {
        document.querySelectorAll('.toc-item').forEach(item => {
            item.classList.remove('active');
        });
        const tocItem = document.querySelector(`[data-article="${activeArticle}"]`);
        if (tocItem) {
            tocItem.classList.add('active');
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
    
    tocContainer.innerHTML = allArticles.map(articulo => {
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
        
        return `
            <div class="toc-item ${classes.join(' ')}" 
                 data-article="${articulo.numero}"
                 onclick="scrollToArticle('${articulo.numero}')">
                Art. ${displayNumber}
            </div>
        `;
    }).join('');
}

function scrollToArticle(numero) {
    const articleElement = document.getElementById(`article-${numero}`);
    if (articleElement) {
        articleElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        document.querySelectorAll('.toc-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-article="${numero}"]`).classList.add('active');
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
    
    if (!allArticles || allArticles.length === 0) {
        container.innerHTML = '<p class="placeholder">No se encontraron artículos.</p>';
        return;
    }
    
    let html = '';
    let currentTitulo = null;
    let currentCapitulo = null;
    
    allArticles.forEach(articulo => {
        const cambio = getCambioForArticulo(articulo.numero);
        const hasChange = cambio !== undefined;
        
        if (currentTitulo !== articulo.tituloNumero) {
            currentTitulo = articulo.tituloNumero;
            html += `
                <div class="split-section-header">
                    <div class="split-section-left">
                        <h3 class="section-title">Título ${articulo.tituloNumero}: ${articulo.tituloNombre}</h3>
                    </div>
                    <div class="split-section-right">
                        <h3 class="section-title">Título ${articulo.tituloNumero}: ${articulo.tituloNombre}</h3>
                    </div>
                </div>
            `;
        }
        
        if (articulo.capituloNumero && currentCapitulo !== articulo.capituloNumero) {
            currentCapitulo = articulo.capituloNumero;
            html += `
                <div class="split-section-header">
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
                    <div class="split-article-header">
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
                        <div class="split-article-header">
                            <span class="split-article-number">Art. ${displayNumber}</span>
                            <span class="split-change-badge" style="background: #e74c3c;">DERÓGASE</span>
                        </div>
                        <div class="split-article-content changed" style="background: #ffe6e6;">
                            <p class="placeholder" style="color: #c0392b; font-weight: bold; font-style: italic;">Artículo eliminado</p>
                        </div>
                    ` : hasChange ? `
                        <div class="split-article-header">
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
                        <div class="split-article-header">
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

function exportToPDF() {
    const element = document.getElementById('split-container');
    const opt = {
        margin: [10, 10, 10, 10],
        filename: 'ley_contrato_trabajo_comparacion.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }
    };
    
    html2pdf().set(opt).from(element).save();
}

window.scrollToArticle = scrollToArticle;

init();
