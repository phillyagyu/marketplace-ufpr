# Justificativas da Modelagem UML — CampusHub (Tema 11)

Este documento detalha as decisões de design e arquitetura adotadas na modelagem UML do sistema CampusHub. O objetivo principal da modelagem foi garantir a consistência entre os artefatos e o alinhamento estrito com os Requisitos Arquiteturalmente Significativos (ASRs), utilizando os padrões GRASP e princípios SOLID.

---

## 1. Diagrama de Componentes (Arquitetura Hexagonal / Ports & Adapters)

O Diagrama de Componentes ilustra a separação física e lógica dos módulos do sistema, adotando o estilo arquitetural centrado no domínio (Hexagonal/Clean Architecture).

* **Princípio da Inversão de Dependência (DIP - SOLID):** O diagrama evidencia que a camada `src/application` e `src/domain` (módulos de alto nível) não possuem setas de dependência apontando para tecnologias externas. Em vez disso, dependem de abstrações (interfaces em `src/ports`). As implementações reais, como `EmailNotificador` e `SqliteContratacaoRepository`, residem na camada de infraestrutura e apontam "para dentro", implementando essas interfaces.
* **Substituibilidade de Integrações (ASR-01):** O padrão *Protected Variations* (Variações Protegidas) foi aplicado ao isolar o serviço de notificação. A troca futura de um disparo de e-mail por WhatsApp envolverá apenas a criação de um novo adaptador na infraestrutura, sem recompilar ou alterar o núcleo do sistema.
* **Testabilidade (ASR-03):** O design em portas e adaptadores permite que, em tempo de teste, o `SolicitarContratacaoUseCase` receba injeções do `NotificadorFake` e do `InMemoryContratacaoRepository`. Isso viabiliza testes automatizados da lógica de negócio em milissegundos.

---

## 2. Diagrama de Classes (Modelo de Domínio Rico)

O Diagrama de Classes rejeita o antipadrão "Modelo Anêmico", encapsulando o estado e o comportamento dentro das entidades (*Rich Domain Model*).

* **Consistência Transacional (ASR-02) e *Information Expert* (GRASP):** A entidade `Servico` atua como Especialista na Informação para validar a regra **RES01** (auto-contratação), pois ela detém o `prestador_id`. Da mesma forma, o método `reservar()` pertence à entidade interna `SlotDisponibilidade`, garantindo que o status seja checado antes de qualquer mutação. O modelo recusa transições inválidas lançando subclasses de `ErroDominio`.
* **Padrão *Creator* (GRASP):** A instanciação da entidade `Avaliacao` foi delegada ao método `registrar_avaliacao()` dentro da Raiz de Agregado `Contratacao`. Isso blinda a integridade do sistema (**RES03**), garantindo que uma avaliação nunca seja criada solta no sistema ou associada a um serviço que ainda não tenha o status `CONCLUIDA`.
* **Alta Coesão:** As classes de domínio não contêm referências a SQL, JSON ou SMTP. Seu único motivo para mudar (SRP - Princípio da Responsabilidade Única) é a alteração de regras do negócio universitário.

---

## 3. Diagrama de Sequência (Caso de Uso: Solicitar Contratação)

O Diagrama de Sequência mostra o fluxo dinâmico e temporal da contratação de um serviço, evidenciando como a camada de Aplicação orquestra o Domínio e a Infraestrutura.

* **Padrão *Controller* (GRASP) e SRP (SOLID):** O `SolicitarContratacaoUseCase` não detém lógica condicional de negócios (ex: `if slot.status == LIVRE`). Ele atua puramente como um coordenador que repassa mensagens. A lógica foi delegada para os *Information Experts* (`Servico` e `Slot`).
* **Atomicidade (ASR-02):** O fluxo ilustra que o caso de uso recupera as instâncias, executa as validações de domínio em memória e, apenas em caso de sucesso absoluto, invoca o método `salvar()` do repositório. Se o `reservar()` falhar no meio do processo, o fluxo é interrompido por uma exceção, prevenindo gravações parciais no banco de dados e mitigando *overbooking*.
* **Isolamento de Efeitos Colaterais:** A notificação externa (envio de e-mail/mensagem) só é disparada após a confirmação da transação no banco de dados (`salvar()`), garantindo que o usuário não seja notificado de uma transação que falhou no repositório.

---

## 4. Diagrama de Comunicação (Colaboração de Instâncias)

Complementar ao Diagrama de Sequência, o Diagrama de Comunicação reforça a topologia da rede de mensagens entre as instâncias envolvidas no Caso de Uso.

* **Visão Espacial da Inversão de Controle:** O diagrama deixa visualmente claro que o Controlador (`UC`) é o nó central da colaboração, enviando mensagens radiadas tanto para as abstrações de saída (itens 1, 5 e 6: *Repositories* e *NotificadorPort*) quanto para o modelo de domínio central (itens 2, 3 e 4: *Servico*, *Slot* e *Contratacao*).
* **Consistência de Nomenclatura:** Este diagrama prova a consistência entre a modelagem estática e dinâmica, pois as assinaturas das mensagens (`validar_contratante`, `reservar`, `salvar`) correspondem exatamente aos métodos definidos no Diagrama de Classes e às portas do Diagrama de Componentes.