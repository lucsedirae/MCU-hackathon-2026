"""Synthetic disk-backed Moodle fixtures; no real accounts, files or provider calls."""
import asyncio
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Original, User, Workspace, Document, Revision
from app import uploads
from app.content import text_of, import_file, MAX_UPLOAD
from tests.test_moodle import course_files, backup_bytes


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.patch = patch.object(uploads, 'UPLOAD_DIR', self.directory / 'originals')
        self.patch.start()
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.patch.stop(); self.engine.dispose(); self.tmp.cleanup()

    def upload(self, session, source, name='course.mbz'):
        return asyncio.run(uploads.read_upload(UploadFile(file=source, filename=name), session))

    def test_backup_larger_than_old_upload_limit_is_streamed_and_retained(self):
        path = self.directory / 'large.mbz'
        # A 24 MB stored media member, created in small buffers instead of a huge allocation.
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, data in course_files().items(): archive.writestr(name, data)
            with archive.open('files/large-media', 'w') as member:
                for _ in range(24): member.write(b'x' * 1024 * 1024)
        self.assertGreater(path.stat().st_size, MAX_UPLOAD)
        class BoundedReader:
            def __init__(self, handle): self.handle = handle
            def seek(self, *args): return self.handle.seek(*args)
            def read(self, size):
                if size > uploads.COPY_CHUNK or size < 0: raise AssertionError('Unbounded read')
                return self.handle.read(size)
        with Session(self.engine) as s, path.open('rb') as source:
            s.begin()
            content, comments, stored = self.upload(s, BoundedReader(source))
            self.assertIn('Clinical skills', text_of(content)); self.assertEqual(comments, [])
            self.assertIsNone(stored['data'])
            target = uploads.stored_path(stored['storage_key'])
            self.assertEqual(target.stat().st_size, path.stat().st_size)
            s.commit()
            self.assertTrue(target.exists())
        self.assertTrue(target.exists())

    def test_parse_failures_and_oversized_uploads_leave_no_original(self):
        with Session(self.engine) as s:
            with self.assertRaises(HTTPException) as e:
                self.upload(s, io.BytesIO(b'not a valid backup'))
            self.assertEqual(e.exception.status_code, 422)
            self.assertEqual(list(uploads.UPLOAD_DIR.iterdir()), [])
            with patch.object(uploads, 'MAX_MBZ_UPLOAD', 20), self.assertRaises(HTTPException) as e:
                self.upload(s, io.BytesIO(b'large backup bytes' * 10))
            self.assertEqual(e.exception.status_code, 413)
            self.assertEqual(list(uploads.UPLOAD_DIR.iterdir()), [])

    def test_database_rollback_and_close_remove_pending_original(self):
        for close in (False, True):
            s = Session(self.engine); s.begin()
            _, _, stored = self.upload(s, io.BytesIO(backup_bytes()))
            path = uploads.stored_path(stored['storage_key']); self.assertTrue(path.exists())
            if close: s.close()
            else: s.rollback(); s.close()
            self.assertFalse(path.exists())

    def test_gzip_backup_uses_disk_path_and_regular_files_stay_small(self):
        with Session(self.engine) as s:
            s.begin()
            content, _, storage = self.upload(s, io.BytesIO(backup_bytes('gzip')), 'COURSE.MBZ')
            self.assertIn('Clinical skills', text_of(content)); self.assertIsNone(storage['data'])
            _, _, ordinary = self.upload(s, io.BytesIO(b'Notes'), 'notes.txt')
            self.assertEqual(ordinary['data'], b'Notes'); self.assertIsNone(ordinary['storage_key'])
            with self.assertRaises(HTTPException) as e:
                import_file('large.txt', b'x' * (MAX_UPLOAD + 1))
            self.assertEqual(e.exception.status_code, 413)
            s.rollback()

    def test_selected_xml_total_is_bounded(self):
        with patch('app.moodle.MAX_SELECTED_XML', 50), self.assertRaises(HTTPException) as e:
            import_file('course.mbz', backup_bytes())
        self.assertIn('total imported XML', e.exception.detail)

    def test_storage_key_cannot_escape_volume(self):
        with self.assertRaises(HTTPException): uploads.stored_path('../backup.mbz')
