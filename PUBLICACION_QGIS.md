# Publicación en el repositorio oficial de QGIS

## Datos preparados

- Nombre público: **Acotación de parcela GIS**.
- Identificador/carpeta: `qgis_pacela_cotas`.
- Versión: `1.2.0`.
- Categoría: `Vector`.
- Licencia: `GPL-2.0-or-later`.
- QGIS compatible: 3.28 a 3.99.
- Dependencias externas: ninguna.
- Repositorio público creado: `https://github.com/motacj/qgis_pacela_cotas`.
- Correo del autor: `atom.susej@gmail.com`.

## Diferencia respecto de otros complementos

Aunque existen complementos generales de acotación CAD, este realiza en una
sola operación el flujo completo de una parcela: acotación de todos sus lados,
vértices numerados, tabla de coordenadas X/Y, superficie interior o exterior
con llamada y persistencia de todos los elementos en un GeoPackage. No genera
únicamente capas temporales de memoria.

## Requisitos pendientes antes de subir

1. Subir al repositorio público el código fuente descomprimido, no solamente el
   ZIP.
2. Confirmar que funcionan las URL de `homepage`, `repository` y `tracker`.
3. Probar la instalación y una ejecución completa en QGIS 3.44.2 para Windows.
4. Si es posible, repetir una prueba básica en Linux o macOS.
5. Grabar y publicar el vídeo de demostración; después, sustituir el enlace
   provisional del README por su URL pública.

## Envío

1. Crear un OSGeo ID en `https://id.osgeo.org/ldap/create` si todavía no existe.
2. Iniciar sesión en `https://plugins.qgis.org/`.
3. Elegir **Upload a plugin**.
4. Subir el ZIP de distribución sin descomprimirlo.
5. Esperar el análisis automático y la aprobación de un moderador.

## Comprobaciones realizadas localmente

- Estructura ZIP con una única carpeta raíz ASCII.
- Existencia de `metadata.txt`, `__init__.py` y `LICENSE`.
- Metadatos UTF-8, versión, categoría, descripción inglesa y campos booleanos.
- Icono PNG incluido y referenciado.
- Compilación sintáctica de todos los archivos Python.
- Pruebas unitarias de geometría y formato numérico.
- Ausencia de ejecutables, bibliotecas compiladas, cachés y carpetas ocultas.
- Ausencia de credenciales, claves, telemetría y llamadas de red.
- Tamaño del paquete inferior a 25 MB.

El portal ejecutará además Bandit, detect-secrets y Flake8 después del envío.
La prueba funcional final debe hacerse dentro de QGIS, ya que requiere PyQGIS.
