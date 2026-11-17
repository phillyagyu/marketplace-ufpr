# 5. Alternativas Arquiteturais e Trade-offs

Para a definição da arquitetura do **CampusHub**, foram analisadas três alternativas arquiteturais frente às restrições do projeto (**RES01 a RES05**) e aos Requisitos Arquiteturalmente Significativos (**ASR-01**: Modificabilidade de integrações externas; **ASR-02**: Consistência transacional e anti-overbooking; **ASR-03**: Testabilidade isolada e independência de banco de dados):

```text
Alternativa A : Monolito Simples em Camadas Acopladas (Transaction Script / Active Record)
Alternativa B : Arquitetura de Microsserviços Distribuídos
Alternativa C : Monolito Modular com Arquitetura Hexagonal (Ports & Adapters) [ESCOLHIDA]
```

Toda decisão arquitetural envolve *trade-offs*: priorizar um atributo de qualidade exige aceitar custos controlados em outra dimensão.

---

## 5.1 Matriz Comparativa de Alternativas e Critérios de Qualidade

| Critério Avaliado | Alternativa A: Monolito Simples (Acoplado) | Alternativa B: Microsserviços Distribuídos | Alternativa C: Monolito Modular + Hexagonal *(Escolhida)* |
| :--- | :---: | :---: | :---: |
| **Modificabilidade (ASR-01)** | `--` (Integrações e SQL misturados ao fluxo) | `++` (Serviços independentes) | `++` (Isolamento via *Ports & Adapters* / DIP) |
| **Consistência Transacional (ASR-02)** | `++` (Transação ACID local no mesmo banco) | `--` (Consistência eventual / Sagas distribuídas) | `++` (Transação ACID local + Modelo de Domínio Rico) |
| **Testabilidade (ASR-03)** | `--` (Exige banco real ativo para testar regras) | `-` (Testes de integração complexos entre serviços) | `++` (Testes em memória em milissegundos via Fakes) |
| **Desempenho (Latência)** | `++` (Chamadas em memória) | `-` (Overhead de serialização HTTP/gRPC e rede) | `++` (Chamadas em memória dentro do mesmo processo) |
| **Disponibilidade e Resiliência** | `0` (Ponto único de falha do processo) | `++` (Isolamento de falhas por serviço) | `+` (Transações atômicas locais sem falha parcial de rede) |
| **Complexidade Estrutural** | `++` (Estrutura inicial mínima) | `--` (Alta complexidade distribuída) | `0` (Moderada: exige interfaces e separação de pacotes) |
| **Implantação (RES05)** | `++` (Artefato único) | `--` (Múltiplos containers, broker e bancos) | `++` (Artefato único autocontido e executável localmente) |
| **Escalabilidade** | `-` (Escala apenas o bloco todo) | `++` (Escala cada serviço de forma independente) | `+` (Módulos desacoplados prontos para futura extração) |
| **Custo de Desenvolvimento e Operação** | `++` (Baixo no curto prazo, alto na manutenção) | `--` (Alto custo de infraestrutura e DevOps) | `+` (Equilíbrio ideal para o escopo acadêmico e evolução) |

*(Legenda: `++` Muito favorável | `+` Favorável | `0` Neutro | `-` Desfavorável | `--` Muito desfavorável)*

---

## 5.2 Análise das Alternativas e Relação com os ASRs

* **Alternativa A — Monolito Simples (Descartada):**
  * *Análise:* Apresenta o menor esforço inicial de codificação, mas concentra validações de negócio, queries SQL e chamadas de rede nos próprios controladores (*Controller Gordo* / *Transaction Script*).
  * *Por que não atende aos ASRs:* Viola frontalmente o **ASR-01** e o **ASR-03**. Substituir o envio de e-mail por WhatsApp ou trocar o SQLite pelo PostgreSQL exigiria alterar as classes que contêm a regra de contratação (violando SRP, OCP e DIP). Além disso, impede testes unitários rápidos da lógica de domínio sem banco de dados.
* **Alternativa B — Microsserviços (Descartada):**
  * *Análise:* Dividir o sistema em microsserviços independentes (`servico-catalogo`, `servico-contratacao`, `servico-notificacao`) proporcionaria escalabilidade independente, porém introduziria comunicação via rede entre a agenda de *slots* e o registro da contratação.
  * *Por que não atende aos ASRs e Restrições:* Prejudica diretamente o **ASR-02** (exigiria transações distribuídas ou consistência eventual com padrão *Saga* para evitar *overbooking* de horários) e viola a **RES05** (alto custo operacional e de implantação para o volume de usuários de um campus universitário).
* **Alternativa C — Monolito Modular com Arquitetura Hexagonal (Escolhida):**
  * *Análise:* Combina a simplicidade operacional e a consistência transacional em memória/ACID de um processo único (**ASR-02** e **RES05**) com o desacoplamento estrutural de **Ports & Adapters** (**ASR-01** e **ASR-03**).
  * *Trade-off assumido:* Aceitamos uma complexidade estrutural interna levemente superior (criação explícita de interfaces em `src/ports/` e adaptadores em `src/adapters/`) e a exigência de disciplina da equipe na direção das dependências em troca de altíssima testabilidade e facilidade de evolução.

---

# 9. Análise de Evolução Arquitetural

Em resposta direta à questão de evolução proposta na especificação do trabalho:

> **Se uma das principais tecnologias ou integrações utilizadas precisasse ser substituída, quais partes do sistema seriam afetadas?**

Graças à aplicação combinada de **Ports & Adapters (Arquitetura Hexagonal)**, **Inversão de Dependência (DIP - SOLID)** e **Protected Variations / Indirection (GRASP)**, mudanças tecnológicas ficam estritamente confinadas às bordas do sistema (`src/adapters/` e `src/main.py`), preservando 100% do núcleo de negócio (`src/domain/` e `src/application/`). Abaixo analisamos **três cenários concretos de evolução**:

---

### Cenário de Mudança 1: Substituição do Mecanismo de Persistência (`SQLite` $\rightarrow$ `PostgreSQL`)

* **Quais elementos seriam afetados:**
  1. Criação de duas novas classes adaptadoras em `src/adapters/outbound/`: `PostgresServicoRepository(ServicoRepository)` e `PostgresContratacaoRepository(ContratacaoRepository)` (utilizando `psycopg` ou `SQLAlchemy`).
  2. Alteração de 2 linhas no arquivo de composição (`src/main.py`) para instanciar e injetar os repositórios PostgreSQL no lugar dos repositórios SQLite.
* **Quais elementos permaneceriam inalterados:**
  * **100% da Camada de Domínio (`src/domain/`):** `MembroComunidade`, `Servico`, `SlotDisponibilidade`, `Contratacao`, `Avaliacao` e exceções de negócio.
  * **100% da Camada de Aplicação (`src/application/`):** `SolicitarContratacaoUseCase`, `ConsultarServicosUseCase` e `ConcluirEAvaliarUseCase`.
  * **100% das Portas (`src/ports/`):** As interfaces `ServicoRepository` e `ContratacaoRepository`.
  * **100% dos Adaptadores de Notificação e Entrada (`EmailNotificador`, `NotificadorFake`, `MarketplaceController`)** e toda a suíte de testes unitários em memória.
* **Que decisões arquiteturais ajudariam ou dificultariam a mudança:**
  * **Ajudam:** O uso do padrão **Repository** aliado ao **DIP (ADR-002)** e à modelagem de entidades de domínio puras (sem herança de ORM / *Active Record*) permite trocar o SGBD sem tocar em nenhuma regra de negócio.
  * **Dificultam (Custo controlado):** Como o domínio é puro, o desenvolvedor do novo adaptador precisará escrever o mapeamento de dados (*Data Mapper*) entre as tabelas do PostgreSQL e os objetos de domínio.

---

### Cenário de Mudança 2: Substituição do Serviço de Notificação (`E-mail SMTP` $\rightarrow$ `API de WhatsApp`)

* **Quais elementos seriam afetados:**
  1. Criação de uma única classe em `src/adapters/outbound/`: `WhatsAppNotificador(NotificadorPort)`, implementando o método `notificar(destinatario, assunto, mensagem)` via requisição HTTP para a API do WhatsApp.
  2. Substituição da instância injetada no bootstrap (`src/main.py`): de `EmailNotificador()` para `WhatsAppNotificador()`.
* **Quais elementos permaneceriam inalterados:**
  * **100% das Entidades de Domínio (`src/domain/`)** e **100% dos Casos de Uso (`src/application/`)**, incluindo o `SolicitarContratacaoUseCase` e o `ConcluirEAvaliarUseCase`.
  * **100% dos Repositórios de Persistência** (`Sqlite...` e `InMemory...`) e a porta `NotificadorPort`.
* **Que decisões arquiteturais ajudariam ou dificultariam a mudança:**
  * **Ajudam:** O isolamento de integrações externas via Porta de Saída (**ADR-003**, *Protected Variations* e **OCP - SOLID**) garante que o Caso de Uso dependa apenas da abstração `NotificadorPort`.
  * **Dificultam (Ponto de atenção):** Caso a API externa de WhatsApp apresente alta latência ou instabilidade, o contrato síncrono atual (`notificar()`) pode aumentar o tempo de resposta da contratação, podendo motivar no futuro um adaptador assíncrono com fila em background (sem precisar alterar a assinatura da porta `NotificadorPort`).

---

### Cenário de Mudança 3: Inclusão de Aplicativo Mobile ou Interface Web (`CLI` $\rightarrow$ `API REST com FastAPI/Flask`)

* **Quais elementos seriam afetados:**
  1. Criação de um novo adaptador primário (de entrada) em `src/adapters/inbound/` (ex: `MarketplaceRestController` com rotas HTTP `GET /servicos`, `POST /contratacoes`, `POST /contratacoes/{id}/avaliacao` que serializam JSON e invocam os Casos de Uso).
  2. Configuração do servidor ASGI/WSGI na inicialização (`src/main.py`) injetando as mesmas instâncias de `SolicitarContratacaoUseCase`, `ConsultarServicosUseCase` e `ConcluirEAvaliarUseCase`.
* **Quais elementos permaneceriam inalterados:**
  * **100% da Camada de Aplicação (`src/application/`)** e **100% da Camada de Domínio (`src/domain/`)** — todas as regras de anti-overbooking (**RES02**), proibição de auto-contratação (**RES01**) e validação de avaliações (**RES03**) são reaproveitadas integralmente sem duplicação de código.
  * **100% da Camada de Portas (`src/ports/`) e Adaptadores de Saída (`src/adapters/outbound/`)**, bem como o próprio `MarketplaceController` via CLI (que pode coexistir com a API REST).
* **Que decisões arquiteturais ajudariam ou dificultariam a mudança:**
  * **Ajudam:** A separação estrita da **Arquitetura Hexagonal (ADR-001)** e o padrão **Controller (GRASP)**: os Casos de Uso na camada de Aplicação funcionam como uma fronteira de API agnóstica de protocolo de transporte (não retornam HTML nem códigos de status HTTP, mas sim objetos de domínio e exceções semânticas como `SlotIndisponivelError`, facilmente convertidas pelo adaptador REST em `HTTP 409 Conflict` ou `HTTP 422 Unprocessable Entity`).
