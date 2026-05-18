# Baserow Data Backups

We need to be able to back-up all Baserow data for disaster recovery. There are a number
of ways to do this detailed below, followed by proposal of which solution to pick.

With a back-up solution ideally we are looking for:

* A consistent back-up
* A process that works on a running, production version of Baserow without impacting
  user performance or preventing them from deleting or altering Baserow tables
* A solution that can handle hundreds of thousands of tables (this is common in a large
  Baserow database) or ideally an arbitrary number of tables

## Option 1: pg_dump the entire database at once

[pg_dump](https://www.postgresql.org/docs/11/app-pgdump.html) is the standard logical
back-up tool for Postgres. It essentially generates a big SQL script which when run
recreates the backed-up database.

To do this, pg_dump takes
an [ACCESS SHARE](https://www.postgresql.org/docs/11/explicit-locking.html)
table level lock on all tables it wants to dump, for all tables at once in a single
transaction. This is to guarantee it will get a constant snapshot of the data across the
tables. Unfortunately this means that pg_dump will need to hold a lock per table all in
the same transaction. Postgres controls how many locks a single transaction can hold at
once with the
(`max_locks_per_transaction`)[https://www.postgresql.org/docs/11/runtime-config-locks.html]
configuration parameter, which defaults to 64. Baserow creates an actual Postgres
database table per Baserow table resulting in a potentially huge number of tables in the
database, which will continue to grow over time. This means if we want to pg_dump the
entire database at once, we would need to set `max_locks_per_transaction` to at-least be
the number of tables in the database. This is unfeasible as we would need to set this to
a huge number, or be constantly updating it. Additionally, we would then need to
configure other related config parameters to ensure Postgresql has enough shared memory
to open that many locks at
once [1](https://stackoverflow.com/questions/59092696/can-max-locks-per-transaction-be-increased-to-a-very-large-amount)
, [2](https://dba.stackexchange.com/questions/77928/postgresql-complaining-about-shared-memory-but-shared-memory-seems-to-be-ok)
. This is undesirable as our back-up process would over time require an increasing
amount of shared memory and potentially encounter unsupported behaviour with huge
numbers of tables.

Another problem with pg_dump taking out an ACCESS SHARE lock on all tables during the
back-up process is that during this time users cannot delete or alter tables and will
receive database errors.

## Option 2: run pg_dump multiple times on sub sets of the database 

To avoid the `max_locks_per_transaction` issue encountered in Option 1 we could instead
use the various pg_dump parameters to only dump a smaller part of the database. Then you
could split the backup over multiple separate pg_dump commands/transactions. Also, this
method still has the problem of preventing users altering fields or deleting tables
whilst pg_dump for that particular table is running.

One way of doing this would be using the `-t` pg_dump parameter and dumping each table
at once. However here we run into data consistency issues. What if we dump a through
relation table, then a user deletes a row referenced in that table before we are able to
dump the related table.

We could do something "smarter" by calculating all the connected tables and dumping them
in one transaction. However that seems overly complex, and you still result in a
database backup which isn't from a single snapshot in time. What if users are using
tables in a "related" fashion without using actual FK's, after a restore they could see
very odd results.

Finally, this method also means we could need to come up with our own custom script to
find all the tables/workspaces of tables to back-up, loop over them running pg_dump many
times, and then somehow combine the resulting SQL scripts and store them. It also means
we can't use pg_dump's built in non SQL script output formats it provides, like the
custom compressed format or the directory format, as we need to stitch together
different pg_dump result files. Or if we did use the custom formats we would need
another custom baserow restore script which knew how to loop over the many different
back-up files comprising of a single backup. This custom script would also be a
dangerous source of bugs, what happens if we accidentally miss out some key tables or
database objects from our custom back-up logic.

### Advantages

1. Can generate human-readable SQL
1. Uses minimal disk space when compressed
1. Can directly run pg_restore to apply a back-up to any existing postgres database,
   managed or not
1. If outputting as SQL then the back-up is super compatible as long as the SQL it uses
   is supported by future postgres versions
1. If outputting as compressed pg_dump custom file formats then still future versions of
   postgres are back-wards compatible. However older versions of postgres might not be
   supported.

### Disadvantages

1. Not consistent across the entire DB, but consistent enough due to
1. If run on a live DB users will be prevented from altering / deleting tables for the
   portion of the back-up run over their table
1. Requires custom Baserow logic to split up the big pg_dump into many smaller ones
1. Higher chance of bugs in back-up due to having to do custom logic
1. Long running back-ups will not include any changes made during the back-up period

## Option 3: fork the database and then run pg_dump (Chosen solution)

We could fork the database in digital ocean, hopefully then we could do Option 1 if we
then manually raised `max_locks_per_transaction` for the fork (assuming this scales to
hundreds of thousands of tables!), or instead do Option 2 as because it is a non-live
fork and no longer be updated the back-up we generate will be consistent. In reality
we cannot raise `max_locks_per_transaction` without making support ticket on a managed
Digital Ocean postgres cluster so instead we had to go with this Option combined with
Option 2.

### Advantages
1. If digital ocean's forking works well they are doing the hard part for us
1. The same advantages of Option 1 and/or 2 but without the disadvantages of ending up
   with an inconsistent snapshot or having to raise config parameters to insane levels
   on a live production database, but instead do that on a temporary non public fork

### Disadvantages
1. You have to pay for the fork whilst it is running
1. Still involves custom Baserow logic/scripting if Option 2 is used with this one.
1. Harder to automate, might require us to manually click fork in Digital ocean, ensure
   the new fork spins up, then trigger another script and then tear it manually down
1. Every single backup will take time to fork + time to pg_dump to do, which might be 
   ages

## Option 4: pg_basebackup (Potential Future solution)

>
> We were not able to use this option as it is not possible to open a replication
> connection to a managed Digital Ocean postgres cluster, which is required to run
> pg_basebackup. In the future if Baserow switches to a different provider where this
> is possible and we want to start doing live back-ups directly on the production
> database then we should re-visit this option.
> 

[pg_basebackup](https://www.postgresql.org/docs/11/app-pgbasebackup.html) is another
built-in Postgres back-up tool which works at the file-system level and not logically
like pg_dump. As a result it does not need to open and hold any locks over tables, nor
does it affect clients who are connected and using the database. I believe this exact
command is what Digital Ocean is doing when a managed cluster is forked. So you could
see this solution as us manually forking the database. The advantage being is that
we end up with the actual back-up files for the fork, which we could then archive. Which
might be preferable compared to forking -> then running some sort of pg_dump -> then
archiving as we skip the middle step and just get the archive files immediately.

### Advantages

1. Single well-supported postgres builtin command, no custom Baserow logic needed
1. Generates tarred, compressed backup files automatically
1. No locks taken out on the database
1. Can be run on a live database with no impact on clients
1. If self-hosting our own database in the future then this is pre-requisite for point
   in time recovery and replicas
1. Back-up is completely consistent (if the transaction logs are included)
1. True clone of database, no chance of missing some schemas or objects etc
1. Back-up of database will include all changes made to the database whilst the back-up
   is running when running with `-X stream`! So say if the back-up takes an hour, you
   won't be missing that hours worth of data when it finishes.
1. Should be comparable in speed with digital oceans fork, and only when you actually
   need to restore do you need to do any potential pg_dumping of a copy at that point,
   instead of having to do that for every single backup compared to option 3.

### Disadvantages

1. Only works if the major version of the target Postgres is the same and if both are
   running the same operating system
1. More low level and somewhat harder to understand than pg_dump
1. The backups a direct copy of the postgres file system, indexes and all, meaning more
   disk space will be used compared to pg_dump
1. Can't directly restore into an existing running postgres cluster without taking it
   down and replacing all of its main files
1. Restore steps are more complex and require filesystem access to the cluster
1. The back-up files are not human-readable SQL but instead raw postgres binary data
1. Can't directly restore from back-up straight into a Digital Ocean managed DB
    1. To do this you will have to launch you own postgres server where you do have file
       system access using the back-up
    1. Then once restored to your own DB you would need generate a normal compressed
       dump using pg_dump and then use pg_restore to load into the remote managed
       cluster.
    1. The same issues outlined above with pg_dump will still potentially stand with
       this method. Hopefully it is much easier to say,
       raise `max_locks_per_transaction` to the correct value in this temporary not live
       database to generate the pg_dump file successfully.

We also need to be slightly more careful with how exactly we run pg_basebackup as it is
possible to create backups without transaction logs. If we did not have the transaction
logs included (also known as WALs), it is almost certain that the backup is corrupted
and un-usable.
See https://www.cybertec-postgresql.com/en/pg_basebackup-creating-self-sufficient-backups/
for more details. As long as we properly understand what pg_basebackup is doing, test
the resulting command line script works and test it can be used to recover Baserow, we
are fine.

# Chosen Solution

In the end due to limitations with the Digital Ocean managed cluster we went with
Option 2 combined with Option 3. Two new scripts `backup_baserow` and `restore_baserow`
were made which split the database into chunks to `pg_dump` separately and store in a 
tar. This is literally the only way we could back-up the DO cluster without making
support tickets for them to manually change the config. Additionally, we need this 
script even if we went with Option 4 as once the basedump has been made we still need
to turn it into something that can be pg_restored, and being able to do that without
having to modify `max_locks_per_transaction` is a useful ability.






