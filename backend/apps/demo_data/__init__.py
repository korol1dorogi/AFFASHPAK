"""Synthetic demo data generator (S2). Pure Python, no Django; everything is marked «демо».

One seed → byte-identical JSON. No datetime.now(), uuid4, global random or set/dict ordering:
randomness comes only from rng.Rng, dates only from the explicit `as_of`.
The JSON format is a draft until docs/data-spec.md (D7) is approved — see build.SCHEMA_VERSION.
"""
