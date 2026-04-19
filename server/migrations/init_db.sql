-- Idempotent migration script for thi-data tables

-- Ensure pg_crypto for gen_random_uuid() if needed (built-in in PG 13+)
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto"

-- Ensure the DLT dataset schema exists for the ETL pipeline
CREATE SCHEMA IF NOT EXISTS clinical_data;

-- Clean up legacy corrupted_rows table so it doesn't shadow DLT's version
DROP TABLE IF EXISTS public.corrupted_rows;

CREATE TABLE IF NOT EXISTS public.file_registry (
  file_id uuid NOT NULL DEFAULT gen_random_uuid(),
  object_key text NOT NULL,
  status text,
  target_table_name text,
  error_message text,
  uploaded_by text,
  CONSTRAINT file_registry_pkey PRIMARY KEY (file_id)
);
-- Idempotent backfill for existing deployments that predate the uploaded_by column
ALTER TABLE public.file_registry ADD COLUMN IF NOT EXISTS uploaded_by text;

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

-- Better Auth core schema. Quoted identifiers are required: "user" is reserved,
-- and all columns use camelCase to match the library's default Kysely mappings.
CREATE TABLE IF NOT EXISTS public."user" (
  "id" text PRIMARY KEY,
  "name" text NOT NULL,
  "email" text NOT NULL UNIQUE,
  "emailVerified" boolean NOT NULL DEFAULT false,
  "image" text,
  "createdAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public."session" (
  "id" text PRIMARY KEY,
  "expiresAt" timestamp NOT NULL,
  "token" text NOT NULL UNIQUE,
  "createdAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "ipAddress" text,
  "userAgent" text,
  "userId" text NOT NULL REFERENCES public."user"("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public."account" (
  "id" text PRIMARY KEY,
  "accountId" text NOT NULL,
  "providerId" text NOT NULL,
  "userId" text NOT NULL REFERENCES public."user"("id") ON DELETE CASCADE,
  "accessToken" text,
  "refreshToken" text,
  "idToken" text,
  "accessTokenExpiresAt" timestamp,
  "refreshTokenExpiresAt" timestamp,
  "scope" text,
  "password" text,
  "createdAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public."verification" (
  "id" text PRIMARY KEY,
  "identifier" text NOT NULL,
  "value" text NOT NULL,
  "expiresAt" timestamp NOT NULL,
  "createdAt" timestamp DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" timestamp DEFAULT CURRENT_TIMESTAMP
);
