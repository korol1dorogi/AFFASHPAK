# PDF-заглушки документов — ДЕМО (S9)

Синтетические документы для сценария 4 (`furniture_maker`: запрос документа → загрузка), docs/data-spec.md §7.6 и §9.3. Компания, ИНН и все тексты выдуманы; на каждой странице крупный водяной знак «DEMO» и под ним «ДЕМО», нарисованное линиями (без шрифта).

Имена файлов латиницей (`_demo`, а не `_демо` из data-spec §7.6): кириллица в именах ломает zip на Windows и заголовок Content-Disposition.

| Файл | Вид (`DocumentKind`) | Когда загружается |
|---|---|---|
| `bank_statement_0001000042_demo.pdf` | `bank_statement` | бухгалтер, до отправки |
| `tax_return_0001000042_demo.pdf` | `tax_return` | бухгалтер, до отправки |
| `contract_0001000042_demo.pdf` | `contract` | бухгалтер, до отправки |
| `invoice_0001000042_demo.pdf` | `invoice` | бухгалтер, до отправки |
| `financial_report_0001000042_demo.pdf` | `financial_report` | в ответ на запрос сотрудника банка |

PDF собираются генератором без зависимостей (стандартный шрифт Helvetica без встраивания — поэтому текст латиницей, а «ДЕМО» — векторными линиями); байты одинаковы на каждом прогоне. Файлы не правим руками — перегенерируем:

```sh
python3 data/sample/documents/generate.py
```

Проверки (из корня репозитория):

```sh
docker compose run --rm -v ./data/sample/documents:/s9 -e PYTHONPATH=/app:/s9 backend sh -c \
  "cd /s9 && ruff check --config /app/pyproject.toml --extend-per-file-ignores 'tests/*:S101' . \
   && ruff format --config /app/pyproject.toml --check . && pytest -p no:cacheprovider /s9"
```
