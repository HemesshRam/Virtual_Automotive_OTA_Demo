from flask import Flask

from ota_server.routes import ota
from ota_server.config import HOST, HTTPS_ENABLED, PORT, PUBLIC_SCHEME, TLS_CERT_FILE, TLS_KEY_FILE

app = Flask(__name__)

app.register_blueprint(ota)


if __name__ == "__main__":

    print()

    print("=" * 60)
    print("AUTOMOTIVE OTA CLOUD SERVER")
    print("=" * 60)

    ssl_context = None
    if HTTPS_ENABLED:
        if not TLS_CERT_FILE or not TLS_KEY_FILE:
            raise RuntimeError(
                "OTA_HTTPS_ENABLED=1 requires OTA_TLS_CERT_FILE and OTA_TLS_KEY_FILE"
            )
        ssl_context = (TLS_CERT_FILE, TLS_KEY_FILE)

    print(f"Listening on {PUBLIC_SCHEME}://{HOST}:{PORT}")
    if HTTPS_ENABLED:
        print(f"TLS cert : {TLS_CERT_FILE}")

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        ssl_context=ssl_context,
    )
