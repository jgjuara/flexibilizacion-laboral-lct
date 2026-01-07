let leyData = null;
let dictamenData = null;
let modifiedArticles = new Set();

function extractArticleNumberFromHeader(encabezado) {
    if (!encabezado) return null;
    const match = encabezado.match(/artículo\s+(\d+)/i);
    if (match) {
        return match[1];
    }
    return null;
}

function getDestinoArticulo(cambio) {
    if (cambio.destino_articulo) {
        return String(cambio.destino_articulo);
    }
    const fromHeader = extractArticleNumberFromHeader(cambio.encabezado);
    return fromHeader ? String(fromHeader) : null;
}

async function init() {
    try {
        const [leyResponse, dictamenResponse] = await Promise.all([
            fetch('ley_contrato_trabajo_oficial_completa.json'),
            fetch('dictamen_modernizacion_laboral_parsed.json')
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

function processDictamenData() {
    dictamenData.forEach(cambio => {
        const destinoArticulo = getDestinoArticulo(cambio);
        if (destinoArticulo) {
            modifiedArticles.add(destinoArticulo);
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
        return `
            <div class="toc-item ${hasChange ? 'has-change' : ''}" 
                 data-article="${articulo.numero}"
                 onclick="scrollToArticle('${articulo.numero}')">
                Art. ${articulo.numero}
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

function getAllArticles() {
    const allArticles = [];
    const titulos = leyData.ley.titulos;
    
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
    
    return allArticles.sort((a, b) => {
        const numA = parseInt(a.numero) || 0;
        const numB = parseInt(b.numero) || 0;
        return numA - numB;
    });
}

function getCambioForArticulo(numero) {
    const numeroStr = String(numero);
    return dictamenData.find(c => {
        const destinoArticulo = getDestinoArticulo(c);
        return destinoArticulo === numeroStr;
    });
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
        
        html += `
            <div class="split-article-row ${hasChange ? 'has-change' : ''}" id="article-${articulo.numero}">
                <div class="split-article-left">
                    <div class="split-article-header">
                        <span class="split-article-number">Art. ${articulo.numero}</span>
                        ${articulo.titulo ? `<span class="split-article-title">${articulo.titulo}</span>` : ''}
                    </div>
                    <div class="split-article-content">
                        ${renderArticleContent(articulo)}
                    </div>
                </div>
                <div class="split-article-right">
                    ${hasChange ? `
                        <div class="split-article-header">
                            <span class="split-article-number">Art. ${articulo.numero}</span>
                            <span class="split-change-badge">${cambio.accion || 'Modificación'}</span>
                        </div>
                        <div class="split-article-content changed">
                            ${formatText(cambio.texto_nuevo || '')}
                        </div>
                    ` : `
                        <div class="split-article-header">
                            <span class="split-article-number">Art. ${articulo.numero}</span>
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
