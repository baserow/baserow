# Adding a new job type

Use a `JobType` for user-triggered async work that needs progress,
cancellation, and frontend visibility. If the work is fire-and-forget, use a
[plain Celery task](celery-tasks.md). For runtime details see
[Jobs](../technical/jobs.md).

## Files You Usually Touch

| Layer | File | Purpose |
|---|---|---|
| Backend | `<app>/models.py` | `Job` subclass with type-specific columns. |
| Backend | `<app>/job_types.py` | `JobType` subclass and `run()`. |
| Backend | `<app>/apps.py` | Register with `job_type_registry`. |
| Backend API | `api/<app>/views.py`, `urls.py` | Type-specific create endpoint. |
| Frontend | `modules/<app>/jobTypes.js` | Frontend `JobType`. |
| Frontend | `modules/<app>/plugin.js` | Register in `$registry`. |
| Frontend | `modules/<app>/services/...js` | Start-job endpoint wrapper. |
| Frontend | Component | Starts the job and displays progress. |

There is no generic job-create endpoint. Each domain owns its URL and request
serializer.

## Backend Model

```python
from django.db import models
from baserow.core.jobs.models import Job

class CountRowsJob(Job):
    table = models.ForeignKey("database.Table", on_delete=models.CASCADE)
    result = models.BigIntegerField(null=True)
```

Generate a migration. If the job needs audit user/IP fields, mix in
`JobWithUserIpAddress` before `Job`.

## Backend `JobType`

Required: `type`, `model_class`, and `run`.

```python
from rest_framework import serializers
from baserow.core.jobs.registries import JobType

class CountRowsJobType(JobType):
    type = "count_rows"
    model_class = CountRowsJob
    max_count = 3

    serializer_field_names = ["table_id", "result"]
    request_serializer_field_names = ["table_id"]

    @property
    def serializer_field_overrides(self):
        return {
            "table_id": serializers.IntegerField(),
            "result": serializers.IntegerField(read_only=True),
        }

    def prepare_values(self, values, user):
        table = TableHandler().get_table(values["table_id"])
        CoreHandler().check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )
        return {"table": table}

    def run(self, job, progress):
        progress.set_progress(0)
        job.result = job.table.get_model().objects.count()
        job.save()
        progress.set_progress(100)
```

`prepare_values` validates all user-supplied ids and permissions before the row
is created. `run` must call `progress.set_progress(...)` often enough for the
UI and cancellation to work.

Common hooks:

- `after_job_creation(job, values)`: save files or other state that needs the
  job id.
- `transaction_atomic_context(job)`: change isolation or avoid the wrapping
  transaction.
- `before_delete(job)`: clean up files, scratch tables, or external state.
- `on_cancelled(job)` / `on_error(job, error)`: side effects that should survive
  rollback.
- `_can_schedule_or_raise(...)`: job-specific concurrency rules; call `super()`
  to keep the `max_count` cap.

Register in `apps.py`:

```python
job_type_registry.register(CountRowsJobType())
```

## REST Endpoint

The endpoint authenticates, validates, starts the job, and returns the job
serializer:

```python
class CountRowsView(APIView):
    permission_classes = [IsAuthenticated]

    @validate_body(CountRowsJobType().request_serializer_class)
    @map_exceptions(CountRowsJobType().api_exceptions_map)
    def post(self, request, data):
        job = JobHandler().create_and_start_job(
            request.user,
            CountRowsJobType.type,
            **data,
        )
        return Response(CountRowsJobType().response_serializer_class(job).data)
```

`create_and_start_job` creates the row, runs `after_job_creation`, checks
concurrency, and enqueues `run_async_job.delay(job.id)` from
`transaction.on_commit(...)`.

## Frontend `JobType`

The frontend type controls how the job appears in the sidebar and which
workspace/application it belongs to:

```javascript
import { JobType } from '@baserow/modules/core/jobTypes'

export class CountRowsJobType extends JobType {
  static getType() {
    return 'count_rows'
  }

  getName() {
    return this.app.$i18n.t('countRowsJobType.name')
  }

  isJobPartOfApplication(job, application) {
    return job.table?.database_id === application.id
  }
}
```

Register it from the module's `plugin.js`:

```javascript
$registry.register('job', new CountRowsJobType(context))
```

The frontend `getType()` must match the backend `type`.

## Start and Display

The host component owns the type-specific create request, then hands the returned
job to the shared job machinery:

```javascript
const { data: job } = await CountRowsService(this.$client).start(table.id)
await this.createAndMonitorJob(job)
```

Use `modules/core/mixins/job.js` when working in an options-API component. It
provides reactive state such as `jobIsRunning`, `jobIsFinished`,
`jobHumanReadableState`, `createAndMonitorJob(job)`, and `cancelJob()`.

New locale strings go in `en.json` only.

## Checklist

- [ ] Backend model, migration, `JobType`, registration, endpoint, and route.
- [ ] Backend and frontend type strings match.
- [ ] `prepare_values` validates permissions for every user-supplied id.
- [ ] `run` reports progress and therefore checks cancellation.
- [ ] Cleanup hooks cover files or scratch state outside Django cascade.
- [ ] Frontend `JobType`, registration, service, and component are wired.
- [ ] Sidebar scope methods return correct workspace/application membership.
- [ ] Backend tests cover success, failure, cancellation where relevant.
- [ ] Frontend tests cover visible state transitions.

## Related

- [Jobs](../technical/jobs.md).
- [Celery](../technical/celery.md).
- [Celery tasks](celery-tasks.md).
- [Creating a feature](creating-features.md).
