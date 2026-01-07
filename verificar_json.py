import json

with open('ley_contrato_trabajo_completa.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 60)
print("VERIFICACIÓN DEL JSON GENERADO")
print("=" * 60)

# Contar artículos por título
print("\nARTÍCULOS POR TÍTULO:")
print("-" * 60)
for titulo in data['ley']['titulos']:
    arts_directos = len(titulo.get('articulos', []))
    arts_en_caps = sum(len(cap.get('articulos', [])) for cap in titulo.get('capitulos', []))
    total_arts = arts_directos + arts_en_caps
    print(f"Título {titulo['numero']}: {titulo['nombre'][:40]}...")
    print(f"  - Artículos directos: {arts_directos}")
    print(f"  - Artículos en capítulos: {arts_en_caps}")
    print(f"  - Total: {total_arts}")

# Mostrar últimos 10 artículos
print("\n" + "=" * 60)
print("ÚLTIMOS 10 ARTÍCULOS CAPTURADOS:")
print("-" * 60)

todos_articulos = []
for titulo in data['ley']['titulos']:
    for art in titulo.get('articulos', []):
        todos_articulos.append(art)
    for cap in titulo.get('capitulos', []):
        for art in cap.get('articulos', []):
            todos_articulos.append(art)

for art in todos_articulos[-10:]:
    print(f"Art. {art['numero']}: {art['titulo'][:50]}")

print("\n" + "=" * 60)
print(f"TOTAL DE ARTÍCULOS CAPTURADOS: {len(todos_articulos)}")
print("=" * 60)

