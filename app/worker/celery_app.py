from __future__ import annotations

from celery import Celery

from config import env

broker_url = env("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
result_backend = env("CELERY_RESULT_BACKEND", broker_url)

task_always_eager = (env("CELERY_TASK_ALWAYS_EAGER", "false") or "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

celery_app = Celery(
    "workflow_builder",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    task_always_eager=task_always_eager,
    task_eager_propagates=False,
)

celery_app.autodiscover_tasks(["app.worker"])
