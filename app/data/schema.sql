<<<<<<< HEAD
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
=======
-- ============================================================
-- VOXEVIA
-- Single-Hospital AI Voice Agent Database
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================

create extension if not exists "uuid-ossp";
create extension if not exists "vector";


-- ============================================================
-- HOSPITAL INFORMATION
-- One hospital record for Voxevia
-- ============================================================

create table if not exists hospital_information (
    id uuid primary key default uuid_generate_v4(),

    name text not null,
    address text,
    phone text,
    email text,
    website text,
    description text,
    emergency_phone text,

    working_hours jsonb default '{}'::jsonb,
    services jsonb default '[]'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================
-- DEPARTMENTS
-- ============================================================

create table if not exists departments (
    id uuid primary key default uuid_generate_v4(),

    name text not null unique,
    description text,
    phone text,
    location text,

    status text not null default 'active'
        check (status in ('active', 'inactive')),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================
-- DOCTORS
-- ============================================================

create table if not exists doctors (
    id uuid primary key default uuid_generate_v4(),

    department_id uuid
        references departments(id)
        on delete set null,

    name text not null,
    specialization text,
    qualification text,
    experience_years integer,

    consultation_fee numeric(10,2),

    phone text,
    email text,

    status text not null default 'active'
        check (status in ('active', 'inactive')),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================
-- DOCTOR SCHEDULES
-- Recurring weekly schedule
-- ============================================================

create table if not exists doctor_schedules (
    id uuid primary key default uuid_generate_v4(),

    doctor_id uuid not null
        references doctors(id)
        on delete cascade,

    day_of_week integer not null
        check (day_of_week between 0 and 6),

    start_time time not null,
    end_time time not null,

    slot_duration_minutes integer not null default 30
        check (slot_duration_minutes > 0),

    active boolean not null default true,

    created_at timestamptz not null default now(),

    constraint valid_schedule_time
        check (end_time > start_time),

    constraint unique_doctor_schedule
        unique (doctor_id, day_of_week, start_time)
);


-- ============================================================
-- APPOINTMENT SLOTS
-- Actual bookable slots
-- ============================================================

create table if not exists appointment_slots (
    id uuid primary key default uuid_generate_v4(),

    doctor_id uuid not null
        references doctors(id)
        on delete cascade,

    slot_date date not null,

    start_time time not null,
    end_time time not null,

    status text not null default 'available'
        check (status in (
            'available',
            'booked',
            'blocked'
        )),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint valid_slot_time
        check (end_time > start_time),

    constraint unique_doctor_slot
        unique (doctor_id, slot_date, start_time)
);


-- ============================================================
-- PATIENTS
-- ============================================================

create table if not exists patients (
    id uuid primary key default uuid_generate_v4(),

    patient_number text unique,

    full_name text not null,

    date_of_birth date,
    gender text,

    phone text,
    email text,
    address text,

    emergency_contact text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================
-- APPOINTMENTS
-- ============================================================

create table if not exists appointments (
    id uuid primary key default uuid_generate_v4(),

    patient_id uuid not null
        references patients(id)
        on delete restrict,

    doctor_id uuid not null
        references doctors(id)
        on delete restrict,

    department_id uuid
        references departments(id)
        on delete set null,

    slot_id uuid
        references appointment_slots(id)
        on delete set null,

    appointment_date date not null,

    start_time time not null,
    end_time time not null,

    reason text,

    status text not null default 'scheduled'
        check (status in (
            'scheduled',
            'confirmed',
            'completed',
            'cancelled',
            'no_show'
        )),

    notes text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint valid_appointment_time
        check (end_time > start_time)
);


-- ============================================================
-- KNOWLEDGE DOCUMENTS
-- Hospital information used by RAG
-- ============================================================

create table if not exists knowledge_documents (
    id uuid primary key default uuid_generate_v4(),

    title text not null,

    source text,

    content text not null,

    metadata jsonb default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================
-- KNOWLEDGE CHUNKS
-- Text chunks + embeddings
-- ============================================================

create table if not exists knowledge_chunks (
    id uuid primary key default uuid_generate_v4(),

    document_id uuid not null
        references knowledge_documents(id)
        on delete cascade,

    content text not null,

    embedding vector(1536),

    metadata jsonb default '{}'::jsonb,

    created_at timestamptz not null default now()
);


-- ============================================================
-- VECTOR INDEX
-- ============================================================

create index if not exists idx_knowledge_chunks_embedding
on knowledge_chunks
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);


-- ============================================================
-- CONVERSATIONS
-- ============================================================

create table if not exists conversations (
    id uuid primary key default uuid_generate_v4(),

    phone_number text,

    channel text not null default 'voice',

    status text not null default 'active'
        check (status in (
            'active',
            'completed',
            'failed'
        )),

    started_at timestamptz not null default now(),
    ended_at timestamptz
);


-- ============================================================
-- MESSAGES
-- ============================================================

create table if not exists messages (
    id uuid primary key default uuid_generate_v4(),

    conversation_id uuid not null
        references conversations(id)
        on delete cascade,

    role text not null
        check (role in (
            'user',
            'assistant',
            'system',
            'tool'
        )),

    content text not null,

    created_at timestamptz not null default now()
);


-- ============================================================
-- CALLS
-- ============================================================

create table if not exists calls (
    id uuid primary key default uuid_generate_v4(),

    conversation_id uuid
        references conversations(id)
        on delete set null,

    provider text not null default 'twilio',

    provider_call_id text unique,

    from_number text,
    to_number text,

    direction text not null default 'inbound'
        check (direction in (
            'inbound',
            'outbound'
        )),

    status text not null default 'initiated'
        check (status in (
            'initiated',
            'ringing',
            'in_progress',
            'completed',
            'failed'
        )),

    duration_seconds integer,

    started_at timestamptz,
    ended_at timestamptz,

    created_at timestamptz not null default now()
);


-- ============================================================
-- CALL EVENTS
-- ============================================================

create table if not exists call_events (
    id uuid primary key default uuid_generate_v4(),

    call_id uuid not null
        references calls(id)
        on delete cascade,

    event_type text not null,

    event_data jsonb default '{}'::jsonb,

    created_at timestamptz not null default now()
);


-- ============================================================
-- INDEXES
-- ============================================================

create index if not exists idx_doctors_department
on doctors(department_id);

create index if not exists idx_doctor_schedules_doctor
on doctor_schedules(doctor_id);

create index if not exists idx_appointment_slots_doctor_date
on appointment_slots(doctor_id, slot_date);

create index if not exists idx_appointments_patient
on appointments(patient_id);

create index if not exists idx_appointments_doctor
on appointments(doctor_id);

create index if not exists idx_appointments_date
on appointments(appointment_date);

create index if not exists idx_messages_conversation
on messages(conversation_id);

create index if not exists idx_calls_conversation
on calls(conversation_id);

create index if not exists idx_call_events_call
on call_events(call_id);


-- ============================================================
-- RAG SEARCH FUNCTION
-- ============================================================

create or replace function match_knowledge_chunks (
    query_embedding vector(1536),
    match_count integer default 5
)
returns table (
    id uuid,
    document_id uuid,
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
    content text,
    metadata jsonb,
    similarity float
)
<<<<<<< HEAD
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
=======
language sql
stable
as $$
    select
        kc.id,
        kc.document_id,
        kc.content,
        kc.metadata,
        1 - (kc.embedding <=> query_embedding) as similarity
    from knowledge_chunks kc
    where kc.embedding is not null
    order by kc.embedding <=> query_embedding
    limit match_count;
$$;
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
