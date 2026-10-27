from pathlib import Path

BASE_DIR = Path(__file__).parent

CONFIG = {
    # ── Plataforma ──────────────────────────────────────────────
    # SFCC / Salesforce Commerce Cloud, site "fragua"
    # Endpoint clave: Product-ShowQuickView (sin auth, JSON puro)
    # EAN en: product.barcode (EAN-13, prefijo 750x)
    # ────────────────────────────────────────────────────────────
    "base_url": "https://www.farmaciasguadalajara.com",
    "quickview_url": (
        "https://www.farmaciasguadalajara.com"
        "/on/demandware.store/Sites-fragua-Site/default"
        "/Product-ShowQuickView"
    ),
    "sitemap_urls": [
        "https://www.farmaciasguadalajara.com/sitemap_0.xml",
        "https://www.farmaciasguadalajara.com/sitemap_1.xml",
        "https://www.farmaciasguadalajara.com/sitemap_2.xml",
    ],

    # ── Coleccion ────────────────────────────────────────────────
    "delay":            1.2,   # s entre requests (Cloudflare activo)
    "delay_on_error":   5.0,   # s extra tras error
    "delay_on_429":    60.0,   # s si recibimos 429 (rate limit)
    "max_retries":      3,
    "session_reset_every": 350,    # reiniciar sesion cada N requests
                                   # Cloudflare cierra conexiones HTTP/2 en ~422 streams.
                                   # 350 es el reset proactivo para no llegar al limite.
    "checkpoint_every":   100,     # guardar checkpoint cada N productos

    # ── Test mode ────────────────────────────────────────────────
    "test_size": 150,   # productos en --test

    # ── Rutas de archivo ────────────────────────────────────────
    "checkpoint_file": BASE_DIR / "checkpoint.json",
    "pids_file":       BASE_DIR / "pids.json",
    "output_dir":      BASE_DIR,
    "log_file":        BASE_DIR / "scraper_guadalajara.log",
}
