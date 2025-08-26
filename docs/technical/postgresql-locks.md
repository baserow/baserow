# PostgreSQL locking and Baserow

## Exceeding `max_locks_per_transaction`

In a handful of Baserow features, such as snapshotting and duplicating, we take the specified database and fetch all of its tables
to perform operations on them.

Unfortunately if the total number of tables in the database is very high (i.e. 5,000-10,000), it's possible to exceed
the total number of locks specified in [PostgreSQL's `max_locks_per_transaction`](https://www.postgresql.org/docs/current/runtime-config-locks.html)
configuration setting.

To resolve this, the steps are as follows:

1. Find the path to your `postgresql.conf`. In `psql` this can be found with `SHOW config_file`.
2. Edit the file, and find `max_locks_per_transaction`.
3. Increase the value. The new value will depend on a number of factors, such as what [`max_connections`](https://www.postgresql.org/docs/current/runtime-config-connection.html#GUC-MAX-CONNECTIONS) and [`max_prepared_transactions`](https://www.postgresql.org/docs/current/runtime-config-resource.html#GUC-MAX-PREPARED-TRANSACTIONS) are set to. We recommend experimenting with higher values.
4. For the new value to effect, restart postgresql.

If you are hosting Baserow with a managed database, please ask your hosting provider how `max_locks_per_transaction`
can be increased, they may be able to increase it for you.
