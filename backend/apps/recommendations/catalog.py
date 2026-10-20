"""Which products answer which need, and the term offered when the client gave none.

Need → product kinds follow docs/products.md («Потребность → продукт»), in the order of that
table: the first kind fits the task best. Default terms are a proposal to the lead to move into
`Product.params`; until then they live here, clamped to the product's term range anyway.
"""

from types import MappingProxyType

NEED_PRODUCT_KINDS = MappingProxyType(
    {
        "cash_gap": ("overdraft",),
        "receivable_delay": ("factoring",),
        "working_capital": ("working_capital_loan",),
        "capex": ("investment_loan", "leasing"),
    }
)

DEFAULT_TERM_MONTHS = MappingProxyType(
    {
        "overdraft": 12,  # the limit is opened for a year (products.md)
        "factoring": 2,  # a typical 60-day deferral, as for persona 2
        "working_capital_loan": 12,
        "investment_loan": 36,
        "leasing": 36,
    }
)
