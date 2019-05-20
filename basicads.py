#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function

__all__ = []

import re
import ads
import shlex
from collections import namedtuple


Tokens = namedtuple("Tokens", ("years", "authors"))


def tokenize(query):
    tokens = shlex.split(query)
    years = []
    authors = []
    for token in tokens:
        token = token.strip()
        numbers = re.findall("[0-9]+", token)
        years += list(sorted(int(n) for n in numbers if len(n) == 4))
        if len(numbers) == 0:
            authors.append(token)
    return Tokens(
        list(sorted(years)),
        authors,
    )


def perform_query(query):
    tokens = tokenize(query)
    if len(tokens.authors) == 0:
        return

    # Construct the query
    q = []
    for author in tokens.authors:
        q.append("author:\"" + author + "\"")
    if len(tokens.years) == 1:
        q.append("year:{0}".format(tokens.years[0]))
    elif len(tokens.years) > 1:
        q.append("year:[{0} TO {1}]".format(
            min(tokens.years), max(tokens.years)))
    q = " ".join(q)

    # Get the list of papers
    papers = list(ads.SearchQuery(
        q=q,
        fl=["id", "title", "author", "doi", "year", "pubdate", "pub",
            "volume", "page", "identifier", "doctype", "citation_count",
            "bibcode"], max_pages=1))

    # Get the list of bibtex entries
    # bibcodes = [p.bibcode for p in papers]
    # query = ads.ExportQuery(bibcodes=bibcodes, format="bibtex")
    # bibtex = (b for b in query.execute().split("\n\n"))

    return papers


if __name__ == "__main__":
    print(perform_query("Foreman-Mackey Hogg 2013 2015"))
