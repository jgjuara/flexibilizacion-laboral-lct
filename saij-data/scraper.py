"""
Scraper para obtener información semiestructurada de legislación argentina desde SAIJ.

El flujo de trabajo es:
1. Buscar la ley por número de norma en el buscador de SAIJ (obtiene JSON de búsqueda)
2. Extraer los UUIDs de los documentos desde searchResults.documentResultList
3. Construir la URL del JSON directamente: view-document?guid={uuid}
4. Obtener el JSON semiestructurado del documento
5. Guardar el JSON en un archivo

Uso desde línea de comandos:
    # Básico (busca automáticamente y usa nombre generado desde JSON)
    python scraper.py 20744
    
    # Con nombre de archivo personalizado
    python scraper.py 20744 --archivo "mi-archivo"
    
    # Con directorio de destino
    python scraper.py 20744 --directorio "output"
    
    # Combinando opciones
    python scraper.py 20744 --directorio "data" --archivo "ley-20744"
    
    # Con UUID directo (opcional, si la búsqueda automática falla)
    python scraper.py 20744 --uuid "123456789-0abc-defg-g61-50000scanyel"
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


BASE_URL = "https://www.saij.gob.ar"
SEARCH_URL = f"{BASE_URL}/busqueda"
VIEW_DOCUMENT_URL = f"{BASE_URL}/view-document"


def buscar_ley_json(numero_norma: int) -> list[str]:
    """
    Busca una ley por número de norma en SAIJ y devuelve los UUIDs de los documentos encontrados.
    
    La búsqueda devuelve un JSON con los resultados. De ese JSON se extraen los UUIDs
    de los documentos en searchResults.documentResultList.
    
    Args:
        numero_norma: Número de la norma a buscar (ej: 20744)
        
    Returns:
        Lista de UUIDs de los documentos encontrados
        
    Raises:
        requests.RequestException: Si hay un error en la petición HTTP
        ValueError: Si no se encuentran resultados o la respuesta no es válida
    """
    r_param = f'(numero-norma:{numero_norma})'
    full_url = f"{SEARCH_URL}?r={r_param}&o=0&p=25&f=Total%7CTipo+de+Documento%2FLegislaci%C3%B3n%2FLey%7CFecha%7COrganismo%7CPublicaci%C3%B3n%7CTema%7CEstado+de+Vigencia%2FVigente%2C+de+alcance+general%7CAutor%7CJurisdicci%C3%B3n%2FNacional&s=&v=colapsa"
    # full_url = "https://www.saij.gob.ar/busqueda?r=(numero-norma%3A20744+)&o=0&p=25&f=Total%7CTipo+de+Documento%2FLegislaci%C3%B3n%2FLey%7CFecha%7COrganismo%7CPublicaci%C3%B3n%7CTema%7CEstado+de+Vigencia%2FVigente%2C+de+alcance+general%7CAutor%7CJurisdicci%C3%B3n%2FNacional&s=&v=colapsada"

    logger.info(f"Buscando ley número {numero_norma} en SAIJ...")
    logger.info(f"URL de búsqueda: {full_url}")
    print(f"\n=== BÚSQUEDA DE LEY {numero_norma} ===")
    print(f"URL: {full_url}")
    
    response = requests.get(full_url, timeout=30)
    response.raise_for_status()
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    
    # Intentar parsear como JSON directamente
    json_data = None
    try:
        json_data = response.json()
        print("✓ Respuesta es JSON directo")
    except (ValueError, json.JSONDecodeError):
        # Si no es JSON, buscar JSON embebido en scripts
        print("Respuesta no es JSON directo, buscando JSON embebido...")
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Buscar JSON en scripts que contenga 'searchResults'
        for script in soup.find_all('script'):
            if script.string and 'searchResults' in script.string:
                # Buscar el objeto JSON completo
                json_match = re.search(r'(\{.*?"searchResults".*?\})', script.string, re.DOTALL)
                if json_match:
                    try:
                        json_data = json.loads(json_match.group(1))
                        print("✓ JSON encontrado en script embebido")
                        break
                    except (ValueError, json.JSONDecodeError):
                        continue
        
        # Si aún no se encontró, buscar en todo el texto
        if json_data is None:
            json_match = re.search(r'(\{.*?"queryObjectData".*?"searchResults".*?\})', response.text, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group(1))
                    print("✓ JSON encontrado en el texto de la respuesta")
                except (ValueError, json.JSONDecodeError):
                    pass
    
    if json_data is None:
        raise ValueError(
            f"No se pudo obtener JSON de búsqueda para la ley {numero_norma}. "
            f"La respuesta puede haber cambiado de formato."
        )
    
    # Extraer UUIDs de los documentos
    search_results = json_data.get('searchResults', {})
    document_list = search_results.get('documentResultList', [])
    total_results = search_results.get('totalSearchResults', 0)
    
    print(f"\nTotal de resultados encontrados: {total_results}")
    print(f"Documentos en la lista: {len(document_list)}")
    
    if not document_list:
        raise ValueError(f"No se encontraron documentos para la ley {numero_norma}")
    
    uuids = []
    for i, doc in enumerate(document_list, 1):
        uuid = doc.get('uuid')
        if uuid:
            uuids.append(uuid)
            print(f"  [{i}] UUID: {uuid}")
        else:
            logger.warning(f"Documento {i} no tiene UUID")
    
    if not uuids:
        raise ValueError(f"No se encontraron UUIDs válidos en los resultados para la ley {numero_norma}")
    
    logger.info(f"Encontrados {len(uuids)} UUIDs")
    return uuids




def obtener_json_documento(uuid: str) -> tuple[Dict[str, Any], requests.Response]:
    """
    Obtiene el JSON semiestructurado del documento desde el endpoint view-document.
    
    Args:
        uuid: UUID del documento
        
    Returns:
        Tupla con (diccionario con la información semiestructurada, response object)
        
    Raises:
        requests.RequestException: Si hay un error en la petición HTTP
        ValueError: Si la respuesta no contiene JSON válido
    """
    params = {'guid': uuid}
    
    logger.info(f"Obteniendo JSON del documento con UUID: {uuid}")
    response = requests.get(VIEW_DOCUMENT_URL, params=params, timeout=30)
    response.raise_for_status()
    
    try:
        data = response.json()
        # Si 'data' es un string, necesita ser parseado como JSON
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], str):
            data['data'] = json.loads(data['data'])
        logger.info("JSON obtenido exitosamente")
        return data, response
    except ValueError as e:
        raise ValueError(f"La respuesta no es un JSON válido: {e}")


def determinar_nombre_archivo(json_data: Dict[str, Any], response: requests.Response, numero_norma: int) -> str:
    """
    Determina el nombre de archivo para guardar el JSON.
    
    Intenta obtener el nombre desde:
    1. Headers Content-Disposition de la respuesta
    2. Datos del JSON (numero-norma, tipo-norma, fecha)
    3. Número de norma como fallback
    
    Args:
        json_data: Datos JSON del documento
        response: Objeto response de la petición HTTP
        numero_norma: Número de norma como fallback
        
    Returns:
        Nombre de archivo (sin extensión .json)
    """
    # Intentar obtener desde Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition', '')
    if content_disposition:
        # Buscar filename en Content-Disposition
        filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition, re.IGNORECASE)
        if filename_match:
            filename = filename_match.group(1).strip('"\'')
            # Remover extensión si existe
            if filename.endswith('.json'):
                filename = filename[:-5]
            return filename
    
    # Intentar construir desde los datos del JSON
    try:
        if isinstance(json_data.get('data'), dict):
            doc = json_data['data'].get('document', {})
            content = doc.get('content', {})
            
            numero = content.get('numero-norma', numero_norma)
            tipo_norma = content.get('tipo-norma', {})
            tipo_codigo = tipo_norma.get('codigo', '')
            fecha = content.get('fecha', '')
            
            # Construir nombre: numero-tipo-fecha
            partes = [str(numero)]
            if tipo_codigo:
                partes.append(tipo_codigo.lower())
            if fecha:
                # Formato fecha: YYYY-MM-DD, usar solo YYYY-MM-DD
                partes.append(fecha.replace('-', ''))
            
            if len(partes) > 1:
                return '-'.join(partes)
    except Exception as e:
        logger.warning(f"No se pudo construir nombre desde JSON: {e}")
    
    # Fallback: usar número de norma
    return f"ley-{numero_norma}"


def escribir_json(json_data: Dict[str, Any], directorio: Optional[str] = None, nombre_archivo: Optional[str] = None, 
                  response: Optional[requests.Response] = None, numero_norma: Optional[int] = None) -> str:
    """
    Escribe el JSON a un archivo.
    
    Args:
        json_data: Datos JSON a escribir
        directorio: Directorio de destino (None = directorio actual)
        nombre_archivo: Nombre del archivo sin extensión (None = determinar desde response/JSON)
        response: Objeto response para obtener nombre desde headers
        numero_norma: Número de norma como fallback para nombre
        
    Returns:
        Ruta completa del archivo escrito
    """
    # Determinar nombre de archivo
    if not nombre_archivo:
        if response and numero_norma is not None:
            nombre_archivo = determinar_nombre_archivo(json_data, response, numero_norma)
        elif numero_norma is not None:
            nombre_archivo = f"ley-{numero_norma}"
        else:
            nombre_archivo = "documento"
    
    # Asegurar que tiene extensión .json
    if not nombre_archivo.endswith('.json'):
        nombre_archivo += '.json'
    
    # Determinar directorio
    if directorio:
        dir_path = Path(directorio)
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / nombre_archivo
    else:
        file_path = Path(nombre_archivo)
    
    # Escribir archivo
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"JSON guardado en: {file_path}")
    return str(file_path)


def construir_url_directa(numero_norma: int) -> Optional[str]:
    """
    Intenta construir una URL directa para una ley basándose en el número de norma.
    
    Si la búsqueda no funciona, esta función puede intentar construir la URL
    usando patrones comunes. Sin embargo, sin información adicional (descripción,
    fecha, etc.) esto puede no ser siempre posible.
    
    Args:
        numero_norma: Número de la norma
        
    Returns:
        URL directa si se puede construir, None en caso contrario
    """
    # Por ahora, retornamos None ya que necesitamos más información
    # para construir la URL completa
    return None


def scraper_completo(numero_norma: int, uuid_directo: Optional[str] = None, 
                     directorio_destino: Optional[str] = None, 
                     nombre_archivo: Optional[str] = None) -> str:
    """
    Ejecuta el flujo completo de scraping para una ley y guarda el JSON en un archivo.
    
    Args:
        numero_norma: Número de la norma a buscar (ej: 20744)
        uuid_directo: UUID directo opcional. Si se proporciona, se usa este UUID
                     en lugar de buscar
        directorio_destino: Directorio donde guardar el archivo (None = directorio actual)
        nombre_archivo: Nombre del archivo sin extensión (None = determinar desde response/JSON)
        
    Returns:
        Ruta completa del archivo JSON guardado
        
    Raises:
        ValueError: Si no se puede completar algún paso del proceso
        requests.RequestException: Si hay errores en las peticiones HTTP
    """
    try:
        # Si se proporciona un UUID directo, usarlo
        if uuid_directo:
            logger.info(f"Usando UUID directo proporcionado: {uuid_directo}")
            uuids = [uuid_directo]
        else:
            # Paso 1: Buscar la ley y obtener UUIDs
            logger.info(f"Iniciando búsqueda automática para la ley {numero_norma}...")
            uuids = buscar_ley_json(numero_norma)
            
            if not uuids:
                raise ValueError(f"No se encontraron UUIDs para la ley {numero_norma}")
        
        # Paso 2: Usar el primer UUID (o permitir selección si hay múltiples)
        uuid = uuids[0]
        if len(uuids) > 1:
            logger.info(f"Se encontraron {len(uuids)} documentos. Usando el primero: {uuid}")
            logger.info(f"Otros UUIDs disponibles: {uuids[1:]}")
        
        # Paso 3: Obtener JSON del documento
        json_data, response = obtener_json_documento(uuid)
        
        # Paso 4: Escribir JSON a archivo
        file_path = escribir_json(json_data, directorio_destino, nombre_archivo, response, numero_norma)
        
        return file_path
        
    except requests.RequestException as e:
        logger.error(f"Error en petición HTTP: {e}")
        raise
    except ValueError as e:
        logger.error(f"Error en el proceso: {e}")
        raise


if __name__ == "__main__":
    # Ejemplo de uso
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scraper para obtener información semiestructurada de legislación argentina desde SAIJ. '
                    'Busca automáticamente la ley por número y descarga el JSON del documento.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Ejemplos:\n'
               '  python scraper.py 20744\n'
               '  python scraper.py 26206 --directorio data\n'
               '  python scraper.py 20744 --archivo ley-20744 --directorio output'
    )
    parser.add_argument('numero_norma', type=int, 
                       help='Número de la norma a buscar (ej: 20744, 26206)')
    parser.add_argument('--uuid', type=str, 
                       help='UUID directo del documento (opcional, solo si la búsqueda automática falla)')
    parser.add_argument('--directorio', type=str, 
                       help='Directorio de destino para guardar el JSON (opcional, por defecto: directorio actual)')
    parser.add_argument('--archivo', type=str, 
                       help='Nombre del archivo sin extensión .json (opcional, por defecto: generado desde los datos del documento)')
    
    args = parser.parse_args()
    
    try:
        file_path = scraper_completo(
            args.numero_norma,
            uuid_directo=args.uuid,
            directorio_destino=args.directorio,
            nombre_archivo=args.archivo
        )
        print(f"JSON guardado exitosamente en: {file_path}")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

