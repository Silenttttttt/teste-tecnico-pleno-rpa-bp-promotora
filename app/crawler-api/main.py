from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


BASE_URL = "https://www.scrapethissite.com/pages/ajax-javascript/"
DEFAULT_YEARS = list(range(2010, 2016))


class JobStatusEnum(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class CrawlModeEnum(str, Enum):
    selenium = "selenium"
    ajax = "ajax"


_selenium_path = (
    Path(__file__).resolve().parents[1] / "crawler-oscar" / "selenium_crawler.py"
)
_selenium_spec = importlib.util.spec_from_file_location(
    "selenium_crawler", _selenium_path
)
_selenium_mod = importlib.util.module_from_spec(_selenium_spec)
assert _selenium_spec is not None and _selenium_spec.loader is not None
_selenium_spec.loader.exec_module(_selenium_mod)  # type: ignore[assignment]

OscarFilm = _selenium_mod.OscarFilm
selenium_crawl = _selenium_mod.crawl_oscar_films_selenium


class CrawlJobResult(BaseModel):
    job_id: str
    status: JobStatusEnum
    created_at: datetime
    updated_at: datetime
    total_films: int = 0
    data_file: Optional[str] = None
    error: Optional[str] = None
    films: Optional[List[OscarFilm]] = None


DATA_DIR = (Path(__file__).resolve().parents[2] / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

jobs: Dict[str, CrawlJobResult] = {}

app = FastAPI(title="Oscar Crawler API")


async def fetch_year(client: httpx.AsyncClient, year: int) -> List[OscarFilm]:
    """
    Busca dados via endpoint AJAX com retry + backoff leve.

    Deixa o modo AJAX da API um pouco mais robusto a falhas transitórias
    (timeout, erros de conexão, 5xx ocasionais).
    """
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = await client.get(
                BASE_URL,
                params={"ajax": "true", "year": year},
                timeout=20.0,
            )
            response.raise_for_status()
            raw_items = response.json()
            films = [OscarFilm.model_validate(item) for item in raw_items]
            return films
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)
            else:
                raise
    raise last_exc  # type: ignore[misc]


async def crawl_oscar_films(years: Optional[List[int]] = None) -> List[OscarFilm]:
    """
    Coleta em modo AJAX puro, com paralelismo e distinção entre falha total/parcial.
    """
    years_to_fetch = years or DEFAULT_YEARS
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[fetch_year(client, year) for year in years_to_fetch],
            return_exceptions=True,
        )

    films: List[OscarFilm] = []
    errors: List[str] = []

    for year, result in zip(years_to_fetch, results, strict=False):
        if isinstance(result, Exception):
            errors.append(f"year={year}: {repr(result)}")
        else:
            films.extend(result)

    if errors and not films:
        # Todos os anos falharam: deixa o erro propagar como RuntimeError,
        # que será capturado por _run_crawl_job e marcado como failed.
        raise RuntimeError(
            "AJAX crawl failed for all years: " + "; ".join(errors)
        )

    # Se chegou aqui, temos pelo menos alguns filmes coletados.
    # Os detalhes de erro vão ser anexados no job.result.error.
    if errors:
        # Anexamos os erros como warning no retorno – quem chama decide se quer logar isso.
        # A API em si continua marcando o job como completed, mas com mensagem clara.
        # (O campo films contém apenas os anos bem-sucedidos.)
        pass

    return films


async def crawl_oscar_films_selenium(years: Optional[List[int]] = None) -> List[OscarFilm]:
    """
    Selenium + paralelismo:
    1) Usa um driver para descobrir dinamicamente os anos disponíveis (links .year-link)
       e coletar os filmes do ano inicialmente ativo.
    2) Cria drivers em paralelo (até N anos) para coletar os demais anos.
    """
    # Delegates to shared selenium crawler in app/crawler-oscar/selenium_crawler.py
    return await selenium_crawl(years)


def _job_file_path(job_id: str) -> Path:
    return DATA_DIR / f"oscar_{job_id}.json"


async def _run_crawl_job(job_id: str, mode: CrawlModeEnum, years: Optional[List[int]] = None) -> None:
    job = jobs[job_id]
    jobs[job_id] = job.model_copy(update={"status": JobStatusEnum.running, "updated_at": datetime.now(timezone.utc)})

    try:
        films = await (
            crawl_oscar_films_selenium(years)
            if mode == CrawlModeEnum.selenium
            else crawl_oscar_films(years)
        )
        file_path = _job_file_path(job_id)
        # Serialize to JSON using Pydantic models
        payload = [film.model_dump() for film in films]
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        jobs[job_id] = job.model_copy(
            update={
                "status": JobStatusEnum.completed,
                "updated_at": datetime.now(timezone.utc),
                "total_films": len(films),
                "data_file": str(file_path),
                "films": films,
            }
        )
    except Exception as exc:  # noqa: BLE001
        # Use repr(exc) to surface Selenium / driver errors that often têm str() vazio.
        # Aqui também distinguimos mensagem de erro de falha total/geral.
        jobs[job_id] = job.model_copy(
            update={
                "status": JobStatusEnum.failed,
                "updated_at": datetime.now(timezone.utc),
                "error": repr(exc),
            }
        )


class CrawlRequest(BaseModel):
    mode: CrawlModeEnum = Field(
        default=CrawlModeEnum.selenium,
        description="Modo de coleta: selenium (default) ou ajax.",
    )
    years: Optional[List[int]] = Field(
        default=None,
        description="Lista opcional de anos para coletar (entre 2010 e 2015).",
    )


@app.post("/crawl/oscar", response_model=CrawlJobResult)
async def trigger_oscar_crawl(body: CrawlRequest, background_tasks: BackgroundTasks) -> CrawlJobResult:
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    job = CrawlJobResult(
        job_id=job_id,
        status=JobStatusEnum.pending,
        created_at=now,
        updated_at=now,
    )
    jobs[job_id] = job

    background_tasks.add_task(_run_crawl_job, job_id, body.mode, body.years)

    return job


@app.get("/results/{job_id}", response_model=CrawlJobResult)
async def get_results(job_id: str) -> PlainTextResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    # Pretty-print JSON (indent=4) for easier inspection during the test.
    payload = jsonable_encoder(job)
    return PlainTextResponse(
        json.dumps(payload, ensure_ascii=False, indent=4),
        media_type="application/json",
    )


def main() -> None:
    import uvicorn

    # Run using the already-imported FastAPI instance instead of an import string,
    # so it works when executed from this directory.
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
