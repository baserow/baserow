from datetime import timedelta

from baserow.config.celery import app

from .handler import AssistantHandler
from .tools import KnowledgeBaseHandler


@app.task(bind=True)
def delete_old_unrated_predictions(self):
    AssistantHandler().delete_predictions(older_than_days=30, exclude_rated=True)


@app.task(bind=True, queue="export")
def sync_assistant_knowledge_base(self):
    KnowledgeBaseHandler().sync_knowledge_base()


@app.on_after_finalize.connect
def setup_period_trash_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(days=1),
        delete_old_unrated_predictions.s(),
    )
