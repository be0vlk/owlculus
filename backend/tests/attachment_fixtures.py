"""Small synthetic OOXML containers containing known investigation facts."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def office(extension, *, extra=None):
    word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    sheet = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    drawing = "http://schemas.openxmlformats.org/drawingml/2006/main"
    presentation = "http://schemas.openxmlformats.org/presentationml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    parts = {
        "docx": {
            "word/document.xml": f'<w:document xmlns:w="{word}"><w:body><w:p><w:r><w:t>Ada works at Acme.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Employer disputed.</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        },
        "xlsx": {
            "xl/workbook.xml": f'<workbook xmlns="{sheet}" xmlns:r="{rel}"><sheets><sheet name="Witnesses" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{package_rel}"><Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{sheet}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Ada</t></is></c><c r="B1" t="inlineStr"><is><t>Acme</t></is></c></row><row r="2"><c r="B2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>',
        },
        "pptx": {
            "ppt/presentation.xml": f'<p:presentation xmlns:p="{presentation}" xmlns:r="{rel}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>',
            "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{package_rel}"><Relationship Id="rId1" Type="{rel}/slide" Target="slides/slide1.xml"/></Relationships>',
            "ppt/slides/slide1.xml": f'<p:sld xmlns:p="{presentation}" xmlns:a="{drawing}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Ada works at Acme.</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>',
        },
    }[extension]
    content_types = {
        "docx": "wordprocessingml.document",
        "xlsx": "spreadsheetml.sheet",
        "pptx": "presentationml.presentation",
    }
    main = {
        "docx": "word/document.xml",
        "xlsx": "xl/workbook.xml",
        "pptx": "ppt/presentation.xml",
    }[extension]
    prefix = {
        "docx": "wordprocessingml.document",
        "xlsx": "spreadsheetml.sheet",
        "pptx": "presentationml.presentation",
    }[extension]
    data = BytesIO()
    with ZipFile(data, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{main}" ContentType="application/vnd.openxmlformats-officedocument.{prefix}.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{package_rel}"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="{main}"/></Relationships>',
        )
        for name, content in (parts | (extra or {})).items():
            archive.writestr(name, content)
    return (
        data.getvalue(),
        "application/vnd.openxmlformats-officedocument." + content_types[extension],
    )


def screenshot(format="PNG", label="Ada -> Acme"):
    import io

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (600, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 50), label, fill="black", font_size=36)
    draw.rectangle((20, 30, 330, 110), outline="blue", width=3)
    output = io.BytesIO()
    image.save(output, format=format)
    return output.getvalue()


def document(kinds=("text", "scan")):
    import io

    from fpdf import FPDF

    pdf = FPDF()
    for kind in kinds:
        pdf.add_page()
        if kind == "text":
            pdf.set_font("Helvetica", size=16)
            pdf.text(20, 30, "Ada works at Otherco; employer disputed.")
        else:
            pdf.image(io.BytesIO(screenshot()), x=20, y=30, w=150)
    return bytes(pdf.output())
