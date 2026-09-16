import io
import tarfile
import unittest
import zipfile
from unittest.mock import patch

from fastapi import HTTPException
from app.content import import_file, text_of


def course_files():
    return {
        'moodle_backup.xml': b'<moodle_backup><information><original_course_fullname>Course</original_course_fullname></information></moodle_backup>',
        'course/course.xml': b'<course id="7"><fullname>Clinical skills</fullname><summary>&lt;p&gt;Practice safely.&lt;/p&gt;</summary></course>',
        'sections/section_2/section.xml': b'<section id="2"><number>1</number><name>Assessment</name><summary>&lt;p&gt;Week one.&lt;/p&gt;</summary><sequence>12,11,13</sequence></section>',
        'sections/section_1/section.xml': b'<section id="1"><number>0</number><name>$@NULL@$</name><summary>Welcome</summary><sequence></sequence></section>',
        'activities/page_11/module.xml': b'<module id="11"><modulename>page</modulename><sectionid>2</sectionid></module>',
        'activities/page_11/page.xml': b'<activity moduleid="11" modulename="page"><page><name>Assessment page</name><intro>&lt;p&gt;Read this first.&lt;/p&gt;</intro><content><![CDATA[<h2>Observe</h2><p>Check &amp; record findings.</p><ul><li>Measure</li><li>Explain</li></ul><table><tr><th>Skill</th><th>Evidence</th></tr><tr><td>Observation</td><td>Practice</td></tr></table><script>secretScript()</script><p>After script.</p>]]></content></page></activity>',
        'activities/book_12/module.xml': b'<module id="12"><modulename>book</modulename><sectionid>2</sectionid></module>',
        'activities/book_12/book.xml': b'<activity><book><name>Handbook</name><chapters><chapter><pagenum>2</pagenum><title>Second chapter</title><content>Second content</content></chapter><chapter><pagenum>1</pagenum><title>First chapter</title><content>&lt;p&gt;First content&lt;/p&gt;</content></chapter></chapters></book></activity>',
        'activities/forum_13/module.xml': b'<module id="13"><modulename>forum</modulename><sectionid>2</sectionid></module>',
        'activities/forum_13/forum.xml': b'<activity><forum><name>Discussion</name><intro>Discuss the rubric.</intro><discussions><discussion><posts><post><message>PRIVATE LEARNER POST</message></post></posts></discussion></discussions></forum></activity>',
        'questions.xml': b'<question_categories><question_category><questions><question><name>Safety check</name><questiontext>&lt;p&gt;What comes first?&lt;/p&gt;</questiontext><generalfeedback>Confirm identity.</generalfeedback></question></questions></question_category></question_categories>',
        'users.xml': b'<users><user><email>PRIVATE EMAIL</email></user></users>',
        'activities/page_11/grades.xml': b'<grades>PRIVATE GRADE</grades>',
        'files/ab/abcdef': b'An embedded resource that is retained but not parsed',
    }


def backup_bytes(kind='zip', files=None):
    files = course_files() if files is None else files
    output = io.BytesIO()
    if kind == 'zip':
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,data in files.items():
                archive.writestr(name,data)
    else:
        with tarfile.open(fileobj=output,mode='w:gz') as archive:
            for name,data in files.items():
                entry=tarfile.TarInfo('./'+name);entry.size=len(data)
                archive.addfile(entry,io.BytesIO(data))
    return output.getvalue()


class MoodleImportTests(unittest.TestCase):
    def test_zip_and_gzip_course_content_order_and_privacy(self):
        for kind in ('zip','gzip'):
            with self.subTest(kind=kind):
                content,comments=import_file('course.MBZ',backup_bytes(kind))
                text=text_of(content)
                self.assertEqual(comments,[])
                for expected in ('Clinical skills','Practice safely.','Week one.','Check & record findings.','What comes first?','Confirm identity.'):
                    self.assertIn(expected,text)
                self.assertLess(text.index('Section 0'),text.index('Assessment'))
                self.assertLess(text.index('Handbook'),text.index('Assessment page'))
                self.assertLess(text.index('First chapter'),text.index('Second chapter'))
                self.assertNotIn('PRIVATE',text)
                self.assertNotIn('secretScript',text)
                self.assertNotIn('$@NULL@$',text)
                self.assertTrue(any(b['type']=='table' for b in content['blocks']))
                self.assertTrue(any(b['type']=='list' for b in content['blocks']))
                self.assertTrue(any('original backup is retained in full' in w for w in content['warnings']))

    def test_invalid_incomplete_and_malformed_backups(self):
        cases=[
            b'not an archive',
            backup_bytes(files={'course/course.xml':b'<course/>'}),
            backup_bytes(files={'moodle_backup.xml':b'<moodle_backup/>'}),
            backup_bytes(files={**course_files(),'course/course.xml':b'<course>broken'}),
        ]
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(HTTPException) as error:
                import_file('course.mbz',data)
            self.assertEqual(error.exception.status_code,422)

    def test_archive_paths_links_and_expansion_limits(self):
        for kind in ('zip','gzip'):
            with self.subTest(kind=kind),self.assertRaises(HTTPException):
                import_file('course.mbz',backup_bytes(kind,{**course_files(),'../escape.xml':b'no'}))
        with patch('app.moodle.MAX_EXPANDED',100),self.assertRaises(HTTPException) as error:
            import_file('course.mbz',backup_bytes())
        self.assertIn('expanded-size',error.exception.detail)
        with patch('app.moodle.MAX_XML',20),self.assertRaises(HTTPException):
            import_file('course.mbz',backup_bytes())
        with patch('app.moodle.MAX_MEMBERS',2),self.assertRaises(HTTPException):
            import_file('course.mbz',backup_bytes())
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as archive:
            entry=tarfile.TarInfo('course/course.xml');entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd';archive.addfile(entry)
        with self.assertRaises(HTTPException) as error:import_file('course.mbz',output.getvalue())
        self.assertIn('Links',error.exception.detail)

    def test_xml_entities_are_rejected(self):
        xml=b'<!DOCTYPE course [<!ENTITY secret SYSTEM "file:///etc/passwd">]><course><fullname>&secret;</fullname></course>'
        with self.assertRaises(HTTPException) as error:
            import_file('course.mbz',backup_bytes(files={**course_files(),'course/course.xml':xml}))
        self.assertIn('entity',error.exception.detail)

    def test_unknown_activities_keep_description_and_warn(self):
        files=course_files()
        files.update({
            'activities/custom_20/module.xml':b'<module id="20"><modulename>custom</modulename><sectionid>2</sectionid></module>',
            'activities/custom_20/custom.xml':b'<activity><custom><name>Custom learning activity</name><intro>Read the instructions.</intro><private_records><record>PRIVATE RECORD</record></private_records></custom></activity>',
        })
        content,_=import_file('course.mbz',backup_bytes(files=files))
        self.assertIn('Custom learning activity',text_of(content))
        self.assertNotIn('PRIVATE RECORD',text_of(content))
        self.assertTrue(any('custom' in w for w in content['warnings']))

if __name__=='__main__':unittest.main()
