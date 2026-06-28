"""defproc-monitor scraper package.

Pipeline: fetch (public GETs) -> parse (HTML -> rows) -> enrich (detail page) ->
classify (supplied classify.py) -> geocode (offline CSV) -> diff/retain -> JSON.
classify.py is supplied and FINAL; import ProcurementClassifier and use as-is.
"""
