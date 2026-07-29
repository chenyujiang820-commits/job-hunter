"""Database-backed read-only collection task service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crawlers.access_guard import ManualInterventionRequired
from server.adapters.browser_connector import BrowserConnector, CollectionResult
from server.models.entities import SearchTemplate, Task
from server.repositories.tenant import JobRepository
from server.services.browser_sessions import BrowserSessionService


class CollectionTaskService:
    def __init__(self, db: Session, sessions: BrowserSessionService, connector: BrowserConnector):
        self.db = db
        self.sessions = sessions
        self.connector = connector

    def create(self, user_id: str, template_id: str) -> Task:
        template = self.db.scalar(
            select(SearchTemplate).where(
                SearchTemplate.id == template_id,
                SearchTemplate.user_id == user_id,
            )
        )
        if template is None:
            raise ValueError("search template not found")
        task = Task(
            user_id=user_id,
            task_type="boss_collection",
            status="queued",
            payload={"template_id": template_id},
        )
        self.db.add(task)
        self.db.commit()
        return task

    def run(self, task_id: str) -> Task:
        task = self.db.get(Task, task_id)
        if task is None or task.task_type != "boss_collection":
            raise ValueError("collection task not found")
        task.status = "running"
        task.error_code = None
        task.error_message = None
        self.db.commit()
        try:
            template = self.db.scalar(
                select(SearchTemplate).where(
                    SearchTemplate.id == task.payload.get("template_id"),
                    SearchTemplate.user_id == task.user_id,
                )
            )
            if template is None:
                raise ValueError("search template not found")
            result = self.connector.collect(task.user_id, template.data or {})
            if result.status == "paused":
                return self._pause(task, result.reason or "暂停人工处理")
            for job in result.jobs:
                JobRepository(self.db).upsert_public_job(job)
            task.status = "completed"
            self.db.commit()
            return task
        except ManualInterventionRequired as exc:
            return self._pause(task, str(exc))
        except Exception as exc:
            task.status = "failed"
            task.error_code = "collection_failed"
            task.error_message = str(exc)
            self.db.commit()
            return task

    def _pause(self, task: Task, reason: str) -> Task:
        task.status = "paused"
        task.error_code = "manual_intervention"
        task.error_message = reason if "暂停人工处理" in reason else f"暂停人工处理：{reason}"
        self.db.commit()
        return task
