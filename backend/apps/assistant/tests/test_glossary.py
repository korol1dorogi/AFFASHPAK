"""AI12-fix: the glossary knows the terms of the client's path (ЭДО, documents, signature)."""

import pytest

from apps.assistant import glossary


@pytest.mark.parametrize(
    ("asked", "term"),
    [
        ("ЭДО", "эдо"),
        ("эдо", "эдо"),
        ("Электронный документооборот", "эдо"),
        ("электронный документ оборот", "эдо"),
        ("ЭП", "электронная подпись"),
        ("КЭП", "электронная подпись"),
        ("счет на оплату", "счёт поставщика"),
        ("Счёт поставщика", "счёт поставщика"),
        ("выписка", "выписка по счёту"),
        ("обороты", "оборот"),
        ("кредитный договор", "кредитный договор"),
        ("согласие БКИ", "согласие на запрос в бки"),
    ],
)
def test_lookup_finds_the_new_terms(asked, term):
    found = glossary.lookup(asked)
    assert found is not None, asked
    assert found[0] == term


def test_edo_ties_the_term_to_the_products():
    _, text = glossary.lookup("ЭДО")
    assert "факторинг" in text.lower()
    assert "документ" in text.lower()


def test_every_alias_points_to_a_term():
    assert set(glossary.ALIASES.values()) <= set(glossary.TERMS)
