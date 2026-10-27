"""
Parser de respuesta JSON de Product-ShowQuickView.

Campos confirmados (Fase 4):
  product.barcode          → EAN-13 (7501033920325)
  product.price.sales.value → precio de venta (con descuento si aplica)
  product.price.list.value  → precio de lista (original)
  product.brand            → marca
  product.manufacturerName → fabricante
  product['productGroup-noFriendly'] → categoria (MEDICINA, HIGIENE Y BELLEZA...)
  product['productLine-noFriendly']  → linea (SISTEMA NERVIOSO, ANALGESICOS...)
  product.isAntibiotic     → boolean
  product.isControlled     → boolean
  product.isRefrigeratedProduct → boolean
  product.isCBD            → boolean
  product.isOwnBrand       → boolean
  product.PLMData          → JSON string con datos farmaceuticos
  product.available        → disponible (general)
  product.availableForInStorePickup → disponible en tienda
"""

import json
import logging

logger = logging.getLogger("guadalajara")


def parse_product(data, pid, url):
    """
    Parsea el JSON completo de Product-ShowQuickView.
    Devuelve dict con todos los campos del producto, o None si hay error critico.
    """
    try:
        p = data.get("product", {}) or {}
    except Exception:
        return None

    if not p:
        logger.warning(f"PID {pid}: product object vacio")
        return None

    # ── Precio ──────────────────────────────────────────────────
    price_obj  = p.get("price", {}) or {}
    sales_obj  = price_obj.get("sales", {}) or {}
    list_obj   = price_obj.get("list", {}) or {}

    precio_venta = _safe_float(sales_obj.get("value"))
    precio_lista = _safe_float(list_obj.get("value"))

    # Descuento porcentual
    descuento_pct = None
    if precio_lista and precio_venta is not None and precio_lista > 0:
        raw = (precio_lista - precio_venta) / precio_lista * 100
        descuento_pct = round(raw, 1)

    # ── Imagen ──────────────────────────────────────────────────
    images     = p.get("images", {}) or {}
    large_list = images.get("large", []) or []
    url_imagen = large_list[0].get("absURL") if large_list else None

    # ── Campos con guion en el nombre ───────────────────────────
    # No se puede acceder con dot notation — usar .get()
    categoria   = p.get("productGroup-noFriendly", "") or ""
    linea       = p.get("productLine-noFriendly",  "") or ""
    desc_int    = p.get("description-noFriendly",  "") or ""

    # ── Disponibilidad ──────────────────────────────────────────
    disponible        = p.get("available", None)
    disponible_tienda = p.get("availableForInStorePickup", None)

    # Nivel de inventario
    inv_level = p.get("inventoryAvailabilityLevel", {}) or {}
    stock_online = inv_level.get("available", None)
    stock_bajo   = inv_level.get("lowStock", None)

    # ── PLM Data (datos farmaceuticos) ──────────────────────────
    plm_data_raw = p.get("PLMData", None)
    principio_activo = None

    if plm_data_raw and isinstance(plm_data_raw, str):
        try:
            plm = json.loads(plm_data_raw)
            attrs = plm.get("Attributes", [])
            if attrs and isinstance(attrs, list):
                # El primer atributo suele ser la composicion
                content = attrs[0].get("AttributeContent", "") or ""
                # Limpiar HTML entities y espacios
                content = content.replace("&#9;", " ").replace("\r\n", " ").strip()
                principio_activo = content[:500] if content else None
        except Exception:
            pass  # PLMData mal formado — ignorar

    # ── Promotions ──────────────────────────────────────────────
    promos  = p.get("promotions", []) or []
    promo_nombres = [pr.get("name", "") for pr in promos
                     if pr.get("promotionClass") != "SHIPPING" and pr.get("name")]

    # ── Construir resultado ─────────────────────────────────────
    result = {
        # Identificadores
        "pid":                pid,
        "url":                url,

        # Datos principales
        "nombre":             p.get("productName", "") or "",
        "ean":                p.get("barcode", "") or "",

        # Precios
        "precio_venta":       precio_venta,
        "precio_lista":       precio_lista,
        "descuento_pct":      descuento_pct,

        # Marca y fabricante
        "marca":              p.get("brand", "") or "",
        "fabricante":         p.get("manufacturerName", "") or "",

        # Clasificacion
        "categoria":          categoria,
        "linea":              linea,
        "descripcion_interna": desc_int,

        # Descripciones
        "descripcion_larga":  p.get("longDescription", "") or "",

        # Farmacia / tipo de producto
        "principio_activo":   principio_activo,
        "es_antibiotico":     bool(p.get("isAntibiotic", False)),
        "es_controlado":      bool(p.get("isControlled", False)),
        "refrigerar":         bool(p.get("isRefrigeratedProduct", False)),
        "es_cbd":             bool(p.get("isCBD", False)),
        "es_bebida_alcohol":  bool(p.get("isAlcoholDrink", False)),
        "marca_propia":       bool(p.get("isOwnBrand", False)),
        "es_a_granel":        bool(p.get("isBulkSale", False)),
        "regional":           bool(p.get("regional", False)),

        # Impuestos
        "iva_pct":            p.get("IVAPercentage", 0) or 0,
        "ieps_pct":           p.get("IEPSPercentage", 0) or 0,

        # Disponibilidad
        "disponible":         disponible,
        "disponible_tienda":  disponible_tienda,
        "stock_online":       stock_online,
        "stock_bajo":         stock_bajo,

        # PLM
        "plm_id":             p.get("PLMId", "") or "",

        # Imagen
        "url_imagen":         url_imagen,

        # Promociones (excluye envio gratis)
        "promociones":        "; ".join(promo_nombres) if promo_nombres else "",
    }

    return result


def _safe_float(val):
    """Convierte valor a float o devuelve None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
