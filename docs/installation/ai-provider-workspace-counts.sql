-- Read-only sizing inventory; counts are not validated import candidates.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';

SELECT trashed, count(*) AS workspace_rows,
       count(*) FILTER (WHERE generative_ai_models_settings IS NOT NULL
         AND generative_ai_models_settings NOT IN ('{}'::jsonb, 'null'::jsonb))
         AS nonempty_settings,
       count(*) FILTER (WHERE jsonb_typeof(generative_ai_models_settings)
         NOT IN ('object', 'null')) AS malformed_workspace_settings
FROM core_workspace GROUP BY trashed ORDER BY trashed;

WITH entries AS (
  SELECT w.trashed, p.key AS provider_type, p.value AS config
  FROM core_workspace w
  CROSS JOIN LATERAL jsonb_each(CASE
    WHEN jsonb_typeof(w.generative_ai_models_settings) = 'object'
    THEN w.generative_ai_models_settings ELSE '{}'::jsonb END) p
), described AS (
  SELECT *, CASE WHEN provider_type = 'ollama'
    THEN config->'host' ELSE config->'api_key' END AS connection_value
  FROM entries
)
SELECT trashed,
  CASE WHEN provider_type IN ('openai', 'anthropic', 'mistral', 'ollama', 'openrouter')
    THEN provider_type ELSE '(unsupported key)' END AS provider_type,
  count(*) AS stored_provider_entries,
  count(*) FILTER (WHERE jsonb_typeof(config) <> 'object') AS non_object_entries,
  count(*) FILTER (WHERE jsonb_typeof(config) = 'object' AND NOT coalesce(
    jsonb_typeof(connection_value) = 'string'
      AND btrim(connection_value #>> '{}', E' \t\n\r\f\013') <> '', false))
    AS missing_or_non_string_connection,
  count(*) FILTER (WHERE config->'models' IS NOT NULL
    AND jsonb_typeof(config->'models') NOT IN ('array', 'string', 'null'))
    AS unexpected_models_type,
  sum(CASE jsonb_typeof(config->'models')
    WHEN 'array' THEN jsonb_array_length(config->'models')
    WHEN 'string' THEN cardinality(string_to_array(config->>'models', ','))
    ELSE 0 END) AS model_entries_before_normalization
FROM described
GROUP BY trashed,
  CASE WHEN provider_type IN ('openai', 'anthropic', 'mistral', 'ollama', 'openrouter')
    THEN provider_type ELSE '(unsupported key)' END
ORDER BY trashed, provider_type;

COMMIT;
