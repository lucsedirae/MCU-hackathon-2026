"""Read Moodle 2+ backup course text without restoring a course or extracting files.

Schema references: Moodle's backup/moodle2/backup_stepslib.php and the page/book
backup steps. Only curriculum fields are read; user records and attempts are not.
"""
import io
import re
import tarfile
import zipfile
from pathlib import PurePosixPath
from uuid import uuid4

from lxml import etree, html

MAX_EXPANDED = 100 * 1024 * 1024
MAX_XML = 16 * 1024 * 1024
MAX_MEMBERS = 10000
SELECTED_XML = re.compile(
    r"(?:moodle_backup\.xml|course/course\.xml|questions\.xml|"
    r"sections/section_[^/]+/section\.xml|activities/[^/]+/[a-zA-Z0-9_]+\.xml)\Z"
)


def _name(raw):
    path = PurePosixPath(raw)
    if path.is_absolute() or '..' in path.parts or '\\' in raw:
        raise ValueError('The Moodle backup contains an unsafe archive path.')
    return str(path)


def _read_archive(data):
    selected, seen, total, count = {}, set(), 0, 0

    def check(raw, size):
        nonlocal total, count
        name = _name(raw)
        count += 1
        total += size
        if count > MAX_MEMBERS or total > MAX_EXPANDED:
            raise ValueError('The Moodle backup exceeds the 100 MB expanded-size or 10,000-entry limit.')
        if name in seen:
            raise ValueError('The Moodle backup contains duplicate archive paths.')
        seen.add(name)
        # Avoid even parsing learner records, logs, submissions, and attempts.
        keep = bool(SELECTED_XML.fullmatch(name)) and (
            not name.startswith('activities/')
            or PurePosixPath(name).stem == 'module'
            or PurePosixPath(name).stem == PurePosixPath(name).parent.name.rsplit('_', 1)[0]
        )
        if keep and size > MAX_XML:
            raise ValueError('An XML file in the Moodle backup exceeds the 16 MB limit.')
        return name, keep

    try:
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for entry in archive.infolist():
                    name, keep = check(entry.filename, entry.file_size)
                    if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('Links are not supported inside Moodle backups.')
                    if entry.flag_bits & 1:
                        raise ValueError('Encrypted Moodle backups are not supported.')
                    if keep and not entry.is_dir():
                        with archive.open(entry) as source:
                            selected[name] = source.read(MAX_XML + 1)
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r|*') as archive:
                for entry in archive:
                    name, keep = check(entry.name, entry.size)
                    if not entry.isfile() and not entry.isdir():
                        raise ValueError('Links and special files are not supported inside Moodle backups.')
                    if keep and entry.isfile():
                        with archive.extractfile(entry) as source:
                            selected[name] = source.read(MAX_XML + 1)
    except (tarfile.TarError, zipfile.BadZipFile, EOFError, OSError) as exc:
        raise ValueError('Could not read this Moodle backup. Upload a valid ZIP or gzip/TAR .mbz file.') from exc
    if any(len(value) > MAX_XML for value in selected.values()):
        raise ValueError('An XML file in the Moodle backup exceeds the 16 MB limit.')
    return selected


def _xml(data, name):
    try:
        root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
        if root.getroottree().docinfo.doctype or any(isinstance(e, etree._Entity) for e in root.iter()):
            raise ValueError('DTD and entity declarations are not supported in Moodle backup XML.')
        return root
    except etree.XMLSyntaxError as exc:
        raise ValueError(f'The Moodle backup contains malformed XML in {name}.') from exc


def _text(node, path):
    if node is None:
        return ''
    value = node.findtext(path) or ''
    return '' if value.strip() == '$@NULL@$' else value.strip()


def _number(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _block(kind, text='', **extra):
    return {'id': str(uuid4()), 'type': kind, 'text': text, **extra}


def _html_blocks(value):
    """Convert Moodle's HTML fields to inert paragraphs, lists, headings and tables."""
    if not value.strip():
        return []
    root = html.fragment_fromstring(value, create_parent='div')
    for element in list(root.iter()):
        if element.tag in ('script', 'style', 'iframe', 'object', 'embed'):
            element.drop_tree()
    output, pending = [], []

    def flush():
        value = re.sub(r'\s+', ' ', ''.join(pending)).strip()
        if value:
            output.append(_block('paragraph', value))
        pending.clear()

    def plain(element):
        return re.sub(r'\s+', ' ', ''.join(element.itertext())).strip()

    def visit(element):
        tag = element.tag
        if tag == 'table':
            flush()
            rows = [[plain(cell) for cell in row if cell.tag in ('td','th')] for row in element.iter('tr')]
            rows = [row for row in rows if row]
            if rows:
                output.append(_block('table', rows=rows))
            return
        if tag in ('h1','h2','h3','h4','h5','h6','li'):
            flush()
            value = plain(element)
            if value:
                output.append(_block('list' if tag == 'li' else 'heading', value,
                    level=1 if tag == 'li' else min(int(tag[1]) + 2, 6),
                    ordered=tag == 'li' and element.getparent().tag == 'ol'))
            return
        boundary = tag in ('p','div','section','article','br','ul','ol')
        if boundary:
            flush()
        if element.text:
            pending.append(element.text)
        for child in element:
            visit(child)
            if child.tail:
                pending.append(child.tail)
        if tag == 'img':
            pending.append(' [Image: '+(element.get('alt') or 'embedded media')+'] ')
        if tag == 'a' and element.get('href','').startswith(('https://','http://')):
            pending.append(' ('+element.get('href')+')')
        if boundary:
            flush()
    visit(root)
    flush()
    return output


def import_moodle(data):
    archive = _read_archive(data)
    if 'moodle_backup.xml' not in archive:
        raise ValueError('This is not a Moodle 2+ course backup: moodle_backup.xml is missing.')
    manifest = _xml(archive['moodle_backup.xml'], 'moodle_backup.xml')
    if manifest.tag != 'moodle_backup':
        raise ValueError('The Moodle backup manifest is invalid.')
    if 'course/course.xml' not in archive:
        raise ValueError('Upload a full Moodle course backup; course/course.xml is missing.')
    course = _xml(archive['course/course.xml'], 'course/course.xml')
    if course.tag != 'course':
        raise ValueError('The Moodle backup course definition is invalid.')
    title = _text(course,'fullname') or _text(manifest,'information/original_course_fullname') or 'Moodle course'
    blocks = [_block('heading', title, level=1)]
    blocks += _html_blocks(_text(course,'summary'))
    warnings = ['Moodle course text imported for review. Embedded files/media, SCORM/H5P packages, and interactive behavior are not extracted. Learner records, submissions, grades, and attempts are not included in the review text. The original backup is retained in full and is downloadable by team members.']
    sections, activities = [], {}
    for name in sorted(archive):
        if name.startswith('sections/') and name.endswith('/section.xml'):
            section = _xml(archive[name], name)
            sections.append(section)
        elif name.startswith('activities/') and name.endswith('/module.xml'):
            module = _xml(archive[name], name)
            directory = str(PurePosixPath(name).parent)
            kind = _text(module,'modulename') or directory.rsplit('/',1)[-1].rsplit('_',1)[0]
            activities[module.get('id') or directory.rsplit('_',1)[-1]] = (directory,kind,module)
    # Manifest fallback retains activities whose module metadata was omitted.
    for activity in manifest.findall('./information/contents/activities/activity'):
        key = _text(activity,'moduleid')
        directory = _name(_text(activity,'directory'))
        kind = _text(activity,'modulename')
        if key and key not in activities and directory.startswith('activities/'):
            activities[key] = (directory,kind,None)
    visited, unsupported = set(), set()

    def add_activity(key):
        if key in visited or key not in activities:
            return
        visited.add(key)
        directory,kind,module = activities[key]
        path = f'{directory}/{kind}.xml'
        if not re.fullmatch(r'[a-zA-Z0-9_]+',kind) or path not in archive:
            blocks.append(_block('heading',f'{kind or "Unknown"} activity',level=3))
            warnings.append(f'Activity {key}: readable activity definition is missing.')
            return
        root = _xml(archive[path],path)
        activity = root.find(kind) if root.tag == 'activity' else root
        if activity is None:
            warnings.append(f'Activity {key}: expected {kind} content was not found.')
            return
        blocks.append(_block('heading',_text(activity,'name') or f'{kind.title()} activity',level=3))
        blocks.append(_block('paragraph',f'Activity type: {kind}'))
        blocks.extend(_html_blocks(_text(activity,'intro')))
        if kind == 'page':
            blocks.extend(_html_blocks(_text(activity,'content')))
        elif kind == 'book':
            for chapter in sorted(activity.findall('./chapters/chapter'),key=lambda c:_number(_text(c,'pagenum'))):
                blocks.append(_block('heading',_text(chapter,'title') or 'Chapter',level=4))
                blocks.extend(_html_blocks(_text(chapter,'content')))
        elif kind == 'url':
            url = _text(activity,'externalurl')
            if url:
                blocks.append(_block('paragraph',url))
        elif kind == 'assign':
            blocks.extend(_html_blocks(_text(activity,'activity')))
        elif kind == 'lesson':
            for page in activity.findall('./pages/page'):
                blocks.append(_block('heading',_text(page,'title') or 'Lesson page',level=4))
                blocks.extend(_html_blocks(_text(page,'contents')))
        elif kind not in ('label','resource','folder','forum','quiz','choice','feedback','workshop','scorm','h5pactivity'):
            unsupported.add(kind)
    for section in sorted(sections,key=lambda s:_number(_text(s,'number'))):
        blocks.append(_block('heading',_text(section,'name') or f'Section {_text(section,"number") or "0"}',level=2))
        blocks.extend(_html_blocks(_text(section,'summary')))
        for key in _text(section,'sequence').split(','):
            add_activity(key.strip())
        for key,(_,_,module) in activities.items():
            if module is not None and _text(module,'sectionid') == section.get('id'):
                add_activity(key)
    remaining = [key for key in activities if key not in visited]
    if remaining:
        blocks.append(_block('heading','Other course activities',level=2))
        for key in remaining:
            add_activity(key)
    if 'questions.xml' in archive:
        questions = _xml(archive['questions.xml'],'questions.xml')
        found = [q for q in questions.iter('question') if _text(q,'questiontext')]
        if found:
            blocks.append(_block('heading','Question bank',level=2))
            warnings.append('Question-bank text can include unused questions or multiple versions; it is not an exact mapping to quiz slots. Question-type-specific options are not reconstructed.')
            for question in found:
                blocks.append(_block('heading',_text(question,'name') or 'Question',level=3))
                blocks.extend(_html_blocks(_text(question,'questiontext')))
                feedback = _text(question,'generalfeedback')
                if feedback:
                    blocks.append(_block('paragraph','General feedback:'))
                    blocks.extend(_html_blocks(feedback))
    if unsupported:
        warnings.append('Only names and descriptions were imported for these additional activity types: '+', '.join(sorted(unsupported))+'.')
    warnings.append('Activity settings, access/completion rules, detailed quiz configuration, and learner discussions are not reconstructed.')
    return {'blocks':blocks,'warnings':warnings}
