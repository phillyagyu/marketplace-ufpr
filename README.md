# Trabalho Final — Design e Arquitetura de Software (2026-2)

## CampusHub — Marketplace de Serviços dentro do Campus (Tema 11)

Plataforma para que membros da comunidade universitária (estudantes, docentes e técnicos) ofereçam e solicitem serviços especializados no campus, com controle estrito de disponibilidade de horários (*slots*), contratação sem *overbooking*, registro de conclusão e avaliação de reputação.

### Integrantes do Grupo
* Eloiza Sthefanny Rocha da Silva Cardoso
* Helen Kaori Iijima
* Mateus Augusto Godoy De Oliveira
* Phillip Yagyu Moribayashi

---

## Resposta à Questão Central do Trabalho

> **"Como este sistema deve ser organizado para atender aos requisitos atuais e permitir sua evolução sem gerar dependências desnecessárias?"**

O **CampusHub** é organizado como um **Monolito Modular em Camadas combinado com o padrão *Ports & Adapters* (Arquitetura Hexagonal Simplificada)** e um **Modelo de Domínio Rico (*Rich Domain Model*)**, guiado pelo **Princípio da Inversão de Dependência (DIP - SOLID)** e pelos padrões **GRASP** (*Information Expert, Creator, Controller, Pure Fabrication, Indirection e Protected Variations*):

1. **Núcleo de Negócio Blindado (`src/domain/`):** As regras críticas do marketplace — proibição de auto-contratação (**RES01**), reserva exclusiva de horário sem *overbooking* (**RES02 / ASR-02**) e integridade de avaliações (**RES03**) — vivem encapsuladas dentro das próprias entidades de domínio (`Servico`, `SlotDisponibilidade`, `Contratacao`, `Avaliacao`), sem nenhum *import* de banco de dados, framework web ou biblioteca de rede.
2. **Orquestração Desacoplada por Contratos (`src/application/` e `src/ports/`):** Os Casos de Uso (`SolicitarContratacaoUseCase`, `ConsultarServicosUseCase`, `ConcluirEAvaliarUseCase`) coordenam o fluxo transacional dependendo **exclusivamente de interfaces abstratas** (`ServicoRepository`, `ContratacaoRepository`, `NotificadorPort`).
3. **Infraestrutura Plugável nas Bordas (`src/adapters/`):** Detalhes tecnológicos voláteis — como persistência em `SQLite` vs. `InMemory` (**ASR-03**) e envio de notificações via `EmailNotificador` vs. `NotificadorFake` ou futuro `WhatsAppNotificador` (**ASR-01**) — são implementados como adaptadores secundários que apontam para dentro e são injetados apenas no ponto de inicialização (`src/main.py`). Assim, o sistema atende com consistência transacional local aos requisitos atuais e permite substituir bancos de dados, canais de notificação ou interfaces de usuário sem alterar nenhuma linha do domínio ou dos casos de uso.

---

## Sumário da Documentação e Artefatos

Toda a documentação foi estruturada para manter rastreabilidade ponta a ponta entre requisitos, ASRs, decisões de design, modelos UML e código:

| Seção do Edital | Documento / Artefato | Conteúdo Principal |
| :--- | :--- | :--- |
| **1. Problema, Requisitos e ASRs** | [`docs/requisitos.md`](docs/requisitos.md) | Contexto do Tema 11, 4 Atores, 8 Requisitos Funcionais (RF01–RF08), 5 Restrições (RES01–RES05), 3 ASRs concretos (ASR-01 a ASR-03) e tabela de influência arquitetural. |
| **2. Modelo de Domínio e Design** | [`docs/arquitetura.md` (Seção 2)](docs/arquitetura.md#2-modelo-de-domínio-e-distribuição-de-responsabilidades) | Responsabilidades das classes, justificativas **GRASP**, análise de coesão/acoplamento e aplicação dos 5 princípios **SOLID**. |
| **3. Modelagem UML e Consistência** | [`docs/diagramas.md`](docs/diagramas.md) | Justificativas de design e verificação de consistência entre os 4 diagramas UML obrigatórios:<ul><li>Diagrama de Classes: [`docs/diagramas/classes.puml`](docs/diagramas/classes.puml)</li><li>Diagrama de Sequência: [`docs/diagramas/sequencia.puml`](docs/diagramas/sequencia.puml)</li><li>Diagrama de Comunicação: [`docs/diagramas/comunicacao.puml`](docs/diagramas/comunicacao.puml)</li><li>Diagrama de Componentes: [`docs/diagramas/componentes.puml`](docs/diagramas/componentes.puml)</li></ul> |
| **4. Proposta Arquitetural** | [`docs/arquitetura.md` (Seção 4)](docs/arquitetura.md#4-proposta-arquitetural) | Explicitação do estilo arquitetural, componentes, regra de direção de dependências, persistência transacional, integração externa e contratos de API. |
| **5. Alternativas e Trade-offs** | [`docs/tradeoffs.md` (Seção 5)](docs/tradeoffs.md#5-alternativas-arquiteturais-e-trade-offs) | Matriz comparativa entre Monolito Simples, Microsserviços e Monolito Modular Hexagonal frente aos atributos de qualidade e ASRs. |
| **6. Registros de Decisão (ADRs)** | [`docs/adr/ADR-001.md`](docs/adr/ADR-001.md)<br>[`docs/adr/ADR-002.md`](docs/adr/ADR-002.md)<br>[`docs/adr/ADR-003.md`](docs/adr/ADR-003.md) | **ADR-001:** Monolito Modular com Arquitetura Hexagonal<br>**ADR-002:** Modelo de Domínio Rico e Padrão Repository<br>**ADR-003:** Isolamento de Integrações Externas via `NotificadorPort` |
| **9. Análise de Evolução** | [`docs/tradeoffs.md` (Seção 9)](docs/tradeoffs.md#9-análise-de-evolução-arquitetural) | Análise de impacto detalhada para 3 cenários de mudança:1. `SQLite` $\rightarrow$ `PostgreSQL`2. `E-mail SMTP` $\rightarrow$ `WhatsApp API`3. `CLI` $\rightarrow$ `API REST / Aplicativo Mobile` |

---

## Estrutura do Repositório

```text
marketplace-ufpr/
├── README.md                        # Visão geral, resposta à questão central e índice
├── docs/
│   ├── requisitos.md                # Seção 1: Contexto, Atores, RFs, Restrições e ASRs
│   ├── arquitetura.md               # Seções 2 e 4: Domínio, GRASP, SOLID e Proposta Arquitetural
│   ├── diagramas.md                 # Seção 3: Explicação e consistência da Modelagem UML
│   ├── tradeoffs.md                 # Seções 5 e 9: Alternativas, Trade-offs e Análise de Evolução
│   ├── adr/
│   │   ├── ADR-001.md               # Decisão: Monolito Modular com Arquitetura Hexagonal
│   │   ├── ADR-002.md               # Decisão: Modelo de Domínio Rico e Padrão Repository
│   │   └── ADR-003.md               # Decisão: Isolamento de Notificações via Porta de Saída
│   └── diagramas/
│       ├── classes.puml             # Diagrama de Classes (Domínio, Portas, Casos de Uso e Adaptadores)
│       ├── sequencia.puml           # Diagrama de Sequência (Solicitar Contratação e Fluxos de Erro)
│       ├── comunicacao.puml         # Diagrama de Comunicação (Colaboração de Instâncias)
│       └── componentes.puml         # Diagrama de Componentes (Arquitetura Hexagonal / DIP)
└── src/
    ├── domain/                      # Núcleo de Domínio Rico (Entidades, Enums e Exceções)
    ├── ports/                       # Portas de Saída abstratas (Repositories e NotificadorPort)
    ├── application/                 # Casos de Uso (Coordenação transacional da fatia vertical)
    ├── adapters/                    # Adaptadores Primários (CLI) e Secundários (SQLite, InMemory, Email, Fake)
    └── main.py                      # Composition Root e Demonstração Executável da Fatia Vertical
```
