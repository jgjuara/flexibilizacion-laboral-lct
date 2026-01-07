# Publicación en GitHub Pages

Esta página web permite explorar la Ley de Contrato de Trabajo y los cambios propuestos en el Dictamen de Modernización Laboral.

## Estructura de archivos

- `index.html` - Página principal
- `styles.css` - Estilos
- `app.js` - Lógica de la aplicación
- `ley_contrato_trabajo_oficial_completa.json` - Datos de la ley actual
- `dictamen_modernizacion_laboral_parsed.json` - Datos de los cambios propuestos

## Publicación en GitHub Pages

### Opción 1: Desde la configuración del repositorio

1. Ve a la configuración del repositorio en GitHub
2. Navega a "Pages" en el menú lateral
3. En "Source", selecciona la rama principal (main/master)
4. Selecciona la carpeta raíz `/ (root)`
5. Guarda los cambios
6. La página estará disponible en `https://[tu-usuario].github.io/[nombre-repo]/`

### Opción 2: Usando GitHub Actions (recomendado)

Si prefieres usar GitHub Actions, puedes crear un workflow que publique automáticamente.

## Notas importantes

- Los archivos JSON deben estar en la misma carpeta que `index.html`
- La página funciona completamente en el cliente (no requiere servidor)
- Asegúrate de que los archivos JSON estén incluidos en el repositorio

## Funcionalidades

- **Ley Actual**: Navegación por títulos, capítulos y artículos de la ley
- **Cambios Propuestos**: Lista de todos los cambios del dictamen
- **Comparar**: Vista lado a lado del texto actual vs. propuesto
- **Búsqueda**: Buscar artículos por número

Los artículos que tienen cambios propuestos se marcan en rojo en la navegación.

