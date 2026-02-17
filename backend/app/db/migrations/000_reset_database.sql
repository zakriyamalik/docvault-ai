-- WARNING: This resets all tables for PostgreSQL conversion
-- Drop tables if they exist (clean slate)
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS faiss_index_map CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS migrations_applied CASCADE;
