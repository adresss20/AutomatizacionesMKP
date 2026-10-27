import sys
import io

# ============================================================
# CRITICO: UTF-8 antes de cualquier import o print
# Sin esto, cualquier acento crashea el terminal CP1252 en Windows
# ============================================================
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import warnings
warnings.filterwarnings("ignore")

import argparse
import time
from pathlib import Path

from config import CONFIG
from scrapers.sitemap import SitemapScraper
from scrapers.catalog import CatalogScraper
from exporters.excel import export_to_excel
from utils.checkpoint import (
    load_checkpoint, save_checkpoint,
    save_pids, load_pids,
)
from utils.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(
        description="Scraper Farmacias Guadalajara — SFCC/Demandware"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help=f"Solo primeros {CONFIG['test_size']} productos (verificar antes de correr completo)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanudar desde el ultimo checkpoint"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=CONFIG["delay"],
        help=f"Delay entre requests en segundos (default {CONFIG['delay']}s)"
    )
    args = parser.parse_args()

    logger = setup_logger(CONFIG["log_file"])

    logger.info("=" * 60)
    logger.info("SCRAPER FARMACIAS GUADALAJARA")
    logger.info(f"Modo    : {'TEST' if args.test else 'COMPLETO'} | {'RESUME' if args.resume else 'NUEVO'}")
    logger.info(f"Delay   : {args.delay}s entre requests")
    logger.info(f"Endpoint: Product-ShowQuickView (JSON, sin auth)")
    logger.info(f"EAN     : product.barcode — cobertura 100% confirmada")
    logger.info("=" * 60)

    t_start = time.time()

    # ──────────────────────────────────────────────────────────
    # FASE 1: Obtener PIDs desde sitemaps
    # ──────────────────────────────────────────────────────────
    all_entries = None

    if args.resume:
        # Intentar cargar PIDs guardados (evitar re-fetch de sitemaps)
        all_entries = load_pids(CONFIG["pids_file"])
        if all_entries:
            logger.info(f"PIDs cargados desde {CONFIG['pids_file']}: {len(all_entries)}")

    if not all_entries:
        logger.info("Recolectando PIDs desde sitemaps...")
        sitemap_scraper = SitemapScraper(CONFIG)
        all_entries = sitemap_scraper.collect_all_pids()

        # Guardar para posibles --resume
        save_pids(CONFIG["pids_file"], all_entries)
        logger.info(f"PIDs guardados: {len(all_entries)}")

    if not all_entries:
        logger.error("No se obtuvieron PIDs. Verificar conectividad y sitemaps.")
        sys.exit(1)

    logger.info(f"Total PIDs disponibles: {len(all_entries)}")

    if args.test:
        all_entries = all_entries[:CONFIG["test_size"]]
        logger.info(f"Modo TEST: limitado a {len(all_entries)} productos")

    # ──────────────────────────────────────────────────────────
    # FASE 2: Coleccion de datos de producto
    # ──────────────────────────────────────────────────────────
    already_collected = []
    done_pids         = set()

    if args.resume:
        checkpoint = load_checkpoint(CONFIG["checkpoint_file"])
        if checkpoint:
            already_collected = checkpoint.get("products", [])
            done_pids         = set(checkpoint.get("processed_pids", []))
            logger.info(f"Resumiendo: {len(already_collected)} productos ya recopilados")
        else:
            logger.info("Checkpoint no encontrado — iniciando desde cero")

    pending = [(pid, url) for pid, url in all_entries if pid not in done_pids]
    logger.info(f"Productos pendientes: {len(pending)}")

    if not pending:
        logger.info("Todos los productos ya estan en el checkpoint — exportando directamente")
        all_products = already_collected
    else:
        catalog_scraper = CatalogScraper(CONFIG, delay=args.delay)

        try:
            new_products = catalog_scraper.collect(
                pending,
                already_collected,
                CONFIG["checkpoint_file"],
            )
        except KeyboardInterrupt:
            logger.info("Interrumpido por usuario (Ctrl+C) — checkpoint guardado")
            new_products = []

        all_products = already_collected + new_products
        logger.info(f"Coleccion finalizada: {len(all_products)} productos totales")

        # Checkpoint final
        save_checkpoint(CONFIG["checkpoint_file"], {
            "products":       all_products,
            "processed_pids": list(done_pids) + [p["pid"] for p in new_products],
        })

    # ──────────────────────────────────────────────────────────
    # EXPORTAR A EXCEL
    # ──────────────────────────────────────────────────────────
    if not all_products:
        logger.warning("Sin productos para exportar")
        sys.exit(0)

    suffix   = "_test" if args.test else ""
    out_file = CONFIG["output_dir"] / f"guadalajara{suffix}.xlsx"

    logger.info(f"Exportando {len(all_products)} productos a Excel...")
    export_to_excel(all_products, out_file)

    # Stats finales
    elapsed    = time.time() - t_start
    with_ean   = sum(1 for p in all_products if p.get("ean"))
    with_price = sum(1 for p in all_products if p.get("precio_venta") is not None)

    logger.info("=" * 60)
    logger.info(f"FINALIZADO en {elapsed/60:.1f} minutos")
    logger.info(f"Productos  : {len(all_products)}")
    logger.info(f"Con EAN    : {with_ean} ({with_ean/len(all_products)*100:.1f}%)")
    logger.info(f"Con precio : {with_price} ({with_price/len(all_products)*100:.1f}%)")
    logger.info(f"Archivo    : {out_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
