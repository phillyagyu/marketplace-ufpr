# 2. Modelo de Domínio e Distribuição de Responsabilidades

O núcleo do **CampusHub** foi modelado segundo a abordagem de **Modelo de Domínio Rico** (*Rich Domain Model*), evitando o antipadrão de Modelo Anêmico. As regras de negócio críticas como proibição de auto-contratação, verificação de disponibilidade de horário, bloqueio de *slot* e validação de avaliação estão encapsuladas diretamente nas entidades de domínio, enquanto os Casos de Uso (Camada de Aplicação) atuam apenas como coordenadores de fluxo.

---

## 2.1 Principais Classes, Conceitos e Responsabilidades

### Camada de Domínio (`src/domain/`)
| Classe / Enum | Tipo | Atributos Principais | Responsabilidades e Métodos de Negócio |
| :--- | :--- | :--- | :--- |
| **`MembroComunidade`** | Entidade | `id: str`, `nome: str`, `email: str`, `registro_academico: str` | Representa qualquer ator universitário (aluno, técnico ou docente) apto a oferecer ou contratar serviços no campus. |
| **`Servico`** | Entidade (Raiz de Agregado) | `id: str`, `prestador_id: str`, `titulo: str`, `descricao: str`, `categoria: str`, `valor: float`, `slots: list[SlotDisponibilidade]` | Mantém os dados da oferta, gerencia sua lista de horários (`adicionar_slot()`, `obter_slots_livres()`) e valida se um solicitante pode contratá-lo (`validar_contratante(solicitante_id)`). |
| **`SlotDisponibilidade`** | Entidade Interna | `id: str`, `servico_id: str`, `inicio: datetime`, `fim: datetime`, `status: StatusSlot` | Controla o estado da janela de horário (`LIVRE` ou `RESERVADO`). Possui os métodos de proteção de invariante `esta_livre() -> bool`, `reservar() -> None` e `liberar() -> None`. |
| **`Contratacao`** | Entidade (Raiz de Agregado) | `id: str`, `servico_id: str`, `slot_id: str`, `solicitante_id: str`, `prestador_id: str`, `status: StatusContratacao`, `criado_em: datetime`, `avaliacao: Optional[Avaliacao]` | Governa o ciclo de vida do contrato (`CONFIRMADA`, `CANCELADA`, `CONCLUIDA`). Responsável por `concluir()`, `cancelar()` e pela criação segura de avaliações via `registrar_avaliacao(nota, comentario)`. |
| **`Avaliacao`** | Objeto de Valor / Entidade | `id: str`, `contratacao_id: str`, `nota: int`, `comentario: str`, `data: datetime` | Valida em sua própria construção a invariante `1 <= nota <= 5` e comentário não vazio, garantindo que nunca exista uma avaliação inválida em memória. |
| **`ErroDominio`** *(e subclasses)* | Exceções de Domínio | `mensagem: str` | Hierarquia de exceções de negócio: `AutoContratacaoError`, `SlotIndisponivelError`, `TransicaoEstadoInvalidaError` e `NotaInvalidaError`. |

### Camada de Portas / Interfaces (`src/ports/`)
| Interface (ABC Python) | Tipo | Métodos Definidos | Responsabilidade Arquitetural |
| :--- | :--- | :--- | :--- |
| **`ServicoRepository`** | *Outbound Port* | `salvar(servico)`, `buscar_por_id(id)`, `listar_disponiveis()` | Contrato abstrato para persistência e consulta de ofertas de serviços e seus *slots*. |
| **`ContratacaoRepository`** | *Outbound Port* | `salvar(contratacao)`, `buscar_por_id(id)`, `listar_por_usuario(usuario_id)` | Contrato abstrato para persistência transacional de contratações e avaliações. |
| **`NotificadorPort`** | *Outbound Port* | `notificar(destinatario: str, assunto: str, mensagem: str) -> None` | Contrato abstrato para disparo de avisos externos (E-mail, WhatsApp ou Fake em testes). |

### Camada de Aplicação / Casos de Uso (`src/application/`)
| Classe | Tipo | Dependências Injetadas (Construtor) | Responsabilidades |
| :--- | :--- | :--- | :--- |
| **`SolicitarContratacaoUseCase`** | Caso de Uso (*Application Service*) | `servico_repo: ServicoRepository`, `contratacao_repo: ContratacaoRepository`, `notificador: NotificadorPort` | Coordena a fatia vertical de mutação: recupera `Servico` e `Slot`, aciona as validações de domínio, reserva o *slot*, instancia e persiste a `Contratacao` e dispara a notificação. |
| **`ConsultarServicosUseCase`** | Caso de Uso (*Query*) | `servico_repo: ServicoRepository` | Recupera e filtra os serviços com *slots* disponíveis para exibição ao solicitante. |
| **`ConcluirEAvaliarUseCase`** | Caso de Uso | `contratacao_repo: ContratacaoRepository`, `notificador: NotificadorPort` | Orquestra a conclusão do serviço e o registro da avaliação vinculada. |

---

## 2.2 Justificativas de Design baseadas em GRASP

1. **Information Expert (Especialista na Informação):**
   * *Onde foi aplicado:* Nas classes `SlotDisponibilidade`, `Servico` e `Contratacao`.
   * *Justificativa:* Quem possui o atributo `status` do horário é `SlotDisponibilidade`, logo, o método `reservar()` (que verifica se `status == StatusSlot.LIVRE` antes de alterar para `RESERVADO` ou lançar `SlotIndisponivelError`) pertence ao próprio *Slot*, e não ao Caso de Uso ou ao Controller. Da mesma forma, `Servico` detém o `prestador_id`, sendo o especialista para validar se `solicitante_id != prestador_id`.
2. **Creator (Criador):**
   * *Onde foi aplicado:* `Contratacao.registrar_avaliacao(nota, comentario)` cria a instância de `Avaliacao`, e `Servico.adicionar_slot(inicio, fim)` cria `SlotDisponibilidade`.
   * *Justificativa:* `Contratacao` agrega, contém e gerencia o ciclo de vida de `Avaliacao` (uma avaliação só pode nascer dentro de uma contratação `CONCLUIDA`). Ao delegar a criação para `Contratacao`, garantimos que nenhuma `Avaliacao` órfã ou associada a um serviço não concluído seja instanciada no sistema.
3. **Controller (Controlador):**
   * *Onde foi aplicado:* `SolicitarContratacaoUseCase` e `MarketplaceCLIController` (Adaptador de Entrada).
   * *Justificativa:* Isola a camada de interface (CLI/REST) da lógica de domínio. O caso de uso atua como controlador de caso de uso, recebendo DTOs/parâmetros primitivos, coordenando chamadas ao domínio e às portas de saída sem conter regras de interface gráfica.
4. **Pure Fabrication (Fabricação Pura):**
   * *Onde foi aplicado:* `SqliteContratacaoRepository`, `InMemoryContratacaoRepository`, `EmailNotificador` e `NotificadorFake`.
   * *Justificativa:* Conceitos como "conexão SQLite" ou "servidor SMTP" não existem no domínio do problema do campus. Criar essas classes fora do domínio evita poluir `Contratacao` e `Servico` com código de infraestrutura (preservando a coesão do domínio).
5. **Indirection (Indireção) & Protected Variations (Variações Protegidas):**
   * *Onde foi aplicado:* Nas interfaces `NotificadorPort`, `ServicoRepository` e `ContratacaoRepository` (`src/ports/`).
   * *Justificativa:* Atende diretamente aos **ASR-01** e **ASR-03**. Os pontos de instabilidade tecnológica (API de notificação e SGBD) são encapsulados atrás de interfaces estáveis, protegendo o domínio e os casos de uso contra variações de fornecedores externos.

---

## 2.3 Análise de Coesão e Acoplamento

* **Alta Coesão (*High Cohesion*):** Cada classe possui um foco único e bem delimitado. As entidades em `src/domain/` lidam exclusivamente com regras e invariantes de negócio (zero `import sqlite3` ou `import smtplib`). O `SolicitarContratacaoUseCase` lida apenas com o fluxo de contratação, enquanto o `SqliteContratacaoRepository` lida exclusivamente com instruções SQL e mapeamento de tuplas para objetos.
* **Baixo Acoplamento (*Low Coupling*):** O acoplamento entre camadas é estritamente unidirecional (de fora para dentro) e mediado por abstrações. O Caso de Uso não conhece `EmailNotificador` nem `SqliteContratacaoRepository`, ele conhece apenas os contratos abstratos (`NotificadorPort` e `ContratacaoRepository`). Assim, uma mudança na biblioteca de banco de dados ou no serviço de mensageria tem impacto zero nas camadas de Aplicação e Domínio.

---

## 2.4 Aplicação dos Princípios SOLID

* **SRP (*Single Responsibility Principle*):** `Contratacao` muda apenas se as regras de negócio de contratação/avaliação mudarem, `SqliteContratacaoRepository` muda apenas se o esquema do banco mudar, `EmailNotificador` muda apenas se o protocolo de envio de e-mail mudar.
* **OCP (*Open/Closed Principle*):** O sistema está aberto para extensão de novos canais de alerta (ex: criar `WhatsAppNotificador(NotificadorPort)`) e novos bancos (ex: `PostgresContratacaoRepository(ContratacaoRepository)`), mas fechado para modificação no `SolicitarContratacaoUseCase`.
* **LSP (*Liskov Substitution Principle*):** Qualquer implementação de `NotificadorPort` (`EmailNotificador` ou `NotificadorFake`) e de `ContratacaoRepository` (`SqliteContratacaoRepository` ou `InMemoryContratacaoRepository`) pode substituir a outra em tempo de execução ou nos testes automatizados sem quebrar o comportamento esperado pelo `SolicitarContratacaoUseCase`.
* **ISP (*Interface Segregation Principle*):** Em vez de uma interface monolítica `DadosPort` com dezenas de métodos não relacionados, separamos as portas por contexto (`ServicoRepository`, `ContratacaoRepository` e `NotificadorPort`), de modo que `ConsultarServicosUseCase` dependa apenas de `ServicoRepository`.
* **DIP (*Dependency Inversion Principle*):** Módulos de alto nível (`SolicitarContratacaoUseCase`) não dependem de módulos de baixo nível (`SqliteContratacaoRepository`, `EmailNotificador`). Ambos dependem das abstrações definidas em `src/ports/` (classes base abstratas com `abc.ABC`), sendo conectadas na inicialização (`main.py`) via Injeção de Dependência pelo construtor.