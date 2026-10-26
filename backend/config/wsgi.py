import os
import threading

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()


def _warm_up() -> None:
    """Build the per-process caches before the first visitor needs them.

    The credit policy screen scores the 240-company synthetic population (~13 s cold) and the
    first submit reads the simulators' dataset (~2 s): without this the first jury member to open
    them in each worker waits. Only the web server loads this module — not the Celery worker,
    tests or manage.py. A failure here is harmless: the request builds the cache as before.
    """
    try:
        from apps.integrations.simulator_data import dataset
        from apps.scoring.population import population

        dataset()
        population()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("warm-up failed; caches will fill on first use")


if os.environ.get("WARM_UP", "1") != "0":
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
