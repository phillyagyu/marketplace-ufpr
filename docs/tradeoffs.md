# 5. Alternativas Arquiteturais e Trade-offs

Para a definição da arquitetura do **CampusHub** foram feitas avaliações de diferentes estilos para satisfazer os Requisitos Arquiteturalmente Significativos (ASRs), em especial a necessidade de suportar a troca de provedores de notificação (ASR-01, Modificabilidade), garantir a integridade da reserva de horários (ASR-02, Consistência) e permitir a testabilidade isolada das regras de negócio sem dependência de banco de dados (ASR-03, Testabilidade).

Toda decisão arquitetural exige sacrifícios (trade-offs), onde priorizar um atributo de qualidade pode prejudicar outro ou introduzir complexidade indesejada.

## 5.1 Matriz de Decisão Arquitetural

| Alternativa | Modificabilidade | Consistência | Testabilidade | Complexidade | Observação |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **A: Monolito Simples (Acoplado)** | 0 | ++ | 0 | + | Regras ficam espalhadas e o banco é acessado diretamente, dificultando testes. |
| **B: Microsserviços** | ++ | 0 | 0 | -- | Alto desacoplamento, porém introduz consistência eventual na reserva de horários e dificulta implantação local. |
| **C: Monolito Modular (Hexagonal)** | ++ | ++ | ++ | 0 | **(ESCOLHIDA)** Favorece evolução controlada e testabilidade através da separação lógica. |

*(Legenda: ++ favorece bastante | + favorece | 0 neutro | - dificulta | -- dificulta bastante)*

## 5.2 Análise das Alternativas (Por que a Alternativa C foi escolhida?)

* **Alternativa A (Monolito Simples):** Descartada. Embora apresentasse menor custo inicial, as regras de negócio ficariam misturadas com o acesso ao banco e integrações externas (gerando o sintoma de "Controller Gordo"). Trocar o e-mail por WhatsApp exigiria alterar a regra da contratação, violando o princípio Aberto/Fechado (OCP) e o Princípio da Responsabilidade Única (SRP), prejudicando a manutenibilidade.
* **Alternativa B (Microsserviços):** Descartada. Separar a aplicação em serviços independentes de "Agenda" e "Contratação" transformaria nossas transações locais em comunicação por rede. Isso deslocaria a complexidade para a operação e exigiria lidar com consistência eventual no bloqueio de horários, o que é desnecessário para o tamanho da equipe e escopo atual.
* **Alternativa C (Monolito Modular com Arquitetura Hexagonal):** A escolha ideal. Prioriza a **Modificabilidade** e a **Testabilidade** isolando o domínio do sistema através de portas de entrada e saída (Ports and Adapters). O trade-off assumido é a necessidade de criar interfaces bem definidas internamente e aplicar disciplina para não quebrar a separação lógica das dependências.

---

# 9. Análise de Evolução

Caso o sistema precise passar por mudanças tecnológicas no futuro, a arquitetura isolada limitará o impacto:

**Cenário de Mudança 1: Substituição do Banco de Dados (SQLite -> PostgreSQL)**
* **O que muda:** Apenas a criação de novas classes na camada de Persistência / Infraestrutura (`PostgresServicoRepository`, `PostgresContratacaoRepository`) e a injeção delas no início da aplicação.
* **O que não muda:** As classes de domínio, casos de uso e os testes em memória permanecem 100% inalterados.
* **Por que:** A camada de Aplicação coordena os casos de uso dependendo apenas de interfaces abstratas. Ao aplicar a Inversão de Dependência (DIP) e a Indireção (GRASP), garantimos que o núcleo do sistema desconheça os detalhes da tecnologia de banco de dados.

**Cenário de Mudança 2: Inclusão de Aplicativo Mobile (API REST)**
* **O que muda:** A criação de novos Controladores na Camada de Apresentação (ex: endpoints REST) para receber as requisições Mobile.
* **O que não muda:** serviço de contratação ( `Service`), as validações do Domínio e as integrações externas permanecem as mesmas.
* **Por que:** O uso do padrão Controlador (Controller) separa o recebimento da requisição HTTP da execução da regra de negócio. Essa forte coesão e responsabilidade única (SRP) garantem que a Camada de Apresentação chame a Camada de Aplicação, mas a Aplicação nunca dependa de detalhes visuais ou de telas.