from datetime import timedelta

from baserow.config.celery import app

from .handler import AssistantHandler
from .tools.search_user_docs.handler import KnowledgeBaseHandler

# The first sync after a chunking change re-embeds every document in one transaction.
SYNC_KNOWLEDGE_BASE_TIME_LIMIT = 60 * 30


@app.task(bind=True)
def delete_old_unrated_predictions(self):
    AssistantHandler().delete_predictions(older_than_days=30, exclude_rated=True)


@app.task(
    bind=True,
    queue="export",
    soft_time_limit=SYNC_KNOWLEDGE_BASE_TIME_LIMIT,
    time_limit=SYNC_KNOWLEDGE_BASE_TIME_LIMIT + 60,
)
def sync_assistant_knowledge_base(self):
    KnowledgeBaseHandler().sync_knowledge_base()


@app.on_after_finalize.connect
def setup_period_trash_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(days=1),
        delete_old_unrated_predictions.s(),
    )
