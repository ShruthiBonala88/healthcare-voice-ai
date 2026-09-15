# Healthcare Voice AI

Inbound phone-call voice assistant for a hospital: patients call in, talk
naturally, and can look up departments/doctors, book/reschedule/cancel
appointments, and ask general hospital questions — with a safety net that
hands off to a human for anything urgent or out of scope.

This scaffold implements the architecture:

```
Patient -> Twilio (voice + media streams) -> FastAPI backend
        -> Voice layer (VAD / STT / TTS, barge-in, silence detection)
        -> Agent layer (LangGraph orchestration + LangChain tools/RAG)
        -> OpenRouter (LLM + embeddings) / Supabase pgvector (RAG)
        -> Business/tool layer (appointments, patients, hospital info, handoff)
             -> Policy + validation (auth, business rules, allowed tools)
        -> Data layer (Supabase Postgres + pgvector)
        -> Upstash Redis (rate limiting, session state, locks)
        -> Observability (structured logs, call events)
```

## Project layout

```
app/
  main.py                  FastAPI app entrypoint
  config.py                 Settings (env vars)
  api/
    routes_calls.py         Twilio webhook + WebSocket media stream endpoint
    routes_health.py        Health check
  voice/
    vad.py                  WebRTC VAD + silence/end-of-turn tracking
    stt.py                  Streaming STT (Deepgram)
    tts.py                  Streaming TTS (ElevenLabs)
    stream_handler.py       Ties audio <-> agent together; barge-in logic
  agent/
    graph.py                LangGraph state graph (LLM <-> tools loop)
    state.py                Conversation state schema
    prompts.py               System prompt / safety rules
    llm.py                    OpenRouter chat + embedding clients
    rag.py                    Supabase pgvector retriever
  tools/
    appointment_tools.py      get_departments/doctors/slots, book/cancel/reschedule
    patient_tools.py          find_patient, create_patient
    hospital_tools.py         hospital_information (RAG-backed)
    human_handoff.py          Safety escape hatch
    policy.py                 Auth gate + business rules + allowed-tool list
  data/
    supabase_client.py        Supabase client
    redis_client.py            Upstash Redis client
    models.py                  Pydantic models
    schema.sql                  Full Postgres/pgvector schema
  observability/
    logging_config.py           structlog setup
    call_events.py                Call lifecycle event logging
  utils/
    session.py                    Rate limiting helper
tests/
  test_health.py
```

## Setup

1. **Python deps**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment**
   ```bash
   cp .env.example .env
   # fill in Twilio, OpenRouter, Deepgram, ElevenLabs, Supabase, Upstash keys
   ```

3. **Database**
   - Create a Supabase project, enable the `vector` extension.
   - Run `app/data/schema.sql` in the Supabase SQL editor.
   - Seed `departments`, `doctors`, `doctor_schedules`, and generate
     `appointment_slots` from those schedules (a scheduled job/cron is a
     good place for slot generation — not included in this scaffold).

4. **Run locally**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Expose it publicly for Twilio to reach (e.g. `ngrok http 8000`), then
   set your Twilio phone number's **Voice webhook** to:
   `https://<your-ngrok-domain>/calls/incoming`

5. **Or run via Docker**
   ```bash
   docker compose up --build
   ```

## Notes / what you'll still need to fill in

- **STT/TTS vendors**: this scaffold wires up Deepgram + ElevenLabs; swap
  `app/voice/stt.py` / `tts.py` for other vendors if preferred, keeping the
  same interface.
- **Slot generation**: a scheduled job that expands `doctor_schedules`
  into concrete `appointment_slots` rows on a rolling basis.
- **Knowledge base ingestion**: a script to chunk + embed hospital policy
  documents into the `knowledge_base` table for RAG.
- **Human handoff transfer**: `app/tools/human_handoff.py` sets a flag in
  agent state; wire the actual Twilio `<Dial>` transfer to your staff
  queue/number in `app/api/routes_calls.py` once `handoff_requested` is
  observed.
- **Twilio signature validation** is stubbed in `routes_calls.py` — make
  sure it's enabled (`TWILIO_VALIDATE_SIGNATURE=true`) in production.
- **Testing**: only a basic health-check test is included; add tests per
  tool/policy rule as you build them out.
