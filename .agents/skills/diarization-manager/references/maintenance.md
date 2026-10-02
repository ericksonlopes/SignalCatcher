# Mapa de manutenção

Caminhos abaixo são relativos à raiz do projeto indicado. Revalide nomes e contratos
quando o código mudar; esta referência descreve a implementação observada em 2026-10-02.

## API e persistência — SignalCatcher

Sob `src/modules/diarization/`:
- `domain/entities/diarization_entity.py`, `domain/enums/diarization_step.py` e
  `domain/interfaces/repositories/diarization_repository.py`: entidade, estados e contrato.
- `application/use_cases/diarization_commands.py` e `diarization_queries.py`:
  operações e enriquecimento via serviço YouTube.
- `application/dtos/diarization_card_dto.py` e `application/mappers/diarization_card_mapper.py`:
  contrato da biblioteca, incluindo `channelName`, `progress_percent`, `queue_priority`
  e `result_json`.
- `infrastructure/repositories/diarization_repository.py`: deduplicação, listagem,
  reprocessamento, cancelamento e priorização.
- `infrastructure/repositories/models/diarization_model.py` e
  `infrastructure/repositories/mappers/diarization_mapper.py`: ORM e conversão.
- `infrastructure/unit_of_work.py` e `presentation/api/dependencies.py`:
  transação por requisição; preserve o commit antes da resposta via dependência
  com `scope="function"`.
- `presentation/api/routes/diarization_route.py`: rotas.
- `infrastructure/clients/diarization_api_client.py` e
  `application/dtos/diarization_api_dtos.py`: cliente HTTP de path/upload, distinto
  da criação direta por YouTube.

Fora do módulo:
- `main.py` monta `/api/diarization` com `require_admin`.
- `src/core/api/security.py` exige `X-API-Key` nas mutações; chave vem de `ADMIN_API_KEY`.
- `src/modules/youtube/infrastructure/repositories/models/step_tracking_model.py`
  implementa o helper usado pelos listeners do model da API.
- `alembic/versions/`: procure as revisões de progress, worker lease e queue priority;
  obtenha o head atual antes de criar a próxima migration.

### Rotas e identidade

| API principal, prefixo /api/diarization | Semântica atual |
| --- | --- |
| POST /youtube/{external_id} | Vídeo COMPLETED, com arquivo e sem deletion_requested; body language e start_now |
| GET /list e GET / | items e diarizations como aliases; total, page, limit, total_pages, status_counts, total_status_count |
| POST /{id}/reprocess e /{id}/retry | Reutiliza tarefa ativa vinculada ou limpa/recoloca a tarefa em PENDING |
| POST /{id}/cancel | Retorna 409 se o estado não permite cancelar |
| POST /{id}/start-now | Prioriza selecionada e revoga a execução atual |

A busca de comandos aceita UUID da tarefa e, como fallback, ID externo.
O repositório serializa a criação por entidade no PostgreSQL e reutiliza tarefa ativa.
Não remova essa proteção ao adicionar parâmetros de criação.

`PROCESSING` é estado legado e também filtro agregado de todos os estados em execução.
`DIARIZED` ainda é ativo: atribuição de falantes terminou, persistência final não.
Os estados canceláveis atuais são PENDING, STARTED, TRANSCRIPTION, ALIGNMENT e DIARIZATION;
não suponha que todo estado ativo seja cancelável.

A listagem deduplica tentativas antes de busca/status e usa a mesma base para contagens.
Em ALL, estados ativos vêm primeiro; depois created_at DESC e id DESC.
Em COMPLETED, usa COALESCE(updated_at, created_at) DESC e id DESC.
Contagens atuais são globais por estado, não necessariamente o total da busca.

## Worker — SignalCatcherDiarization

Sob `src/modules/diarization/`:
- `presentation/router.py`: POST /process-file, POST /process-path e GET /task/{task_id},
  todos sob `/api/diarization`.
- `application/use_cases.py`, `application/dtos.py`, `domain/entities.py`:
  upload/path, configuração e resultados.
- `presentation/schedules/scheduler_manager.py`: job `process_diarization_tasks`,
  intervalo atual de 10 segundos e max_instances=1.
- `presentation/schedules/jobs/process_pending_diarization_job.py`:
  lock global, subprocesso, mensagens de progresso, heartbeat, resultado e cleanup.
- `infrastructure/repositories/diarization_task_repository.py`:
  claim, lease, recuperação, progresso e histórico.
- `infrastructure/repositories/models/diarization_task_model.py`:
  segundo mapeamento da tabela compartilhada.
- `infrastructure/services/audio_diarizer.py` e `infrastructure/utils/audio_utils.py`:
  transcrição, alinhamento, separação/atribuição de falantes e dispositivo.

Em `src/core/services/model_loader_service.py` ficam cache e unload dos modelos.
Settings, dependências e execução estão em `src/core/config/settings.py`,
`pyproject.toml`, `main.py`, `Dockerfile` e `docker-compose.yml`.

### Concorrência e fila

Preserve em conjunto:
- Lock PostgreSQL de sessão em `DiarizationExecutionLock`, mantido durante a execução.
  O fallback local de teste não demonstra exclusão entre réplicas PostgreSQL.
- Lock transacional `diarization:queue`, row lock e verificação da próxima tarefa no claim.
- Token por tentativa; lease atual de 120 segundos e renovação aproximadamente a cada 5 segundos.
- Recuperação forçada apenas depois de adquirir exclusividade de execução. Não chame
  `recover_interrupted_tasks(force=True)` como reparo genérico com outro worker ativo.
- Finalização/erro guardados pelo token e estado ativo; progresso guardado também pela etapa.
- Cleanup do subprocesso e da fila mesmo quando start, banco ou persistência falham.
  Sucesso aguarda o filho; cancelamento/reenfileiramento não deve virar ERROR.

A fila usa queue_priority DESC, duração positiva ASC com desconhecida por último quando
há tabela youtube_contents, COALESCE(queued_at, created_at) ASC e id ASC. O claim confirma
essa mesma ordem. Isso difere da ordenação da biblioteca.

Start-now limpa prioridade anterior, reenfileira ativos com token/lease/progresso/resultados
limpos e dá prioridade 1 à selecionada. A recuperação usa prioridade 2; claim zera a
prioridade. A tarefa interrompida reinicia do começo, sem checkpoint. Atualizar queued_at
não garante último lugar absoluto, pois duração precede esse campo. Preserve essa distinção
ao explicar o comportamento ou modificar a política de fila.

A API registra transições por listeners ORM na transação da requisição. O worker registra
explicitamente em savepoint, com histórico best-effort: falha no insert do histórico é
logada sem desfazer o estado da tarefa. Evite duplicar listeners e inserts no mesmo fluxo.
Datas persistidas são UTC sem tzinfo, conforme convenção atual dos dois models.

### Inferência e progresso

Fluxo normal: PENDING -> TRANSCRIPTION -> ALIGNMENT -> DIARIZATION -> DIARIZED -> COMPLETED.
STARTED e PROCESSING continuam compatíveis com registros antigos.

WhisperX transcreve/alinha; o pipeline de diarização e a atribuição de falantes completam
o resultado. Preserve texto original quando alinhamento falha, idioma detectado e
segmentos alinhados na atribuição de falantes. Leia a implementação antes de substituir
o algoritmo por funções semelhantes da biblioteca.

O resultado contém segments, language, duration e speakers; segmentos expõem start/end
em segundos, text e speaker. Verifique consumidores antes de mudar esse JSON.

O progresso usa callbacks suportados pela versão instalada, com compatibilidade para
bibliotecas sem callback. Não simule porcentagem pelo tempo. O reporter limita a frequência
das mensagens e reinicia por etapa; DIARIZATION só chega a 100 e emite DIARIZED depois da
atribuição dos falantes. Inspecione as assinaturas instaladas se alterar essa integração.

A configuração atual limita batch_size em CPU e usa int8 em CPU/float16 em CUDA.
O pyproject aponta pacotes Torch para índice CPU; não prometa CUDA apenas porque existe
detecção no código. Preserve unload entre etapas. Imports do scheduler não devem carregar
Torch/WhisperX, e o processo spawn configura seu próprio logging.

### Diagnóstico operacional

- Fila parada: conferir scheduler, lock de execução, tarefa ativa, lease, ordem do claim,
  schema instalado e logs; não zerar estados diretamente para mascarar o problema.
- Arquivo ausente: conferir file_path e DOWNLOAD_YOUTUBE_PATH no ambiente real do worker.
  O job resolve o caminho sob essa raiz; API e worker precisam acessar a mesma mídia.
- Falha de modelo: conferir presença de HF_TOKEN sem exibi-lo, acesso ao modelo, FFmpeg,
  versões instaladas, memória e dispositivo. .env.example do worker não lista tudo;
  settings e Compose são fontes mais precisas.
- Progresso congelado: distinguir fase sem callback, evento de etapa, persistência,
  lease e atualização no frontend.
- Conexão: conferir porta do processo e mapeamento Compose. O Compose observado publica
  8001 no host para 8000 no container; não inferir a porta interna pelo host.
- Antes de mudar integração com WhisperX/PyTorch, consultar primeiro dependências e código
  instalados e, se necessário, documentação oficial correspondente à versão.

## Frontend — SignalCatcherFrontend

- `src/components/apps/DiarizationApp.tsx`: biblioteca, filtros e ações;
  declara também `DiarizationVideo`.
- `src/hooks/useInfiniteDiarizations.ts`: páginas de 20, polling de 5 segundos,
  AbortController, merge por ID e atualização da janela já carregada.
- `src/components/apps/diarization/DiarizationViewer.tsx`: busca, filtro por falante,
  nomes locais à visualização e exportação TXT.
- `src/components/apps/diarization/transcript.ts` e `transcript.test.ts`:
  normalização, agrupamento, horários e estatísticas de fala.
- `src/types.ts`, `src/api.ts`, `src/App.tsx` e
  `src/components/apps/SignalCatcherApp.tsx`: contratos compartilhados, transporte,
  shell e ações nos vídeos. Localize os handlers atuais com rg.
- `server.ts`: mocks de listagem, criação, retry, cancel e start-now.
- `src/locales/en.ts` e `src/locales/pt.ts`: textos visíveis.

Mudanças em estados, progresso ou prioridade devem revisar também fingerprint, filtros,
ações permitidas e mocks. Preserve cancelamento de respostas antigas ao mudar busca/filtro
e ausência de duplicatas ao carregar novas páginas.

O transcript agrupa falas consecutivas do mesmo falante apenas sem sobreposição e com
pausa de até 2 segundos; conserva frases para estatísticas sem contar sobreposição duas
vezes por falante. Falante ausente usa UNKNOWN. Nomes editados no viewer não são persistidos
no backend atualmente. Não prometa persistência sem implementá-la.

## Validação proporcional à mudança

Execute na raiz de cada projeto usando seu ambiente existente. Exemplos em PowerShell;
se o projeto usar uv, o equivalente é uv run python, sem instalar dependências desnecessárias.

API, para fila/listagem/tracking:
```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_diarization*.py"
```

Worker, para inferência/fila/progresso e logging:
```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_diarization_improvements.py"
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_worker_logging.py"
```

Os testes do worker isolam banco e inferência; os de logging exercitam spawn.
Regressões relevantes: tentativa antiga não grava depois de cancel/requeue; claim único;
restart recupera tarefa; erro do banco encerra filho; progresso não gera histórico;
falha no alinhamento mantém transcrição; DIARIZED só após atribuição bem-sucedida.
SQLite não valida locks PostgreSQL: use integração isolada com PostgreSQL quando alterar
essas garantias e reporte explicitamente quando ela não puder ser executada.

Frontend:
```powershell
npm run lint
npm run build
npx --no-install tsx --test src/components/apps/diarization/transcript.test.ts
```

Para mudança visual/interativa, confira também busca/filtro, polling, carregamento de páginas,
estados vazios/erro, start-now/cancel/retry, falantes e exportação conforme o escopo.
Para schema, confira heads e migration sem aplicá-la a banco compartilhado como teste.
Não execute script/test_diarizer.py ou inicialize a API do worker para uma validação que
só exige testes isolados: isso pode carregar modelos ou consumir recursos/dados reais.
