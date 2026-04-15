from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


EMU_PER_INCH = 914400
SLIDE_CX = 12192000
SLIDE_CY = 6858000

TITLE_FONT = "Cambria"
BODY_FONT = "Calibri"
MONO_FONT = "Consolas"

COLOR_BG = "F6F7F9"
COLOR_PANEL = "FFFFFF"
COLOR_PANEL_ALT = "F0F3F7"
COLOR_GOLD = "7B8696"
COLOR_TEAL = "3F5F8A"
COLOR_TEXT = "1E2A36"
COLOR_MUTED = "5E6B7A"
COLOR_SOFT = "2B3A4A"
COLOR_LINE = "C9D2DC"

PRESENTATION_NAME = "legal_argument_aware_summarization_mvp_presentation"
OUT_DIR = Path("docs")


def emu(value_in_inches: float) -> int:
    return int(value_in_inches * EMU_PER_INCH)


@dataclass
class Paragraph:
    text: str
    font_size: int = 20
    color: str = COLOR_TEXT
    bold: bool = False
    font_face: str = BODY_FONT
    align: str = "l"


@dataclass
class TextBox:
    x: int
    y: int
    cx: int
    cy: int
    paragraphs: list[Paragraph]
    name: str
    no_fill: bool = True
    line_color: str | None = None


@dataclass
class Rectangle:
    x: int
    y: int
    cx: int
    cy: int
    fill: str
    name: str
    line_color: str | None = None
    geometry: str = "rect"


@dataclass
class SlideSpec:
    title: str
    section: str
    text_boxes: list[TextBox] = field(default_factory=list)
    rectangles: list[Rectangle] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def xml_header() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def shape_tree_prefix() -> str:
    return (
        "<p:spTree>"
        "<p:nvGrpSpPr>"
        '<p:cNvPr id="1" name=""/>'
        "<p:cNvGrpSpPr/>"
        "<p:nvPr/>"
        "</p:nvGrpSpPr>"
        "<p:grpSpPr>"
        "<a:xfrm>"
        '<a:off x="0" y="0"/>'
        '<a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/>'
        '<a:chExt cx="0" cy="0"/>'
        "</a:xfrm>"
        "</p:grpSpPr>"
    )


def shape_tree_suffix() -> str:
    return "</p:spTree>"


def paragraph_xml(paragraph: Paragraph) -> str:
    text = escape(paragraph.text)
    size = paragraph.font_size * 100
    bold = ' b="1"' if paragraph.bold else ""
    return (
        "<a:p>"
        f'<a:pPr algn="{paragraph.align}"/>'
        "<a:r>"
        f'<a:rPr lang="en-US" sz="{size}"{bold} dirty="0" smtClean="0">'
        "<a:solidFill>"
        f'<a:srgbClr val="{paragraph.color}"/>'
        "</a:solidFill>"
        f'<a:latin typeface="{escape(paragraph.font_face)}"/>'
        "</a:rPr>"
        f"<a:t>{text}</a:t>"
        "</a:r>"
        f'<a:endParaRPr lang="en-US" sz="{size}" dirty="0"/>'
        "</a:p>"
    )


def textbox_xml(shape_id: int, textbox: TextBox) -> str:
    fill_xml = "<a:noFill/>" if textbox.no_fill else f"<a:solidFill><a:srgbClr val=\"{COLOR_PANEL}\"/></a:solidFill>"
    if textbox.line_color:
        line_xml = f"<a:ln w=\"9525\"><a:solidFill><a:srgbClr val=\"{textbox.line_color}\"/></a:solidFill></a:ln>"
    else:
        line_xml = "<a:ln><a:noFill/></a:ln>"
    paragraphs = "".join(paragraph_xml(paragraph) for paragraph in textbox.paragraphs)
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(textbox.name)}"/>'
        '<p:cNvSpPr txBox="1"/>'
        "<p:nvPr/>"
        "</p:nvSpPr>"
        "<p:spPr>"
        "<a:xfrm>"
        f'<a:off x="{textbox.x}" y="{textbox.y}"/>'
        f'<a:ext cx="{textbox.cx}" cy="{textbox.cy}"/>'
        "</a:xfrm>"
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f"{fill_xml}{line_xml}"
        "</p:spPr>"
        '<p:txBody><a:bodyPr wrap="square" rtlCol="0" anchor="t"/><a:lstStyle/>'
        f"{paragraphs}</p:txBody>"
        "</p:sp>"
    )


def rectangle_xml(shape_id: int, rectangle: Rectangle) -> str:
    if rectangle.line_color:
        line_xml = f"<a:ln w=\"9525\"><a:solidFill><a:srgbClr val=\"{rectangle.line_color}\"/></a:solidFill></a:ln>"
    else:
        line_xml = "<a:ln><a:noFill/></a:ln>"
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(rectangle.name)}"/>'
        "<p:cNvSpPr/>"
        "<p:nvPr/>"
        "</p:nvSpPr>"
        "<p:spPr>"
        "<a:xfrm>"
        f'<a:off x="{rectangle.x}" y="{rectangle.y}"/>'
        f'<a:ext cx="{rectangle.cx}" cy="{rectangle.cy}"/>'
        "</a:xfrm>"
        f'<a:prstGeom prst="{rectangle.geometry}"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{rectangle.fill}"/></a:solidFill>'
        f"{line_xml}"
        "</p:spPr>"
        "</p:sp>"
    )


def make_footer(slide_number: int) -> list[TextBox]:
    return [
        TextBox(
            x=emu(0.75),
            y=emu(7.0),
            cx=emu(3.2),
            cy=emu(0.25),
            name=f"Footer Left {slide_number}",
            paragraphs=[Paragraph("Legal Argument-Aware Summarization MVP", font_size=10, color=COLOR_MUTED)],
        ),
        TextBox(
            x=emu(11.55),
            y=emu(6.95),
            cx=emu(1.0),
            cy=emu(0.3),
            name=f"Footer Right {slide_number}",
            paragraphs=[Paragraph(f"{slide_number:02d}", font_size=12, color=COLOR_GOLD, bold=True, align="r")],
        ),
    ]


def panel(
    rect_name: str,
    title_name: str,
    body_name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: Sequence[str],
    accent: str = COLOR_GOLD,
    geometry: str = "rect",
) -> tuple[list[Rectangle], list[TextBox]]:
    rectangles = [
        Rectangle(emu(x), emu(y), emu(w), emu(h), COLOR_PANEL, rect_name, line_color=COLOR_LINE, geometry=geometry),
        Rectangle(emu(x), emu(y), emu(w), emu(0.08), accent, f"{rect_name} Accent"),
    ]
    text_boxes = [
        TextBox(
            x=emu(x + 0.2),
            y=emu(y + 0.18),
            cx=emu(w - 0.4),
            cy=emu(0.35),
            name=title_name,
            paragraphs=[Paragraph(title, font_size=18, color=COLOR_SOFT, bold=True)],
        ),
        TextBox(
            x=emu(x + 0.2),
            y=emu(y + 0.6),
            cx=emu(w - 0.35),
            cy=emu(h - 0.75),
            name=body_name,
            paragraphs=[Paragraph(line, font_size=16, color=COLOR_TEXT) for line in lines],
        ),
    ]
    return rectangles, text_boxes


def add_slide_header(slide: SlideSpec) -> None:
    slide.rectangles.extend(
        [
            Rectangle(0, 0, SLIDE_CX, emu(0.08), COLOR_TEAL, "Top Accent"),
        ]
    )
    slide.text_boxes.extend(
        [
            TextBox(
                x=emu(0.92),
                y=emu(0.62),
                cx=emu(1.5),
                cy=emu(0.18),
                name="Section Label",
                paragraphs=[Paragraph(slide.section.upper(), font_size=10, color=COLOR_MUTED, bold=True)],
            ),
            TextBox(
                x=emu(0.85),
                y=emu(0.92),
                cx=emu(11.3),
                cy=emu(0.7),
                name="Slide Title",
                paragraphs=[Paragraph(slide.title, font_size=26, color=COLOR_TEXT, bold=True, font_face=TITLE_FONT)],
            ),
        ]
    )


def slide_xml(spec: SlideSpec) -> str:
    shapes: list[str] = []
    shape_id = 2
    for rectangle in spec.rectangles:
        shapes.append(rectangle_xml(shape_id, rectangle))
        shape_id += 1
    for textbox in spec.text_boxes:
        shapes.append(textbox_xml(shape_id, textbox))
        shape_id += 1
    return (
        xml_header()
        + '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        + 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        + "<p:cSld>"
        + "<p:bg><p:bgPr><a:solidFill><a:srgbClr val=\""
        + COLOR_BG
        + "\"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>"
        + shape_tree_prefix()
        + "".join(shapes)
        + shape_tree_suffix()
        + "</p:cSld>"
        + "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        + "</p:sld>"
    )


def slide_relationship_xml() -> str:
    return (
        xml_header()
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        + "</Relationships>"
    )


def content_types_xml(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    return (
        xml_header()
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        + '<Default Extension="xml" ContentType="application/xml"/>'
        + '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        + '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        + '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        + '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        + '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        + slide_overrides
        + "</Types>"
    )


def package_relationships_xml() -> str:
    return (
        xml_header()
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        + '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        + '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        + "</Relationships>"
    )


def app_xml(slides: Sequence[SlideSpec]) -> str:
    slide_titles = "".join(f"<vt:lpstr>{escape(slide.title)}</vt:lpstr>" for slide in slides)
    return (
        xml_header()
        + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        + 'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        + "<Application>Microsoft Office PowerPoint</Application>"
        + "<PresentationFormat>Widescreen</PresentationFormat>"
        + f"<Slides>{len(slides)}</Slides>"
        + "<Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        + "<ScaleCrop>false</ScaleCrop>"
        + "<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\">"
        + "<vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant>"
        + "<vt:variant><vt:i4>1</vt:i4></vt:variant>"
        + "</vt:vector></HeadingPairs>"
        + f"<TitlesOfParts><vt:vector size=\"{len(slides)}\" baseType=\"lpstr\">{slide_titles}</vt:vector></TitlesOfParts>"
        + "<Company>OpenAI Codex</Company>"
        + "<LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged>"
        + "<AppVersion>16.0000</AppVersion>"
        + "</Properties>"
    )


def core_xml() -> str:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        xml_header()
        + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        + 'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        + 'xmlns:dcterms="http://purl.org/dc/terms/" '
        + 'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        + 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        + "<dc:title>Legal Argument-Aware Summarization MVP</dc:title>"
        + "<dc:subject>Project presentation</dc:subject>"
        + "<dc:creator>OpenAI Codex</dc:creator>"
        + "<cp:keywords>legal nlp, summarization, generative ai, powerpoint</cp:keywords>"
        + "<dc:description>Presentation deck for the legal argument-aware summarization MVP.</dc:description>"
        + "<cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>"
        + f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        + f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
        + "</cp:coreProperties>"
    )


def presentation_xml(slides: Sequence[SlideSpec]) -> str:
    slide_refs = "".join(
        f'<p:sldId id="{255 + index}" r:id="rId{index}"/>'
        for index in range(1, len(slides) + 1)
    )
    master_rel_id = len(slides) + 1
    return (
        xml_header()
        + '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        + 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1" autoCompressPictures="0">'
        + f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{master_rel_id}"/></p:sldMasterIdLst>'
        + f"<p:sldIdLst>{slide_refs}</p:sldIdLst>"
        + f'<p:sldSz cx="{SLIDE_CX}" cy="{SLIDE_CY}"/>'
        + '<p:notesSz cx="6858000" cy="9144000"/>'
        + "<p:defaultTextStyle>"
        + '<a:defPPr/><a:lvl1pPr marL="0" algn="l"><a:defRPr sz="1800"/></a:lvl1pPr>'
        + '<a:lvl2pPr marL="457200" algn="l"><a:defRPr sz="1600"/></a:lvl2pPr>'
        + '<a:lvl3pPr marL="914400" algn="l"><a:defRPr sz="1400"/></a:lvl3pPr>'
        + "</p:defaultTextStyle>"
        + "</p:presentation>"
    )


def presentation_relationships_xml(slides: Sequence[SlideSpec]) -> str:
    slide_relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, len(slides) + 1)
    )
    master_rel_id = len(slides) + 1
    return (
        xml_header()
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + slide_relationships
        + f'<Relationship Id="rId{master_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
        + "</Relationships>"
    )


def slide_master_xml() -> str:
    return (
        xml_header()
        + '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        + 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        + '<p:cSld name="Codex Master">'
        + shape_tree_prefix()
        + shape_tree_suffix()
        + "</p:cSld>"
        + '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        + '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        + "<p:txStyles>"
        + "<p:titleStyle><a:lvl1pPr algn=\"l\"><a:defRPr sz=\"3200\" b=\"1\"/></a:lvl1pPr></p:titleStyle>"
        + "<p:bodyStyle>"
        + '<a:lvl1pPr marL="0" algn="l"><a:defRPr sz="2000"/></a:lvl1pPr>'
        + '<a:lvl2pPr marL="457200" algn="l"><a:defRPr sz="1800"/></a:lvl2pPr>'
        + '<a:lvl3pPr marL="914400" algn="l"><a:defRPr sz="1600"/></a:lvl3pPr>'
        + "</p:bodyStyle>"
        + "<p:otherStyle><a:lvl1pPr algn=\"l\"><a:defRPr sz=\"1800\"/></a:lvl1pPr></p:otherStyle>"
        + "</p:txStyles>"
        + "</p:sldMaster>"
    )


def slide_master_relationships_xml() -> str:
    return (
        xml_header()
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        + '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        + "</Relationships>"
    )


def slide_layout_xml() -> str:
    return (
        xml_header()
        + '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        + 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
        + '<p:cSld name="Blank">'
        + shape_tree_prefix()
        + shape_tree_suffix()
        + "</p:cSld>"
        + "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        + "</p:sldLayout>"
    )


def slide_layout_relationships_xml() -> str:
    return (
        xml_header()
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        + "</Relationships>"
    )


def theme_xml() -> str:
    return (
        xml_header()
        + '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Counsel Desk">'
        + "<a:themeElements>"
        + '<a:clrScheme name="Counsel Desk">'
        + '<a:dk1><a:srgbClr val="0B1320"/></a:dk1>'
        + '<a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        + '<a:dk2><a:srgbClr val="1F2D3D"/></a:dk2>'
        + '<a:lt2><a:srgbClr val="EAF1F8"/></a:lt2>'
        + f'<a:accent1><a:srgbClr val="{COLOR_GOLD}"/></a:accent1>'
        + f'<a:accent2><a:srgbClr val="{COLOR_TEAL}"/></a:accent2>'
        + '<a:accent3><a:srgbClr val="7A90A8"/></a:accent3>'
        + '<a:accent4><a:srgbClr val="E57F84"/></a:accent4>'
        + '<a:accent5><a:srgbClr val="94C973"/></a:accent5>'
        + '<a:accent6><a:srgbClr val="F3C46F"/></a:accent6>'
        + f'<a:hlink><a:srgbClr val="{COLOR_TEAL}"/></a:hlink>'
        + f'<a:folHlink><a:srgbClr val="{COLOR_GOLD}"/></a:folHlink>'
        + "</a:clrScheme>"
        + '<a:fontScheme name="Counsel Fonts">'
        + f'<a:majorFont><a:latin typeface="{TITLE_FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        + f'<a:minorFont><a:latin typeface="{BODY_FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        + "</a:fontScheme>"
        + '<a:fmtScheme name="Counsel Format">'
        + "<a:fillStyleLst>"
        + "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        + "<a:gradFill rotWithShape=\"1\"><a:gsLst>"
        + "<a:gs pos=\"0\"><a:schemeClr val=\"phClr\"><a:tint val=\"50000\"/><a:satMod val=\"300000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"35000\"><a:schemeClr val=\"phClr\"><a:tint val=\"37000\"/><a:satMod val=\"300000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"100000\"><a:schemeClr val=\"phClr\"><a:tint val=\"15000\"/><a:satMod val=\"350000\"/></a:schemeClr></a:gs>"
        + "</a:gsLst><a:lin ang=\"16200000\" scaled=\"1\"/></a:gradFill>"
        + "<a:gradFill rotWithShape=\"1\"><a:gsLst>"
        + "<a:gs pos=\"0\"><a:schemeClr val=\"phClr\"><a:shade val=\"51000\"/><a:satMod val=\"130000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"80000\"><a:schemeClr val=\"phClr\"><a:shade val=\"93000\"/><a:satMod val=\"130000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"100000\"><a:schemeClr val=\"phClr\"><a:shade val=\"94000\"/><a:satMod val=\"135000\"/></a:schemeClr></a:gs>"
        + "</a:gsLst><a:lin ang=\"16200000\" scaled=\"0\"/></a:gradFill>"
        + "</a:fillStyleLst>"
        + "<a:lineStyleLst>"
        + "<a:ln w=\"9525\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/><a:miter lim=\"800000\"/></a:ln>"
        + "<a:ln w=\"25400\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/><a:miter lim=\"800000\"/></a:ln>"
        + "<a:ln w=\"38100\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/><a:miter lim=\"800000\"/></a:ln>"
        + "</a:lineStyleLst>"
        + "<a:effectStyleLst>"
        + "<a:effectStyle><a:effectLst/></a:effectStyle>"
        + "<a:effectStyle><a:effectLst/></a:effectStyle>"
        + "<a:effectStyle><a:effectLst/></a:effectStyle>"
        + "</a:effectStyleLst>"
        + "<a:bgFillStyleLst>"
        + "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        + "<a:solidFill><a:schemeClr val=\"phClr\"><a:tint val=\"95000\"/><a:satMod val=\"170000\"/></a:schemeClr></a:solidFill>"
        + "<a:gradFill rotWithShape=\"1\"><a:gsLst>"
        + "<a:gs pos=\"0\"><a:schemeClr val=\"phClr\"><a:tint val=\"93000\"/><a:satMod val=\"150000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"50000\"><a:schemeClr val=\"phClr\"><a:tint val=\"98000\"/><a:satMod val=\"130000\"/></a:schemeClr></a:gs>"
        + "<a:gs pos=\"100000\"><a:schemeClr val=\"phClr\"><a:shade val=\"90000\"/><a:satMod val=\"120000\"/></a:schemeClr></a:gs>"
        + "</a:gsLst><a:path path=\"circle\"><a:fillToRect l=\"50000\" t=\"-80000\" r=\"50000\" b=\"180000\"/></a:path></a:gradFill>"
        + "</a:bgFillStyleLst>"
        + "</a:fmtScheme>"
        + "</a:themeElements>"
        + "<a:objectDefaults/><a:extraClrSchemeLst/>"
        + "</a:theme>"
    )


def build_slides() -> list[SlideSpec]:
    slides: list[SlideSpec] = []

    slide1 = SlideSpec(
        title="Legal Argument-Aware Summarization MVP",
        section="Overview",
        notes=[
            "Open by positioning the system as a legal GenAI project and a research-grade MVP.",
            "Mention that the pipeline is designed for long legal opinions and makes candidate selection structure-aware.",
        ],
    )
    add_slide_header(slide1)
    slide1.text_boxes.append(
        TextBox(
            x=emu(0.9),
            y=emu(1.82),
            cx=emu(10.9),
            cy=emu(0.8),
            name="Subtitle",
            paragraphs=[
                Paragraph(
                    "Open-source local pipeline for long court judgments with rhetorical-role labeling, multi-candidate generation, and structure-aware reranking.",
                    font_size=22,
                    color=COLOR_MUTED,
                )
            ],
        )
    )
    chips = [
        ("TXT + PDF intake", 0.95),
        ("Argument-aware reranking", 4.25),
        ("CPU fallback + local UI", 8.1),
    ]
    for index, (label, x) in enumerate(chips, start=1):
        slide1.rectangles.append(Rectangle(emu(x), emu(3.0), emu(3.0), emu(0.6), COLOR_PANEL_ALT, f"Chip {index}", line_color=COLOR_LINE))
        slide1.text_boxes.append(
            TextBox(
                x=emu(x + 0.18),
                y=emu(3.18),
                cx=emu(2.7),
                cy=emu(0.22),
                name=f"Chip Text {index}",
                paragraphs=[Paragraph(label, font_size=15, color=COLOR_SOFT, bold=True, align="c")],
            )
        )
    hero_rects, hero_boxes = panel(
        "Hero Panel",
        "Hero Title",
        "Hero Body",
        0.95,
        4.0,
        11.45,
        1.85,
        "Why this project matters",
        [
            "Long legal opinions mix facts, issues, arguments, statutes, analysis, and the final ruling across many pages.",
            "A plain summarizer can miss the court's reasoning path, so this project adds structure understanding before selecting the final summary.",
        ],
        accent=COLOR_TEAL,
    )
    slide1.rectangles.extend(hero_rects)
    slide1.text_boxes.extend(hero_boxes + make_footer(1))
    slides.append(slide1)

    slide2 = SlideSpec(
        title="Problem Statement And Motivation",
        section="Problem",
        notes=[
            "Explain why legal summarization is harder than generic article summarization.",
            "Highlight the need to preserve the issue, analysis, and final ruling.",
        ],
    )
    add_slide_header(slide2)
    left_rects, left_boxes = panel(
        "Problem Left",
        "Problem Left Title",
        "Problem Left Body",
        0.9,
        1.85,
        5.55,
        3.95,
        "Why plain summarizers struggle",
        [
            "- Legal documents are long and exceed standard context windows.",
            "- Key reasoning is distributed across sections rather than stated once.",
            "- Different stakeholders care about different rhetorical roles.",
            "- Courts embed citations, statutory references, and procedural history that should survive summarization.",
        ],
    )
    right_rects, right_boxes = panel(
        "Problem Right",
        "Problem Right Title",
        "Problem Right Body",
        6.65,
        1.85,
        5.55,
        3.95,
        "What this MVP optimizes for",
        [
            "- Abstractive legal summaries that stay useful, not just fluent.",
            "- Transparent selection through candidate comparison and score breakdowns.",
            "- Practical local execution using open-source models and heuristic fallbacks.",
            "- A full deliverable with API, UI, configs, scripts, tests, and sample data.",
        ],
        accent=COLOR_TEAL,
    )
    slide2.rectangles.extend(left_rects + right_rects)
    slide2.text_boxes.extend(left_boxes + right_boxes + make_footer(2))
    slides.append(slide2)

    slide3 = SlideSpec(
        title="Objectives And Key Contributions",
        section="Solution",
        notes=[
            "Summarize the three main contribution buckets: structure extraction, candidate generation and selection, and explainable delivery.",
        ],
    )
    add_slide_header(slide3)
    columns = [
        (
            0.9,
            "Input And Structure",
            [
                "- Accepts TXT or PDF legal documents.",
                "- Normalizes citations, whitespace, and section headers.",
                "- Segments text into paragraphs, sentences, and rhetorical units.",
                "- Preserves source span mapping for explainability.",
            ],
        ),
        (
            4.37,
            "Generation And Selection",
            [
                "- Produces multiple abstractive summary candidates.",
                "- Uses role-focused and chunk-merge strategies for long opinions.",
                "- Reranks candidates with semantic, structural, and factual signals.",
                "- Returns the best summary instead of trusting one decode.",
            ],
        ),
        (
            7.84,
            "Explainability And Delivery",
            [
                "- Shows rhetorical roles with confidence scores.",
                "- Exposes reranking components and supporting source segments.",
                "- Supports FastAPI, Streamlit, export flows, and CPU-safe fallback.",
                "- Includes tests, configs, demo data, and a training script.",
            ],
        ),
    ]
    for idx, (x, heading, lines) in enumerate(columns, start=1):
        rects, boxes = panel(
            f"Contribution {idx}",
            f"Contribution {idx} Title",
            f"Contribution {idx} Body",
            x,
            2.05,
            3.0,
            3.85,
            heading,
            lines,
            accent=COLOR_GOLD if idx != 2 else COLOR_TEAL,
        )
        slide3.rectangles.extend(rects)
        slide3.text_boxes.extend(boxes)
    slide3.text_boxes.extend(make_footer(3))
    slides.append(slide3)

    slide4 = SlideSpec(
        title="Architecture Overview",
        section="Architecture",
        notes=[
            "Walk through the repo architecture from ingestion to final delivery.",
        ],
    )
    add_slide_header(slide4)
    architecture_steps = [
        ("1. Loader", "TXT/PDF intake and dataset reading", 0.95, 2.1),
        ("2. DataProcessor", "Normalization, segmentation, and chunking", 3.2, 2.1),
        ("3. RoleClassifier", "Facts, issue, arguments, analysis, ruling, statute, other", 5.45, 2.1),
        ("4. SummaryGenerator", "Five candidate strategies across full-document and chunk-aware inputs", 7.7, 2.1),
        ("5. SummaryReranker", "Weighted scoring with semantic and structural signals", 2.05, 4.45),
        ("6. Evaluator + UI/API", "ROUGE, BERTScore, explainability, FastAPI, Streamlit", 6.1, 4.45),
    ]
    for index, (heading, body, x, y) in enumerate(architecture_steps, start=1):
        slide4.rectangles.append(Rectangle(emu(x), emu(y), emu(2.05), emu(1.25), COLOR_PANEL, f"Architecture Box {index}", line_color=COLOR_LINE))
        slide4.rectangles.append(Rectangle(emu(x), emu(y), emu(2.05), emu(0.07), COLOR_GOLD if index % 2 else COLOR_TEAL, f"Architecture Accent {index}"))
        slide4.text_boxes.append(
            TextBox(
                x=emu(x + 0.12),
                y=emu(y + 0.16),
                cx=emu(1.8),
                cy=emu(0.3),
                name=f"Architecture Heading {index}",
                paragraphs=[Paragraph(heading, font_size=15, color=COLOR_SOFT, bold=True, align="c")],
            )
        )
        slide4.text_boxes.append(
            TextBox(
                x=emu(x + 0.12),
                y=emu(y + 0.48),
                cx=emu(1.82),
                cy=emu(0.58),
                name=f"Architecture Body {index}",
                paragraphs=[Paragraph(body, font_size=12, color=COLOR_MUTED, align="c")],
            )
        )
    slide4.text_boxes.append(
        TextBox(
            x=emu(1.65),
            y=emu(3.45),
            cx=emu(10.0),
            cy=emu(0.35),
            name="Architecture Flow",
            paragraphs=[Paragraph("Loader -> DataProcessor -> RoleClassifier -> SummaryGenerator -> SummaryReranker -> Evaluator/UI", font_size=16, color=COLOR_GOLD, bold=True, align="c", font_face=MONO_FONT)],
        )
    )
    slide4.text_boxes.extend(make_footer(4))
    slides.append(slide4)

    slide5 = SlideSpec(
        title="Detailed Pipeline With Chunking Example",
        section="Pipeline",
        notes=[
            "Explain each stage in operational order and call out why chunking is necessary for long judgments.",
        ],
    )
    add_slide_header(slide5)
    left_rects, left_boxes = panel(
        "Pipeline Steps",
        "Pipeline Steps Title",
        "Pipeline Steps Body",
        0.9,
        1.95,
        5.65,
        4.3,
        "What happens after the user clicks summarize",
        [
            "1. Load text from TXT or extract it from PDF.",
            "2. Normalize legal citations, headers, whitespace, and encoding artifacts.",
            "3. Segment into paragraphs, sentences, and rhetorical units.",
            "4. Chunk the document into overlapping windows for long-context safety.",
            "5. Predict rhetorical roles for each unit.",
            "6. Generate multiple summary candidates.",
            "7. Rerank candidates and return the best summary with evidence.",
        ],
    )
    right_rects, right_boxes = panel(
        "Chunking Example",
        "Chunking Example Title",
        "Chunking Example Body",
        6.75,
        1.95,
        5.45,
        4.3,
        "How chunking works in practice",
        [
            "Example long opinion -> Chunk 1: facts + issue",
            "Chunk 2: issue overlap + party arguments",
            "Chunk 3: analysis + statute references",
            "Chunk 4: analysis overlap + final ruling",
            "Overlap preserves continuity so key reasoning is not cut off at chunk boundaries.",
            "Later strategies either summarize each chunk and merge them or create role-aware inputs from the segmented document.",
        ],
        accent=COLOR_TEAL,
    )
    slide5.rectangles.extend(left_rects + right_rects)
    slide5.text_boxes.extend(left_boxes + right_boxes + make_footer(5))
    slides.append(slide5)

    slide6 = SlideSpec(
        title="Models And Libraries",
        section="Stack",
        notes=[
            "Use this slide if someone asks whether the project relies on paid APIs or a custom model checkpoint.",
        ],
    )
    add_slide_header(slide6)
    model_rects, model_boxes = panel(
        "Model Panel",
        "Model Panel Title",
        "Model Panel Body",
        0.9,
        1.95,
        5.6,
        4.35,
        "Models used by the system",
        [
            "- Summarization: allenai/led-base-16384",
            "- Fallback summarization: facebook/bart-large-cnn",
            "- Lightweight fallback: google/flan-t5-base",
            "- Role classification: law-ai/InLegalBERT",
            "- Reranking embeddings: sentence-transformers/all-MiniLM-L6-v2",
            "- Lightweight role fallback: distilbert-base-uncased",
        ],
    )
    lib_rects, lib_boxes = panel(
        "Library Panel",
        "Library Panel Title",
        "Library Panel Body",
        6.7,
        1.95,
        5.5,
        4.35,
        "Core libraries and runtime choices",
        [
            "- PyTorch, Hugging Face Transformers, datasets, scikit-learn",
            "- sentence-transformers, numpy, pandas, YAML configs",
            "- FastAPI + Pydantic for backend APIs",
            "- Streamlit for the analyst-facing interface",
            "- pdfplumber and pypdf for PDF extraction",
            "- pytest, Dockerfile, and CPU-safe runtime flags",
        ],
        accent=COLOR_TEAL,
    )
    slide6.rectangles.extend(model_rects + lib_rects)
    slide6.text_boxes.extend(model_boxes + lib_boxes)
    slide6.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(6.45),
            cx=emu(11.2),
            cy=emu(0.32),
            name="Training Note",
            paragraphs=[Paragraph("Important note: the app does not require a custom trained model to run. A fine-tuned rhetorical-role classifier is optional and improves quality rather than enabling the pipeline.", font_size=14, color=COLOR_GOLD)],
        )
    )
    slide6.text_boxes.extend(make_footer(6))
    slides.append(slide6)

    slide7 = SlideSpec(
        title="Candidate Generation And Role-Aware Reranking",
        section="Selection",
        notes=[
            "Explain that candidates are multiple possible summaries for the same legal document.",
            "The final summary is chosen only after reranking with semantic and rhetorical-role-aware signals.",
        ],
    )
    add_slide_header(slide7)
    top_left_rects, top_left_boxes = panel(
        "Candidate Strategies",
        "Candidate Strategies Title",
        "Candidate Strategies Body",
        0.9,
        1.95,
        5.55,
        2.0,
        "Generation strategies",
        [
            "- baseline_full_document",
            "- role_focus_facts_issue_ruling",
            "- analysis_heavy",
            "- chunk_merge_conservative",
            "- chunk_merge_diverse",
        ],
    )
    top_right_rects, top_right_boxes = panel(
        "Reranker Signals",
        "Reranker Signals Title",
        "Reranker Signals Body",
        6.65,
        1.95,
        5.55,
        2.0,
        "Final score components",
        [
            "- semantic similarity = 0.38",
            "- role coverage = 0.26",
            "- factual proxy = 0.20",
            "- readability bonus = 0.08",
            "- redundancy and length penalties are subtracted during ranking",
        ],
        accent=COLOR_TEAL,
    )
    bottom_rects, bottom_boxes = panel(
        "Why Candidates",
        "Why Candidates Title",
        "Why Candidates Body",
        0.9,
        4.2,
        11.3,
        1.95,
        "Why multiple candidates matter",
        [
            "One candidate may cover the facts well, another may better capture the court's reasoning, and a third may be more concise.",
            "The reranker makes the final decision by balancing meaning preservation, legal-role coverage, factual support proxies, repetition control, and target length.",
        ],
        accent=COLOR_GOLD,
    )
    slide7.rectangles.extend(top_left_rects + top_right_rects + bottom_rects)
    slide7.text_boxes.extend(top_left_boxes + top_right_boxes + bottom_boxes + make_footer(7))
    slides.append(slide7)

    slide8 = SlideSpec(
        title="Evaluation Metrics And Why They Matter",
        section="Evaluation",
        notes=[
            "Explain both automatic metrics and the qualitative explainability outputs available in the app.",
        ],
    )
    add_slide_header(slide8)
    metric_rects, metric_boxes = panel(
        "Metric Panel",
        "Metric Panel Title",
        "Metric Panel Body",
        0.9,
        1.95,
        5.65,
        4.4,
        "Automatic evaluation metrics",
        [
            "- ROUGE-1: unigram overlap for content coverage",
            "- ROUGE-2: bigram overlap for phrase-level fidelity",
            "- ROUGE-L: longest common subsequence for sequence similarity",
            "- BERTScore Precision/Recall/F1: semantic match even when wording changes",
        ],
    )
    explain_rects, explain_boxes = panel(
        "Explainability Panel",
        "Explainability Panel Title",
        "Explainability Panel Body",
        6.75,
        1.95,
        5.45,
        4.4,
        "Interpretability outputs",
        [
            "- predicted rhetorical role distribution",
            "- top supporting legal segments for the selected summary",
            "- candidate comparison table with component scores",
            "- explanation of why the top summary was chosen",
            "- optional gold-summary comparison when a reference summary is supplied",
        ],
        accent=COLOR_TEAL,
    )
    slide8.rectangles.extend(metric_rects + explain_rects)
    slide8.text_boxes.extend(metric_boxes + explain_boxes + make_footer(8))
    slides.append(slide8)

    slide9 = SlideSpec(
        title="User Experience, API, And Deployment",
        section="Product",
        notes=[
            "Show that this is a usable application, not only a model pipeline.",
        ],
    )
    add_slide_header(slide9)
    ui_rects, ui_boxes = panel(
        "UI Panel",
        "UI Panel Title",
        "UI Panel Body",
        0.9,
        1.95,
        5.55,
        4.3,
        "Streamlit UI highlights",
        [
            "- dark-mode legal-tech interface with local sign-in",
            "- TXT/PDF upload or paste-text intake",
            "- live pipeline status during chunking, role prediction, generation, and reranking",
            "- best-summary-first layout with optional advanced analysis",
            "- export to Markdown, JSON, and optional PDF",
        ],
    )
    api_rects, api_boxes = panel(
        "API Panel",
        "API Panel Title",
        "API Panel Body",
        6.65,
        1.95,
        5.55,
        4.3,
        "Backend and operational features",
        [
            "- POST /upload-pdf for PDF extraction",
            "- POST /summarize for full end-to-end inference",
            "- POST /evaluate for ROUGE and BERTScore",
            "- config-driven model names, chunk sizes, and score weights",
            "- Dockerfile, tests, scripts, and CPU-safe local execution path",
        ],
        accent=COLOR_TEAL,
    )
    slide9.rectangles.extend(ui_rects + api_rects)
    slide9.text_boxes.extend(ui_boxes + api_boxes)
    slide9.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(6.45),
            cx=emu(11.2),
            cy=emu(0.3),
            name="Operational Note",
            paragraphs=[Paragraph("The system can run entirely with heuristic fallback when heavyweight Hugging Face models are unavailable or the machine is CPU-only.", font_size=14, color=COLOR_GOLD)],
        )
    )
    slide9.text_boxes.extend(make_footer(9))
    slides.append(slide9)

    slide10 = SlideSpec(
        title="Faithful To The Paper Vs Pragmatic Adaptation",
        section="Research",
        notes=[
            "Be direct here: this is paper-inspired and faithful to the high-level idea, but it is not a one-to-one reproduction.",
        ],
    )
    add_slide_header(slide10)
    faithful_rects, faithful_boxes = panel(
        "Faithful Panel",
        "Faithful Panel Title",
        "Faithful Panel Body",
        0.9,
        1.95,
        5.55,
        4.3,
        "What is faithful to the paper",
        [
            "- Structure-aware summarization of long legal opinions",
            "- Multiple candidate summaries instead of one final decode",
            "- Final selection based on rhetorical or argument-aware cues",
            "- Long-document handling through chunking and merge-style processing",
        ],
    )
    pragmatic_rects, pragmatic_boxes = panel(
        "Pragmatic Panel",
        "Pragmatic Panel Title",
        "Pragmatic Panel Body",
        6.65,
        1.95,
        5.55,
        4.3,
        "What was adapted for an MVP",
        [
            "- Hybrid role prediction using pretrained encoders and heuristics",
            "- Practical reranking proxies for coverage and faithfulness",
            "- Productized API, UI, auth, export, and test layers",
            "- Open-source local stack that works without proprietary APIs",
        ],
        accent=COLOR_TEAL,
    )
    slide10.rectangles.extend(faithful_rects + pragmatic_rects)
    slide10.text_boxes.extend(faithful_boxes + pragmatic_boxes + make_footer(10))
    slides.append(slide10)

    slide11 = SlideSpec(
        title="Limitations And Future Work",
        section="Roadmap",
        notes=[
            "Close the technical story with honest limitations and a strong next-step roadmap.",
        ],
    )
    add_slide_header(slide11)
    limits_rects, limits_boxes = panel(
        "Limits Panel",
        "Limits Panel Title",
        "Limits Panel Body",
        0.9,
        1.95,
        5.55,
        4.3,
        "Current limitations",
        [
            "- Not a one-to-one reproduction of the ACL experimental setup",
            "- Summary quality depends on local model availability and CPU constraints",
            "- Rhetorical-role quality is best when a fine-tuned classifier is available",
            "- PDF extraction quality depends on the source PDF formatting",
        ],
    )
    future_rects, future_boxes = panel(
        "Future Panel",
        "Future Panel Title",
        "Future Panel Body",
        6.65,
        1.95,
        5.55,
        4.3,
        "Recommended future upgrades",
        [
            "- Fine-tune on a richer legal rhetorical-role dataset",
            "- Add stronger factuality checks and citation grounding",
            "- Benchmark on larger legal summarization datasets",
            "- Expand jurisdiction-specific prompt templates and scoring rules",
            "- Add richer PDF layout parsing and table extraction",
        ],
        accent=COLOR_TEAL,
    )
    slide11.rectangles.extend(limits_rects + future_rects)
    slide11.text_boxes.extend(limits_boxes + future_boxes)
    slide11.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(6.45),
            cx=emu(11.2),
            cy=emu(0.3),
            name="Roadmap Note",
            paragraphs=[Paragraph("Best next research step: train a dedicated rhetorical-role classifier checkpoint and plug it into the same pipeline for stronger reranking quality.", font_size=14, color=COLOR_GOLD)],
        )
    )
    slide11.text_boxes.extend(make_footer(11))
    slides.append(slide11)

    slide12 = SlideSpec(
        title="Closing Summary",
        section="Wrap-Up",
        notes=[
            "End with the one-sentence definition of the system and invite questions.",
        ],
    )
    add_slide_header(slide12)
    summary_rects, summary_boxes = panel(
        "Summary Panel",
        "Summary Panel Title",
        "Summary Panel Body",
        1.25,
        2.15,
        10.7,
        2.45,
        "One-line takeaway",
        [
            "This project reads a long legal document, understands its rhetorical structure, generates multiple abstractive summaries, reranks them using argument-aware scoring, and returns the best summary with evidence.",
        ],
        accent=COLOR_TEAL,
    )
    slide12.rectangles.extend(summary_rects)
    slide12.text_boxes.extend(summary_boxes)
    slide12.text_boxes.append(
        TextBox(
            x=emu(1.35),
            y=emu(5.15),
            cx=emu(10.4),
            cy=emu(0.8),
            name="Closing Prompt",
            paragraphs=[
                Paragraph("Questions?", font_size=30, color=COLOR_GOLD, bold=True, align="c", font_face=TITLE_FONT),
                Paragraph("Thank you.", font_size=18, color=COLOR_MUTED, align="c"),
            ],
        )
    )
    slide12.text_boxes.extend(make_footer(12))
    slides.append(slide12)

    return slides


def build_polished_slides() -> list[SlideSpec]:
    slides: list[SlideSpec] = []

    slide1 = SlideSpec(
        title="Legal Argument-Aware Summarization MVP",
        section="Overview",
        notes=[
            "Introduce the project as a legal GenAI system built for long court judgments and legal opinions.",
            "Call out the three strongest ideas immediately: structure understanding, multiple candidates, and argument-aware reranking.",
            "Use the metric tiles to anchor the audience in the scale of the system.",
        ],
    )
    add_slide_header(slide1)
    slide1.rectangles.extend(
        [
            Rectangle(emu(8.9), emu(0.95), emu(2.45), emu(2.45), COLOR_PANEL_ALT, "Hero Orb A", geometry="ellipse", line_color=COLOR_LINE),
            Rectangle(emu(10.2), emu(2.15), emu(1.4), emu(1.4), COLOR_TEAL, "Hero Orb B", geometry="ellipse"),
            Rectangle(emu(0.92), emu(5.55), emu(10.95), emu(0.02), COLOR_LINE, "Hero Divider"),
        ]
    )
    slide1.text_boxes.append(
        TextBox(
            x=emu(0.9),
            y=emu(1.75),
            cx=emu(7.2),
            cy=emu(1.2),
            name="Hero Summary",
            paragraphs=[
                Paragraph(
                    "Open-source legal summarization system that reads long judgments, detects rhetorical structure, generates multiple abstractive summaries, reranks them intelligently, and returns the best summary with evidence.",
                    font_size=24,
                    color=COLOR_SOFT,
                )
            ],
        )
    )
    stats = [
        ("5", "candidate strategies", 0.95),
        ("7", "rhetorical roles", 3.55),
        ("3", "API endpoints", 6.15),
        ("CPU", "safe fallback mode", 8.75),
    ]
    for idx, (value, label, x) in enumerate(stats, start=1):
        slide1.rectangles.append(Rectangle(emu(x), emu(4.15), emu(2.2), emu(1.05), COLOR_PANEL, f"Stat Card {idx}", line_color=COLOR_LINE, geometry="roundRect"))
        slide1.text_boxes.append(
            TextBox(
                x=emu(x + 0.16),
                y=emu(4.28),
                cx=emu(0.8),
                cy=emu(0.35),
                name=f"Stat Value {idx}",
                paragraphs=[Paragraph(value, font_size=28, color=COLOR_GOLD, bold=True)],
            )
        )
        slide1.text_boxes.append(
            TextBox(
                x=emu(x + 0.16),
                y=emu(4.66),
                cx=emu(1.8),
                cy=emu(0.25),
                name=f"Stat Label {idx}",
                paragraphs=[Paragraph(label, font_size=13, color=COLOR_MUTED)],
            )
        )
    slide1.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(5.8),
            cx=emu(10.6),
            cy=emu(0.8),
            name="Hero Footer",
            paragraphs=[
                Paragraph("Research inspiration: ACL Findings 2023 | Productization: API + Streamlit + auth + exports + tests", font_size=16, color=COLOR_MUTED),
                Paragraph("Target use case: Indian judgments and U.S. legal opinions", font_size=16, color=COLOR_TEXT, bold=True),
            ],
        )
    )
    slide1.text_boxes.extend(make_footer(1))
    slides.append(slide1)

    slide2 = SlideSpec(
        title="Executive Summary",
        section="Summary",
        notes=[
            "Use this slide like an executive overview for faculty or evaluators.",
            "Cover the problem, the technical approach, the product output, and the practical value in under one minute.",
        ],
    )
    add_slide_header(slide2)
    left_rects, left_boxes = panel(
        "Exec Left",
        "Exec Left Title",
        "Exec Left Body",
        0.9,
        1.9,
        7.15,
        4.55,
        "What the project does",
        [
            "- Accepts TXT and PDF legal documents and extracts clean text.",
            "- Segments documents into paragraphs, sentences, rhetorical units, and long-context chunks.",
            "- Predicts rhetorical roles such as facts, issue, arguments, analysis, ruling, statute, and other.",
            "- Generates multiple abstractive summary candidates with different strategies.",
            "- Reranks those candidates with semantic, structural, factual, redundancy, and length-aware scoring.",
            "- Returns the best summary, evaluation metrics, and interpretable evidence.",
        ],
        accent=COLOR_TEAL,
    )
    right_rects, right_boxes = panel(
        "Exec Right",
        "Exec Right Title",
        "Exec Right Body",
        8.3,
        1.9,
        3.85,
        4.55,
        "Why it stands out",
        [
            "- GenAI, not just extractive summarization",
            "- Local open-source stack",
            "- Paper-inspired but deployable",
            "- Strong explainability layer",
            "- Complete repo with scripts, configs, tests, Docker, API, and UI",
        ],
    )
    slide2.rectangles.extend(left_rects + right_rects)
    slide2.text_boxes.extend(left_boxes + right_boxes + make_footer(2))
    slides.append(slide2)

    slide3 = SlideSpec(
        title="Problem Statement And Motivation",
        section="Problem",
        notes=[
            "Frame the problem in human terms: lawyers and researchers need reasoning-aware summaries, not only short summaries.",
            "Emphasize that judgments are long, dense, and structurally layered.",
        ],
    )
    add_slide_header(slide3)
    problem_rects, problem_boxes = panel(
        "Problem Panel",
        "Problem Panel Title",
        "Problem Panel Body",
        0.9,
        1.9,
        5.55,
        4.65,
        "Why legal summarization is hard",
        [
            "- Long opinions exceed the context window of many standard summarization models.",
            "- Facts, issue, statute, analysis, and ruling are spread across the document rather than grouped in one place.",
            "- Legal summaries must preserve what was decided and why, not just what happened.",
            "- Domain-specific citations, section headers, numbers, and procedural details need careful handling.",
        ],
    )
    gap_rects, gap_boxes = panel(
        "Gap Panel",
        "Gap Panel Title",
        "Gap Panel Body",
        6.65,
        1.9,
        5.55,
        4.65,
        "Design response in this MVP",
        [
            "- Add rhetorical-role awareness before generation and selection.",
            "- Use chunking so long cases can be processed safely.",
            "- Produce multiple candidates instead of trusting one decode.",
            "- Use reranking to explicitly reward coverage of legally important roles and penalize weak summaries.",
        ],
        accent=COLOR_TEAL,
    )
    slide3.rectangles.extend(problem_rects + gap_rects)
    slide3.text_boxes.extend(problem_boxes + gap_boxes + make_footer(3))
    slides.append(slide3)

    slide4 = SlideSpec(
        title="Project Objectives And Deliverables",
        section="Objectives",
        notes=[
            "This slide is good for showing that the project is a full system, not only a model experiment.",
        ],
    )
    add_slide_header(slide4)
    columns = [
        (
            0.9,
            "Data + Structure",
            [
                "- robust TXT and PDF loading",
                "- reusable preprocessing for training and inference",
                "- paragraph, sentence, and rhetorical-unit segmentation",
                "- segment-to-source mapping for explainability",
            ],
        ),
        (
            4.25,
            "Modeling + Generation",
            [
                "- transformer-backed role labeling",
                "- heuristic fallback if supervised model is missing",
                "- role-aware and chunk-aware multi-candidate generation",
                "- configurable local model stack",
            ],
        ),
        (
            7.6,
            "Product + Evaluation",
            [
                "- FastAPI backend and Streamlit frontend",
                "- ROUGE and BERTScore evaluation",
                "- export, logging, tests, configs, and Docker support",
                "- training, preprocessing, demo, and evaluation scripts",
            ],
        ),
    ]
    for idx, (x, heading, lines) in enumerate(columns, start=1):
        rects, boxes = panel(
            f"Objective {idx}",
            f"Objective {idx} Title",
            f"Objective {idx} Body",
            x,
            2.0,
            3.0,
            4.45,
            heading,
            lines,
            accent=COLOR_GOLD if idx != 2 else COLOR_TEAL,
        )
        slide4.rectangles.extend(rects)
        slide4.text_boxes.extend(boxes)
    slide4.text_boxes.extend(make_footer(4))
    slides.append(slide4)

    slide5 = SlideSpec(
        title="End-To-End System Architecture",
        section="Architecture",
        notes=[
            "Walk left to right through the flow. Keep it high-level and connect modules to the repo structure.",
        ],
    )
    add_slide_header(slide5)
    blocks = [
        ("Input", "TXT / PDF / JSON / CSV", 0.9, 2.25),
        ("Loader", "File parsing + PDF extraction", 2.55, 2.25),
        ("DataProcessor", "normalize -> segment -> chunk", 4.35, 2.25),
        ("RoleClassifier", "label rhetorical roles", 6.55, 2.25),
        ("SummaryGenerator", "create 5 candidates", 8.55, 2.25),
        ("SummaryReranker", "pick the best summary", 3.25, 4.55),
        ("Evaluator + Apps", "metrics, API, UI, export", 7.2, 4.55),
    ]
    for idx, (heading, body, x, y) in enumerate(blocks, start=1):
        slide5.rectangles.append(Rectangle(emu(x), emu(y), emu(1.7), emu(1.2), COLOR_PANEL, f"Arch Block {idx}", line_color=COLOR_LINE, geometry="roundRect"))
        slide5.rectangles.append(Rectangle(emu(x), emu(y), emu(1.7), emu(0.07), COLOR_GOLD if idx % 2 else COLOR_TEAL, f"Arch Accent {idx}"))
        slide5.text_boxes.append(
            TextBox(
                x=emu(x + 0.1),
                y=emu(y + 0.14),
                cx=emu(1.5),
                cy=emu(0.28),
                name=f"Arch Head {idx}",
                paragraphs=[Paragraph(heading, font_size=15, color=COLOR_SOFT, bold=True, align="c")],
            )
        )
        slide5.text_boxes.append(
            TextBox(
                x=emu(x + 0.08),
                y=emu(y + 0.48),
                cx=emu(1.54),
                cy=emu(0.42),
                name=f"Arch Body {idx}",
                paragraphs=[Paragraph(body, font_size=12, color=COLOR_MUTED, align="c")],
            )
        )
    slide5.text_boxes.append(
        TextBox(
            x=emu(1.3),
            y=emu(3.75),
            cx=emu(9.7),
            cy=emu(0.28),
            name="Architecture Flow Line",
            paragraphs=[Paragraph("Input -> Loader -> DataProcessor -> RoleClassifier -> SummaryGenerator -> SummaryReranker -> Evaluator/UI", font_size=15, color=COLOR_GOLD, bold=True, align="c", font_face=MONO_FONT)],
        )
    )
    slide5.text_boxes.extend(make_footer(5))
    slides.append(slide5)

    slide6 = SlideSpec(
        title="Pipeline Walkthrough",
        section="Pipeline",
        notes=[
            "This is the operational flow slide. Keep it concrete and sequential.",
        ],
    )
    add_slide_header(slide6)
    step_lines = [
        ("01", "Ingest", "Load TXT/PDF and capture metadata"),
        ("02", "Normalize", "Clean whitespace, citations, headers, and artifacts"),
        ("03", "Segment", "Create paragraphs, sentences, and rhetorical units"),
        ("04", "Chunk", "Split long documents into overlapping windows"),
        ("05", "Label", "Predict rhetorical roles for each unit"),
        ("06", "Generate", "Create 5 candidate summaries"),
        ("07", "Rerank", "Score candidates and choose the best"),
        ("08", "Evaluate", "Compute ROUGE, BERTScore, and explanations"),
    ]
    start_x = 0.9
    for idx, (num, head, body) in enumerate(step_lines):
        x = start_x + (idx % 4) * 2.85
        y = 2.0 if idx < 4 else 4.25
        slide6.rectangles.append(Rectangle(emu(x), emu(y), emu(2.45), emu(1.65), COLOR_PANEL, f"Pipeline Card {idx}", line_color=COLOR_LINE, geometry="roundRect"))
        slide6.rectangles.append(Rectangle(emu(x + 0.12), emu(y + 0.16), emu(0.55), emu(0.55), COLOR_TEAL if idx % 2 else COLOR_GOLD, f"Pipeline Badge {idx}", geometry="ellipse"))
        slide6.text_boxes.append(TextBox(x=emu(x + 0.26), y=emu(y + 0.27), cx=emu(0.25), cy=emu(0.18), name=f"Pipeline Num {idx}", paragraphs=[Paragraph(num, font_size=13, color=COLOR_BG, bold=True, align="c")]))
        slide6.text_boxes.append(TextBox(x=emu(x + 0.8), y=emu(y + 0.2), cx=emu(1.45), cy=emu(0.25), name=f"Pipeline Head {idx}", paragraphs=[Paragraph(head, font_size=16, color=COLOR_SOFT, bold=True)]))
        slide6.text_boxes.append(TextBox(x=emu(x + 0.16), y=emu(y + 0.82), cx=emu(2.1), cy=emu(0.45), name=f"Pipeline Body {idx}", paragraphs=[Paragraph(body, font_size=13, color=COLOR_MUTED)]))
    slide6.text_boxes.extend(make_footer(6))
    slides.append(slide6)

    slide7 = SlideSpec(
        title="Chunking And Rhetorical Role Detection",
        section="Understanding",
        notes=[
            "Use this slide to explain two important pieces of the system: chunking for long documents and role labeling for legal structure.",
            "You can mention the exact chunk size and overlap from config here.",
        ],
    )
    add_slide_header(slide7)
    chunk_rects, chunk_boxes = panel(
        "Chunk Panel",
        "Chunk Panel Title",
        "Chunk Panel Body",
        0.9,
        1.95,
        5.55,
        4.55,
        "Long-document chunking",
        [
            "- Configured chunk size: 850 words",
            "- Configured overlap: 120 words",
            "- Purpose: preserve context while staying within model limits",
            "- Example flow: facts + issue -> arguments -> analysis + statutes -> ruling",
            "- Overlap ensures important reasoning is not lost at chunk boundaries",
        ],
    )
    role_rects, role_boxes = panel(
        "Role Panel",
        "Role Panel Title",
        "Role Panel Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Rhetorical role detection",
        [
            "- Labels: facts, issue, arguments, analysis, ruling, statute, other",
            "- Preferred model: law-ai/InLegalBERT",
            "- Alternative model: nlpaueb/legal-bert-base-uncased",
            "- Heuristic fallback: cue phrases, section headers, regex, keyword dictionaries",
            "- Output: label, confidence, and optional top-k probabilities",
        ],
        accent=COLOR_TEAL,
    )
    slide7.rectangles.extend(chunk_rects + role_rects)
    slide7.text_boxes.extend(chunk_boxes + role_boxes + make_footer(7))
    slides.append(slide7)

    slide8 = SlideSpec(
        title="Candidate Summary Generation",
        section="Generation",
        notes=[
            "Explain that candidates are multiple summary versions for the same document, created with different strategies.",
        ],
    )
    add_slide_header(slide8)
    strategy_rects, strategy_boxes = panel(
        "Strategy Panel",
        "Strategy Panel Title",
        "Strategy Panel Body",
        0.9,
        1.95,
        5.3,
        4.55,
        "Implemented generation strategies",
        [
            "- baseline_full_document",
            "- role_focus_facts_issue_ruling",
            "- analysis_heavy",
            "- chunk_merge_conservative",
            "- chunk_merge_diverse",
            "- fallback path when large models are unavailable locally",
        ],
    )
    model_rects, model_boxes = panel(
        "Gen Model Panel",
        "Gen Model Panel Title",
        "Gen Model Panel Body",
        6.4,
        1.95,
        5.8,
        4.55,
        "Model stack and decoding policy",
        [
            "- Preferred summarizer: allenai/led-base-16384",
            "- Fallback: facebook/bart-large-cnn",
            "- Lightweight fallback: google/flan-t5-base",
            "- Summary length target: 80 to 220 tokens",
            "- Candidate count in config: 5",
        ],
        accent=COLOR_TEAL,
    )
    slide8.rectangles.extend(strategy_rects + model_rects)
    slide8.text_boxes.extend(strategy_boxes + model_boxes + make_footer(8))
    slides.append(slide8)

    slide9 = SlideSpec(
        title="Role-Aware Reranking And Final Selection",
        section="Reranking",
        notes=[
            "This is one of the most important slides because reranking is the core paper-inspired idea.",
            "Show that the project does not simply accept the first generated summary.",
        ],
    )
    add_slide_header(slide9)
    score_rects, score_boxes = panel(
        "Score Panel",
        "Score Panel Title",
        "Score Panel Body",
        0.9,
        1.95,
        5.6,
        4.55,
        "Weighted scoring function",
        [
            "final_score =",
            "0.38 * semantic_similarity",
            "+ 0.26 * role_coverage",
            "+ 0.20 * factual_proxy",
            "+ 0.08 * readability_bonus",
            "- redundancy_penalty - length_penalty",
        ],
        accent=COLOR_GOLD,
    )
    reason_rects, reason_boxes = panel(
        "Reason Panel",
        "Reason Panel Title",
        "Reason Panel Body",
        6.7,
        1.95,
        5.5,
        4.55,
        "Why this makes the final summary better",
        [
            "- semantic similarity keeps the summary close to the source meaning",
            "- role coverage rewards summaries that capture issue, analysis, and ruling",
            "- factual proxy checks numbers, citations, and support-like overlap",
            "- redundancy and length penalties discourage noisy or padded summaries",
            "- readability bonus keeps the result easier to consume",
        ],
        accent=COLOR_TEAL,
    )
    slide9.rectangles.extend(score_rects + reason_rects)
    slide9.text_boxes.extend(score_boxes + reason_boxes)
    slide9.text_boxes.append(
        TextBox(
            x=emu(1.1),
            y=emu(3.0),
            cx=emu(5.0),
            cy=emu(1.8),
            name="Score Formula Highlight",
            paragraphs=[Paragraph("semantic_similarity 0.86\nrole_coverage 0.78\nfactual_proxy 0.74\nfinal_score 0.80", font_size=15, color=COLOR_SOFT, font_face=MONO_FONT)],
        )
    )
    slide9.text_boxes.extend(make_footer(9))
    slides.append(slide9)

    slide10 = SlideSpec(
        title="Evaluation Metrics And Relevance",
        section="Evaluation",
        notes=[
            "Separate internal reranking signals from final evaluation metrics so the audience understands both.",
        ],
    )
    add_slide_header(slide10)
    metric_rects, metric_boxes = panel(
        "Metric Panel",
        "Metric Panel Title",
        "Metric Panel Body",
        0.9,
        1.95,
        5.45,
        4.55,
        "Automatic evaluation metrics",
        [
            "- ROUGE-1: unigram overlap for content coverage",
            "- ROUGE-2: bigram overlap for phrase-level fidelity",
            "- ROUGE-L: longest common subsequence for structural similarity",
            "- BERTScore Precision / Recall / F1: semantic similarity even when wording changes",
        ],
    )
    interp_rects, interp_boxes = panel(
        "Interp Panel",
        "Interp Panel Title",
        "Interp Panel Body",
        6.55,
        1.95,
        5.65,
        4.55,
        "Qualitative analysis surfaced by the app",
        [
            "- key supporting source segments for the chosen summary",
            "- rhetorical role distribution across the document",
            "- candidate comparison table with component scores",
            "- explanation of why the top summary was selected",
            "- optional comparison against a provided gold summary",
        ],
        accent=COLOR_TEAL,
    )
    slide10.rectangles.extend(metric_rects + interp_rects)
    slide10.text_boxes.extend(metric_boxes + interp_boxes + make_footer(10))
    slides.append(slide10)

    slide11 = SlideSpec(
        title="Example Walkthrough On A Legal Opinion",
        section="Example",
        notes=[
            "This slide makes the system concrete. Walk through a mini case from intake to final summary.",
        ],
    )
    add_slide_header(slide11)
    input_rects, input_boxes = panel(
        "Example Input",
        "Example Input Title",
        "Example Input Body",
        0.9,
        1.95,
        3.75,
        4.6,
        "Input excerpt",
        [
            "Facts: allotment cancelled after flood-related delays.",
            "Issue: could the authority cancel without notice?",
            "Arguments: natural justice vs conditional allotment.",
            "Analysis: vested benefit cannot be withdrawn without fair procedure.",
            "Ruling: cancellation set aside and matter remanded.",
        ],
    )
    role_example_rects, role_example_boxes = panel(
        "Example Roles",
        "Example Roles Title",
        "Example Roles Body",
        4.85,
        1.95,
        3.45,
        4.6,
        "Detected structure",
        [
            "- facts -> background and procedure",
            "- issue -> legal question before the court",
            "- arguments -> both party positions",
            "- analysis -> court reasoning",
            "- ruling -> final disposition",
        ],
        accent=COLOR_TEAL,
    )
    output_rects, output_boxes = panel(
        "Example Output",
        "Example Output Title",
        "Example Output Body",
        8.5,
        1.95,
        3.7,
        4.6,
        "Selected final summary",
        [
            "The petitioner challenged cancellation of a housing allotment after flood-related delays.",
            "The core issue was whether the authority could cancel the allotment without notice.",
            "The court held that fair procedure was required and set aside the cancellation, remanding the matter for fresh consideration.",
        ],
        accent=COLOR_GOLD,
    )
    slide11.rectangles.extend(input_rects + role_example_rects + output_rects)
    slide11.text_boxes.extend(input_boxes + role_example_boxes + output_boxes + make_footer(11))
    slides.append(slide11)

    slide12 = SlideSpec(
        title="Product Experience: UI, API, Auth, And Exports",
        section="Product",
        notes=[
            "Use this slide to show that the project is deployable and user-facing, not only research code.",
        ],
    )
    add_slide_header(slide12)
    ui_rects, ui_boxes = panel(
        "UI Feature Panel",
        "UI Feature Panel Title",
        "UI Feature Panel Body",
        0.9,
        1.95,
        5.55,
        4.55,
        "Streamlit workspace",
        [
            "- dark-mode legal-tech interface",
            "- local email/password authentication with salted PBKDF2 hashing",
            "- upload file, paste text, or use bundled demo documents",
            "- live progress across normalization, chunking, labeling, generation, and reranking",
            "- summary-first display with optional advanced analysis",
        ],
    )
    api_rects, api_boxes = panel(
        "API Feature Panel",
        "API Feature Panel Title",
        "API Feature Panel Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Backend and export surfaces",
        [
            "- POST /upload-pdf for PDF extraction",
            "- POST /summarize for end-to-end summarization",
            "- POST /evaluate for ROUGE and BERTScore",
            "- export to Markdown, JSON, and optional PDF",
            "- config-driven runtime with logging and validation",
        ],
        accent=COLOR_TEAL,
    )
    slide12.rectangles.extend(ui_rects + api_rects)
    slide12.text_boxes.extend(ui_boxes + api_boxes + make_footer(12))
    slides.append(slide12)

    slide13 = SlideSpec(
        title="Engineering Quality And Repository Structure",
        section="Engineering",
        notes=[
            "This slide is important for demonstrating software engineering maturity alongside NLP work.",
        ],
    )
    add_slide_header(slide13)
    eng_rects, eng_boxes = panel(
        "Engineering Panel",
        "Engineering Panel Title",
        "Engineering Panel Body",
        0.9,
        1.95,
        5.55,
        4.55,
        "Engineering strengths",
        [
            "- modular src/ packages: data, roles, summarization, reranking, evaluation, pipeline",
            "- app/ layer for FastAPI schemas and Streamlit UI",
            "- configs/ for model names, thresholds, and scoring weights",
            "- scripts/ for preprocess, train, demo, and evaluation flows",
            "- tests/ covering loader, preprocessing, roles, generation, reranker, auth, and API",
        ],
    )
    repo_rects, repo_boxes = panel(
        "Repo Panel",
        "Repo Panel Title",
        "Repo Panel Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "What the repository includes",
        [
            "- README, requirements, .env.example, Dockerfile",
            "- sample Indian and U.S. legal documents",
            "- notebook for exploratory experiments",
            "- CPU-safe fallback behavior and open-source-only model policy",
            "- reproducible local workflow for demo and evaluation",
        ],
        accent=COLOR_TEAL,
    )
    slide13.rectangles.extend(eng_rects + repo_rects)
    slide13.text_boxes.extend(eng_boxes + repo_boxes)
    slide13.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(6.45),
            cx=emu(11.2),
            cy=emu(0.28),
            name="Test Note",
            paragraphs=[Paragraph("Repository includes 7 focused pytest modules plus shared fixtures for critical-path coverage.", font_size=14, color=COLOR_GOLD)],
        )
    )
    slide13.text_boxes.extend(make_footer(13))
    slides.append(slide13)

    slide14 = SlideSpec(
        title="How To Run, Train, And Evaluate",
        section="Operations",
        notes=[
            "This slide is practical. It helps if someone asks how the project is actually executed.",
        ],
    )
    add_slide_header(slide14)
    run_rects, run_boxes = panel(
        "Run Panel",
        "Run Panel Title",
        "Run Panel Body",
        0.9,
        1.95,
        5.5,
        4.55,
        "Daily usage flow",
        [
            "1. Run FastAPI or Streamlit",
            "2. Upload TXT/PDF or paste document text",
            "3. Generate candidate summaries",
            "4. Inspect the selected summary and score breakdown",
            "5. Optionally evaluate against a gold summary",
        ],
    )
    command_rects, command_boxes = panel(
        "Command Panel",
        "Command Panel Title",
        "Command Panel Body",
        6.6,
        1.95,
        5.6,
        4.55,
        "Important commands",
        [
            "uvicorn app.api:app --host 0.0.0.0 --port 8000",
            "streamlit run app/streamlit_app.py",
            "python scripts/run_demo.py --input-path data/demo/indian_judgment_sample.txt",
            "python scripts/train_role_classifier.py --dataset-path data/samples/legal_samples.json --allow-weak-labels",
            "python scripts/evaluate_model.py --dataset-path data/samples/legal_samples.json --output-path data/processed/evaluation_metrics.json",
        ],
        accent=COLOR_TEAL,
    )
    slide14.rectangles.extend(run_rects + command_rects)
    slide14.text_boxes.extend(run_boxes + command_boxes + make_footer(14))
    slides.append(slide14)

    slide15 = SlideSpec(
        title="Faithful To The Paper Vs Pragmatic MVP Adaptation",
        section="Research",
        notes=[
            "Be transparent here. This honesty usually strengthens the presentation rather than weakening it.",
        ],
    )
    add_slide_header(slide15)
    faithful_rects, faithful_boxes = panel(
        "Faithful V2",
        "Faithful V2 Title",
        "Faithful V2 Body",
        0.9,
        1.95,
        5.55,
        4.55,
        "Faithful to the paper's core idea",
        [
            "- long legal opinions are treated as structure-heavy documents",
            "- multiple candidate summaries are generated instead of one single output",
            "- final selection uses argument or rhetorical awareness",
            "- chunking is used for long-document handling",
        ],
    )
    pragmatic_rects, pragmatic_boxes = panel(
        "Pragmatic V2",
        "Pragmatic V2 Title",
        "Pragmatic V2 Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Pragmatic choices for an MVP",
        [
            "- hybrid role classifier instead of an exact paper-specific training setup",
            "- practical coverage and faithfulness proxies in the reranker",
            "- local open-source models with heuristic fallback",
            "- added UI, API, auth, exports, tests, and config-driven engineering",
        ],
        accent=COLOR_TEAL,
    )
    slide15.rectangles.extend(faithful_rects + pragmatic_rects)
    slide15.text_boxes.extend(faithful_boxes + pragmatic_boxes + make_footer(15))
    slides.append(slide15)

    slide16 = SlideSpec(
        title="Limitations, Future Work, And Closing",
        section="Close",
        notes=[
            "End on a confident but honest note. The system is already strong as an MVP, with clear next steps for research improvement.",
        ],
    )
    add_slide_header(slide16)
    close_rects, close_boxes = panel(
        "Close Left",
        "Close Left Title",
        "Close Left Body",
        0.9,
        1.95,
        5.4,
        4.55,
        "Current limitations",
        [
            "- not an exact one-to-one reproduction of the ACL experiment",
            "- CPU inference can be slow for long-context models",
            "- rhetorical-role accuracy is strongest with a fine-tuned classifier",
            "- PDF extraction quality depends on document formatting",
        ],
    )
    roadmap_rects, roadmap_boxes = panel(
        "Close Right",
        "Close Right Title",
        "Close Right Body",
        6.55,
        1.95,
        5.65,
        4.55,
        "High-value next steps",
        [
            "- fine-tune a stronger rhetorical-role checkpoint",
            "- add richer legal factuality and citation-grounding checks",
            "- benchmark on larger legal summarization datasets",
            "- extend jurisdiction-specific prompts and scoring rules",
            "- improve PDF layout understanding and structured parsing",
        ],
        accent=COLOR_TEAL,
    )
    slide16.rectangles.extend(close_rects + roadmap_rects)
    slide16.text_boxes.extend(close_boxes + roadmap_boxes)
    slide16.text_boxes.append(
        TextBox(
            x=emu(1.1),
            y=emu(6.0),
            cx=emu(10.2),
            cy=emu(0.55),
            name="Closing Statement",
            paragraphs=[Paragraph("One-line takeaway: this system combines legal document understanding, abstractive generation, and argument-aware reranking to produce better summaries of long court opinions.", font_size=18, color=COLOR_GOLD, bold=True, align="c")],
        )
    )
    slide16.text_boxes.extend(make_footer(16))
    slides.append(slide16)

    return slides


def build_academic_focus_slides() -> list[SlideSpec]:
    slides: list[SlideSpec] = []

    slide1 = SlideSpec(
        title="Legal Argument-Aware Summarization MVP",
        section="Overview",
        notes=[
            "Introduce the project in one sentence: long legal documents, structure-aware summarization, and reranking.",
            "Keep this slide calm and direct.",
        ],
    )
    add_slide_header(slide1)
    slide1.text_boxes.append(
        TextBox(
            x=emu(0.95),
            y=emu(1.75),
            cx=emu(10.9),
            cy=emu(1.0),
            name="Overview Summary",
            paragraphs=[
                Paragraph(
                    "This project summarizes long court judgments by first understanding their rhetorical structure, then generating multiple abstractive summaries, and finally selecting the best one through argument-aware reranking.",
                    font_size=24,
                    color=COLOR_SOFT,
                )
            ],
        )
    )
    overview_cards = [
        ("Input", "TXT / PDF legal documents", 0.95),
        ("Method", "segment -> label -> generate -> rerank", 4.2),
        ("Output", "best summary + metrics + reasoning", 7.45),
    ]
    for idx, (head, body, x) in enumerate(overview_cards, start=1):
        slide1.rectangles.append(Rectangle(emu(x), emu(3.45), emu(2.9), emu(1.7), COLOR_PANEL, f"Overview Card {idx}", line_color=COLOR_LINE, geometry="roundRect"))
        slide1.rectangles.append(Rectangle(emu(x), emu(3.45), emu(2.9), emu(0.08), COLOR_GOLD if idx != 2 else COLOR_TEAL, f"Overview Accent {idx}"))
        slide1.text_boxes.append(TextBox(x=emu(x + 0.18), y=emu(3.65), cx=emu(2.2), cy=emu(0.28), name=f"Overview Head {idx}", paragraphs=[Paragraph(head, font_size=18, color=COLOR_SOFT, bold=True)]))
        slide1.text_boxes.append(TextBox(x=emu(x + 0.18), y=emu(4.12), cx=emu(2.45), cy=emu(0.45), name=f"Overview Body {idx}", paragraphs=[Paragraph(body, font_size=15, color=COLOR_MUTED)]))
    slide1.text_boxes.append(
        TextBox(
            x=emu(1.0),
            y=emu(5.65),
            cx=emu(10.6),
            cy=emu(0.55),
            name="Overview Footnote",
            paragraphs=[Paragraph("Open-source only | CPU fallback supported | Paper-inspired, production-style MVP", font_size=16, color=COLOR_GOLD, align="c")],
        )
    )
    slide1.text_boxes.extend(make_footer(1))
    slides.append(slide1)

    slide2 = SlideSpec(
        title="Problem Statement",
        section="Problem",
        notes=[
            "Explain why legal summarization is harder than generic summarization.",
            "Connect directly to the need for structure-aware processing.",
        ],
    )
    add_slide_header(slide2)
    left_rects, left_boxes = panel(
        "Problem Left",
        "Problem Left Title",
        "Problem Left Body",
        0.9,
        1.95,
        5.45,
        4.65,
        "Challenges in long legal opinions",
        [
            "- opinions are long and exceed normal context limits",
            "- important content is distributed across facts, issue, analysis, and ruling",
            "- legal summaries must preserve what the court decided and why",
            "- citations, sections, and procedural details should not be dropped carelessly",
        ],
    )
    right_rects, right_boxes = panel(
        "Problem Right",
        "Problem Right Title",
        "Problem Right Body",
        6.65,
        1.95,
        5.55,
        4.65,
        "Research objective",
        [
            "Build a local legal summarization system that:",
            "- understands rhetorical structure",
            "- generates multiple abstractive candidates",
            "- reranks candidates with argument-aware scoring",
            "- returns the best summary with metrics and interpretable reasoning",
        ],
        accent=COLOR_TEAL,
    )
    slide2.rectangles.extend(left_rects + right_rects)
    slide2.text_boxes.extend(left_boxes + right_boxes + make_footer(2))
    slides.append(slide2)

    slide3 = SlideSpec(
        title="Method Overview",
        section="Pipeline",
        notes=[
            "This is the main system diagram. Walk from left to right.",
        ],
    )
    add_slide_header(slide3)
    pipeline_boxes = [
        ("Input", "TXT / PDF", 0.85),
        ("Preprocess", "normalize + segment + chunk", 2.55),
        ("Roles", "predict rhetorical labels", 4.55),
        ("Generate", "create summary candidates", 6.55),
        ("Rerank", "score and select", 8.55),
        ("Output", "best summary + metrics", 10.25),
    ]
    for idx, (head, body, x) in enumerate(pipeline_boxes, start=1):
        width = 1.45 if idx in {1, 6} else 1.7
        slide3.rectangles.append(Rectangle(emu(x), emu(3.0), emu(width), emu(1.45), COLOR_PANEL, f"Method Box {idx}", line_color=COLOR_LINE, geometry="roundRect"))
        slide3.rectangles.append(Rectangle(emu(x), emu(3.0), emu(width), emu(0.07), COLOR_GOLD if idx % 2 else COLOR_TEAL, f"Method Accent {idx}"))
        slide3.text_boxes.append(TextBox(x=emu(x + 0.1), y=emu(3.18), cx=emu(width - 0.2), cy=emu(0.24), name=f"Method Head {idx}", paragraphs=[Paragraph(head, font_size=16, color=COLOR_SOFT, bold=True, align="c")]))
        slide3.text_boxes.append(TextBox(x=emu(x + 0.08), y=emu(3.62), cx=emu(width - 0.16), cy=emu(0.35), name=f"Method Body {idx}", paragraphs=[Paragraph(body, font_size=12, color=COLOR_MUTED, align="c")]))
        if idx < len(pipeline_boxes):
            slide3.rectangles.append(Rectangle(emu(x + width + 0.08), emu(3.48), emu(0.38), emu(0.24), COLOR_TEAL, f"Method Arrow {idx}", geometry="rightArrow"))
    slide3.text_boxes.append(
        TextBox(
            x=emu(1.0),
            y=emu(5.05),
            cx=emu(10.8),
            cy=emu(0.7),
            name="Method Note",
            paragraphs=[
                Paragraph("Core idea: do not trust a single generated summary. Generate multiple candidates and choose the one that best matches the legal argument structure.", font_size=18, color=COLOR_GOLD, align="c"),
            ],
        )
    )
    slide3.text_boxes.extend(make_footer(3))
    slides.append(slide3)

    slide4 = SlideSpec(
        title="Preprocessing And Chunking",
        section="Pipeline",
        notes=[
            "Explain segmentation and chunking clearly because these steps make long-document summarization possible.",
        ],
    )
    add_slide_header(slide4)
    preprocess_rects, preprocess_boxes = panel(
        "Preprocess Panel",
        "Preprocess Panel Title",
        "Preprocess Panel Body",
        0.9,
        1.95,
        5.45,
        4.55,
        "Preprocessing stages",
        [
            "- text normalization",
            "- legal citation cleanup",
            "- whitespace and section-header normalization",
            "- paragraph segmentation",
            "- sentence segmentation",
            "- rhetorical-unit approximation",
            "- source-to-segment mapping for explainability",
        ],
    )
    chunk_rects, chunk_boxes = panel(
        "Chunk Panel Academic",
        "Chunk Panel Academic Title",
        "Chunk Panel Academic Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Chunking logic",
        [
            "chunk_max_words = 850",
            "chunk_overlap_words = 120",
            "",
            "document -> chunk 1 -> chunk 2 -> chunk 3 -> chunk 4",
            "overlap keeps reasoning continuous across boundaries",
            "this allows LED/BART/T5 based pipelines to handle long cases more safely",
        ],
        accent=COLOR_TEAL,
    )
    slide4.rectangles.extend(preprocess_rects + chunk_rects)
    slide4.text_boxes.extend(preprocess_boxes + chunk_boxes + make_footer(4))
    slides.append(slide4)

    slide5 = SlideSpec(
        title="Role Prediction And Candidate Generation",
        section="Modeling",
        notes=[
            "Group the two modeling stages that happen before reranking.",
        ],
    )
    add_slide_header(slide5)
    role_rects, role_boxes = panel(
        "Role Academic Panel",
        "Role Academic Panel Title",
        "Role Academic Panel Body",
        0.9,
        1.95,
        5.45,
        4.55,
        "Rhetorical role module",
        [
            "labels = facts, issue, arguments, analysis, ruling, statute, other",
            "preferred model = law-ai/InLegalBERT",
            "alternative = nlpaueb/legal-bert-base-uncased",
            "fallback = heuristics based on cue phrases, headers, regex, and keyword dictionaries",
            "output = label + confidence + top-k probabilities",
        ],
    )
    candidate_rects, candidate_boxes = panel(
        "Candidate Academic Panel",
        "Candidate Academic Panel Title",
        "Candidate Academic Panel Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Candidate generation",
        [
            "preferred summarizer = allenai/led-base-16384",
            "fallbacks = facebook/bart-large-cnn, google/flan-t5-base",
            "strategies:",
            "- baseline_full_document",
            "- role_focus_facts_issue_ruling",
            "- analysis_heavy",
            "- chunk_merge_conservative / chunk_merge_diverse",
        ],
        accent=COLOR_TEAL,
    )
    slide5.rectangles.extend(role_rects + candidate_rects)
    slide5.text_boxes.extend(role_boxes + candidate_boxes + make_footer(5))
    slides.append(slide5)

    slide6 = SlideSpec(
        title="Reranking Formula And Selection Logic",
        section="Reranking",
        notes=[
            "Spend time here. This is the main paper-inspired mechanism in the system.",
        ],
    )
    add_slide_header(slide6)
    formula_rects, formula_boxes = panel(
        "Formula Panel",
        "Formula Panel Title",
        "Formula Panel Body",
        0.9,
        1.95,
        5.55,
        4.55,
        "Final score",
        [
            "final_score =",
            "0.38 * semantic_similarity",
            "+ 0.26 * role_coverage",
            "+ 0.20 * factual_proxy",
            "+ 0.08 * readability_bonus",
            "- redundancy_penalty - length_penalty",
        ],
    )
    explain_rects, explain_boxes = panel(
        "Explain Formula Panel",
        "Explain Formula Panel Title",
        "Explain Formula Panel Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Why each term matters",
        [
            "- semantic_similarity: meaning match with the source",
            "- role_coverage: whether important legal roles are present",
            "- factual_proxy: overlap of citations, numbers, and support-like cues",
            "- redundancy_penalty: repeated content should be punished",
            "- length_penalty: very short or very long summaries should be penalized",
        ],
        accent=COLOR_TEAL,
    )
    slide6.rectangles.extend(formula_rects + explain_rects)
    slide6.text_boxes.extend(formula_boxes + explain_boxes)
    slide6.text_boxes.append(
        TextBox(
            x=emu(1.05),
            y=emu(3.15),
            cx=emu(4.7),
            cy=emu(1.3),
            name="Reranking Example",
            paragraphs=[Paragraph("Example score card\nsemantic_similarity = 0.86\nrole_coverage = 0.78\nfactual_proxy = 0.74\nfinal_score = 0.80", font_size=15, color=COLOR_SOFT, font_face=MONO_FONT)],
        )
    )
    slide6.text_boxes.extend(make_footer(6))
    slides.append(slide6)

    slide7 = SlideSpec(
        title="Evaluation Metrics And Formulas",
        section="Evaluation",
        notes=[
            "Explain evaluation separately from reranking so the audience does not confuse the two.",
        ],
    )
    add_slide_header(slide7)
    rouge_rects, rouge_boxes = panel(
        "ROUGE Panel",
        "ROUGE Panel Title",
        "ROUGE Panel Body",
        0.9,
        1.95,
        3.75,
        4.55,
        "ROUGE",
        [
            "ROUGE-N = overlap n-grams / total reference n-grams",
            "ROUGE-1 -> unigram coverage",
            "ROUGE-2 -> bigram or phrase-level fidelity",
            "ROUGE-L -> longest common subsequence similarity",
        ],
    )
    bert_rects, bert_boxes = panel(
        "BERT Panel",
        "BERT Panel Title",
        "BERT Panel Body",
        4.85,
        1.95,
        3.45,
        4.55,
        "BERTScore",
        [
            "Precision = semantic support of generated text",
            "Recall = semantic coverage of the reference",
            "F1 = 2PR / (P + R)",
            "useful when summaries paraphrase instead of copying wording",
        ],
        accent=COLOR_TEAL,
    )
    quality_rects, quality_boxes = panel(
        "Quality Panel",
        "Quality Panel Title",
        "Quality Panel Body",
        8.5,
        1.95,
        3.7,
        4.55,
        "Interpretation",
        [
            "ROUGE answers: did we cover the right content words and phrases?",
            "BERTScore answers: did we preserve the meaning?",
            "Together they provide lexical and semantic evaluation.",
        ],
    )
    slide7.rectangles.extend(rouge_rects + bert_rects + quality_rects)
    slide7.text_boxes.extend(rouge_boxes + bert_boxes + quality_boxes + make_footer(7))
    slides.append(slide7)

    slide8 = SlideSpec(
        title="Example Case Flow",
        section="Example",
        notes=[
            "Use a compact example to show how the pipeline behaves on one legal opinion.",
        ],
    )
    add_slide_header(slide8)
    input_rects, input_boxes = panel(
        "Example Input Panel",
        "Example Input Panel Title",
        "Example Input Panel Body",
        0.9,
        1.95,
        3.75,
        4.55,
        "Input text",
        [
            "Facts: allotment cancelled after flood delay.",
            "Issue: whether cancellation without notice was valid.",
            "Arguments: natural justice vs conditional allotment.",
            "Analysis: fair procedure required.",
            "Ruling: cancellation set aside and matter remanded.",
        ],
    )
    flow_rects, flow_boxes = panel(
        "Example Flow Panel",
        "Example Flow Panel Title",
        "Example Flow Panel Body",
        4.85,
        1.95,
        3.45,
        4.55,
        "Pipeline result",
        [
            "facts -> issue -> arguments -> analysis -> ruling",
            "candidate summaries generated",
            "best candidate selected after reranking",
            "supporting segments returned for explainability",
        ],
        accent=COLOR_TEAL,
    )
    output_rects, output_boxes = panel(
        "Example Output Panel",
        "Example Output Panel Title",
        "Example Output Panel Body",
        8.5,
        1.95,
        3.7,
        4.55,
        "Final summary",
        [
            "The petitioner challenged cancellation of an allotment after flood-related delay.",
            "The issue was whether the authority could act without notice.",
            "The court held that fair procedure was required and remanded the matter.",
        ],
    )
    slide8.rectangles.extend(input_rects + flow_rects + output_rects)
    slide8.text_boxes.extend(input_boxes + flow_boxes + output_boxes + make_footer(8))
    slides.append(slide8)

    slide9 = SlideSpec(
        title="Conclusion",
        section="Conclusion",
        notes=[
            "Finish with the core takeaway, current limitation, and next step.",
        ],
    )
    add_slide_header(slide9)
    conclusion_rects, conclusion_boxes = panel(
        "Conclusion Left",
        "Conclusion Left Title",
        "Conclusion Left Body",
        0.9,
        1.95,
        5.45,
        4.55,
        "Key takeaway",
        [
            "This project improves legal summarization by combining:",
            "- long-document preprocessing",
            "- rhetorical-role understanding",
            "- multi-candidate abstractive generation",
            "- argument-aware reranking",
            "- evaluation and explainability",
        ],
    )
    next_rects, next_boxes = panel(
        "Conclusion Right",
        "Conclusion Right Title",
        "Conclusion Right Body",
        6.65,
        1.95,
        5.55,
        4.55,
        "Limitations and next step",
        [
            "- not an exact paper reproduction",
            "- CPU inference can be slow for long models",
            "- no bundled custom fine-tuned checkpoint",
            "- strongest next step: train a dedicated rhetorical-role classifier and benchmark on larger legal datasets",
        ],
        accent=COLOR_TEAL,
    )
    slide9.rectangles.extend(conclusion_rects + next_rects)
    slide9.text_boxes.extend(conclusion_boxes + next_boxes)
    slide9.text_boxes.append(
        TextBox(
            x=emu(1.0),
            y=emu(6.05),
            cx=emu(10.8),
            cy=emu(0.4),
            name="Conclusion Statement",
            paragraphs=[Paragraph("In one line: the system reads a long legal opinion, understands its structure, generates several summaries, and selects the best one using argument-aware scoring.", font_size=18, color=COLOR_GOLD, bold=True, align="c")],
        )
    )
    slide9.text_boxes.extend(make_footer(9))
    slides.append(slide9)

    return slides


def write_notes(slides: Sequence[SlideSpec], notes_path: Path) -> None:
    lines: list[str] = [
        "# Legal Argument-Aware Summarization MVP - Presentation Notes",
        "",
        "These notes match the generated PowerPoint deck in the same `docs` folder.",
        "",
    ]
    for index, slide in enumerate(slides, start=1):
        lines.append(f"## Slide {index}: {slide.title}")
        lines.append("")
        for bullet in slide.notes:
            lines.append(f"- {bullet}")
        lines.append("")
    notes_path.write_text("\n".join(lines), encoding="utf-8")


def write_presentation(slides: Sequence[SlideSpec], output_path: Path) -> None:
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml(len(slides)))
        archive.writestr("_rels/.rels", package_relationships_xml())
        archive.writestr("docProps/app.xml", app_xml(slides))
        archive.writestr("docProps/core.xml", core_xml())
        archive.writestr("ppt/presentation.xml", presentation_xml(slides))
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_relationships_xml(slides))
        archive.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_relationships_xml())
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_relationships_xml())
        archive.writestr("ppt/theme/theme1.xml", theme_xml())
        for index, slide in enumerate(slides, start=1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide_xml(slide))
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", slide_relationship_xml())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slides = build_academic_focus_slides()
    ppt_path = OUT_DIR / f"{PRESENTATION_NAME}.pptx"
    notes_path = OUT_DIR / f"{PRESENTATION_NAME}_notes.md"
    write_presentation(slides, ppt_path)
    write_notes(slides, notes_path)
    print(f"Created {ppt_path}")
    print(f"Created {notes_path}")


if __name__ == "__main__":
    main()
