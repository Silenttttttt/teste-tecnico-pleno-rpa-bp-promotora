## Crawler Oscar

Pequeno serviço responsável por **coletar os filmes do Oscar** diretamente da página:

`https://www.scrapethissite.com/pages/ajax-javascript/`

### Visão geral

- **`main.py`**  
  - CLI principal do crawler.  
  - **Selenium é o modo padrão**: sem flags, usa o `selenium_crawler.py` internamente.  
  - Modo alternativo **AJAX direto** (`httpx + asyncio`) apenas quando passado `--mode ajax`.  

- **`selenium_crawler.py`**  
  - Implementa o crawler em modo **Selenium** (utilizado também pela API).  
  - Fluxo:
    1. Abre a página do Oscar.  
    2. Descobre dinamicamente os anos via links `.year-link`.  
    3. Clica no ano ativo para disparar o `fetchFilms(year)` (tabela é populada via AJAX).  
    4. Usa `asyncio.to_thread` para abrir drivers em paralelo e clicar nos demais anos.  
    5. Lê a tabela renderizada no DOM (`.film-title`, `.film-nominations`, `.film-awards`, `.film-best-picture`).  
  - Persiste o resultado em `data/oscar_selenium.json` quando executado diretamente (via `main()`).

### Como rodar (modo CLI)

Pré-requisitos (no diretório raiz do projeto):

- Ativar o ambiente (Nix + direnv ou venv com dependências instaladas).

#### Execução padrão (Selenium)

```bash
cd app/crawler-oscar
python main.py
```

Saída:

- Log no terminal com a quantidade de filmes coletados.  
- Arquivo `data/oscar_selenium_cli.json` com a lista de filmes.

#### Execução em modo AJAX (explícito)

```bash
cd app/crawler-oscar
python main.py --mode ajax
```

Saída:

- Log no terminal com a quantidade de filmes coletados.  
- Arquivo `data/oscar_ajax_cli.json` com a lista de filmes.

### Observações técnicas

- **Paralelismo**:  
  - Ambos os modos usam `asyncio` para coletar múltiplos anos em paralelo.  
- **Validação**:  
  - `OscarFilm` usa Pydantic e normaliza o `title` (remove espaços extras).  
- **Selenium / Chrome**:  
  - O caminho do Chrome e do Chromedriver é resolvido via:
    - Variáveis de ambiente (`CHROME_EXECUTABLE_PATH`, `CHROMEDRIVER_PATH`) ou  
    - Selenium Manager (`chromedriver` no PATH).  

## Crawler Oscar

Pequeno serviço responsável por **coletar os filmes do Oscar** diretamente da página:

`https://www.scrapethissite.com/pages/ajax-javascript/`

### Visão geral

- **`main.py`**  
  - Implementa o crawler em modo **AJAX direto** usando `httpx + asyncio`.  
  - Faz chamadas paralelas para cada ano disponível (2010–2015) usando `?ajax=true&year=YYYY`.  
  - Usa o modelo `OscarFilm` (Pydantic) para validar `title`, `year`, `nominations`, `awards`, `best_picture`.  
  - Persiste o resultado em `data/oscar_cli.json`.

- **`selenium_crawler.py`**  
  - Implementa o crawler em modo **Selenium** (utilizado pela API e também executável via `main()` aqui).  
  - Fluxo:
    1. Abre a página do Oscar.  
    2. Descobre dinamicamente os anos via links `.year-link`.  
    3. Clica no ano ativo para disparar o `fetchFilms(year)` (tabela é populada via AJAX).  
    4. Usa `asyncio.to_thread` para abrir drivers em paralelo e clicar nos demais anos.  
    5. Lê a tabela renderizada no DOM (`.film-title`, `.film-nominations`, `.film-awards`, `.film-best-picture`).  
  - Persiste o resultado em `data/oscar_selenium.json`.

### Como rodar (modo CLI)

Pré-requisitos (no diretório raiz do projeto):

- Ativar o ambiente (Nix + direnv ou venv com dependências instaladas).

#### Modo AJAX (rápido, sem Selenium)

```bash
cd app/crawler-oscar
python main.py
```

Saída:

- Log no terminal com a quantidade de filmes coletados.  
- Arquivo `data/oscar_cli.json` com a lista de filmes.

#### Modo Selenium (mesma lógica usada pela API)

```bash
cd app/crawler-oscar
python selenium_crawler.py
```

Saída:

- Log no terminal com a quantidade de filmes coletados.  
- Arquivo `data/oscar_selenium.json` com a lista de filmes.

### Observações técnicas

- **Paralelismo**:  
  - Ambos os modos usam `asyncio` para coletar múltiplos anos em paralelo.  
- **Validação**:  
  - `OscarFilm` usa Pydantic e normaliza o `title` (remove espaços extras).  
- **Selenium / Chrome**:  
  - O caminho do Chrome e do Chromedriver é resolvido via:
    - Variáveis de ambiente (`CHROME_EXECUTABLE_PATH`, `CHROMEDRIVER_PATH`) ou  
    - Selenium Manager (`chromedriver` no PATH).  

