import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.content import import_file, text_of
from test_moodle import backup_bytes


class PackageTests(unittest.TestCase):
    def load(self, files):
        return import_file('course.ZIP', backup_bytes(files=files))[0]

    def test_scorm_namespaces_order_dependencies_and_inert_html(self):
        content = self.load({
            'imsmanifest.xml': b'''<manifest xmlns="urn:ims"><organizations default="o"><organization identifier="o"><title>Safety course</title><item identifierref="b"><title>Second first</title></item><item identifierref="a"><title>First second</title></item></organization></organizations><resources xml:base="pages/"><resource identifier="a" href="a.html"/><resource identifier="b" href="b.html?launch=1"><dependency identifierref="a"/><file href="b.html"/></resource></resources></manifest>''',
            'pages/a.html': b'<p>Alpha content</p>',
            'pages/b.html': b'<html><body><h1>Beta content</h1><script>PRIVATE_SCRIPT</script><table><tr><td>Evidence</td></tr></table></body></html>',
        })
        text = text_of(content)
        self.assertLess(text.index('Beta content'), text.index('Alpha content'))
        self.assertEqual(text.count('Beta content'), 1)
        self.assertNotIn('PRIVATE_SCRIPT', text)
        self.assertTrue(any(b['type'] == 'table' for b in content['blocks']))

    def test_tincan_and_cmi5_language_maps(self):
        for manifest, xml in [
            ('tincan.xml', '<tincan><activities><activity><name lang="en-US">Course title</name><description>Course description</description><launch>launch.html</launch></activity></activities></tincan>'),
            ('cmi5.xml', '<courseStructure xmlns="urn:cmi5"><course id="c"><title><langstring lang="en-US">Course title</langstring></title></course><au id="a"><description><langstring lang="en">Course description</langstring></description><url>launch.html</url></au></courseStructure>'),
        ]:
            with self.subTest(manifest=manifest):
                content = self.load({manifest: xml.encode(), 'launch.html': b'<p>Learning objectives</p>'})
                for value in ('Course title', 'Course description', 'Learning objectives'):
                    self.assertIn(value, text_of(content))

    def test_incomplete_and_external_content_warns(self):
        content = self.load({'tincan.xml': b'<tincan><activities><activity><name>Remote course</name><launch>https://example.com/launch</launch></activity><activity><launch>empty.html</launch></activity><activity><launch>missing.html</launch></activity></activities></tincan>', 'empty.html': b'<script>runCourse()</script>'})
        warnings = ' '.join(content['warnings'])
        self.assertIn('external', warnings)
        self.assertIn('No readable static text', warnings)
        self.assertIn('missing.html', warnings)
        self.assertNotIn('runCourse', text_of(content))

    def test_invalid_and_unsafe_packages(self):
        for files in [
            {'readme.txt': b'Not a course'},
            {'tincan.xml': b'<broken'},
            {'tincan.xml': b'<wrong/>'},
            {'tincan.xml': b'<!DOCTYPE tincan [<!ENTITY a SYSTEM "file:///etc/passwd">]><tincan>&a;</tincan>'},
            {'../escape': b'bad'},
            {'tincan.xml': b'<tincan><activities><activity><launch>%2e%2e/secret.html</launch></activity></activities></tincan>'},
        ]:
            with self.subTest(files=list(files)), self.assertRaises(HTTPException) as error:
                self.load(files)
            self.assertEqual(error.exception.status_code, 422)
        with patch('app.packages.MAX_EXPANDED', 1), self.assertRaises(HTTPException):
            self.load({'tincan.xml': b'<tincan/>'})
