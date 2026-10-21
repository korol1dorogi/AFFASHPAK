from django.db import models


class DemoState(models.Model):
    """Simulator outage flags of the demo stand (docs/data-model.md, DemoState).

    In the database, not in process memory: every gunicorn worker and the demo panel must
    see the same flag.
    """

    source = models.CharField(max_length=32, unique=True)
    failing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "сбой симулятора (демо)"
        verbose_name_plural = "сбои симуляторов (демо)"

    def __str__(self) -> str:
        return f"{self.source}: {'сбой' if self.failing else 'работает'}"
