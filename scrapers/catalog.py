import logging
import time

from api.client import make_session, retry_get, Http2StreamError
from parsers.product import parse_product
from utils.checkpoint import save_checkpoint

logger = logging.getLogger("guadalajara")


class CatalogScraper:

    def __init__(self, config, delay=None):
        self.config   = config
        self.delay    = delay if delay is not None else config["delay"]
        self.qv_url   = config["quickview_url"]
        self.session  = make_session()
        self._req_count = 0   # contador para reset periodico de sesion

    def _reset_session(self, reason="periodico"):
        """Crea una nueva sesion HTTP/2 y resetea el contador."""
        logger.info(f"Reiniciando sesion curl_cffi ({reason}, {self._req_count} requests)")
        self.session = make_session()
        self._req_count = 0
        time.sleep(2.5)

    def collect(self, pending_entries, already_collected, checkpoint_file):
        """
        Itera sobre pending_entries (pid, url), fetcha QuickView y parsea.
        Guarda checkpoint cada config['checkpoint_every'] productos.
        Devuelve lista de nuevos dicts de producto.
        """
        new_products  = []
        total         = len(pending_entries)
        done_pids     = [p["pid"] for p in already_collected]

        logger.info(f"Iniciando coleccion: {total} productos pendientes")
        logger.info(f"Delay: {self.delay}s | Checkpoint cada {self.config['checkpoint_every']}")
        logger.info(f"Reset de sesion cada {self.config['session_reset_every']} requests (proactivo)")

        for i, (pid, url) in enumerate(pending_entries):
            # Reset periodico ANTES de llegar al limite de streams de Cloudflare (~422)
            if self._req_count > 0 and self._req_count % self.config["session_reset_every"] == 0:
                self._reset_session("periodico")

            logger.info(f"[{i+1}/{total}] PID {pid}")

            product = self._fetch_one(pid, url)

            if product:
                ean   = product.get("ean", "")
                price = product.get("precio_venta", "")
                name  = product.get("nombre", "")[:50]
                logger.info(f"  OK  EAN:{ean or 'N/A':<15} ${price or '?':<9} {name}")
                new_products.append(product)
                done_pids.append(pid)
            else:
                logger.warning(f"  SKIP PID {pid}")

            # Checkpoint periodico
            checkpoint_every = self.config["checkpoint_every"]
            if (i + 1) % checkpoint_every == 0:
                all_so_far = already_collected + new_products
                save_checkpoint(checkpoint_file, {
                    "products":       all_so_far,
                    "processed_pids": done_pids,
                })
                logger.info(f"  >>> Checkpoint: {len(all_so_far)} productos guardados")

            self._req_count += 1
            time.sleep(self.delay)

        return new_products

    def _fetch_one(self, pid, url):
        """
        Fetch + parse de un solo producto.
        Si la sesion HTTP/2 fue cerrada por el servidor, la resetea
        y reintenta una sola vez antes de rendirse.
        Devuelve dict o None.
        """
        for session_attempt in range(1, 3):  # max 2 intentos de sesion
            try:
                r = retry_get(
                    self.session,
                    self.qv_url,
                    params={"pid": str(pid)},
                    max_retries=self.config["max_retries"],
                    delay_on_error=self.config["delay_on_error"],
                    delay_on_429=self.config["delay_on_429"],
                )
                break  # exito o 404 — salir del loop de sesion

            except Http2StreamError:
                # Sesion HTTP/2 cerrada por el servidor — crear nueva y reintentar
                logger.warning(f"  HTTP/2 stream error PID {pid} (sesion #{session_attempt}) — reset")
                self._reset_session(f"H2 error en PID {pid}")
                if session_attempt == 2:
                    logger.error(f"  HTTP/2 error persistente para PID {pid} — SKIP")
                    return None
                # Continuar al siguiente intento del loop
                continue
        else:
            return None

        if r is None:
            return None

        if r.status_code != 200:
            logger.warning(f"  HTTP {r.status_code} para PID {pid}")
            return None

        # Verificar que devuelve JSON (no pagina de error HTML)
        ct = r.headers.get("content-type", "")
        if "json" not in ct and not r.text.strip().startswith("{"):
            logger.warning(f"  Respuesta no-JSON para PID {pid}: {r.text[:100]}")
            return None

        try:
            data = r.json()
        except Exception as e:
            logger.error(f"  Error parseando JSON PID {pid}: {e}")
            return None

        return parse_product(data, pid, url)
