from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from shutil import which
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://www.scrapethissite.com/pages/ajax-javascript/"

DATA_DIR = (Path(__file__).resolve().parents[2] / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
SELENIUM_OUTPUT_FILE = DATA_DIR / "oscar_selenium.json"


class OscarFilm(BaseModel):
    title: str
    year: int
    nominations: int
    awards: int
    best_picture: bool = Field(default=False, alias="best_picture")

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


def _build_driver() -> webdriver.Chrome:
    chrome_path = os.getenv("CHROME_EXECUTABLE_PATH")
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH") or which("chromedriver")

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")

    if chrome_path:
        options.binary_location = chrome_path

    if chromedriver_path:
        service = ChromeService(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)

    return webdriver.Chrome(options=options)


def _scrape_current_table(driver: webdriver.Chrome, year: int) -> List[OscarFilm]:
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "tbody#table-body tr.film")) > 0
    )

    rows = driver.find_elements(By.CSS_SELECTOR, "tbody#table-body tr.film")
    films: List[OscarFilm] = []
    for row in rows:
        title = row.find_element(By.CSS_SELECTOR, "td.film-title").text
        nominations = int(row.find_element(By.CSS_SELECTOR, "td.film-nominations").text)
        awards = int(row.find_element(By.CSS_SELECTOR, "td.film-awards").text)
        best_picture = len(
            row.find_elements(By.CSS_SELECTOR, "td.film-best-picture i.glyphicon-flag")
        ) > 0

        films.append(
            OscarFilm(
                title=title,
                year=year,
                nominations=nominations,
                awards=awards,
                best_picture=best_picture,
            )
        )

    return films


def _discover_years_and_first_page() -> Tuple[List[int], int, List[OscarFilm]]:
    driver = _build_driver()
    try:
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 20)

        try:
            links = wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "a.year-link"))
        except TimeoutException as exc:
            raise RuntimeError("Timeout waiting for .year-link anchors on Oscar page") from exc

        years_found: List[int] = []
        active_year: Optional[int] = None

        for link in links:
            year_id = link.get_attribute("id")
            if not year_id:
                continue
            try:
                year_int = int(year_id)
            except ValueError:
                continue
            years_found.append(year_int)

            classes = (link.get_attribute("class") or "").split()
            if "active" in classes:
                active_year = year_int

        if not years_found:
            raise RuntimeError("Nenhum ano encontrado via Selenium (.year-link).")

        if active_year is None:
            active_year = years_found[0]

        # A página carrega sem nenhum ano selecionado de fato.
        # Precisamos simular o clique no ano ativo para disparar o fetchFilms(year).
        driver.find_element(By.ID, str(active_year)).click()

        first_films = _scrape_current_table(driver, active_year)
        return years_found, active_year, first_films
    finally:
        driver.quit()


def _fetch_year_selenium(year: int) -> List[OscarFilm]:
    driver = _build_driver()
    try:
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 20)

        wait.until(lambda d: d.find_element(By.ID, str(year)))
        driver.find_element(By.ID, str(year)).click()

        return _scrape_current_table(driver, year)
    finally:
        driver.quit()


async def crawl_oscar_films_selenium(years: Optional[List[int]] = None) -> List[OscarFilm]:
    """
    Selenium + paralelismo:
    1) Usa um driver para descobrir dinamicamente os anos disponíveis (links .year-link)
       e coletar os filmes do ano inicialmente ativo.
    2) Cria drivers em paralelo (até N anos) para coletar os demais anos.
    """
    # Se o chamador passou explicitamente os anos, usamos direto.
    if years is not None:
        years_to_fetch = years
        semaphore = asyncio.Semaphore(len(years_to_fetch))

        async def run_one(y: int) -> List[OscarFilm]:
            async with semaphore:
                return await asyncio.to_thread(_fetch_year_selenium, y)

        results = await asyncio.gather(*[run_one(y) for y in years_to_fetch])
        flattened: List[OscarFilm] = []
        for sublist in results:
            flattened.extend(sublist)
        return flattened

    # Caso padrão: descobrir anos via Selenium.
    years_found, active_year, first_films = await asyncio.to_thread(_discover_years_and_first_page)

    remaining_years = [y for y in years_found if y != active_year]
    if not remaining_years:
        return first_films

    semaphore = asyncio.Semaphore(len(remaining_years))

    async def run_one_remaining(y: int) -> List[OscarFilm]:
        async with semaphore:
            return await asyncio.to_thread(_fetch_year_selenium, y)

    remaining_results = await asyncio.gather(*[run_one_remaining(y) for y in remaining_years])
    all_films: List[OscarFilm] = list(first_films)
    for sublist in remaining_results:
        all_films.extend(sublist)
    return all_films


def main() -> None:
    films: List[OscarFilm] = asyncio.run(crawl_oscar_films_selenium())

    SELENIUM_OUTPUT_FILE.write_text(
        json.dumps([film.model_dump() for film in films], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[Selenium] Collected {len(films)} films → {SELENIUM_OUTPUT_FILE}")


if __name__ == "__main__":
    main()

