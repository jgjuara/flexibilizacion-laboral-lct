# Ley de Contrato de Trabajo - JSON Estructurado

Este repositorio contiene herramientas para procesar, convertir y consultar la **Ley de Contrato de Trabajo N° 20.744** (texto ordenado 1976) en formato JSON estructurado, así como herramientas para parsear dictámenes que modifican la ley.

## 📋 Contenido del Proyecto

### Archivos JSON Generados

- **`ley_contrato_trabajo_completa.json`**: Ley completa estructurada desde archivo de texto
- **`ley_contrato_trabajo_oficial_completa.json`**: Ley completa desde JSON oficial con metadatos y referencias normativas
- **`dictamen_modernizacion_laboral_parsed.json`**: Dictamen parseado con operaciones legislativas

### Scripts Python

- **`consultar_ley.py`**: Herramienta principal para consultar artículos de la ley
- **`procesar_ley_final.py`**: Convierte archivo de texto plano a JSON estructurado
- **`convertir_json_oficial_final.py`**: Convierte JSON oficial (InfoJus) a formato estructurado con metadatos
- **`parse_dictamen.py`**: Parsea dictámenes PDF que modifican la ley
- **`verificar_json.py`**: Verifica y muestra estadísticas del JSON generado

### Archivos Fuente

- **`LEY DE CONTRATO DE TRABAJO.txt`**: Texto plano de la ley
- **`view-document.json`**: JSON oficial exportado desde InfoJus
- **`Dictamen DE MODERNIZACIÓN LABORAL.pdf`**: PDF del dictamen de modernización laboral

### Documentación

- **`EJEMPLO_ESTRUCTURA.md`**: Ejemplos de estructura del JSON
- **`schema_ley_template.json`**: Plantilla de esquema para validación

## 🚀 Instalación

### Requisitos

- Python 3.8 o superior
- `uv` (gestor de paquetes recomendado)

### Configuración

```bash
# Instalar uv si no está instalado
# Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh

# Sincronizar dependencias
uv sync

# Para procesar PDFs (opcional)
uv sync --extra pdf
```

## 📖 Uso

### Consultar Artículos de la Ley

La herramienta principal es `consultar_ley.py`:

```bash
# Consultar un artículo específico
uv run consultar_ley.py 1

# Listar todos los artículos
uv run consultar_ley.py
```

**Ejemplo de salida:**
```
======================================================================
ARTÍCULO 1
======================================================================
Título:  Fuentes de regulación.
Pertenece a: Título I - Disposiciones Generales
----------------------------------------------------------------------

Texto:
El contrato de trabajo y la relación de trabajo se rige:

----------------------------------------------------------------------
Incisos:

  a) Por esta ley.
  b) Por las leyes y estatutos profesionales.
  c) Por las convenciones colectivas o laudos con fuerza de tales.
  d) Por la voluntad de las partes.
  e) Por los usos y costumbres.
======================================================================
```

### Procesar Archivo de Texto a JSON

Convierte un archivo de texto plano a JSON estructurado:

```bash
uv run procesar_ley_final.py
```

Requiere el archivo `LEY DE CONTRATO DE TRABAJO.txt` en el directorio actual. Genera `ley_contrato_trabajo_completa.json`.

### Convertir JSON Oficial

Convierte el JSON oficial de InfoJus a formato estructurado con metadatos:

```bash
uv run convertir_json_oficial_final.py
```

Requiere el archivo `view-document.json` en el directorio actual. Genera `ley_contrato_trabajo_oficial_completa.json` con:
- Metadatos completos (UUID, timestamps, URLs)
- Referencias normativas (modificaciones, derogaciones, observaciones)
- Decretos reglamentarios
- Información de publicación

### Parsear Dictámenes

Extrae operaciones legislativas de dictámenes en PDF:

```bash
uv run parse_dictamen.py "Dictamen DE MODERNIZACIÓN LABORAL.pdf" -o salida.json --pretty
```

**Características:**
- Detecta artículos del dictamen con verbos operativos (Sustitúyese, Incorpórase, Derógase, etc.)
- Extrae el texto nuevo que se incorpora a la ley
- Identifica artículos e incisos destino
- Genera JSON con operaciones estructuradas

**Ejemplo de salida:**
```json
[
  {
    "dictamen_articulo": "1",
    "encabezado": "ARTÍCULO 1- Sustitúyese el artículo 1 de la Ley N° 20.744",
    "accion": "sustitúyese",
    "ley_numero": "20.744",
    "destino_articulo": "1",
    "texto_nuevo": "El contrato de trabajo y la relación de trabajo se rige por..."
  }
]
```

### Verificar JSON Generado

Muestra estadísticas y verifica la estructura del JSON:

```bash
uv run verificar_json.py
```

## 🏗️ Estructura del JSON

### Estructura Básica

```json
{
  "ley": {
    "nombre": "LEY DE CONTRATO DE TRABAJO",
    "numero": "20.744",
    "año": "1976",
    "texto_ordenado": "1976",
    "titulos": [
      {
        "numero": "I",
        "nombre": "Disposiciones Generales",
        "capitulos": [],
        "articulos": [
          {
            "numero": "1",
            "titulo": "Fuentes de regulación",
            "texto": "El contrato de trabajo...",
            "incisos": [
              {
                "letra": "a",
                "texto": "Por esta ley."
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### Artículo con Incisos

```json
{
  "numero": "1",
  "titulo": "Fuentes de regulación",
  "texto": "El contrato de trabajo y la relación de trabajo se rige:",
  "incisos": [
    {
      "letra": "a",
      "texto": "Por esta ley."
    },
    {
      "letra": "b",
      "texto": "Por las leyes y estatutos profesionales."
    }
  ]
}
```

### Metadatos en JSON Oficial

El JSON generado desde la fuente oficial incluye campos adicionales:

```json
{
  "ley": {
    "nombre": "LEY DE CONTRATO DE TRABAJO",
    "numero": "20.744",
    "tipo": {...},
    "fecha": "1976-05-11",
    "estado": "Vigente",
    "metadatos": {
      "uuid": "...",
      "timestamp": "...",
      "friendly_url": {...}
    },
    "decretos_reglamentarios": [...],
    "articulos": [
      {
        "numero": "1",
        "titulo": "...",
        "texto": "...",
        "modificado_por": [...],
        "derogado_por": {...},
        "antecedentes": [...]
      }
    ]
  }
}
```

Para más ejemplos, ver `EJEMPLO_ESTRUCTURA.md`.

## 📊 Estadísticas

- **Total de Títulos**: 15
- **Total de Capítulos**: 44
- **Total de Artículos**: 288
- **Total de Incisos**: 64+

### Distribución por Título

| Título | Nombre | Artículos |
|--------|--------|-----------|
| I | Disposiciones Generales | 21 |
| II | Del Contrato de Trabajo en General | 70 |
| III | De las Modalidades del Contrato de Trabajo | 16 |
| IV | De la Remuneración del Trabajador | 50 |
| V | De las Vacaciones y otras Licencias | 15 |
| VI | De los Feriados Obligatorios y Días no Laborables | 6 |
| VII | Trabajo de Mujeres | 15 |
| VIII | De la Prohibición del Trabajo Infantil | 10 |
| IX | De la Duración del Trabajo y Descanso Semanal | 13 |
| X | De la Suspensión de Ciertos Efectos del Contrato | 18 |
| XI | De la Transferencia del Contrato de Trabajo | 6 |
| XII | De la Extinción del Contrato de Trabajo | 27 |
| XIII | De la Prescripción y Caducidad | 5 |
| XIV | De los Privilegios | 13 |
| XV | Disposiciones Complementarias | 3 |

## 🔧 Desarrollo

### Estructura del Proyecto

```
lct/
├── consultar_ley.py              # Herramienta principal de consulta
├── procesar_ley_final.py        # Procesador de texto a JSON
├── convertir_json_oficial_final.py  # Conversor de JSON oficial
├── parse_dictamen.py            # Parser de dictámenes PDF
├── verificar_json.py            # Verificador de JSON
├── pyproject.toml               # Configuración del proyecto
├── ley_contrato_trabajo_completa.json  # JSON generado desde texto
├── ley_contrato_trabajo_oficial_completa.json  # JSON desde fuente oficial
└── README.md                    # Esta documentación
```

### Dependencias

El proyecto usa solo módulos estándar de Python para las herramientas principales. Las dependencias opcionales para procesar PDFs están en el grupo `pdf`:

- `pdfplumber`: Extracción de texto de PDFs (recomendado)
- `pymupdf`: Alternativa para extracción de PDFs

### Flujo de Trabajo

1. **Procesar texto plano**: `procesar_ley_final.py` → `ley_contrato_trabajo_completa.json`
2. **Convertir JSON oficial**: `convertir_json_oficial_final.py` → `ley_contrato_trabajo_oficial_completa.json`
3. **Consultar artículos**: `consultar_ley.py` (usa cualquiera de los JSON generados)
4. **Parsear dictámenes**: `parse_dictamen.py` → JSON con operaciones legislativas

## 📝 Características

- ✅ Todos los artículos de la ley capturados
- ✅ Estructura jerárquica: Títulos → Capítulos → Artículos → Incisos
- ✅ Preserva el texto completo de cada artículo
- ✅ Incluye referencias a modificaciones normativas (en JSON oficial)
- ✅ Metadatos completos (en JSON oficial)
- ✅ Codificación UTF-8 para caracteres especiales
- ✅ Formato JSON válido y bien estructurado
- ✅ Parser de dictámenes con detección de operaciones legislativas

## 📄 Fuentes

- Ley de Contrato de Trabajo N° 20.744 (t.o. 1976) y sus modificaciones
- InfoJus - Sistema de Información Jurídica del Ministerio de Justicia y Derechos Humanos

## ⚖️ Nota Legal

Este es un recurso informativo. Para uso legal oficial, consultar el Boletín Oficial de la República Argentina o el sitio oficial de InfoJus.

## 📚 Documentación Adicional

- `EJEMPLO_ESTRUCTURA.md`: Ejemplos detallados de la estructura JSON
- `schema_ley_template.json`: Plantilla de esquema para validación

---

**Última actualización**: Enero 2025
