import asyncio
import time
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels_redis.core import RedisChannelLayer

from baserow.core.utils import grouper

# A live process empties its mailbox within milliseconds, so it is nearly always
# empty. A dead one fills up to the capacity and stays full: its messages are only
# removed when they expire, and are then replaced right away. Both are a part of
# the message expiry, because no message in a mailbox gets older than that.
DEAD_WHEN_FULL_FOR_PART_OF_EXPIRY = 1 / 6
DEAD_WHEN_UNREAD_FOR_PART_OF_EXPIRY = 1 / 2
# A process that looks dead is looked at a second time, so that a live one that was
# only behind for a moment keeps its memberships.
SECOND_LOOK_AFTER_SECONDS = 2
BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Removes the channel group memberships of ASGI processes that no longer "
        "exist. A process that is killed or restarted never removes its websocket "
        "connections from their channel groups, so every realtime message keeps "
        "being copied to them in Redis until the group expiry passes. It also "
        "removes the memberships that are older than the group expiry, which only "
        "happens by itself when a message is sent to the group. The channel layer "
        "renews the memberships of live connections and lets the others expire "
        "within minutes, so this is only needed once after upgrading from a "
        "version that kept them for a day. Don't run it during a deployment: "
        "processes of a version that doesn't renew yet would lose the memberships "
        "of their live connections."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be removed without making any changes.",
        )

    def handle(self, *args, **options):
        channel_layer = get_channel_layer()
        if not isinstance(channel_layer, RedisChannelLayer):
            raise CommandError("This only works with the Redis channel layer.")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN mode: nothing is removed."))
        async_to_sync(self.cleanup)(channel_layer, options["dry_run"])

    async def cleanup(self, channel_layer: RedisChannelLayer, dry_run: bool):
        # The connections of the channel layer itself, so that every way it can be
        # configured to reach Redis works here too.
        try:
            await self._cleanup(channel_layer, dry_run)
        finally:
            await channel_layer.close_pools()

    async def _cleanup(self, channel_layer: RedisChannelLayer, dry_run: bool):
        # The same moment the channel layer uses when it sends to a group.
        expired_at = int(time.time()) - channel_layer.group_expiry

        self.stdout.write("Finding the channel groups...")
        groups = []
        for index in range(channel_layer.ring_size):
            connection = channel_layer.connection(index)
            async for key in connection.scan_iter(
                channel_layer._group_key("*"), count=5000
            ):
                groups.append((index, key))

        self.stdout.write(f"Reading the members of {len(groups)} groups...")
        members_per_group = {}
        # With one channel of each process, because the capacity of a mailbox is
        # configured by channel name.
        processes = {}
        memberships = Counter()
        expired = Counter()
        for batch in grouper(BATCH_SIZE, groups):
            pipelines = {}
            for index, key in batch:
                if index not in pipelines:
                    pipelines[index] = channel_layer.connection(index).pipeline(
                        transaction=False
                    )
                pipelines[index].zrange(key, 0, -1, withscores=True)
            results = {
                index: iter(await pipeline.execute())
                for index, pipeline in pipelines.items()
            }
            for index, key in batch:
                members = []
                for member, score in next(results[index]):
                    channel = member.decode()
                    if score <= expired_at:
                        expired[key] += 1
                    elif "!" in channel:
                        # Only the channels of websocket consumers belong to a
                        # process.
                        process = channel_layer.non_local_name(channel)
                        processes.setdefault(process, channel)
                        members.append((member, process))
                        memberships[process] += 1
                members_per_group[(index, key)] = members

        self.stdout.write(f"Checking the mailboxes of {len(memberships)} processes...")
        dead = await self._get_dead_processes(channel_layer, processes)
        for process in dead:
            self.stdout.write(
                f"  {process} is dead: {memberships[process]} memberships"
            )
        dead_memberships = sum(memberships[process] for process in dead)
        self.stdout.write(
            f"{len(dead)} of {len(memberships)} processes are dead, with "
            f"{dead_memberships} memberships. {sum(expired.values())} memberships "
            f"in {len(expired)} groups are older than the group expiry."
        )
        if dry_run:
            return

        removed = 0
        pipelines = {}
        for (index, key), members in members_per_group.items():
            if index not in pipelines:
                pipelines[index] = channel_layer.connection(index).pipeline(
                    transaction=False
                )
            pipeline = pipelines[index]
            dead_members = [member for member, process in members if process in dead]
            for dead_members_batch in grouper(BATCH_SIZE, dead_members):
                pipeline.zrem(key, *dead_members_batch)
            if key in expired:
                pipeline.zremrangebyscore(key, min=0, max=expired_at)
            if len(pipeline) >= BATCH_SIZE:
                removed += sum(await pipeline.execute())
        for pipeline in pipelines.values():
            removed += sum(await pipeline.execute())
        for process in dead:
            mailbox = self._get_mailbox(channel_layer, process)
            # The messages the process was handling when it died never expire.
            await self._get_mailbox_connection(channel_layer, process).unlink(
                mailbox, channel_layer._backup_channel_name(mailbox)
            )
        self.stdout.write(self.style.SUCCESS(f"Removed {removed} memberships."))

    def _get_mailbox(self, channel_layer: RedisChannelLayer, process: str) -> str:
        return channel_layer.prefix + process

    def _get_mailbox_connection(self, channel_layer: RedisChannelLayer, process: str):
        return channel_layer.connection(channel_layer.consistent_hash(process))

    async def _get_oldest_message(
        self, channel_layer: RedisChannelLayer, process: str
    ) -> tuple[bytes, float] | None:
        connection = self._get_mailbox_connection(channel_layer, process)
        oldest = await connection.zrange(
            self._get_mailbox(channel_layer, process), 0, 0, withscores=True
        )
        return tuple(oldest[0]) if oldest else None

    async def _get_dead_processes(
        self, channel_layer: RedisChannelLayer, processes: dict[str, str]
    ) -> list[str]:
        full_for = channel_layer.expiry * DEAD_WHEN_FULL_FOR_PART_OF_EXPIRY
        unread_for = channel_layer.expiry * DEAD_WHEN_UNREAD_FOR_PART_OF_EXPIRY
        suspects = {}
        for process, channel in processes.items():
            oldest = await self._get_oldest_message(channel_layer, process)
            if oldest is None:
                continue
            connection = self._get_mailbox_connection(channel_layer, process)
            size = await connection.zcard(self._get_mailbox(channel_layer, process))
            age = time.time() - oldest[1]
            capacity = channel_layer.get_capacity(channel)
            if age > unread_for or (size >= capacity and age > full_for):
                suspects[process] = oldest
        if not suspects:
            return []

        await asyncio.sleep(SECOND_LOOK_AFTER_SECONDS)
        dead = []
        for process, oldest in suspects.items():
            oldest_now = await self._get_oldest_message(channel_layer, process)
            # A dead mailbox still starts with the same message, unless that one
            # expired in the meantime. If it is gone before that, it was read.
            expired = oldest[1] <= time.time() - channel_layer.expiry
            if oldest_now == oldest or expired:
                dead.append(process)
        return dead
