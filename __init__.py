"""Entrada del complemento Acotacion de parcela GIS."""


def classFactory(iface):
    """Crea la instancia del complemento para QGIS."""
    from .plugin import PacelaResultCotasPlugin

    return PacelaResultCotasPlugin(iface)
