---
name: diarization-manager
description: >-
  Gerenciar, corrigir e evoluir a diarização do SignalCatcher: API e persistência,
  worker SignalCatcherDiarization com WhisperX, fila, progresso, cancelamento,
  transcrições e interface React no SignalCatcherFrontend. Use para mudanças e
  diagnóstico nesse módulo, inclusive integração entre os três projetos.
  Ingestão e download de vídeos sem relação com diarização pertencem ao youtube-manager.
---

# Diarization Manager

Trabalhe no comportamento solicitado, identificando quais dos três projetos participam da mudança.
Responda em português brasileiro; siga as convenções locais de código e comentários em inglês.

## Localizar a implementação

Os checkouts conhecidos ficam em `C:/Users/ofcer/PycharmProjects/`:
- `SignalCatcher`: API de gerenciamento, migrations e contratos de domínio.
- `SignalCatcherDiarization`: API de upload/path, scheduler, inferência e gravação de resultados.
- `SignalCatcherFrontend`: biblioteca, ações, polling e visualizador de transcrição.

Se o workspace mudou, localize os repositórios antes de usar esses caminhos. Leia os
`AGENTS.md` aplicáveis, incluindo `.agents/AGENTS.md`, e o estado Git dos projetos afetados.
Preserve alterações preexistentes. O mapa foi conferido em 2026-10-02; confirme detalhes
no código atual. O README do worker contém documentação antiga de captura YouTube e
não é fonte confiável para sua arquitetura atual.

Leia [references/maintenance.md](references/maintenance.md) apenas nas seções pertinentes:
- API, campos e estados: mapa, contratos, persistência.
- Fila, cancelamento e worker: concorrência, processamento, diagnóstico.
- UI e transcrições: frontend e validação.

## Contratos essenciais

- API principal e worker mapeiam a mesma tabela `diarization`. Alterar sua estrutura
  exige compatibilizar os dois models e criar migration no SignalCatcher, onde estão
  as revisões existentes. Não crie cadeias Alembic concorrentes para a mesma tabela.
- A criação via YouTube na API principal grava a fila diretamente. A existência de
  `DiarizationApiClient` não significa que esse fluxo use HTTP para enfileirar.
- Mantenha `DiarizationStep` separado de `ContentStep`. Sincronize mudanças de estados
  com `ACTIVE_STEPS` do worker, filtros, ações e mocks do frontend.
- Uma execução possui `worker_token` e lease. Resultados, erros e progresso atrasados
  não podem sobrescrever uma tarefa cancelada, reenfileirada ou assumida por outro worker.
  Preserve o lock de execução entre processos, além do claim transacional.
- `progress_percent` representa a etapa atual: pode ser nulo, cresce dentro da etapa e
  é limpo na transição/reset. Telemetria não deve criar entradas em `step_tracking`.
- O histórico pertence ao UUID da tarefa, com `entity_type="diarization"`.
  O vínculo ao vídeo usa `entity_id=external_id` e normalmente `entity_type="YOUTUBE"`.
  Não substitua uma identidade pela outra.
- A biblioteca escolhe a tentativa mais recente por entidade antes de filtrar status;
  uploads sem entidade permanecem independentes. Ordenação e paginação ocorrem no servidor.
- A inferência roda em subprocesso `spawn`. Preserve imports pesados dentro do worker,
  encerramento do processo, liberação dos modelos e fechamento das filas.

Esses são contratos atuais a preservar em mudanças comuns. Se o pedido alterar um deles,
implemente a mudança deliberadamente em todos os participantes e cubra a nova semântica.

## Conduzir a mudança

1. Trace o fluxo relevante pelos arquivos do mapa, sem carregar todo o módulo por padrão.
2. Para campo persistido, revise entity, interface, ambos os models, mappers, DTOs, migration
   e consumidores reais. Para endpoint, revise DI, autorização da API principal e mock.
3. Mantenha o domínio independente de infraestrutura. Na API principal, repositories
   fazem `flush`; o unit of work faz commit/rollback. O worker possui sessões próprias.
4. Escolha as verificações da referência conforme o comportamento afetado. Use testes
   isolados para fila e inferência antes de recorrer a processamento real.
5. Entregue mudanças, verificações executadas e limitações concretas. Diferencie testes
   com SQLite/mocks de validação PostgreSQL e de inferência real.

Não inicie o serviço como simples teste de importação: o lifespan do worker inicia o
scheduler e pode consumir a fila configurada. Alterações de código não implicam aplicar
migrations, reiniciar serviços ou reenfileirar tarefas reais. Use a autorização já dada
pelo usuário quando essas operações fizerem parte do pedido; caso contrário, mantenha a
validação isolada. Não copie tokens ou credenciais para a skill.
