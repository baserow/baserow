# Baserow metrics

## The Problem

We want to be able to observe a running instance of Baserow so we can:

1. Understand its performance
2. Diagnose issues and bugs
3. Get insights into usage

## Proposed solution

1. We integrate and configure the [opentelemetry](https://opentelemetry.io/) libraries
   into our applications.
2. In our codebase we add useful logs, metrics and spans.
3. Self-hosting users can set a couple of env vars and fully monitor Baserow themselves.
4. We start using [`loguru`](https://github.com/Delgan/loguru) for all of our Baserow
   logging and configure with OTEL to
   ship logs.

### Why [Open Telemetry](https://opentelemetry.io/)?

We could directly integrate with many specific telemetry and cloud monitoring providers.
However we aren't sure which provider we want to stick with long term. OTEL is the new
modern way of doing telemetry and you can use it to send telemetry to almost any
cloud application monitoring platform. By picking a specific provider we would be
locking ourselves even further into their eco system. By using OTEL we can easily
switch.

For our self-hosting users, OTEL doesn't force them into a specific
platform
but they can monitor Baserow using their existing platform of choice as long as it
supports OTEL.

OTEL is becoming/already is *the* telemetry standard. It's also completely open source!

### Why loguru?

See https://github.com/Delgan/loguru for details. You will find this library highly
recommended in lots of places as a great way to do logging in modern python.

We could just configure the existing `logger` python framework to send all of
it's logs to OTEL. However i'm worried this might send a ton of duplicate
information or just a massive amount of useless information form all of our libraries
etc.

By using `loguru` (which has a bunch of other benefits as a more modern and nicer
to use logging framework for python) we can be sure we are just sending some
specific Baserow application logs and not a ton of bloat from some libraries.

`loguru` Also supports integrating directly with `logging` if we do want to ship
some libraries logs very easily.

`loguru` Additionally supports structured logging. We use it to send structured
logs which aren't just a single line of text, but instead a JSON object with extra
attributes. This way when structured logging is used (only for sending to OTEL
collectors, your actual container logs are still readable) we can easily attach
contextual information to the logs themselves! We can then search for logs which have
various attributes, like "find me all the logs for group 10, user 5 etc".

#### Example loguru code

This is all we need to do to configure loguru to:

1. Have a lovely coloured output in our normal logs
2. Send all logs also with extra attributes to our open telemetry collector
3. Add some attributes to all logging that occurs inside the context:

```python
from loguru import logger

# A slightly customized default loguru format which includes the process id.
loguru_format = (
    f"<magenta>{os.getpid()}|</magenta>"
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>|"
    "<level>{level}</level>|"
    "<cyan>{name}</cyan>:"
    "<cyan>{function}</cyan>:"
    "<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Remove the default loguru stderr sink
logger.remove()
# Replace it with our format, loguru recommends sending application logs to stderr.
logger.add(sys.stderr, format=loguru_format)
logger.info("Logger setup.")
logger.add(get_otel_handler(), format="{message}")
logger.info("Logger open telemetry exporting setup.")


def run_some_async_task(task):
    with logger.contextualize(task=task.id):
        # This log will be enhanced with the task id set by the context call above :) 
        logger.info('Something happened!')
```
