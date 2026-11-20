# LitKit Laya intake and parent workflow

**Target** · Friday, 20 November 2026  
**Repository baseline** · `main` at `5e3106d`

Introduce Laya at the context resolver boundary, keep the supervisor as a fallback, and run the existing general and calendar workflows through a parent LangGraph. Complete intake and its interface tests before wiring the graph. Keep the current Telegram request and reply interface.

## Milestones

### 1. Define the classifier interface and wire the context resolver

Define an async `RequestClassifier` protocol in `app/context/classifier.py` and a provider-neutral `Classification` in `app/context/models.py`. The result carries a supported task or abstention, the selected option's probability when available, and hints for recent messages and user memory.

**Boundary and reuse.** Inject the protocol into the planning step of [`ContextResolver`](../app/context/resolver.py). Follow the [`MemoryRepo`](../app/context/repositories.py) protocol pattern and retain `RoutingContext`, `ContextPlan`, policy approval, embedding, memory lookup, and `ContextPacket` construction. Python maps the classifier's hints to implemented, available, policy-approved sources. Recent messages and active tasks are currently empty at Telegram ingress. A classifier hint does not make either source available.

**Fallback.** Invoke the current supervisor planner on abstention, invalid intent, or classifier failure. Validate its plan against the registered workflows and context policies. Return a clarification or unsupported-request reply when neither path produces a usable plan.

**Long-term replacement.** The supervisor's structured planner and `CONTEXT_PLANNER_PROMPT` can be retired once the classifier and clarification path cover the cases served by the fallback. The resolver continues to own context assembly.

### 2. Implement the Laya adapter and response mapping

Put the adapter in `app/llm/laya_classifier.py`. Use plain `laya==0.5.0` with the explicit `convaiinnovations/laya-multilingual` checkpoint and `revision="reviewed"`.

**Boundary and reuse.** The adapter accepts `RoutingContext` and returns `Classification`. Pass the current request and any available recent messages and active tasks to Laya. Ask one choice question with `general_chat`, `calendar`, and `uncertain` as options, plus a yes/no question for each context hint. Keep the Laya question definitions and response shape inside the adapter.

**Mapping.** Start with a probability cutoff of `0.80` for the chosen intent and each positive hint. Treat an invalid intent answer as abstention and an invalid hint as unset. Run synchronous inference off the event loop and serialize calls to the shared model. The cutoff is a development default pending evaluation on LitKit requests.

**Long-term replacement.** A future HTTP-backed adapter can use the same protocol if Laya moves to a dedicated inference service.

### 3. Wire Laya through bootstrap

**Boundary and reuse.** Create one adapter per process in [`create_runtime()`](../app/bootstrap.py), inject it into the resolver, and load the checkpoint lazily on first use. If initialization fails, log the failure without request text and use the supervisor for the rest of that process lifetime. Reuse the existing supervisor client for fallback planning and general-agent execution.

**Long-term replacement.** Bootstrap remains the composition root. Direct supervisor injection into the resolver can disappear when the fallback is retired. The existing general agent still needs its configured model.

### 4. Implement interface tests

**Boundary and reuse.** Use the existing pytest async setup. Replace the unfinished fixtures in [`tests/test_context_resolver.py`](../tests/test_context_resolver.py) with a fake classifier, a fake embedding service, and a repository fake that matches `find_relevant`. Test the adapter against representative raw Laya responses with a stub predictor.

Cover both supported routes, the exact cutoff boundary, malformed answers, initialization and inference failures, supervisor fallback, and rejection of unsupported or out-of-policy fallback plans. Verify that an unapproved memory hint skips embedding and DuckDB, and that approved calendar retrieval uses the existing memory limit. Automated tests run without model downloads or live tools.

**Long-term replacement.** The fake classifier remains useful for testing policy and retrieval. Fixtures that emulate the supervisor's structured output can be retired with the fallback.

### 5. Implement the parent LangGraph workflow

**Boundary and reuse.** Define the graph in `app/assistant/workflow.py`, compile it once in bootstrap, and invoke it from [`AssistantService.respond()`](../app/assistant/service.py). Graph state carries the request, resolution outcome, and final reply. Run `resolve → execute → finalize`. A clarification or unsupported outcome goes directly to finalization.

Reuse [`WorkflowDispatcher`](../app/assistant/dispatcher.py), [`WorkflowAgent.run(ContextPacket) -> str`](../app/assistant/agents/base.py), and the existing general and calendar agents. Keep the Telegram handler responsible for sending the final reply.

**Long-term replacement.** The graph takes over the sequencing in `_context_route()` and `_packet_dispatch()`. The dispatcher can shrink to a workflow registry as model and tool selection move into the graph. Future work can extend workflow results with tool receipts and verification evidence, then add bounded repair, write reconciliation, checkpoints, and worklog persistence.

## Acceptance and rollout

- Exercise `AssistantService.respond()` through both registered routes and the clarification path. Verify exactly one workflow invocation for each dispatched request, zero for clarification, and one final reply per request.
- Before enabling Laya-first routing against a live calendar, evaluate the pinned checkpoint on labeled chat, calendar read, calendar change, follow-up, and ambiguous requests. Record intent errors, abstentions, and fallback behavior. Reads and changes share the same calendar route in this milestone, so check for read requests that select write tools with a stubbed calendar tool boundary. Keep actual calendar mutations out of that evaluation.
- Validate dependency installation separately from offline tests. Preserve the existing Windows-only `pywin32` edit. The current manifest omits `sentence-transformers` despite the startup import. Address that gap if it blocks startup, and record any live smoke test blocked by credentials or the Windows-specific MCP launcher.
- This milestone ends at graph finalization. Evaluation inside the graph, bounded retries, checkpoint recovery, and durable worklogs are follow-on work.
