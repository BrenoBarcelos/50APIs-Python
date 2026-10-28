#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHIBATA 50 — seletor interativo de 50 APIs públicas.

- Python puro: usa somente a biblioteca padrão (urllib, json, argparse etc.).
- Faz chamadas GET reais apenas quando a pessoa escolhe uma API.
- Sem chaves de API, sem integrações de pagamento e sem dependências externas.
- Limita tempo de espera, tamanho lido e tamanho exibido para evitar chamadas pesadas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "1.0"
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 128 * 1024  # lê no máximo 128 KiB por chamada
MAX_PRINT_CHARS = 6_000
USER_AGENT = f"Chibata50/{VERSION} (Python standard-library demo)"


# Lista explícita dos hosts públicos usados pelo catálogo. Para cadastrar uma nova
# API, inclua o host aqui; URLs fornecidas pelo usuário nunca definem um host.
ALLOWED_API_HOSTS = frozenset({
    "air-quality-api.open-meteo.com",
    "api.bigdatacloud.net",
    "api.carbonintensity.org.uk",
    "api.chess.com",
    "api.coinbase.com",
    "api.coingecko.com",
    "api.duckduckgo.com",
    "api.frankfurter.dev",
    "api.github.com",
    "api.ipify.org",
    "api.jolpi.ca",
    "api.kraken.com",
    "api.open-meteo.com",
    "api.openf1.org",
    "api.postcodes.io",
    "api.scryfall.com",
    "api.spaceflightnewsapi.net",
    "api.stackexchange.com",
    "api.sunrise-sunset.org",
    "api.tvmaze.com",
    "api.weather.gov",
    "api.wheretheiss.at",
    "api.zippopotam.us",
    "collectionapi.metmuseum.org",
    "crates.io",
    "data.jsdelivr.com",
    "date.nager.at",
    "ddragon.leagueoflegends.com",
    "dog.ceo",
    "dummyjson.com",
    "earthquake.usgs.gov",
    "en.wikipedia.org",
    "hn.algolia.com",
    "ipapi.co",
    "itunes.apple.com",
    "jsonplaceholder.typicode.com",
    "nominatim.openstreetmap.org",
    "open.er-api.com",
    "openlibrary.org",
    "opentdb.com",
    "photon.komoot.io",
    "randomuser.me",
    "registry.npmjs.org",
    "rickandmortyapi.com",
    "rubygems.org",
    "statsapi.mlb.com",
    "swapi.dev",
    "wttr.in",
    "www.7timer.info",
    "xkcd.com",
})


class UnsafeURL(ValueError):
    """URL rejeitada pelas regras de destino seguro do catálogo."""


def validate_api_url(url: str) -> str:
    """Aceita somente HTTPS para um host público explicitamente autorizado."""
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise UnsafeURL("URL vazia, inválida ou excessivamente longa.")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in url):
        raise UnsafeURL("A URL contém caracteres de controle.")
