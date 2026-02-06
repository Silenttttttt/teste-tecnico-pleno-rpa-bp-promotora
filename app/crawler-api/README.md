## Crawler API

Serviço FastAPI responsável por **expor a coleta de filmes do Oscar via HTTP**.

### Endpoints

- **`POST /crawl/oscar`**
  - Dispara um **job assíncrono** de coleta.
  - Corpo (`application/json`):
    ```json
    {
      "mode": "selenium",
      "years": [2010, 2011, 2012]
    }
    ```
  - Campos:
    - `mode` (opcional, default = `"selenium"`):  
      - `"selenium"` → usa o crawler em `app/crawler-oscar/selenium_crawler.py` (**padrão; não há fallback automático para AJAX**).  
      - `"ajax"` → usa o crawler direto por HTTP (`httpx + asyncio`), apenas quando especificado.  
    - `years` (opcional): anos específicos a coletar; se omitido, descobre dinamicamente (Selenium) ou usa o range padrão (AJAX).
  - Resposta (`CrawlJobResult`):
    - `job_id`, `status` (`pending` | `running` | `completed` | `failed`),  
    - timestamps, `total_films`, `data_file`, `error`, `films` (inicialmente `null`).

- **`GET /results/{job_id}`**
  - Retorna o estado atual do job.
  - Quando `status = "completed"`:
    - `total_films` (esperado 87 no caso padrão),  
    - `data_file` (ex.: `data/oscar_<job_id>.json`),  
    - `films`: lista completa de filmes (`OscarFilm`).
  - JSON é retornado com indentação (`indent=4`) para facilitar leitura em `curl`.

### Como rodar localmente

Pré-requisitos (no diretório raiz do projeto):

- Ativar ambiente (Nix + direnv ou venv com dependências instaladas).

#### Rodar o servidor

```bash
cd app/crawler-api
python main.py
```

Servidor sobe em `http://localhost:8000`.

#### Disparar um crawl (modo Selenium padrão)

```bash
curl -X POST http://localhost:8000/crawl/oscar \
  -H "Content-Type: application/json" \
  -d '{}'
```

Guardar o `job_id` retornado.

#### Consultar resultado

```bash
curl http://localhost:8000/results/<job_id>
```

Quando `status` virar `"completed"`, o JSON conterá:

- `total_films = 87`  
- `data_file = "data/oscar_<job_id>.json"`  
- `films = [...]` (lista de filmes)

#### Script de teste automatizado

Na raiz do projeto:

```bash
./run_oscar_api_test.sh
```

O script:

1. Sobe o servidor API.  
2. Faz `POST /crawl/oscar`.  
3. Faz polling em `GET /results/{job_id}` até `status` ser `"completed"` ou `"failed"`.  
4. Imprime a resposta final e derruba o servidor.

### Notas de implementação

- **Selenium + asyncio**:
  - A API delega para `crawler-oscar/selenium_crawler.py`, que:
    - Descobre anos com Selenium via `.year-link`.  
    - Clica no ano ativo para disparar o AJAX da página.  
    - Abre drivers em paralelo (`asyncio.to_thread`) para os demais anos.  
- **Validação**:
  - Modelos Pydantic (`OscarFilm`, `CrawlJobResult`, `CrawlRequest`) garantem tipos corretos e normalização do título.
- **Persistência**:
  - Todos os arquivos JSON são salvos em `./data`, que é montado como volume no `docker-compose`.  

