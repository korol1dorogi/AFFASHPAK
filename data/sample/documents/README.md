# PDF-заглушки документов — ДЕМО (S9)

Синтетические документы для сценария 4 (`furniture_maker`: запрос документа → загрузка), docs/data-spec.md §7.6 и §9.3. Компания, ИНН и все тексты выдуманы; на каждой странице крупный водяной знак «DEMO».

| Файл | Вид (`DocumentKind`) | Когда загружается |
|---|---|---|
| `bank_statement_0001000042_демо.pdf` | `bank_statement` | бухгалтер, до отправки |
| `tax_return_0001000042_демо.pdf` | `tax_return` | бухгалтер, до отправки |
| `contract_0001000042_демо.pdf` | `contract` | бухгалтер, до отправки |
| `invoice_0001000042_демо.pdf` | `invoice` | бухгалтер, до отправки |
| `financial_report_0001000042_демо.pdf` | `financial_report` | в ответ на запрос сотрудника банка |

PDF собираются генератором без зависимостей (стандартный шрифт Helvetica, без встраивания — поэтому текст латиницей); байты одинаковы на каждом прогоне. Файлы не правим руками — перегенерируем:

```sh
python3 data/sample/documents/generate.py
```

Проверки (из корня репозитория):

```sh
docker compose run --rm -v ./data/sample/documents:/s9 -e PYTHONPATH=/app:/s9 backend sh -c \
  "cd /s9 && ruff check --config /app/pyproject.toml --extend-per-file-ignores 'tests/*:S101' . \
   && ruff format --config /app/pyproject.toml --check . && pytest -p no:cacheprovider /s9"
```
