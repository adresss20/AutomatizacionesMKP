import re
import time
import logging

from api.client import make_session, retry_get, HEADERS

logger = logging.getLogger("guadalajara")

# PID al final de la URL: /nombre-del-producto.-{pid}.html
# Patron SFCC de Farmacias Guadalajara
PID_RE = re.compile(r"\.-(\d+)\.html$")


class SitemapScraper:
    def __init__(self, config):
        self.config = config
        self.session = make_session()

    def collect_all_pids(self):
        """
        Fetches los 3 sitemaps y devuelve lista de (pid, url).
        Los 3 sitemaps tienen ~5000 + 5000 + 3750 = ~13,750 productos.
        """
        all_entries = []

        for sitemap_url in self.config["sitemap_urls"]:
            entries = self._fetch_sitemap(sitemap_url)
            all_entries.extend(entries)
            time.sleep(0.8)

        logger.info(f"Sitemaps completos: {len(all_entries)} PIDs extraidos")
        return all_entries

    def _fetch_sitemap(self, url):
        logger.info(f"Fetching sitemap: {url}")
        r = retry_get(self.session, url, max_retries=3)

        if not r or r.status_code != 200:
            logger.error(f"Sitemap no disponible: {url}")
            return []

        # Extraer todas las <loc>
        locs = re.findall(r"<loc>(https?://[^<]+)</loc>", r.text)
        logger.info(f"  {url.split('/')[-1]}: {len(locs)} URLs en sitemap")

        entries = []
        for loc in locs:
            m = PID_RE.search(loc)
            if m:
                pid = int(m.group(1))
                entries.append((pid, loc))
            else:
                logger.debug(f"  URL sin patron PID: {loc}")

        logger.info(f"  {url.split('/')[-1]}: {len(entries)} productos extraidos")
        return entries
