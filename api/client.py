import logging
import time

from curl_cffi import requests as cf

logger = logging.getLogger("guadalajara")

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/html, */*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}

# Señales que identifican el cierre de conexion HTTP/2 por parte del servidor.
# Cloudflare cierra la conexion despues de ~400 requests sobre el mismo socket.
# curl error 92 = NGHTTP2_INTERNAL_ERROR / stream not closed cleanly.
H2_ERROR_SIGNALS = [
    "not closed cleanly",
    "curl: (92)",
    "stream 0 was not closed",
]


class Http2StreamError(Exception):
    """
    La sesion HTTP/2 fue cerrada por el servidor.
    El caller debe crear una nueva sesion con make_session() antes de reintentar.
    """
    pass


def make_session():
    """Siempre chrome136 + verify=False desde el primer request."""
    return cf.Session(impersonate="chrome136", verify=False)


def retry_get(session, url, params=None, max_retries=3,
              delay_on_error=5.0, delay_on_429=60.0, timeout=20):
    """
    GET con retry logic completo.

    Comportamiento especial para HTTP/2 stream errors (curl 92):
    Lanza Http2StreamError inmediatamente — reintentar con la misma
    sesion rota es inutil. El caller debe resetear la sesion.

    Para todo lo demas:
    - 429             → pausa delay_on_429 + reintenta
    - 5xx             → pausa delay_on_error + reintenta
    - otros curl err  → pausa delay_on_error + reintenta
    - 404             → devuelve None (producto no existe)
    - Retorna Response o None
    """
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, headers=HEADERS, params=params, timeout=timeout)

            if r.status_code == 200:
                return r

            if r.status_code == 404:
                logger.debug(f"404 para params={params}")
                return None

            if r.status_code == 429:
                logger.warning(f"429 Rate limit — pausa {delay_on_429}s (intento {attempt}/{max_retries})")
                time.sleep(delay_on_429)
                continue

            if r.status_code >= 500:
                logger.warning(f"HTTP {r.status_code} — pausa {delay_on_error}s (intento {attempt}/{max_retries})")
                time.sleep(delay_on_error)
                continue

            logger.warning(f"HTTP {r.status_code} inesperado para {params}")
            return r

        except Exception as e:
            err_str = str(e)

            # Detectar cierre de conexion HTTP/2 — NO reintentar con sesion rota
            if any(sig in err_str for sig in H2_ERROR_SIGNALS):
                logger.warning(f"HTTP/2 stream error detectado — se necesita reset de sesion")
                raise Http2StreamError(err_str)

            # Otros errores curl/red — reintentar normalmente
            logger.warning(f"curl/red error (intento {attempt}/{max_retries}): {err_str[:80]}")
            if attempt < max_retries:
                time.sleep(delay_on_error)

    logger.error(f"Fallaron {max_retries} intentos para {params}")
    return None
