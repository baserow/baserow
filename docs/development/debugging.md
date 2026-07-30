# Debugging Tools

Baserow development dependencies include some useful tools for debugging that you can use.

## snoop

[snoop](https://github.com/alexmojaki/snoop) is a powerful set of Python debugging tools.

### Automatic tracing

One of the common things to do is to use the `@snoop` decorator or the `snoop` context manager to trace the execution of a piece of Python code and show how variable values change over time:

```python
@snoop
def test():
    for i in range(5):
        a = i*2

# or

with snoop:
    for i in range(5):
        a = i*2
```

The depth can be controlled with `depth` parameter, e.g. `@snoop(depth=2)` for tracing functions that go deep.

Objects and dictionaries can be expanded automatically to show all their items or attributes using the `watch_explode` parameter taking a list of watched variable names:

```python
@snoop(watch_explode=['d'])
def test():
    d = {'key1': 0, 'key2': 1}
    for i in range(5):
        d["key1"] += 1
```

### Pretty printing

Besides automatic tracing, variables can be pretty printed manually with `pp` function:

```python
d = {'key1': 0, 'key2': 1}
pp(d)
```

Note that `import snoop` or `from snoop import pp` is not necessary as snoop is installed and available automatically.

## django-extensions

[django-extensions](https://github.com/django-extensions/django-extensions) is available to provide a variety of features like a shell with auto-imported Django models or a command to list all registered urls.

You can use django-extensions commands inside backend docker containers:

- `django-admin shell_plus` starts an interactive Python shell with loaded Django contexts and imported models.
- `django-admin show_urls` lists all registered urls in the Baserow.

## django-silk

[django-silk](https://github.com/jazzband/django-silk) is a live profiling and inspection tool for executed requests and database queries.

The interface can be accessed at http://localhost:8000/silk/ after Baserow is started in the debug mode. Every request is logged and can be analyzed, including the list of performed database queries.

django-silk can be also configured and used for profiling using the Python's built-in profiler, see the official documentation for details.

Silk adds profiling overhead to every development request. To disable it when measuring
request or OpenTelemetry performance, set `BASEROW_ENABLE_SILK=off` in
`.env.docker-dev` and recreate the backend container with
`just dc-dev up -d backend`. A plain container restart does not reload its environment.
Direct Docker Compose usage reads the same value from its selected environment or
`.env` file.

## flower

[Flower](https://flower.readthedocs.io/en/latest/) is an open source web application for
monitoring and managing Celery clusters. It provides real-time information about the
status of Celery workers and tasks.

The interface can be accessed at http://localhost:5555/ after the Baserow development
environment has started.
