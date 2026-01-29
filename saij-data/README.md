# SAIJ Data Scraper

Scraper para obtener información semiestructurada de legislación argentina desde el Sistema Argentino de Información Jurídica (SAIJ).

## Descripción

Este proyecto permite descargar automáticamente documentos legales en formato JSON desde SAIJ mediante búsqueda por número de norma. El scraper:

1. Busca la ley por número de norma en SAIJ (obtiene JSON de búsqueda)
2. Extrae los UUIDs de los documentos desde `searchResults.documentResultList`
3. Construye la URL del JSON directamente: `view-document?guid={uuid}`
4. Obtiene el JSON semiestructurado del documento
5. Guarda el JSON en un archivo con nombre descriptivo

## Características

- ✅ Búsqueda automática por número de norma
- ✅ Extracción directa de UUIDs desde JSON de búsqueda
- ✅ Descarga de documentos completos en formato JSON
- ✅ Nombres de archivo automáticos basados en metadatos del documento
- ✅ Soporte para múltiples resultados (usa el primero, muestra los demás)
- ✅ Opción de especificar UUID directo si la búsqueda falla
- ✅ Logging detallado del proceso

## Requisitos

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (gestor de paquetes)

## Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/tu-usuario/saij-data.git
cd saij-data
```

2. Instala las dependencias con `uv`:
```bash
uv sync
```

## Uso

### Uso básico

Buscar una ley por número de norma y descargar su JSON:

```bash
uv run scraper.py 20744
```

Esto buscará la ley 20744, descargará su JSON y lo guardará con un nombre generado automáticamente (ej: `20744-lct-19760513.json`).

### Opciones disponibles

**Especificar directorio de destino:**
```bash
uv run scraper.py 20744 --directorio "data"
```

**Especificar nombre de archivo personalizado:**
```bash
uv run scraper.py 20744 --archivo "ley-20744"
```

**Combinar opciones:**
```bash
uv run scraper.py 20744 --directorio "output" --archivo "mi-ley"
```

**Usar UUID directo (si la búsqueda automática falla):**
```bash
uv run scraper.py 20744 --uuid "123456789-0abc-defg-g61-50000scanyel"
```

### Ejemplos prácticos

```bash
# Buscar ley 20744 (Ley de Contrato de Trabajo)
uv run scraper.py 20744

# Buscar ley 26206 y guardar en carpeta "data"
uv run scraper.py 26206 --directorio data

# Buscar ley 24449 con nombre personalizado
uv run scraper.py 24449 --archivo "ley-contrato-trabajo"
```

### Ayuda

Para ver todos los argumentos disponibles:

```bash
uv run scraper.py --help
```

## Estructura del proyecto

```
saij-data/
├── scraper.py          # Script principal del scraper
├── pyproject.toml      # Configuración del proyecto y dependencias
├── uv.lock             # Lock file de dependencias
└── README.md           # Este archivo
```

## Formato de salida

Los archivos JSON descargados contienen información semiestructurada del documento legal, incluyendo:

- Metadatos del documento (UUID, tipo, fecha, etc.)
- Contenido completo de la norma
- Referencias normativas
- Descriptores y temas
- Información de publicación
- Estado de vigencia

Ejemplo de estructura:
```json
{
  "data": {
    "document": {
      "metadata": {
        "uuid": "...",
        "document-content-type": "legislacion",
        "friendly-url": {...}
      },
      "content": {
        "numero-norma": 20744,
        "tipo-norma": {...},
        "fecha": "1976-05-13",
        ...
      }
    }
  }
}
```

## Desarrollo

### Estructura del código

El scraper está organizado en las siguientes funciones principales:

- `buscar_ley_json(numero_norma)`: Busca la ley y extrae UUIDs del JSON de búsqueda
- `obtener_json_documento(uuid)`: Obtiene el JSON completo del documento usando el UUID
- `determinar_nombre_archivo(...)`: Genera un nombre descriptivo para el archivo
- `escribir_json(...)`: Guarda el JSON en un archivo
- `scraper_completo(...)`: Función principal que orquesta todo el proceso

### Dependencias

- `requests`: Para realizar peticiones HTTP
- `beautifulsoup4`: Para parsear HTML cuando el JSON está embebido
- `lxml`: Parser XML/HTML para BeautifulSoup

## Limitaciones

- El scraper depende de la estructura de la API de SAIJ, que puede cambiar
- Si hay múltiples resultados, se usa el primero automáticamente
- Requiere conexión a internet para funcionar

## Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz un fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está disponible bajo la licencia que elijas. Por favor, revisa el archivo LICENSE para más detalles.

## Notas

- El scraper está diseñado para trabajar con la estructura actual de la API de SAIJ
- Si la búsqueda no encuentra resultados, verifica que el número de norma sea correcto
- Los nombres de archivo se generan automáticamente usando el formato: `{numero}-{tipo}-{fecha}.json`

## Troubleshooting

**Error: "No se pudo obtener JSON de búsqueda"**
- Verifica tu conexión a internet
- El formato de la respuesta de SAIJ puede haber cambiado
- Intenta usar el parámetro `--uuid` con el UUID directo del documento

**Error: "No se encontraron documentos"**
- Verifica que el número de norma sea correcto
- Algunas normas pueden no estar disponibles en SAIJ

**Múltiples resultados encontrados**
- El scraper usa automáticamente el primer resultado
- Los demás UUIDs se muestran en los logs para referencia

## Agradecimientos

- SAIJ (Sistema Argentino de Información Jurídica) por proporcionar acceso a la información legal

