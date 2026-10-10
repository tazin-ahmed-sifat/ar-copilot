"""Read worksheet XML by sheet name, so tests don't depend on sheet order."""
import zipfile
from xml.etree import ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def sheet_xml(book: zipfile.ZipFile, name: str) -> bytes:
    workbook = ET.fromstring(book.read('xl/workbook.xml'))
    sheet = next(s for s in workbook.iter(f"{{{NS['m']}}}sheet") if s.attrib['name'] == name)
    rel_id = sheet.attrib[f"{{{NS['r']}}}id"]
    rels = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
    target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rel_id)
    return book.read('xl/' + target.removeprefix('/xl/'))
