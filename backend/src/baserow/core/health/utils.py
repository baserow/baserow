from django.core import cache


def get_celery_queue_size(name="celery"):
    redis_client = cache.cache.client.get_client()
    queue_size = redis_client.llen(name)
    return queue_size
