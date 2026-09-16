"""Bounded disk-backed Moodle uploads; originals survive in a dedicated volume."""
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.content import import_file, MAX_UPLOAD, MAX_MBZ_UPLOAD, validate_text
from app.moodle import import_moodle

UPLOAD_DIR = Path(os.getenv('ORIGINAL_UPLOAD_DIR', '/data/uploads'))
COPY_CHUNK = 1024 * 1024


def stored_path(key):
    if not key or Path(key).name != key or not key.endswith('.mbz'):
        raise HTTPException(404, 'Original upload is unavailable.')
    return UPLOAD_DIR / key


@event.listens_for(Session, 'after_commit')
def commit_uploads(session):
    session.info.pop('pending_uploads', None)


@event.listens_for(Session, 'after_transaction_end')
def discard_uncommitted_uploads(session, transaction):
    if transaction.parent is None:
        for path in session.info.pop('pending_uploads', []):
            path.unlink(missing_ok=True)


async def read_upload(file, session):
    """Returns normalized content, comments, and Original storage fields."""
    name = file.filename or 'upload'
    if Path(name).suffix.lower() != '.mbz':
        data = await file.read(MAX_UPLOAD + 1)
        content, comments = import_file(name, data)
        return content, comments, {'data': data, 'storage_key': None}

    # UploadFile is itself spooled by the multipart parser. All additional reads,
    # parsing and disk writes run off the event loop, with bounded copy buffers.
    def copy_and_parse():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        key = str(uuid4()) + '.mbz'
        path = stored_path(key)
        try:
            total = 0
            file.file.seek(0)
            with path.open('xb') as target:
                os.chmod(path, 0o600)
                while chunk := file.file.read(COPY_CHUNK):
                    total += len(chunk)
                    if total > MAX_MBZ_UPLOAD:
                        raise HTTPException(413, 'Moodle backups must be 1 GB or smaller.')
                    target.write(chunk)
            with path.open('rb') as source:
                content = import_moodle(source)
            validate_text(content, name)
            return content, key, path
        except Exception as exc:
            path.unlink(missing_ok=True)
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else 'Could not read this Moodle backup. Upload a valid ZIP or gzip/TAR .mbz file.') from None

    content, key, path = await run_in_threadpool(copy_and_parse)
    session.info.setdefault('pending_uploads', []).append(path)
    return content, [], {'data': None, 'storage_key': key}
