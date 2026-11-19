"""OOXML text projection without archive extraction, relationship fetches or evaluation."""

import posixpath
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class PreparationFailure(Exception):
    def __init__(self, code):
        self.code = code


class OfficeDocument:
    def __init__(self, archive: ZipFile, max_bytes: int):
        self.archive = archive
        self.warnings: set[str] = set()
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 2000 or sum(entry.file_size for entry in entries) > max_bytes:
            raise PreparationFailure("attachment_expansion_limit")
        if len(names) != len(set(names)):
            raise PreparationFailure("unreadable_file")
        for entry in entries:
            if entry.flag_bits & 1:
                raise PreparationFailure("encrypted_file")
            if entry.filename.startswith("/") or ".." in entry.filename.split("/"):
                raise PreparationFailure("unreadable_file")
            if any(
                part in entry.filename
                for part in (
                    "/media/",
                    "/embeddings/",
                    "/charts/",
                    "/diagrams/",
                    "vbaProject",
                )
            ):
                self.warnings.add("visual_or_embedded_content_unexamined")

    def xml(self, name):
        return fromstring(self.archive.read(name), forbid_dtd=True)

    def relationships(self, part):
        directory, filename = posixpath.split(part)
        name = f"{directory}/_rels/{filename}.rels"
        if name not in self.archive.namelist():
            return {}
        result = {}
        for relationship in self.xml(name):
            if relationship.get("TargetMode") == "External":
                self.warnings.add("external_content_unexamined")
                continue
            target = relationship.get("Target", "")
            resolved = (
                posixpath.normpath(posixpath.join(directory, target))
                if not target.startswith("/")
                else target.lstrip("/")
            )
            if resolved.startswith("../") or ":" in resolved:
                raise PreparationFailure("unreadable_file")
            result[relationship.get("Id")] = resolved
        return result

    def paragraphs(self, root, prefix, namespace):
        for index, paragraph in enumerate(root.iter(namespace + "p"), 1):
            text = []
            for node in paragraph.iter():
                if node.tag == namespace + "t":
                    text.append(node.text or "")
                elif node.tag in {
                    namespace + "tab",
                    namespace + "br",
                    namespace + "cr",
                }:
                    text.append("\t" if node.tag.endswith("tab") else "\n")
            yield f"{prefix}:paragraph:{index}", "".join(text)

    def word(self):
        main = "word/document.xml"
        self.relationships(main)
        root = self.xml(main)
        if root.tag != W + "document" or root.find(W + "body") is None:
            raise PreparationFailure("unreadable_file")
        if any(
            node.tag in {W + "altChunk", W + "object", W + "drawing", W + "pict"}
            for node in root.iter()
        ):
            self.warnings.add("visual_or_embedded_content_unexamined")
        yield from self.paragraphs(root, "document", W)
        for name in sorted(self.archive.namelist()):
            if name.startswith(
                (
                    "word/header",
                    "word/footer",
                    "word/footnotes",
                    "word/endnotes",
                    "word/comments",
                )
            ) and name.endswith(".xml"):
                yield from self.paragraphs(
                    self.xml(name), posixpath.basename(name).removesuffix(".xml"), W
                )

    def spreadsheet(self):
        import json

        relations = self.relationships("xl/workbook.xml")
        strings = []
        if "xl/sharedStrings.xml" in self.archive.namelist():
            strings = [
                "".join(node.itertext()) for node in self.xml("xl/sharedStrings.xml")
            ]
        workbook = self.xml("xl/workbook.xml")
        if workbook.tag != S + "workbook":
            raise PreparationFailure("unreadable_file")
        for sheet in workbook.iter(S + "sheet"):
            target = relations[sheet.attrib[R + "id"]]
            self.relationships(target)
            for row in self.xml(target).iter(S + "row"):
                values = {}
                for cell in row.findall(S + "c"):
                    value = cell.findtext(S + "v", "")
                    kind = cell.get("t")
                    if kind == "s":
                        value = strings[int(value)]
                    elif kind == "b":
                        value = "boolean: " + ("true" if value == "1" else "false")
                    elif kind == "e":
                        value = "cell error: " + value
                    elif kind == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter(S + "t"))
                    formula = cell.find(S + "f")
                    if formula is not None:
                        value = f"formula (not evaluated): {formula.text or ''}; cached value (may be stale): {value}"
                        self.warnings.add("formulas_not_evaluated")
                    elif cell.get("s"):
                        value = (
                            f"stored value (display formatting not applied): {value}"
                        )
                        self.warnings.add("display_formatting_unexamined")
                    values[cell.attrib["r"]] = value
                yield (
                    f"sheet:{sheet.attrib['name']}:row:{row.attrib['r']}",
                    json.dumps(values, ensure_ascii=False),
                )

    def presentation(self):
        relations = self.relationships("ppt/presentation.xml")
        presentation = self.xml("ppt/presentation.xml")
        if presentation.tag != P + "presentation":
            raise PreparationFailure("unreadable_file")
        for index, slide in enumerate(presentation.iter(P + "sldId"), 1):
            target = relations[slide.attrib[R + "id"]]
            yield from self.paragraphs(self.xml(target), f"slide:{index}", A)
            for related in self.relationships(target).values():
                if related.startswith(("ppt/slideLayouts/", "ppt/slideMasters/")):
                    self.warnings.add("inherited_slide_content_unexamined")
                if related.startswith("ppt/notesSlides/notesSlide"):
                    yield from self.paragraphs(
                        self.xml(related), f"slide:{index}:notes", A
                    )
