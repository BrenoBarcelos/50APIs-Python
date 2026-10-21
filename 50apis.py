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
from urllib.parse import quote
from urllib.request import Request, urlopen

VERSION = "1.0"
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 128 * 1024  # lê no máximo 128 KiB por chamada
MAX_PRINT_CHARS = 6_000
USER_AGENT = f"Chibata50/{VERSION} (Python standard-library demo)"


@dataclass(frozen=True)
class Api:
    name: str
    category: str
    url: str
    what_it_does: str
    prompt: Optional[str] = None
    default_query: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    query_safe: str = ""

    def make_url(self) -> str:
        """Monta a URL e pede um termo somente para APIs pesquisáveis."""
        if "{query}" not in self.url:
            return self.url
        entered = input(f"{self.prompt or 'Digite a pesquisa'} [{self.default_query}]: ").strip()
        value = entered or self.default_query
        return self.url.replace("{query}", quote(value, safe=self.query_safe))


# Todos os exemplos são GETs públicos sem chave. Algumas APIs oferecem limites
# de uso próprios; por isso o programa só chama uma delas quando o usuário escolhe.
APIS: list[Api] = [
    Api("Open-Meteo — previsão do tempo", "Clima e ciência",
        "https://api.open-meteo.com/v1/forecast?latitude=-3.73&longitude=-38.52&current=temperature_2m,relative_humidity_2m,wind_speed_10m",
        "Temperatura, umidade e vento para Fortaleza."),
    Api("Open-Meteo — qualidade do ar", "Clima e ciência",
        "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=-3.73&longitude=-38.52&current=pm10,pm2_5",
        "Índices de partículas no ar para Fortaleza."),
    Api("wttr.in — clima em JSON", "Clima e ciência",
        "https://wttr.in/Fortaleza?format=j1",
        "Condições e previsão do tempo em Fortaleza."),
    Api("7Timer! — previsão meteorológica", "Clima e ciência",
        "https://www.7timer.info/bin/api.pl?lon=-38.52&lat=-3.73&product=civil&output=json",
        "Previsão meteorológica para coordenadas de Fortaleza."),
    Api("National Weather Service", "Clima e ciência",
        "https://api.weather.gov/points/39.7456,-97.0892",
        "Metadados meteorológicos de um ponto nos Estados Unidos.",
        headers={"User-Agent": "Chibata50/1.0 (educational demo)"}),
    Api("USGS — terremotos recentes", "Clima e ciência",
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
        "Lista compacta de terremotos de magnitude 4,5 ou maior nas últimas 24 horas."),
    Api("Sunrise-Sunset", "Clima e ciência",
        "https://api.sunrise-sunset.org/json?lat=-3.73&lng=-38.52&formatted=0",
        "Horários de nascer e pôr do sol para Fortaleza."),
    Api("UK Carbon Intensity", "Clima e ciência",
        "https://api.carbonintensity.org.uk/intensity",
        "Índice de intensidade de carbono da eletricidade no Reino Unido."),
    Api("Where the ISS at?", "Clima e ciência",
        "https://api.wheretheiss.at/v1/satellites/25544",
        "Posição atual da Estação Espacial Internacional."),
    Api("Spaceflight News", "Clima e ciência",
        "https://api.spaceflightnewsapi.net/v4/articles/?limit=1",
        "Notícia recente sobre exploração espacial (um resultado)."),

    Api("Zippopotam.us — código postal", "Localização e utilidades",
        "https://api.zippopotam.us/us/90210",
        "Pesquisa de código postal de exemplo nos Estados Unidos."),
    Api("ipify — IP público", "Localização e utilidades",
        "https://api.ipify.org?format=json",
        "Retorna o IP público usado para fazer a requisição. Só consulta se você selecionar esta opção."),
    Api("ipapi.co — dados aproximados da conexão", "Localização e utilidades",
        "https://ipapi.co/json/",
        "Pode retornar IP e localização aproximada da conexão. Só consulta se você selecionar esta opção."),
    Api("BigDataCloud — geolocalização reversa", "Localização e utilidades",
        "https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=52.37&longitude=4.89&localityLanguage=en",
        "Converte coordenadas de exemplo em informações de localidade."),
    Api("Postcodes.io", "Localização e utilidades",
        "https://api.postcodes.io/postcodes/SW1A1AA",
        "Consulta um código postal britânico de exemplo."),
    Api("Nager.Date — próximos feriados", "Localização e utilidades",
        "https://date.nager.at/api/v3/NextPublicHolidays/BR",
        "Próximos feriados públicos do Brasil."),
    Api("Nominatim / OpenStreetMap", "Localização e utilidades",
        "https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1",
        "Geocodifica um lugar; use com moderação, respeitando o limite do serviço.",
        prompt="Local para pesquisar", default_query="Fortaleza, Brazil",
        headers={"User-Agent": "Chibata50/1.0 (educational demo; one request on demand)"}),
    Api("Photon — busca de lugares", "Localização e utilidades",
        "https://photon.komoot.io/api/?q={query}&limit=1",
        "Busca um lugar e retorna coordenadas e dados básicos.",
        prompt="Lugar para pesquisar", default_query="Fortaleza, Brazil"),

    Api("Wikipedia — pesquisar artigo", "Conhecimento e mídia",
        "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit=1",
        "Encontra um artigo da Wikipédia.", prompt="Assunto", default_query="Python programming"),
    Api("Open Library — buscar livros", "Conhecimento e mídia",
        "https://openlibrary.org/search.json?q={query}&limit=1&fields=title,author_name,first_publish_year",
        "Busca um livro e retorna título, autor e ano quando disponível.",
        prompt="Livro ou autor", default_query="The Hobbit"),
    Api("DuckDuckGo Instant Answer", "Conhecimento e mídia",
        "https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1",
        "Busca uma resposta instantânea; nem toda pesquisa terá resumo.",
        prompt="Termo da pesquisa", default_query="Fortaleza"),
    Api("The Met Collection — arte", "Conhecimento e mídia",
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/436535",
        "Dados de uma obra do acervo do Metropolitan Museum of Art."),
    Api("iTunes Search — música", "Conhecimento e mídia",
        "https://itunes.apple.com/search?term={query}&entity=song&limit=1",
        "Busca uma música no catálogo do iTunes.", prompt="Artista ou música", default_query="Radiohead"),
    Api("TVmaze — séries", "Conhecimento e mídia",
        "https://api.tvmaze.com/singlesearch/shows?q={query}",
        "Pesquisa uma série de TV e retorna seus dados básicos.",
        prompt="Nome da série", default_query="Severance"),

    Api("JSONPlaceholder — tarefa de exemplo", "Testes e desenvolvimento",
        "https://jsonplaceholder.typicode.com/todos/1",
        "API de demonstração com um objeto JSON pequeno."),
    Api("DummyJSON — produto", "Testes e desenvolvimento",
        "https://dummyjson.com/products/1",
        "Produto fictício com preço, descrição e categoria."),
    Api("Random User — pessoa fictícia", "Testes e desenvolvimento",
        "https://randomuser.me/api/?results=1&nat=br",
        "Gera um perfil de usuário fictício; não é dado real de uma pessoa."),
    Api("Rick and Morty — personagem", "Testes e desenvolvimento",
        "https://rickandmortyapi.com/api/character/?name={query}&page=1",
        "Pesquisa personagens da série Rick and Morty.",
        prompt="Nome do personagem", default_query="Rick Sanchez"),
    Api("SWAPI — Star Wars", "Testes e desenvolvimento",
        "https://swapi.dev/api/people/1/",
        "Dados de um personagem de Star Wars."),
    Api("Open Trivia DB — pergunta aleatória", "Testes e desenvolvimento",
        "https://opentdb.com/api.php?amount=1&type=multiple",
        "Retorna uma pergunta de conhecimentos gerais e alternativas."),
    Api("Dog CEO — imagem de cachorro", "Testes e desenvolvimento",
        "https://dog.ceo/api/breeds/image/random",
        "Retorna a URL de uma imagem aleatória de cachorro."),
    Api("xkcd — quadrinho", "Testes e desenvolvimento",
        "https://xkcd.com/info.0.json",
        "Metadados do quadrinho mais recente do xkcd."),

    Api("MLB Stats — times de beisebol", "Esportes e jogos",
        "https://statsapi.mlb.com/api/v1/teams?sportId=1&fields=teams,id,name,abbreviation",
        "Lista compacta de times da liga principal de beisebol."),
    Api("Jolpica F1 — resultados de Fórmula 1", "Esportes e jogos",
        "https://api.jolpi.ca/ergast/f1/current/last/results.json",
        "Resultados da última etapa disponível na API de Fórmula 1."),
    Api("OpenF1 — sessões de corrida", "Esportes e jogos",
        "https://api.openf1.org/v1/sessions?year=2026&session_type=Race",
        "Sessões de corrida de F1 em 2026; pode retornar uma lista vazia se ainda não houver dados."),
    Api("Chess.com — perfil de jogador", "Esportes e jogos",
        "https://api.chess.com/pub/player/hikaru",
        "Dados públicos básicos do perfil do jogador Hikaru Nakamura."),
    Api("Riot Data Dragon — versões do LoL", "Esportes e jogos",
        "https://ddragon.leagueoflegends.com/api/versions.json",
        "Lista de versões publicadas de dados de League of Legends."),
    Api("Scryfall — carta de Magic", "Esportes e jogos",
        "https://api.scryfall.com/cards/named?fuzzy=black%20lotus",
        "Consulta de exemplo de uma carta de Magic: The Gathering."),

    Api("Frankfurter — câmbio", "Finanças e cotações",
        "https://api.frankfurter.dev/v1/latest?base=USD&symbols=BRL,EUR,GBP",
        "Taxas de câmbio de referência; não são necessariamente cotações em tempo real."),
    Api("ExchangeRate-API — taxas abertas", "Finanças e cotações",
        "https://open.er-api.com/v6/latest/USD",
        "Taxas cambiais de referência com dólar como moeda-base."),
    Api("Coinbase — preço à vista do Bitcoin", "Finanças e cotações",
        "https://api.coinbase.com/v2/prices/BTC-USD/spot",
        "Preço BTC/USD divulgado pelo serviço; pode variar rapidamente."),
    Api("Kraken — ticker BTC/USD", "Finanças e cotações",
        "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
        "Cotação de mercado BTC/USD da Kraken; sujeita a variações."),
    Api("CoinGecko — preço de criptoativos", "Finanças e cotações",
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        "Preços informativos de Bitcoin e Ethereum em dólares; pode haver limite de requisições."),

    Api("GitHub — pesquisar repositórios", "Desenvolvimento de software",
        "https://api.github.com/search/repositories?q={query}&per_page=1",
        "Pesquisa um repositório público no GitHub.", prompt="Projeto ou termo", default_query="python",
        headers={"Accept": "application/vnd.github+json"}),
    Api("npm Registry — pacote JavaScript", "Desenvolvimento de software",
        "https://registry.npmjs.org/react/latest",
        "Metadados da versão mais recente do pacote React no npm."),
    Api("crates.io — pacotes Rust", "Desenvolvimento de software",
        "https://crates.io/api/v1/crates?q=serde&per_page=1",
        "Pesquisa um pacote no registro da linguagem Rust."),
    Api("jsDelivr — estatísticas de pacote", "Desenvolvimento de software",
        "https://data.jsdelivr.com/v1/stats/packages/npm/react?period=month",
        "Estatísticas de uso do pacote React no jsDelivr."),
    Api("RubyGems — pacote Rails", "Desenvolvimento de software",
        "https://rubygems.org/api/v1/gems/rails.json",
        "Metadados da gem Rails."),
    Api("Stack Exchange — perguntas recentes", "Desenvolvimento de software",
        "https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&site=stackoverflow&pagesize=1",
        "A pergunta recentemente ativa no Stack Overflow, com metadados."),
    Api("Hacker News — buscar notícias de tecnologia", "Desenvolvimento de software",
        "https://hn.algolia.com/api/v1/search?query={query}&hitsPerPage=1",
        "Busca uma notícia/discussão no Hacker News.", prompt="Termo da busca", default_query="Python"),
]


def show_header() -> None:
    print("\n" + "=" * 72)
    print(f"  CHIBATA 50 v{VERSION} | 50 APIs públicas | Python puro")
    print("  Escolha uma API para fazer uma requisição real e ver a resposta.")
    print("=" * 72)


def print_menu() -> None:
    last_category = None
    for number, api in enumerate(APIS, start=1):
        if api.category != last_category:
            last_category = api.category
            print(f"\n[{last_category}]")
        print(f" {number:02d}. {api.name}")
    print("\n  0. Sair")


def print_response_body(body: bytes, content_type: str) -> None:
    text = body.decode("utf-8", errors="replace")
    if len(body) > MAX_RESPONSE_BYTES:
        text = text[:MAX_PRINT_CHARS]
        print(f"\n[Resposta maior que {MAX_RESPONSE_BYTES:,} bytes; leitura limitada por segurança. Prévia abaixo.]".replace(",", "."))
        print(text)
        return

    try:
        parsed = json.loads(text)
        pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        if len(pretty) > MAX_PRINT_CHARS:
            pretty = pretty[:MAX_PRINT_CHARS]
            print("\n[Prévia limitada para o terminal; a API respondeu com sucesso.]")
            print(pretty + "\n... [conteúdo omitido]")
        else:
            print(pretty)
    except (json.JSONDecodeError, TypeError):
        if len(text) > MAX_PRINT_CHARS:
            print(text[:MAX_PRINT_CHARS] + "\n... [conteúdo omitido]")
        else:
            print(text or "[A API retornou uma resposta vazia.] ")


def call_api(api: Api, number: int) -> bool:
    """Chama uma API escolhida. Retorna True caso HTTP 2xx."""
    print("\n" + "-" * 72)
    print(f"API {number:02d}/50 — {api.name}")
    print(f"O que faz: {api.what_it_does}")
    try:
        url = api.make_url()
    except (EOFError, KeyboardInterrupt):
        print("\nConsulta cancelada.")
        return False

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    headers.update(api.headers)
    req = Request(url, headers=headers, method="GET")
    print(f"\nGET {url}")
    print("Consultando...", flush=True)
    started = time.perf_counter()

    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "desconhecido")
            body = response.read(MAX_RESPONSE_BYTES + 1)
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\nSTATUS: HTTP {status} | TEMPO: {elapsed:.0f} ms | TIPO: {content_type}")
        if status < 200 or status >= 300:
            print("A API respondeu, mas o status não indica sucesso.")
            print_response_body(body[:MAX_RESPONSE_BYTES], content_type)
            return False
        print("\nRESPOSTA REAL DA API:")
        print_response_body(body, content_type)
        return True

    except HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\nERRO HTTP {exc.code} após {elapsed:.0f} ms: {exc.reason}")
        try:
            err_body = exc.read(4_000)
            if err_body:
                print_response_body(err_body, exc.headers.get("Content-Type", "desconhecido"))
        except Exception:
            pass
        print("Dica: pode ser limite temporário, mudança do provedor ou endpoint indisponível.")
        return False
    except URLError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        reason = getattr(exc, "reason", exc)
        print(f"\nFALHA DE CONEXÃO após {elapsed:.0f} ms: {reason}")
        print("Confira a internet, DNS, firewall ou tente novamente mais tarde.")
        return False
    except TimeoutError:
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\nTIMEOUT após {elapsed:.0f} ms: a API demorou mais de {TIMEOUT_SECONDS} s.")
        return False
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\nERRO inesperado após {elapsed:.0f} ms: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Escolha e consulte uma de 50 APIs públicas usando somente Python padrão."
    )
    parser.add_argument("--listar", action="store_true", help="mostra a lista sem fazer requisições")
    parser.add_argument("--api", type=int, metavar="N", help="executa uma API pelo número (1 a 50)")
    args = parser.parse_args()

    if len(APIS) != 50:
        print(f"Erro interno: catálogo tem {len(APIS)} APIs, não 50.", file=sys.stderr)
        return 2

    if args.listar:
        show_header()
        print_menu()
        return 0

    if args.api is not None:
        if not 1 <= args.api <= len(APIS):
            print("Número inválido. Escolha um valor entre 1 e 50.", file=sys.stderr)
            return 2
        return 0 if call_api(APIS[args.api - 1], args.api) else 1

    while True:
        show_header()
        print_menu()
        try:
            choice = input("\nDigite o número da API (0 para sair): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nSaindo do CHIBATA 50.")
            return 0

        if choice in {"0", "sair", "q", "quit", "exit"}:
            print("CHIBATA 50 encerrado.")
            return 0
        if not choice.isdigit() or not 1 <= int(choice) <= len(APIS):
            print("Escolha inválida. Digite um número de 1 a 50, ou 0 para sair.")
            input("Pressione ENTER para continuar...")
            continue

        call_api(APIS[int(choice) - 1], int(choice))
        try:
            input("\nPressione ENTER para voltar à lista e escolher outra API...")
        except (EOFError, KeyboardInterrupt):
            print("\nSaindo do CHIBATA 50.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
