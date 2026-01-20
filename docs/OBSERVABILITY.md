# Observability & Telemetry

Shotgun includes built-in observability with PostHog for analytics and exception tracking, and Logfire for logging and tracing. All services track users anonymously using a UUID generated on first run.

## Anonymous User Tracking

Each user gets a unique anonymous ID stored in their config:

```bash
# Get your anonymous user ID
shotgun config get-user-id
```

This ID is automatically included in:
- **PostHog**: Analytics, feature usage, and exception tracking
- **Logfire**: All logs, traces, and spans

## Privacy Commitments

- **No PII collected**: Only anonymous UUIDs are used for identification
- **Opt-in for development**: Telemetry requires explicit environment variables
- **Automatic in production**: Production builds include telemetry for error tracking
- **Transparent**: All telemetry code is open source

## Setting Up Observability (Development)

### Logfire Setup

For local development with Logfire:

```bash
# Set environment variables (SHOTGUN_ prefix required)
export SHOTGUN_LOGFIRE_ENABLED=true
export SHOTGUN_LOGFIRE_TOKEN=your-logfire-token

# Run shotgun - will now send logs to Logfire
shotgun research "topic"
```

### PostHog Setup

For PostHog analytics and exception tracking (automatically configured in production builds):

```bash
# Set for local development (SHOTGUN_ prefix required)
export SHOTGUN_POSTHOG_API_KEY=your-posthog-api-key
export SHOTGUN_POSTHOG_PROJECT_ID=your-posthog-project-id
```

### Environment Variable Prefix

All telemetry environment variables use the `SHOTGUN_` prefix to avoid conflicts with other tools. In production builds, these values are embedded at build time via Hatch build hooks.

## Logfire Queries

Logfire uses SQL for querying logs. Here are helpful queries for debugging and analysis.

### Find All Logs for a Specific User

```sql
SELECT * FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
ORDER BY timestamp DESC;
```

### Track User Actions

```sql
SELECT
  timestamp,
  span_name,
  message,
  attributes
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND span_name LIKE '%research%'
ORDER BY timestamp DESC;
```

### Find Slow Operations for a User

```sql
SELECT
  span_name,
  duration_ms,
  attributes
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND duration_ms > 1000
ORDER BY duration_ms DESC;
```

### Find Errors for a User

```sql
SELECT * FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND level = 'error'
ORDER BY timestamp DESC;
```

### Analyze User's AI Provider Usage

```sql
SELECT
  attributes->>'provider' as provider,
  COUNT(*) as usage_count,
  AVG(duration_ms) as avg_duration
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND attributes->>'provider' IS NOT NULL
GROUP BY provider;
```

### Track Feature Usage by User

```sql
SELECT
  span_name,
  COUNT(*) as usage_count
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND span_name IN ('research', 'plan', 'tasks')
GROUP BY span_name
ORDER BY usage_count DESC;
```

### Find All Users with Errors

```sql
SELECT
  attributes->>'user_id' as user_id,
  COUNT(*) as error_count,
  MAX(timestamp) as last_error
FROM records
WHERE level = 'error'
GROUP BY attributes->>'user_id'
ORDER BY error_count DESC;
```

### Identify Performance Bottlenecks

```sql
SELECT
  span_name,
  AVG(duration_ms) as avg_duration,
  MAX(duration_ms) as max_duration,
  COUNT(*) as call_count
FROM records
WHERE duration_ms IS NOT NULL
GROUP BY span_name
HAVING AVG(duration_ms) > 500
ORDER BY avg_duration DESC;
```

### Track Version Adoption

```sql
SELECT
  attributes->>'version' as version,
  COUNT(DISTINCT attributes->>'user_id') as unique_users,
  COUNT(*) as total_calls
FROM records
WHERE attributes->>'version' IS NOT NULL
GROUP BY attributes->>'version'
ORDER BY unique_users DESC;
```

## PostHog Usage

### Exception Tracking

PostHog automatically captures exceptions via `enable_exception_autocapture=True`. User-actionable errors (like context size limits, rate limits) are filtered out as they represent expected conditions, not bugs.

Each exception includes:
- User ID (anonymous UUID)
- Shotgun version
- Environment (production/development)
- Exception type and message
- Stack trace

### Tracked Events

PostHog tracks:
- Feature usage (research, plan, tasks, spec, export)
- Command execution
- Configuration changes
- Update checks
- Unknown tool encounters (for debugging)

### Spec Operations Events

- `spec_pull_started` - Spec download initiated (properties: source)
- `spec_pull_completed` - Spec download successful (properties: source, file_count, total_bytes, duration_seconds, had_backup)
- `spec_pull_failed` - Spec download failed (properties: source, error_type, phase)
- `spec_pull_cancelled` - Spec download cancelled by user (properties: source, phase)
- `spec_upload_started` - Spec upload initiated
- `spec_upload_completed` - Spec upload successful (properties: file_count, total_bytes, duration_seconds)
- `spec_upload_failed` - Spec upload failed (properties: error_type, phase, files_uploaded, bytes_uploaded)

### Authentication Events

- `auth_started` - Authentication flow initiated
- `auth_completed` - Authentication successful (properties: duration_seconds)
- `auth_failed` - Authentication failed (properties: phase, error_type)
- `auth_cancelled` - Authentication cancelled by user

### Viewing Analytics

1. Log into PostHog dashboard
2. Filter by user ID or cohorts
3. View funnels and user paths
4. Track feature adoption
5. Analyze usage patterns

### Custom Events

To add custom event tracking:

```python
from shotgun.posthog_telemetry import track_event

track_event("event_name", {
    "property1": "value1",
    "property2": "value2"
})
```

### Manual Exception Capture

For exceptions that need to be explicitly captured:

```python
from shotgun.posthog_telemetry import capture_exception

try:
    risky_operation()
except Exception as e:
    capture_exception(e, properties={"context": "additional info"})
    raise
```

Note: `UserActionableError` exceptions are automatically filtered out.

## Debugging with Telemetry

### For Users

If you encounter an issue:

1. Get your user ID: `shotgun config get-user-id`
2. Note the time the error occurred
3. Share your user ID with maintainers
4. Maintainers can query Logfire/PostHog for your specific logs

### For Maintainers

When debugging user issues:

1. Get user ID from issue report
2. Query Logfire for logs around reported time
3. Check PostHog for any exceptions
4. Review PostHog for user's recent activity
5. Analyze patterns across similar users

## Disabling Telemetry

Telemetry is automatically included in production builds. For development:

- Don't set telemetry environment variables to keep it disabled
- Telemetry initialization will gracefully fail without tokens
- All functionality works without telemetry

## Production Builds

In production builds (via Hatch):

- Telemetry tokens are embedded at build time
- `SHOTGUN_` prefixed environment variables are read during build
- Tokens are not included in source code
- Users cannot disable production telemetry (anonymous only)

## Additional Resources

- [Logfire Documentation](https://logfire.pydantic.dev/)
- [PostHog Documentation](https://posthog.com/docs)
- [Pydantic Logfire Python SDK](https://logfire.pydantic.dev/docs/integrations/python/)
