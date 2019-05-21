#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function

__all__ = []

import re
import shlex
import calendar
from datetime import datetime
from operator import itemgetter
from collections import namedtuple

import ads

import flask
from werkzeug.contrib.cache import SimpleCache


app = flask.Flask(__name__)
cache = SimpleCache()
Tokens = namedtuple("Tokens", ("years", "authors"))


class RateLimitError(Exception):
    pass


class InvalidQueryError(Exception):
    pass


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
    ratelimit = cache.get("ratelimit")
    if ratelimit is not None:
        current = calendar.timegm(datetime.utcnow().timetuple())
        delta = current - int(ratelimit.get("reset", 0))
        if ratelimit.get("remaining", "1") == "0" and delta < 0:
            raise RateLimitError()

    tokens = tokenize(query)
    if len(tokens.authors) == 0:
        raise InvalidQueryError()

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
    result = ads.SearchQuery(
        q=q,
        sort="pubdate+desc",
        fl=["id", "title", "author", "doi", "year", "pubdate", "pub",
            "volume", "page", "identifier", "doctype", "citation_count",
            "bibcode"], max_pages=1)
    papers = list(result)

    # Save the rate limit
    ratelimit = result.response.get_ratelimits()
    cache.set("ratelimit", ratelimit)

    # Get the list of bibtex entries
    # bibcodes = [p.bibcode for p in papers]
    # query = ads.ExportQuery(bibcodes=bibcodes, format="bibtex")
    # bibtex = (b for b in query.execute().split("\n\n"))

    dicts = []
    for paper in papers:
        aid = [":".join(t.split(":")[1:]) for t in paper.identifier
               if t.startswith("arXiv:")]
        for t in paper.identifier:
            if len(t.split(".")) != 2:
                continue
            try:
                list(map(int, t.split(".")))
            except ValueError:
                pass
            else:
                aid.append(t)
        try:
            page = int(paper.page[0])
        except (ValueError, TypeError):
            page = None
            if paper.page is not None and paper.page[0].startswith("arXiv:"):
                aid.append(":".join(paper.page[0].split(":")[1:]))
        dicts.append(dict(
            bibcode=paper.bibcode,
            doctype=paper.doctype,
            authors=list(paper.author),
            year=paper.year,
            pubdate=paper.pubdate,
            doi=paper.doi[0] if paper.doi is not None else None,
            title=paper.title[0],
            pub=paper.pub,
            volume=paper.volume,
            page=page,
            arxiv=aid[0] if len(aid) else None,
            citations=(paper.citation_count
                       if paper.citation_count is not None else 0),
            url="https://ui.adsabs.harvard.edu/abs/{0}/abstract"
                .format(paper.bibcode),
            bibtex_url="https://ui.adsabs.harvard.edu/abs/{0}/exportcitation"
                .format(paper.bibcode),
        ))
    return q, sorted(dicts, key=itemgetter("pubdate"), reverse=True)


@app.route("/search/")
def search():
    q = flask.request.args.get("q", None)
    if q is None:
        return flask.redirect(flask.url_for("index"))

    # Get the list of papers from the cache if it exists
    cache_result = cache.get(q)
    if cache_result is None:
        # Otherwise hit ADS with the query
        query, papers = perform_query(q)
        cache.set(q, (query, papers))
    else:
        query, papers = cache_result

    return flask.render_template("results.html", query=query, papers=papers)


@app.route("/")
def index():
    return flask.render_template("index.html")


if __name__ == "__main__":
    print(perform_query("Foreman-Mackey Hogg 2013 2015"))
