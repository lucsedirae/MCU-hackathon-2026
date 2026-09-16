"""Static curriculum extraction from SCORM, Tin Can and cmi5 ZIP packages.

Packages are never launched. Only manifest metadata and referenced HTML/text
are read; scripts, remote resources and learner statements are not interpreted.
"""
import io
import posixpath
import zipfile
from urllib.parse import unquote, urljoin, urlsplit
from lxml import etree
from app.moodle import _block, _html_blocks

MAX_EXPANDED = 100 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_FILE = 16 * 1024 * 1024


def local_tag(node):
    return etree.QName(node).localname if isinstance(node.tag, str) else ''


def children(node, tag):
    return [child for child in node if local_tag(child) == tag]


def field(node, tag):
    matches = children(node, tag)
    if not matches:
        return ''
    # Language maps: choose one translation rather than repeating every language.
    value = matches[0]
    translations = children(value, 'langstring')
    if translations:
        value = next((v for v in translations if v.get('lang', '').startswith('en')), translations[0])
    return ''.join(value.itertext()).strip()


def import_package(data):
    warnings = ['Static course text only. Scripts, interactive exercises, media, tracking, and external websites are not executed or analyzed. Some authoring tools store most course content in scripts, so this preview may be incomplete.']
    blocks, seen_pages = [], set()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError('Upload a valid SCORM, Tin Can, or cmi5 ZIP package.') from exc
    with archive:
        entries = {}
        total = 0
        for entry in archive.infolist():
            name = entry.filename
            total += entry.file_size
            if len(entries) >= MAX_MEMBERS or total > MAX_EXPANDED:
                raise ValueError('Course packages are limited to 100 MB expanded size and 10,000 entries.')
            if name.startswith('/') or '\\' in name or '..' in name.split('/') or ':' in name or '\x00' in name:
                raise ValueError('The course package contains an unsafe archive path.')
            name = posixpath.normpath(name)
            if name in entries:
                raise ValueError('The course package contains duplicate archive paths.')
            if entry.flag_bits & 1 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Encrypted files and links are not supported in course packages.')
            entries[name] = entry

        def read(name):
            entry = entries[name]
            if entry.file_size > MAX_FILE:
                raise ValueError('An imported course file exceeds the 16 MB limit.')
            with archive.open(entry) as stream:
                value = stream.read(MAX_FILE + 1)
            if len(value) > MAX_FILE:
                raise ValueError('An imported course file exceeds the 16 MB limit.')
            return value

        manifests = [name for name in ('imsmanifest.xml', 'tincan.xml', 'cmi5.xml') if name in entries]
        if not manifests:
            raise ValueError('The ZIP must contain imsmanifest.xml, tincan.xml, or cmi5.xml at its root.')
        manifest = manifests[0]
        if len(manifests) > 1:
            warnings.append(f'Multiple package manifests found; using {manifest}.')
        try:
            root = etree.fromstring(read(manifest), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
        except etree.XMLSyntaxError as exc:
            raise ValueError('The course package manifest contains malformed XML.') from exc
        if root.getroottree().docinfo.doctype:
            raise ValueError('DTD and entity declarations are not supported in course manifests.')
        expected = {'imsmanifest.xml': 'manifest', 'tincan.xml': 'tincan', 'cmi5.xml': 'courseStructure'}[manifest]
        if local_tag(root) != expected:
            raise ValueError('The course package manifest has an invalid root element.')

        def page(href, node):
            if not href:
                return
            base = ''
            for ancestor in reversed([node, *node.iterancestors()]):
                base = urljoin(base, ancestor.get('{http://www.w3.org/XML/1998/namespace}base', ''))
            url = urlsplit(urljoin(base, href))
            if url.scheme or url.netloc:
                warnings.append('An external launch/resource was not fetched.')
                return
            path = unquote(url.path)
            path = posixpath.normpath(path)
            if path.startswith('/') or path == '..' or path.startswith('../') or '\\' in path or ':' in path:
                raise ValueError('The course manifest references an unsafe path.')
            if path in seen_pages:
                return
            seen_pages.add(path)
            if path not in entries:
                warnings.append(f'A referenced course file is missing: {path}.')
                return
            if not path.lower().endswith(('.html', '.htm', '.xhtml', '.txt')):
                return
            value = read(path).decode('utf-8-sig', errors='replace')
            extracted = [_block('paragraph', value)] if path.lower().endswith('.txt') else _html_blocks(value)
            if not extracted:
                warnings.append(f'No readable static text was found in {path}.')
            blocks.extend(extracted)

        if manifest == 'imsmanifest.xml':
            resources = {n.get('identifier'): n for n in root.iter() if local_tag(n) == 'resource'}
            visited_resources = set()

            def resource(identifier):
                if identifier in visited_resources:
                    return
                visited_resources.add(identifier)
                node = resources.get(identifier)
                if node is None:
                    warnings.append(f'A manifest resource is missing: {identifier}.')
                    return
                page(node.get('href'), node)
                for child in node:
                    if local_tag(child) == 'file':
                        page(child.get('href'), child)
                    elif local_tag(child) == 'dependency':
                        resource(child.get('identifierref'))

            def item(node, level=1):
                title = field(node, 'title')
                if title:
                    blocks.append(_block('heading', title, level=min(level, 6)))
                if node.get('identifierref'):
                    resource(node.get('identifierref'))
                for child in children(node, 'item'):
                    item(child, level + 1)

            organizations = children(root, 'organizations')
            choices = children(organizations[0], 'organization') if organizations else []
            if choices:
                selected = next((n for n in choices if n.get('identifier') == organizations[0].get('default')), choices[0])
                item(selected)
                if len(choices) > 1:
                    warnings.append('Only the default course organization was imported.')
            else:
                for identifier in resources:
                    resource(identifier)
        else:
            tags = ('activity',) if manifest == 'tincan.xml' else ('course', 'block', 'au')
            for node in root.iter():
                if local_tag(node) not in tags:
                    continue
                title = field(node, 'name' if manifest == 'tincan.xml' else 'title')
                if title:
                    blocks.append(_block('heading', title, level=1 if local_tag(node) == 'course' else 2))
                blocks.extend(_html_blocks(field(node, 'description')))
                page(field(node, 'launch' if manifest == 'tincan.xml' else 'url'), node)
        if not seen_pages:
            warnings.append('No local course pages were referenced; only available manifest metadata was imported.')
        return {'blocks': blocks, 'warnings': list(dict.fromkeys(warnings))}
