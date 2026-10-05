# Historial de cambios

## 1.2.0

- Reconocimiento opcional de cadenas de al menos tres segmentos consecutivos
  menores de 1 m que se ajustan aproximadamente a una circunferencia.
- Sustitución de sus cotas lineales individuales por una única cota radial con
  el formato `R=…`.
- Controles configurables para la longitud máxima del segmento y la tolerancia
  radial del ajuste; valores iniciales de 1,000 m y 0,030 m.
- Registro en el GeoPackage del radio, ángulo del arco, error de ajuste y número
  de segmentos utilizados.
- Conservación automática de las cotas lineales cuando una cadena no cumple
  todos los criterios geométricos.
- Enumeraciones actualizadas al formato exigido por las versiones actuales de
  QGIS y por el validador del repositorio oficial.

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
