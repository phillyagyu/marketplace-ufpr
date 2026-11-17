---

### Divisão da Implementação entre os 4 Integrantes

```text
src/
├── domain/                         --> [1. Eloiza] (JÁ FEITO na main!)
│   ├── entidades.py
│   └── excecoes.py
├── ports/                          --> [2. Helen]  (JÁ FEITO na branch origin/helen!)
│   └── interfaces.py
├── application/                    --> [2. Helen]  (JÁ FEITO na branch origin/helen!)
│   └── casos_de_uso.py
├── adapters/
│   ├── inbound/
│   │   └── cli_controller.py       --> [4. Phillip] (Controlador de Entrada CLI)
│   └── outbound/
│       ├── memoria_repositorios.py --> [1. Eloiza]  (Repositórios InMemory)
│       ├── notificadores.py        --> [3. Mateus]  (EmailNotificador + NotificadorFake)
│       └── sqlite_repositorios.py  --> [3. Mateus]  (SqliteServicoRepo + SqliteContratacaoRepo)
├── main.py                         --> [4. Phillip] (Bootstrap / Roteiro da Fatia Vertical)
└── tests/
    └── test_marketplace.py         --> [2. Helen ou 4. Phillip] (Testes Automatizados)
```

---

### Detalhamento do que cada um faz (com nomes exatos dos diagramas)

#### 1. Eloiza — Domínio Rico + Repositórios em Memória (`ASR-02` e `ASR-03`)
* **O que já está pronto na `main`:**
  * [src/domain/entidades.py](file:///c:/Users/amate/workspace/marketplace-ufpr/src/domain/entidades.py) (`MembroComunidade`, `Servico`, `SlotDisponibilidade`, `Contratacao`, `Avaliacao`, `StatusSlot`, `StatusContratacao`).
  * [src/domain/excecoes.py](file:///c:/Users/amate/workspace/marketplace-ufpr/src/domain/excecoes.py) (`ErroDominio`, `AutoContratacaoError`, `SlotIndisponivelError`, `TransicaoEstadoInvalidaError`, `NotaInvalidaError`).
* **O que falta codificar (~40 linhas):**
  * Criar `src/adapters/outbound/memoria_repositorios.py` implementando `InMemoryServicoRepository(ServicoRepository)` e `InMemoryContratacaoRepository(ContratacaoRepository)` usando dicionários em memória (`self.servicos = {}` e `self.contratacoes = {}`).

---

#### 2. Helen — Portas de Saída (`ports`) + Casos de Uso (`application`)
* **O que já está pronto na branch `origin/helen` (commit `cc817d4`):**
  * `src/ports/interfaces.py` (`ServicoRepository`, `ContratacaoRepository`, `NotificadorPort`).
  * `SolicitarContratacaoUseCase`, `ConsultarServicosUseCase` e `ConcluirEAvaliarUseCase`.
* **O que falta ajustar (2 minutos):**
  * Na branch `origin/helen`, a pasta foi chamada de `src/aplicacao/`. Basta **renomear a pasta para `src/application/casos_de_uso.py`** para ficar 100% idêntica aos diagramas UML e ao `arquitetura.md`, e fazer o merge na `main`!
  * *(Opcional para equilibrar carga)*: Criar os testes unitários em `tests/test_marketplace.py` testando os 3 casos de uso dela com os repositórios em memória.

---

#### 3. Mateus — Adaptadores Secundários: Dependência Externa e Persistência SQLite (`Seções 7 e 8`)
Responsável por provar na prática a **Arquitetura Hexagonal** e o **DIP (SOLID)**:
* **Arquivo 1 (`src/adapters/outbound/notificadores.py`):**
  * Implementar `EmailNotificador(NotificadorPort)`: recebe `servidor_smtp: str = "smtp.ufpr.br"` no `__init__` e implementa `notificar(destinatario, assunto, mensagem)` imprimindo/simulando o despacho SMTP.
  * Implementar `NotificadorFake(NotificadorPort)`: mantém a lista `self.mensagens_enviadas: list[dict] = []` e, ao chamar `notificar(...)`, salva um dicionário `{"destinatario": ..., "assunto": ..., "mensagem": ...}` na lista (para os testes inspecionarem).
* **Arquivo 2 (`src/adapters/outbound/sqlite_repositorios.py`):**
  * Implementar `SqliteServicoRepository(ServicoRepository)` e `SqliteContratacaoRepository(ContratacaoRepository)` usando `import sqlite3` nativo do Python (sem precisar instalar nada externo), criando as tabelas `servicos`, `slots`, `contratacoes` e `avaliacoes` e persistindo com `with self.conn:`.

---

#### 4. Phillip — Adaptador de Entrada (`MarketplaceController`) + Protótipo Executável (`main.py`)
Responsável por fechar a **Fatia Vertical Executável (Seção 7 do PDF)**:
* **Arquivo 1 (`src/adapters/inbound/cli_controller.py`):**
  * Implementar a classe `MarketplaceController`, que recebe os casos de uso no construtor e expõe métodos como `listar_servicos_disponiveis()`, `solicitar_contratacao(servico_id, slot_id, solicitante_id)` (capturando `ErroDominio` para exibir mensagens amigáveis sem quebrar o programa), `concluir_servico(contratacao_id)` e `avaliar_servico(contratacao_id, nota, comentario)`.
* **Arquivo 2 ([src/main.py](file:///c:/Users/amate/workspace/marketplace-ufpr/src/main.py) — *Composition Root*):**
  * Conecta todas as peças (instancia o banco SQLite, o `EmailNotificador`/`NotificadorFake`, os `UseCases` e o `MarketplaceController`) e roda automaticamente uma demonstração clara no terminal com os **5 itens obrigatórios da Seção 7 do PDF**:
    1. **Consulta:** Lista os serviços e horários livres no campus;
    2. **Caso de uso que modifica estado + Persistência + Dependência Externa:** Realiza uma contratação válida, grava no SQLite e dispara a notificação;
    3. **Fluxo de Erro 1 (RES01):** Tenta fazer auto-contratação e mostra o bloqueio `AutoContratacaoError`;
    4. **Fluxo de Erro 2 (RES02 / ASR-02):** Tenta contratar o mesmo *slot* já reservado e mostra o bloqueio `SlotIndisponivelError` (anti-overbooking);
    5. **Ciclo completo:** Conclui a contratação e registra uma avaliação nota 5.

---

### Ordem ideal de Merge para ninguém travar ninguém:
1. **Passo 1 (Base de Contratos):** Fazer o merge da branch da **Helen** (`src/ports/` + `src/application/`) na `main` (já que o `src/domain/` da **Eloiza** já está na `main`).
2. **Passo 2 (Paralelo):** Com `domain`, `ports` e `application` na `main`, **Eloiza**, **Mateus** e **Phillip** criam seus arquivos em `src/adapters/`, `src/main.py` e `tests/` sem tocar nos arquivos uns dos outros.