from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from enum import Enum
from pathlib import Path
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field, field_validator


BASE_URL = "https://www.scrapethissite.com/pages/ajax-javascript/"
DEFAULT_YEARS = list(range(2010, 2016))

# Same data directory used by docker-compose (./data at repo root)
DATA_DIR = (Path(__file__).resolve().parents[2] / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
CLI_OUTPUT_FILE_SELENIUM = DATA_DIR / "oscar_selenium_cli.json"
CLI_OUTPUT_FILE_AJAX = DATA_DIR / "oscar_ajax_cli.json"


class OscarFilm(BaseModel):
    title: str
    year: int
    nominations: int
    awards: int
    best_picture: bool = Field(default=False, alias="best_picture")

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        # Normaliza espaços em branco ao redor do título
        return v.strip() if isinstance(v, str) else v


class CliMode(str, Enum):
    selenium = "selenium"
    ajax = "ajax"


async def fetch_year(client: httpx.AsyncClient, year: int) -> List[OscarFilm]:
    response = await client.get(
        BASE_URL,
        params={"ajax": "true", "year": year},
        timeout=20.0,
    )
    response.raise_for_status()
    raw_items = response.json()
    films = [OscarFilm.model_validate(item) for item in raw_items]
    return films


async def crawl_oscar_films_ajax(years: Optional[List[int]] = None) -> List[OscarFilm]:
    years_to_fetch = years or DEFAULT_YEARS
    async with httpx.AsyncClient() as client:
        tasks = [fetch_year(client, year) for year in years_to_fetch]
        results = await asyncio.gather(*tasks)
    films: List[OscarFilm] = [film for sublist in results for film in sublist]
    return films


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Oscar films crawler CLI (default: selenium)."
    )
    parser.add_argument(
        "--mode",
        choices=[m.value for m in CliMode],
        default=CliMode.selenium.value,
        help="selenium (default) ou ajax",
    )
    args = parser.parse_args()
    mode = CliMode(args.mode)

    if mode is CliMode.selenium:
        # Carrega o crawler Selenium compartilhado (mesmo usado pela API)
        selenium_path = (
            Path(__file__).resolve().parents[0] / "selenium_crawler.py"
        )
        spec = importlib.util.spec_from_file_location(
            "selenium_crawler", selenium_path
        )
        assert spec is not None and spec.loader is not None
        selenium_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(selenium_mod)  # type: ignore[arg-type]

        crawl_selenium = selenium_mod.crawl_oscar_films_selenium
        films: List[OscarFilm] = asyncio.run(crawl_selenium())
        CLI_OUTPUT_FILE_SELENIUM.write_text(
            json.dumps([film.model_dump() for film in films], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[selenium] Collected {len(films)} films → {CLI_OUTPUT_FILE_SELENIUM}")
    else:
        films = asyncio.run(crawl_oscar_films_ajax())
        CLI_OUTPUT_FILE_AJAX.write_text(
            json.dumps([film.model_dump() for film in films], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[ajax] Collected {len(films)} films → {CLI_OUTPUT_FILE_AJAX}")


if __name__ == "__main__":
    main()
