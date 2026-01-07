# Ejemplo de Estructura del JSON

## Artículo Simple (sin incisos)

```json
{
  "numero": "3",
  "titulo": " Ley aplicable.",
  "texto": "Esta ley regirá todo lo relativo a la validez, derechos y obligaciones de las partes, sea que el contrato de trabajo se haya celebrado en el país o fuera de él; en cuanto se ejecute en su territorio."
}
```

## Artículo con Incisos

```json
{
  "numero": "1",
  "titulo": " Fuentes de regulación.",
  "texto": "El contrato de trabajo y la relación de trabajo se rige:",
  "incisos": [
    {
      "letra": "a",
      "texto": "Por esta ley."
    },
    {
      "letra": "b",
      "texto": "Por las leyes y estatutos profesionales."
    },
    {
      "letra": "c",
      "texto": "Por las convenciones colectivas o laudos con fuerza de tales."
    },
    {
      "letra": "d",
      "texto": "Por la voluntad de las partes."
    },
    {
      "letra": "e",
      "texto": "Por los usos y costumbres."
    }
  ]
}
```

## Estructura de un Título con Capítulos

```json
{
  "numero": "II",
  "nombre": "Del Contrato de Trabajo en General",
  "capitulos": [
    {
      "numero": "I",
      "nombre": "Del contrato y la relación de trabajo",
      "articulos": [
        {
          "numero": "21",
          "titulo": " Contrato de trabajo.",
          "texto": "Habrá contrato de trabajo, cualquiera sea su forma o denominación..."
        },
        {
          "numero": "22",
          "titulo": " Relación de trabajo.",
          "texto": "Habrá relación de trabajo cuando una persona realice actos..."
        }
      ]
    },
    {
      "numero": "II",
      "nombre": "De los sujetos del contrato de trabajo",
      "articulos": [...]
    }
  ],
  "articulos": []
}
```

## Estructura Completa del JSON

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
          { "numero": "1", "titulo": "...", "texto": "...", "incisos": [...] },
          { "numero": "2", "titulo": "...", "texto": "..." },
          ...
        ]
      },
      {
        "numero": "II",
        "nombre": "Del Contrato de Trabajo en General",
        "capitulos": [
          {
            "numero": "I",
            "nombre": "Del contrato y la relación de trabajo",
            "articulos": [...]
          }
        ],
        "articulos": []
      },
      ...
    ]
  }
}
```

## Notas sobre la Estructura

1. **Títulos**: Pueden contener artículos directamente o estar organizados en capítulos
2. **Capítulos**: Siempre contienen artículos
3. **Artículos**: Pueden tener o no incisos
4. **Incisos**: Identificados por letras (a, b, c, etc.)

## Casos Especiales

### Artículos "bis", "ter", etc.

```json
{
  "numero": "17",
  "titulo": "bis. Las desigualdades que creara esta ley...",
  "texto": "(Artículo incorporado por art. 1° de la Ley N° 26.592 B.O. 21/5/2010)"
}
```

### Artículos con Modificaciones

El texto del artículo incluye referencias a las modificaciones normativas:

```json
{
  "numero": "9",
  "titulo": " El principio de la norma más favorable para el trabajador.",
  "texto": "En caso de duda sobre la aplicación de normas... (Artículo sustituido por art. 66 del Decreto N° 70/2023 B.O. 21/12/2023.)"
}
```

## Acceso Programático

### Python

```python
import json

# Cargar el JSON
with open('ley_contrato_trabajo_completa.json', 'r', encoding='utf-8') as f:
    ley = json.load(f)

# Acceder a un título
titulo_i = ley['ley']['titulos'][0]
print(titulo_i['nombre'])  # "Disposiciones Generales"

# Acceder a un artículo
articulo_1 = titulo_i['articulos'][0]
print(f"Artículo {articulo_1['numero']}: {articulo_1['titulo']}")

# Iterar sobre incisos
for inciso in articulo_1['incisos']:
    print(f"{inciso['letra']}) {inciso['texto']}")
```

### JavaScript

```javascript
// Cargar el JSON
const ley = require('./ley_contrato_trabajo_completa.json');

// Acceder a un título
const tituloI = ley.ley.titulos[0];
console.log(tituloI.nombre);  // "Disposiciones Generales"

// Buscar un artículo específico
function buscarArticulo(numero) {
  for (const titulo of ley.ley.titulos) {
    // Buscar en artículos directos
    const art = titulo.articulos.find(a => a.numero === numero);
    if (art) return art;
    
    // Buscar en capítulos
    for (const cap of titulo.capitulos || []) {
      const art = cap.articulos.find(a => a.numero === numero);
      if (art) return art;
    }
  }
  return null;
}

const art1 = buscarArticulo('1');
console.log(art1.titulo);
```

## Validación del JSON

El JSON generado es válido y puede ser validado con cualquier herramienta estándar:

```bash
# Con Python
python -m json.tool ley_contrato_trabajo_completa.json > /dev/null && echo "JSON válido"

# Con jq (si está instalado)
jq empty ley_contrato_trabajo_completa.json && echo "JSON válido"
```

