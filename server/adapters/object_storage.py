"""MinIO/S3-compatible object storage adapter."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Any
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from server.settings import Settings


class ObjectStorage:
    def __init__(self, client: Any, bucket: str):
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "ObjectStorage":
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
        )
        return cls(client, settings.s3_bucket)

    def put(
        self,
        owner_id: str,
        content: BinaryIO,
        content_type: str,
        filename: str,
    ) -> dict[str, str | int]:
        data = content.read()
        safe_name = Path(filename).name or "upload"
        object_key = f"users/{owner_id}/source/{uuid4()}-{safe_name}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        return {
            "object_key": object_key,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def open(self, object_key: str) -> BinaryIO:
        body = self.client.get_object(Bucket=self.bucket, Key=object_key)["Body"]
        return body

    def delete(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)


def ensure_bucket(storage: ObjectStorage) -> None:
    try:
        storage.client.head_bucket(Bucket=storage.bucket)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        try:
            storage.client.create_bucket(Bucket=storage.bucket)
        except ClientError as create_error:
            create_code = str(create_error.response.get("Error", {}).get("Code", ""))
            if create_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise
