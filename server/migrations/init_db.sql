-- Idempotent migration script for thi-data tables

-- Ensure pg_crypto for gen_random_uuid() if needed (built-in in PG 13+)
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto"

-- Clean up legacy corrupted_rows table so it doesn't shadow DLT's version
DROP TABLE IF EXISTS public.corrupted_rows;

CREATE TABLE IF NOT EXISTS public.file_registry (
  file_id uuid NOT NULL DEFAULT gen_random_uuid(),
  object_key text NOT NULL,
  status text,
  target_table_name text,
  error_message text,
  CONSTRAINT file_registry_pkey PRIMARY KEY (file_id)
);

CREATE TABLE IF NOT EXISTS public.metadata_creation (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  table_name text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by text NOT NULL,
  CONSTRAINT metadata_creation_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.metadata_updates (
  id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  foreign_key uuid NOT NULL DEFAULT gen_random_uuid(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_by text NOT NULL,
  CONSTRAINT metadata_updates_pkey PRIMARY KEY (id),
  CONSTRAINT metadata_updates_foreign_key_fkey FOREIGN KEY (foreign_key) REFERENCES public.metadata_creation(id)
);

CREATE TABLE IF NOT EXISTS public.test_database (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  first_name text NOT NULL,
  last_name text,
  age smallint,
  CONSTRAINT test_database_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.thi_database (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  first_name text NOT NULL,
  last_name text,
  age integer,
  CONSTRAINT thi_database_pkey PRIMARY KEY (id)
);
