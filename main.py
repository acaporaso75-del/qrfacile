"""
Entrypoint legacy mantenuto solo per compatibilità.

L'applicazione ufficiale QRFACILE parte da:
    qrfacile_app.main:app

Il servizio systemd usa già:
    qrfacile_app.main:app
"""

from qrfacile_app.main import app
