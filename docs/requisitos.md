# 1. Descrição do Problema e Requisitos — CampusHub (Tema 11)

## 1.a Contexto do Sistema
No ambiente universitário, existe uma alta demanda interna por serviços especializados de curto prazo entre os próprios membros da comunidade acadêmica tais como auxílio em análises estatísticas para pesquisas, revisão e formatação de trabalhos acadêmicos (ABNT/LaTeX), aulas particulares de disciplinas complexas, tradução de artigos e prototipagem. Atualmente, a divulgação e a contratação desses serviços ocorrem de maneira descentralizada e informal (murais físicos, grupos de mensagens ou indicações), o que gera falta de visibilidade para quem oferece o serviço, insegurança quanto à reputação do prestador e frequentes conflitos de agenda.

O **CampusHub** é uma plataforma de *Marketplace de Serviços dentro do Campus* projetada para centralizar a oferta, a busca, o controle de disponibilidade de agenda, o fluxo de contratação, o registro de conclusão e a avaliação de serviços prestados exclusivamente entre membros da comunidade universitária. O sistema foi concebido sob o princípio de baixo acoplamento e alta coesão para atender às demandas atuais do campus e permitir fácil evolução tecnológica (como a futura troca de meios de notificação, gateways de pagamento ou bancos de dados) sem impactar as regras de negócio centrais.

---

## 1.b Principais Atores
1. **Solicitante (Membro da Comunidade):** Estudante, docente ou servidor técnico-administrativo que busca serviços na plataforma, consulta a disponibilidade dos prestadores, solicita contratações, confirma a conclusão e avalia o atendimento recebido.
2. **Prestador (Membro da Comunidade):** Membro da comunidade universitária que cadastra ofertas de serviços, gerencia seus horários (slots) disponíveis para atendimento, executa o serviço contratado e registra sua conclusão. (Nota de domínio: um mesmo usuário cadastrado pode atuar tanto como Solicitante quanto como Prestador em momentos distintos, porém nunca na mesma contratação).
3. **Serviço Externo de Notificação (Ator Secundário / Sistema Externo):** Provedor responsável pelo envio de alertas transacionais (ex: Servidor SMTP de E-mail Institucional, API de WhatsApp ou Push Notification) quando uma contratação muda de estado.
4. **Gateway de Pagamento / Validador Institucional (Ator Secundário / Sistema Externo):** Sistema externo (real ou simulado) responsável por autorizar a retenção de saldo/créditos acadêmicos ou validar o vínculo ativo do usuário com a universidade no ato da contratação.

---

## 1.c Requisitos Funcionais (RF)
O sistema contempla **8 Requisitos Funcionais** centrais que cobrem todo o ciclo de vida do marketplace:

* **RF01 — Cadastrar Oferta de Serviço:** O sistema deve permitir que um Prestador cadastre um novo serviço informando título, descrição detalhada, categoria (ex: Mentoria, Revisão, Laboratório, Tradução), modalidade (presencial no campus ou remoto) e valor cobrado.
* **RF02 — Gerenciar Disponibilidade de Agenda (Slots):** O sistema deve permitir que o Prestador cadastre e gerencie janelas de horário disponíveis (slots contendo data, hora de início e hora de término) vinculadas aos seus serviços.
* **RF03 — Consultar e Filtrar Serviços Disponíveis:** O sistema deve permitir que um Solicitante busque serviços ativos filtrando por categoria, termo de busca ou disponibilidade de horário, exibindo a nota média de avaliação do Prestador.
* **RF04 — Solicitar Contratação de Serviço:** O sistema deve permitir que um Solicitante contrate um serviço selecionando um slot de horário com status LIVRE. Ao confirmar a solicitação, o sistema deve validar regras de negócio, criar o registro de contratação com status CONFIRMADA (ou PENDENTE) e alterar imediatamente o status do slot para RESERVADO.
* **RF05 — Cancelar Contratação:** O sistema deve permitir que o Solicitante ou o Prestador cancele uma contratação antes de sua conclusão, alterando o status da contratação para CANCELADA e liberando o slot correspondente de volta para o status LIVRE.
* **RF06 — Registrar Conclusão do Serviço:** O sistema deve permitir que, após a realização da atividade, a contratação tenha seu estado alterado de CONFIRMADA para CONCLUIDA, registrando o timestamp de finalização.
* **RF07 — Avaliar Serviço Prestado:** O sistema deve permitir que o Solicitante registre uma avaliação (nota inteira de 1 a 5 e comentário descritivo) vinculada a uma contratação, exclusivamente se o status dessa contratação for CONCLUIDA e ainda não houver avaliação prévia para ela.
* **RF08 — Notificar Partes sobre Eventos da Contratação:** O sistema deve disparar notificações para o Prestador e para o Solicitante sempre que uma contratação for criada, cancelada ou concluída, utilizando um adaptador de comunicação externa.

---

## 1.d Restrições Relevantes
* **RES01 — Restrição de Domínio (Proibição de Auto-contratação):** Um membro da comunidade não pode solicitar a contratação de um serviço cujo Prestador seja ele mesmo (solicitanteId != prestadorId).
* **RES02 — Restrição de Domínio (Exclusividade de Horário):** Um slot de disponibilidade pertence a um único Prestador e só pode estar vinculado a, no máximo, uma contratação ativa por vez (não é permitido overbooking de horário).
* **RES03 — Restrição de Domínio (Integridade de Avaliação):** Avaliações são imutáveis após criadas e só podem existir associadas a uma contratação real que atingiu o estado CONCLUIDA.
* **RES04 — Restrição Técnica e Acadêmica (Escopo de Implementação):** O protótipo executável deve implementar uma fatia vertical coesa (criação de contratação com reserva de slot, consulta de serviços/contratações, tratamento de erro de negócio como conflito de horário/auto-contratação, persistência e integração com dependência externa substituível), sem necessidade de interface gráfica complexa ou sistema completo de autenticação.
* **RES05 — Restrição de Portabilidade e Execução:** O projeto deve ser autocontido e executável localmente via linha de comando ou container/script padronizado, permitindo que os avaliadores rodem os testes automatizados e o protótipo sem depender de credenciais pagas de serviços de nuvem.

---

## 1.e Requisitos Arquiteturalmente Significativos (ASRs)

Foram selecionados **3 ASRs concretos** que determinam diretamente a estrutura de módulos, interfaces e limites arquiteturais do sistema:

### ASR-01: Modificabilidade e Substituibilidade de Integrações Externas (Notificações e Pagamentos)
* **Cenário Concreto:** Os canais de comunicação e pagamento utilizados na universidade estão sujeitos a mudanças frequentes de fornecedor ou política institucional (ex: substituir o envio de notificações via E-mail SMTP por uma API de WhatsApp ou Telegram, ou substituir um validador simulado de pagamento por uma API de PIX). A substituição ou adição de um novo provedor externo deve ser realizada sem alterar nenhuma linha de código nas entidades de domínio ou nos casos de uso (camada de aplicação), exigindo apenas a implementação de uma nova classe adaptadora.
* **Atributo de Qualidade Principal:** Modificabilidade / Manutenibilidade (Baixo Acoplamento).

### ASR-02: Consistência Transacional e Prevenção de Conflitos na Contratação (Anti-Overbooking)
* **Cenário Concreto:** Quando um Solicitante confirma a contratação de um serviço para um determinado slot de horário (RF04), a validação de disponibilidade do slot, a mudança do estado do slot para RESERVADO e a persistência do registro de Contratacao devem ocorrer como uma operação atômica e consistente. Caso o slot já esteja ocupado, pertença ao próprio solicitante ou ocorra falha na persistência, o sistema deve rejeitar a operação imediatamente lançando uma exceção de domínio explícita, garantindo que nenhum slot fique inconsistente ou duplamente alocado.
* **Atributo de Qualidade Principal:** Confiabilidade / Integridade de Dados.

### ASR-03: Testabilidade Isolada da Lógica de Negócio e Independência do Mecanismo de Persistência
* **Cenário Concreto:** Toda a lógica de regras de negócio do marketplace (validação de auto-contratação, máquina de estados da contratação CONFIRMADA -> CONCLUIDA -> AVALIADA, bloqueio de slot e cálculo de reputação) deve poder ser testada de forma automatizada e determinística em memória (em menos de 2 segundos de execução), sem necessidade de subir um servidor de banco de dados relacional ativo ou servidores de rede externos. Além disso, a migração futura de um banco local (ex: SQLite/In-Memory) para um SGBD robusto de produção (ex: PostgreSQL) deve afetar exclusivamente a camada de infraestrutura.
* **Atributo de Qualidade Principal:** Testabilidade e Portabilidade.

---

## 1.f Justificativa: Como os ASRs Influenciam as Decisões Arquiteturais

Cada um dos ASRs acima impõe forças diretas sobre o design e a arquitetura do software, descartando abordagens acopladas (como Transaction Script com SQL embutido na interface) e orientando as seguintes decisões arquiteturais:

| ASR | Influência Direta na Arquitetura e no Design |
| :--- | :--- |
| **ASR-01 (Modificabilidade de Integrações)** | Exige a aplicação do Princípio da Inversão de Dependência (DIP - SOLID) e do padrão Protected Variations (GRASP) / Ports and Adapters (Arquitetura Hexagonal / Clean Architecture). O núcleo da aplicação definirá uma interface de saída pura (ex: NotificadorServico / NotificationPort), enquanto as implementações concretas (EmailNotificador, WhatsAppNotificador, NotificadorFake) residirão na camada externa de Infraestrutura e serão injetadas via Injeção de Dependência. |
| **ASR-02 (Consistência e Anti-Overbooking)** | Exige um Modelo de Domínio Rico em vez de um modelo anêmico. A lógica de verificação de conflito de horário, proibição de auto-contratação e transição de estados (reservar(), concluir(), avaliar()) será encapsulada diretamente dentro das classes de Domínio (Servico, SlotDisponibilidade, Contratacao), seguindo o padrão Information Expert e Creator (GRASP). O Caso de Uso atuará apenas como orquestrador transacional entre o Repositório e o Domínio. |
| **ASR-03 (Testabilidade e Independência de Persistência)** | Determina a separação estrita entre o modelo de domínio e a tecnologia de banco de dados através do padrão Repository. Os casos de uso dependerão apenas de abstrações (ContratacaoRepository, ServicoRepository). Isso permite que, durante os testes de unidade/integração rápida e na avaliação do protótipo, injetemos implementações em memória ou SQLite embarcado, mantendo 100% de compatibilidade arquitetural para plugar um PostgresContratacaoRepository sem tocar nas regras de negócio. |