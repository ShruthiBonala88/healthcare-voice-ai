-- =========================================================
-- Healthcare Voice AI — Supabase schema
-- Run this in the Supabase SQL editor (or via `supabase db push`)
-- =========================================================

create extension if not exists "uuid-ossp";
create extension if not exists vector;

-- ---------- Core hospital entities ----------

create table if not exists departments (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    description text,
    created_at timestamptz not null default now()
);

create table if not exists doctors (
    id uuid primary key default uuid_generate_v4(),
    first_name text not null,
    last_name text not null,
    department_id uuid references departments(id) on delete set null,
    specialty text,
    bio text,
    created_at timestamptz not null default now()
);

create table if not exists doctor_schedules (
    id uuid primary key default uuid_generate_v4(),
    doctor_id uuid not null references doctors(id) on delete cascade,
    day_of_week smallint not null check (day_of_week between 0 and 6),
    start_time time not null,
    end_time time not null,
    slot_duration_minutes int not null default 30,
    created_at timestamptz not null default now()
);

create table if not exists appointment_slots (
    id uuid primary key default uuid_generate_v4(),
    doctor_id uuid not null references doctors(id) on delete cascade,
    start_at timestamptz not null,
    end_at timestamptz not null,
    is_booked boolean not null default false,
    created_at timestamptz not null default now(),
    unique (doctor_id, start_at)
);
create index if not exists idx_slots_doctor_time on appointment_slots (doctor_id, start_at) where not is_booked;

-- ---------- Patients & appointments ----------

create table if not exists patients (
    id uuid primary key default uuid_generate_v4(),
    first_name text not null,
    last_name text not null,
    phone_number text not null unique,
    email text,
    date_of_birth date,
    created_at timestamptz not null default now()
);

create table if not exists appointments (
    id uuid primary key default uuid_generate_v4(),
    patient_id uuid not null references patients(id) on delete cascade,
    doctor_id uuid not null references doctors(id) on delete cascade,
    slot_id uuid not null references appointment_slots(id) on delete cascade,
    status text not null default 'scheduled'
        check (status in ('scheduled','confirmed','cancelled','completed','no_show')),
    reason text,
    created_at timestamptz not null default now(),
    unique (slot_id)
);

-- ---------- Hospital info / RAG knowledge base ----------

create table if not exists hospital_information (
    id uuid primary key default uuid_generate_v4(),
    title text not null,
    content text not null,
    category text,
    created_at timestamptz not null default now()
);

create table if not exists knowledge_base (
    id uuid primary key default uuid_generate_v4(),
    source text,
    content text not null,
    embedding vector(1536),
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_knowledge_base_embedding
    on knowledge_base using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------- Call telemetry ----------

create table if not exists call_sessions (
    id uuid primary key default uuid_generate_v4(),
    call_sid text not null unique,
    caller_phone_number text not null,
    patient_id uuid references patients(id) on delete set null,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    outcome text
);

create table if not exists call_transcripts (
    id uuid primary key default uuid_generate_v4(),
    call_sid text not null references call_sessions(call_sid) on delete cascade,
    role text not null check (role in ('user','assistant','tool')),
    content text not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_transcripts_call on call_transcripts (call_sid, created_at);

create table if not exists call_events (
    id uuid primary key default uuid_generate_v4(),
    call_sid text not null,
    event_type text not null,
    payload jsonb default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_events_call on call_events (call_sid, created_at);

-- ---------- Helper function for semantic search (used by RAG retriever) ----------

create or replace function match_knowledge_base (
    query_embedding vector(1536),
    match_count int default 5,
    filter jsonb default '{}'::jsonb
)
returns table (
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        knowledge_base.id,
        knowledge_base.content,
        knowledge_base.metadata,
        1 - (knowledge_base.embedding <=> query_embedding) as similarity
    from knowledge_base
    where knowledge_base.metadata @> filter
    order by knowledge_base.embedding <=> query_embedding
    limit match_count;
end;
$$;
