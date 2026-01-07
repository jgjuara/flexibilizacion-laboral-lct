let leyData = null;
let dictamenData = null;
let currentArticle = null;
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
        setupNavigation();
        setupEventListeners();
        renderCambios();
    } catch (error) {
        console.error('Error cargando datos:', error);
        document.getElementById('ley-content').innerHTML = 
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
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const view = e.target.dataset.view;
            switchView(view);
        });
    });

    document.getElementById('search-btn').addEventListener('click', handleSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });
}

function switchView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(`${viewName}-view`).classList.add('active');
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');

    if (viewName === 'comparar' && currentArticle) {
        showComparison(currentArticle);
    } else if (viewName === 'split') {
        renderSplitView();
    }
}

function setupNavigation() {
    const navContainer = document.getElementById('ley-navigation');
    const titulos = leyData.ley.titulos;

    titulos.forEach(titulo => {
        const tituloDiv = createNavItem(titulo.nombre, titulo.numero);
        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'nav-item-children';

        if (titulo.articulos && titulo.articulos.length > 0) {
            titulo.articulos.forEach(articulo => {
                const artLink = createArticleLink(articulo.numero, articulo.titulo);
                childrenDiv.appendChild(artLink);
            });
        }

        if (titulo.capitulos && titulo.capitulos.length > 0) {
            titulo.capitulos.forEach(capitulo => {
                const capDiv = createNavItem(capitulo.nombre, capitulo.numero);
                const capChildrenDiv = document.createElement('div');
                capChildrenDiv.className = 'nav-item-children';

                if (capitulo.articulos && capitulo.articulos.length > 0) {
                    capitulo.articulos.forEach(articulo => {
                        const artLink = createArticleLink(articulo.numero, articulo.titulo);
                        capChildrenDiv.appendChild(artLink);
                    });
                }

                capDiv.appendChild(capChildrenDiv);
                childrenDiv.appendChild(capDiv);
            });
        }

        tituloDiv.appendChild(childrenDiv);
        navContainer.appendChild(tituloDiv);
    });
}

function createNavItem(name, number) {
    const div = document.createElement('div');
    div.className = 'nav-item';
    
    const title = document.createElement('div');
    title.className = 'nav-item-title';
    title.textContent = `${number}. ${name}`;
    title.addEventListener('click', () => {
        title.classList.toggle('expanded');
        div.classList.toggle('expanded');
    });
    
    div.appendChild(title);
    return div;
}

function createArticleLink(numero, titulo) {
    const link = document.createElement('div');
    link.className = 'nav-article';
    if (modifiedArticles.has(String(numero))) {
        link.classList.add('modified');
    }
    link.textContent = `Art. ${numero} - ${titulo || 'Sin título'}`;
    link.addEventListener('click', () => {
        document.querySelectorAll('.nav-article').forEach(a => a.classList.remove('active'));
        link.classList.add('active');
        showArticle(numero);
    });
    return link;
}

function findArticle(numero) {
    const titulos = leyData.ley.titulos;
    const numeroStr = String(numero);
    
    for (const titulo of titulos) {
        if (titulo.articulos) {
            const articulo = titulo.articulos.find(a => String(a.numero) === numeroStr);
            if (articulo) return articulo;
        }
        
        if (titulo.capitulos) {
            for (const capitulo of titulo.capitulos) {
                if (capitulo.articulos) {
                    const articulo = capitulo.articulos.find(a => String(a.numero) === numeroStr);
                    if (articulo) return articulo;
                }
            }
        }
    }
    return null;
}

function showArticle(numero) {
    currentArticle = numero;
    const articulo = findArticle(numero);
    
    if (!articulo) {
        document.getElementById('ley-content').innerHTML = 
            `<p class="placeholder">Artículo ${numero} no encontrado.</p>`;
        return;
    }

    let html = `
        <div class="articulo">
            <div class="articulo-header">
                <div class="articulo-numero">Artículo ${articulo.numero}</div>
                ${articulo.titulo ? `<div class="articulo-titulo">${articulo.titulo}</div>` : ''}
            </div>
            <div class="articulo-texto">${formatText(articulo.texto)}</div>
    `;

    if (articulo.incisos && articulo.incisos.length > 0) {
        html += '<div class="articulo-incisos">';
        articulo.incisos.forEach(inciso => {
            html += `
                <div class="inciso">
                    <span class="inciso-letra">${inciso.letra})</span> ${formatText(inciso.texto)}
                </div>
            `;
        });
        html += '</div>';
    }

    if (modifiedArticles.has(String(numero))) {
        html += `
            <div style="margin-top: 1.5rem; padding: 1rem; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                <strong>⚠️ Este artículo tiene cambios propuestos.</strong>
                <button onclick="switchView('comparar'); showComparison('${numero}')" 
                        style="margin-top: 0.5rem; padding: 0.5rem 1rem; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Ver comparación
                </button>
            </div>
        `;
    }

    html += '</div>';
    document.getElementById('ley-content').innerHTML = html;
}

function formatText(text) {
    if (!text) return '';
    return text
        .replace(/ARTICULO\s+(\d+)[\.-]/gi, '<strong>ARTÍCULO $1</strong>')
        .replace(/\n/g, '<br>');
}

function renderCambios() {
    const container = document.getElementById('cambios-list');
    
    if (!dictamenData || dictamenData.length === 0) {
        container.innerHTML = '<p class="placeholder">No hay cambios propuestos.</p>';
        return;
    }

    container.innerHTML = dictamenData.map(cambio => {
        const accionClass = cambio.accion === 'sustitúyese' ? 'sustituye' : 
                           cambio.accion === 'incorpórase' ? 'incorpora' : 'otro';
        const destinoArticulo = getDestinoArticulo(cambio);
        
        return `
            <div class="cambio-item">
                <div class="cambio-header">
                    <div>
                        <span class="cambio-accion">${cambio.accion || 'Modificación'}</span>
                        ${destinoArticulo ? 
                            `<span class="cambio-destino">Art. ${destinoArticulo}</span>` : ''}
                    </div>
                    <div class="cambio-encabezado">${cambio.encabezado || ''}</div>
                </div>
                <div class="cambio-texto">${formatText(cambio.texto_nuevo || '')}</div>
                ${destinoArticulo ? 
                    `<button onclick="switchView('comparar'); showComparison('${destinoArticulo}')" 
                             style="margin-top: 1rem; padding: 0.5rem 1rem; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Comparar con texto actual
                    </button>` : ''}
            </div>
        `;
    }).join('');
}

function showComparison(numero) {
    const articulo = findArticle(numero);
    const numeroStr = String(numero);
    const cambio = dictamenData.find(c => {
        const destinoArticulo = getDestinoArticulo(c);
        return destinoArticulo === numeroStr;
    });

    if (!articulo) {
        document.getElementById('comparison-actual').innerHTML = 
            '<p class="placeholder">Artículo no encontrado en la ley actual.</p>';
    } else {
        let html = `
            <div class="articulo">
                <div class="articulo-header">
                    <div class="articulo-numero">Artículo ${articulo.numero}</div>
                    ${articulo.titulo ? `<div class="articulo-titulo">${articulo.titulo}</div>` : ''}
                </div>
                <div class="articulo-texto">${formatText(articulo.texto)}</div>
        `;

        if (articulo.incisos && articulo.incisos.length > 0) {
            html += '<div class="articulo-incisos">';
            articulo.incisos.forEach(inciso => {
                html += `
                    <div class="inciso">
                        <span class="inciso-letra">${inciso.letra})</span> ${formatText(inciso.texto)}
                    </div>
                `;
            });
            html += '</div>';
        }

        html += '</div>';
        document.getElementById('comparison-actual').innerHTML = html;
    }

    if (!cambio) {
        document.getElementById('comparison-propuesto').innerHTML = 
            '<p class="placeholder">No hay cambios propuestos para este artículo.</p>';
        document.getElementById('comparison-info').innerHTML = '';
    } else {
        const destinoArticulo = getDestinoArticulo(cambio);
        let html = `
            <div class="articulo">
                <div class="articulo-header">
                    <div class="articulo-numero">Artículo ${destinoArticulo || 'Nuevo'}</div>
                    <div style="margin-top: 0.5rem;">
                        <span class="cambio-accion" style="font-size: 0.875rem;">${cambio.accion || 'Modificación'}</span>
                    </div>
                </div>
                <div class="articulo-texto">${formatText(cambio.texto_nuevo || '')}</div>
            </div>
        `;
        document.getElementById('comparison-propuesto').innerHTML = html;

        document.getElementById('comparison-info').innerHTML = `
            <p><strong>Acción:</strong> ${cambio.accion || 'N/A'}</p>
            <p><strong>Encabezado:</strong> ${cambio.encabezado || 'N/A'}</p>
        `;
    }
}

function handleSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    const numero = query.replace(/[^\d]/g, '');
    if (!numero) {
        alert('Por favor ingrese un número de artículo válido.');
        return;
    }

    const articulo = findArticle(numero);
    if (articulo) {
        switchView('ley');
        showArticle(numero);
        document.getElementById('search-input').value = '';
        
        document.querySelectorAll('.nav-article').forEach(a => {
            if (a.textContent.includes(`Art. ${numero}`)) {
                a.classList.add('active');
                a.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                a.classList.remove('active');
            }
        });
    } else {
        alert(`Artículo ${numero} no encontrado.`);
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
            <div class="split-article-row ${hasChange ? 'has-change' : ''}">
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

window.switchView = switchView;
window.showComparison = showComparison;

init();

