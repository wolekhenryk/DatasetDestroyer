"""unify - builds ONE tidy label table (merged-labels.csv) from every dataset folder in data_to_merge/.

    from unify.build import build_all, write_csv
    df, report = build_all(DATA_ROOT)

Layout: schema.py (columns), common.py (helpers), context.py (what an adapter receives), registry.py (adapter discovery),
build.py (run adapters + generic post-processing), validate.py (checks), adapters/<dataset>.py, vocab/<dataset>.csv.
"""
