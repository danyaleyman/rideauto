-- Sprint B: PostgreSQL index audit cheatsheet
-- Run with:
-- docker-compose exec -T postgres psql -U wra -d wra -f /dev/stdin < deploy/scripts/pg_index_audit.sql

\echo '== table row counts =='
SELECT relname AS table_name, n_live_tup::bigint AS est_rows
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

\echo '== sequential scan pressure =='
SELECT
  relname AS table_name,
  seq_scan,
  idx_scan,
  n_live_tup::bigint AS est_rows,
  CASE WHEN seq_scan + idx_scan = 0 THEN 0
       ELSE round((seq_scan::numeric / (seq_scan + idx_scan)) * 100, 2)
  END AS seq_scan_pct
FROM pg_stat_user_tables
ORDER BY seq_scan DESC, idx_scan ASC;

\echo '== index usage =='
SELECT
  s.relname AS table_name,
  i.relname AS index_name,
  psui.idx_scan,
  pg_size_pretty(pg_relation_size(i.oid)) AS index_size
FROM pg_stat_user_indexes psui
JOIN pg_class i ON i.oid = psui.indexrelid
JOIN pg_class s ON s.oid = psui.relid
ORDER BY psui.idx_scan ASC, pg_relation_size(i.oid) DESC;

\echo '== dead tuples / autovacuum signal =='
SELECT
  relname AS table_name,
  n_live_tup::bigint AS live_rows,
  n_dead_tup::bigint AS dead_rows,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
