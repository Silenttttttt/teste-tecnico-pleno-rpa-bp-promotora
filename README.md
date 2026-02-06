# Teste Técnico - Desenvolvedor Pleno RPA

## Contexto

Você foi contratado para desenvolver um sistema de coleta de dados que extrai informações de uma fonte web e as disponibiliza via API REST.

## Objetivo

Construir uma aplicação que:

1. Colete dados do site Oscar Winning Films
2. Exponha os resultados via API REST
3. Persista os dados coletados em arquivos estruturados (JSON)
4. Utilize paralelismo para otimizar a coleta

---

## Site Alvo

### Oscar Winning Films

**URL:** https://www.scrapethissite.com/pages/ajax-javascript/

**Características:** Página dinâmica que carrega dados via JavaScript

**Dados a coletar:**
- Title
- Nominations
- Awards
- Best Picture (boolean)

---

## Requisitos Técnicos

### Obrigatórios

| Requisito | Descrição |
|-----------|-----------|
| **Selenium** | Deve estar disponível para automação quando necessário |
| **asyncio** | Implementar paralelismo com asyncio para otimizar a coleta |
| **Pydantic** | Validar e tipar todos os dados coletados com Pydantic models |
| **FastAPI** | Expor endpoints REST para trigger e consulta |
| **Persistência** | Salvar resultados em arquivos JSON no volume `./data` |

### Endpoints da API

```
POST /crawl/oscar      → Executa coleta do Oscar Films
GET  /results/{job_id} → Retorna resultados de um job
```

---

## Critérios de Avaliação

| Critério | Peso |
|----------|------|
| **Análise e estratégia** | Alto - Escolha inteligente da abordagem de coleta |
| **Qualidade do código** | Alto - Organização, legibilidade, boas práticas |
| **Funcionamento** | Alto - A solução deve funcionar corretamente |
| **Uso adequado das ferramentas** | Médio - Selenium, asyncio, Pydantic, FastAPI |
| **Tratamento de erros** | Médio - Robustez e resiliência |
| **Documentação** | Baixo |

---

## Ambiente de Desenvolvimento

### Nix + direnv (Obrigatório - Linux)

#### 1. Instalar Nix

```bash
sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install) --daemon
```

#### 2. Habilitar Flakes

Adicione ao `~/.config/nix/nix.conf`:

```
experimental-features = nix-command flakes
```

#### 3. Instalar direnv

Use o gerenciador de pacotes da sua distro:

```bash
# Debian/Ubuntu
sudo apt install direnv

# Fedora
sudo dnf install direnv

# Arch
sudo pacman -S direnv
```

Adicione ao seu shell (`~/.bashrc` ou `~/.zshrc`):

```bash
eval "$(direnv hook bash)"  # ou zsh
```

#### 4. Rodar

O `.envrc` e `flake.nix` já vêm prontos no repositório. Basta permitir o direnv e o ambiente será carregado automaticamente:

```bash
direnv allow
```

Commite o `flake.lock` no seu repositório.

---

## Regras

1. **Entrega:** Fork deste repositório
2. **Dúvidas:** Envie por email - ti@bpcreditos.com.br | gabrielpelizzaro@gmail.com ou entre em contato no whatsapp do Gabriel

---

**Queremos ver como você pensa, não apenas como você escreve código.**

---

## Solução implementada

### Visão geral

- **Serviço `crawler-oscar` (CLI)**  
  - Responsável por **coletar os filmes do Oscar** direto da página `https://www.scrapethissite.com/pages/ajax-javascript/`.  
  - **Modo padrão: Selenium**  
    - Usa um único módulo `selenium_crawler.py` como **fonte única da lógica Selenium**.  
    - Abre a página, descobre dinamicamente os anos disponíveis via links `.year-link`, clica no ano ativo e lê a tabela renderizada no DOM (`.film-title`, `.film-nominations`, `.film-awards`, `.film-best-picture`).  
    - Usa `asyncio.to_thread` + semáforos para abrir drivers em paralelo para os demais anos (paralelismo mesmo com Selenium).  
    - Persiste o resultado em `./data/oscar_selenium_cli.json`.  
  - **Modo alternativo: AJAX** (explícito via flag `--mode ajax`)  
    - Usa `httpx + asyncio` para chamar o endpoint AJAX (`?ajax=true&year=YYYY`) em paralelo para cada ano.  
    - Usa Pydantic (`OscarFilm`) para validar/normalizar os dados (inclui strip de espaços em `title`).  
    - Persiste o resultado em `./data/oscar_ajax_cli.json`.  

- **Serviço `crawler-api` (FastAPI)**  
  - Exposto em `http://localhost:8000` (ver detalhes em `app/crawler-api/README.md`).  
  - **Endpoints principais**:  
    - `POST /crawl/oscar` → dispara um job assíncrono de coleta.  
    - `GET /results/{job_id}` → retorna o status e os resultados do job (com os filmes embutidos e JSON **indentado em 4 espaços** para facilitar a leitura).  
  - **Modo padrão da API: Selenium**  
    - A API carrega dinamicamente o mesmo `selenium_crawler.py` do `crawler-oscar` via `importlib.util`, garantindo **uma única implementação Selenium** para CLI e API.  
  - **Modo alternativo: AJAX** (`mode="ajax"` no corpo da requisição)  
    - Coleta todos os anos com `asyncio.gather`, usando `return_exceptions=True` para distinguir **falha total vs. parcial**.  
    - Implementa **retry com backoff leve** em cada requisição AJAX (até 3 tentativas) para maior robustez a falhas de rede/timeout.  
  - Os resultados de cada job são salvos em `./data/oscar_<job_id>.json` e também mantidos em memória na estrutura `CrawlJobResult` (Pydantic).  

### Tecnologias e requisitos atendidos

- **Selenium**  
  - É o **método padrão** de coleta tanto na CLI quanto na API.  
  - Interage diretamente com o DOM (cliques em anos, leitura da tabela renderizada).  
  - Driver configurado para rodar em modo headless, usando variáveis de ambiente (`CHROME_EXECUTABLE_PATH`, `CHROMEDRIVER_PATH`) ou Selenium Manager.

- **asyncio**  
  - Usado para paralelizar chamadas AJAX (`httpx.AsyncClient` + `asyncio.gather`).  
  - Usado com `asyncio.to_thread` + semáforos para rodar múltiplas instâncias de Selenium em paralelo sem bloquear o event loop.

- **Pydantic**  
  - Modelos `OscarFilm`, `CrawlRequest`, `CrawlJobResult` tipam e validam todos os dados coletados e retornados.  
  - Normalização de título (`strip()`), campos de datas em UTC (`datetime.now(timezone.utc)`).

- **FastAPI**  
  - Implementa os endpoints `POST /crawl/oscar` e `GET /results/{job_id}` usando `BackgroundTasks` para não bloquear o request inicial.  
  - O `GET /results/{job_id}` devolve o JSON **já pretty-printed** (`indent=4`) conforme solicitado.

- **Persistência**  
  - Todos os resultados são salvos em arquivos JSON dentro de `./data`, usado como volume compartilhado (também referenciado no `docker-compose.yml`).  

### Como rodar (resumo)

- **Ambiente**  
  - Ativar Nix + direnv na raiz:  
    - `direnv allow`

- **CLI (crawler-oscar)**  
  - Selenium (padrão):  
    - `cd app/crawler-oscar`  
    - `python main.py`  
  - AJAX explícito:  
    - `cd app/crawler-oscar`  
    - `python main.py --mode ajax`

- **API (crawler-api)**  
  - `cd app/crawler-api`  
  - `python main.py`  
  - Teste automatizado rápido via script na raiz:  
    - `./run_oscar_api_test.sh`  

Para detalhes mais finos de uso e exemplos de requisição/resposta, veja os READMEs específicos em `app/crawler-oscar/README.md` e `app/crawler-api/README.md`.
