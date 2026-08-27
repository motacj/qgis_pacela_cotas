# Privacy

Acotación de parcela GIS processes only the QGIS layers selected by the user and
writes the requested GeoPackage to a local or user-selected file-system path.

The plugin:

- does not connect to online services;
- does not collect analytics or telemetry;
- does not transmit geometries, attributes or file paths;
- does not require an account, API key or credential;
- stores only the parcel-derived output and the settings selected in its dialog.

QGIS stores the last output path and dialog options in the active QGIS user
profile through `QSettings`. Users can change these values the next time the
dialog is opened.
