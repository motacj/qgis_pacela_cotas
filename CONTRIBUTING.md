# Contributing

Thank you for helping improve Acotación de parcela GIS.

## Reporting a problem

Use the GitHub issue templates and include:

- QGIS version and operating system.
- Input layer geometry type and CRS.
- Reference scale and dialog values.
- Exact steps to reproduce the problem.
- The complete QGIS Python error, if one is shown.

Do not attach confidential parcel data. Create a simplified or fictional
geometry that reproduces the problem whenever possible.

## Proposing a change

1. Create a branch from `main`.
2. Keep the plugin compatible with QGIS 3.28 or later.
3. Do not add external Python dependencies unless they are strictly necessary.
4. Add or update unit tests for geometry calculations.
5. Run the local checks:

   ```bash
   python -m unittest discover -s tests -v
   python -m compileall -q .
   python tools/build_plugin.py
   python tools/validate_qgis_package.py dist/qgis_pacela_cotas.zip
   ```

6. Open a pull request describing the reason for the change and its visible
   effect in QGIS.

By contributing, you agree that your contribution is licensed under
GPL-2.0-or-later.
