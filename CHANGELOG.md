# Historial de cambios

## 1.1.2

- Sustituidas nueve enumeraciones antiguas por sus clases de enumeración
  explícitas para superar el validador del repositorio oficial de QGIS.
- Compatibilidad preparada para la API moderna de QGIS/PyQt sin modificar el
  funcionamiento del complemento.

## 1.1.1

- Metadatos y descripción inglesa para el repositorio oficial de QGIS.
- Licencia GPL-2.0-or-later, política de privacidad y guía de publicación.
- Icono PNG compatible con el portal de complementos.
- Documentación de diferencias frente a herramientas CAD generales.

## 1.1.0

- Texto de cota cambiado a Arial 8 pt.
- Separación mínima de dos alturas de texto entre arista y línea de cota.
- Números de vértice desplazados al exterior al menos una altura de texto.
- Superficie exterior con llamada al centroide cuando el texto no cabe dentro.
- Campo opcional de la parcela de origen en el texto de superficie.
- Migración automática de campos cuando se reutiliza un GeoPackage 1.0.

## 1.0.0

- Primera versión instalable.
- Cotas por lado, referencias y trazos configurados a partir de Arial 12 pt.
- Numeración y tabla X/Y de vértices.
- Superficie GIS en el centro de la parcela.
- Persistencia en GeoPackage con historial por `run_id`.
