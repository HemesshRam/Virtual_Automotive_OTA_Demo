from __future__ import annotations

import datetime as dt
import html
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


OUT_PATH = Path("docs/virtual_automotive_ota_demo_slides.pptx")

SLIDE_W = 12192000
SLIDE_H = 6858000


def emu(inches: float) -> int:
    return int(inches * 914400)


def xml_escape(value: str) -> str:
    return html.escape(value, quote=False)


def paragraph_xml(
    text: str,
    *,
    size: int = 2000,
    bold: bool = False,
    color: str = "1F1F1F",
    level: int = 0,
) -> str:
    attrs = [f'lang="en-US"', f'sz="{size}"', f'solidFill="{color}"']
    if bold:
        attrs.append('b="1"')
    attrs_str = " ".join(attrs).replace(' solidFill="', '" dummy="').replace('" dummy="', '"')
    # PowerPoint expects a:rPr + a:solidFill child instead of inline color attr.
    p_pr = f'<a:pPr lvl="{level}"/>' if level else "<a:pPr/>"
    return (
        f"<a:p>{p_pr}"
        f'<a:r><a:rPr lang="en-US" sz="{size}"{" b=\"1\"" if bold else ""}>'
        f"<a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill>"
        f"</a:rPr><a:t>{xml_escape(text)}</a:t></a:r>"
        f'<a:endParaRPr lang="en-US" sz="{size}"/></a:p>'
    )


def textbox_xml(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: list[dict],
    *,
    fill: str = "FFFFFF",
    line: str = "C9D2E3",
    radius: bool = False,
) -> str:
    geom = "roundRect" if radius else "rect"
    paras = "".join(
        paragraph_xml(
            item["text"],
            size=item.get("size", 1800),
            bold=item.get("bold", False),
            color=item.get("color", "1F1F1F"),
            level=item.get("level", 0),
        )
        for item in paragraphs
    )
    return f"""<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{xml_escape(name)}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
    <a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>
    <a:ln w="19050"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" anchor="t"/>
    <a:lstStyle/>{paras}
  </p:txBody>
</p:sp>"""


def slide_xml(shapes: list[str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
      {''.join(shapes)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def slide_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
    Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def title_block(title: str, subtitle: str | None = None) -> list[str]:
    shapes = [
        textbox_xml(
            2,
            "Title",
            emu(0.55),
            emu(0.35),
            emu(12.1),
            emu(0.9),
            [{"text": title, "size": 2400, "bold": True, "color": "0F172A"}],
            fill="E8F0FB",
            line="94A3B8",
            radius=True,
        )
    ]
    if subtitle:
        shapes.append(
            textbox_xml(
                3,
                "Subtitle",
                emu(0.7),
                emu(1.35),
                emu(11.8),
                emu(0.75),
                [{"text": subtitle, "size": 1400, "color": "334155"}],
                fill="FFFFFF",
                line="FFFFFF",
            )
        )
    return shapes


def build_slides() -> list[str]:
    slides: list[str] = []

    # Slide 1
    shapes = title_block(
        "Virtual Automotive OTA Demo",
        "Production-style OTA orchestration with zonal vehicle model, DoIP, VCAN/CAN FD, UDS, ISO-TP, A/B flashing, Uptane-style trust, MQTT/HTTPS cloud control, and optional Mender trigger",
    )
    shapes.append(
        textbox_xml(
            4,
            "Overview",
            emu(0.9),
            emu(2.05),
            emu(11.3),
            emu(3.7),
            [
                {"text": "What this demo shows", "size": 1800, "bold": True, "color": "0F172A"},
                {"text": "TCU acts as the in-vehicle OTA orchestrator.", "size": 1500},
                {"text": "ECUs are updated through realistic transport layers: DoIP or VCAN/CAN FD + ISO-TP + UDS.", "size": 1500},
                {"text": "Zones, dependency planning, ECU availability, partial rollout, A/B activation, and trust validation are all visible.", "size": 1500},
                {"text": "The demo is production-style and runnable, but not a full AUTOSAR or hardware-flash implementation.", "size": 1500},
            ],
            fill="F8FAFC",
            line="CBD5E1",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 2 purpose
    shapes = title_block("Demo Purpose")
    shapes.append(
        textbox_xml(
            4,
            "Purpose",
            emu(0.75),
            emu(1.45),
            emu(5.9),
            emu(4.8),
            [
                {"text": "Why we built it", "size": 1800, "bold": True, "color": "0F172A"},
                {"text": "Show how an automotive OTA platform coordinates cloud, TCU, gateway, zones, and ECUs.", "size": 1500},
                {"text": "Make protocol layers visible instead of hiding them behind vendor tools.", "size": 1500},
                {"text": "Demonstrate skip, abort, partial rollout, and dependency-aware decisions from live vehicle state.", "size": 1500},
            ],
            fill="F8FAFC",
            line="CBD5E1",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "Boundaries",
            emu(6.85),
            emu(1.45),
            emu(5.45),
            emu(4.8),
            [
                {"text": "What it is not", "size": 1800, "bold": True, "color": "7C2D12"},
                {"text": "Not full AUTOSAR DCM/FBL.", "size": 1500},
                {"text": "Not real hardware flash driver integration.", "size": 1500},
                {"text": "Not OEM production PKI or TSN/VLAN Ethernet.", "size": 1500},
                {"text": "It is a realistic integration simulator for architecture, behavior, and demo execution.", "size": 1500},
            ],
            fill="FFF7ED",
            line="FDBA74",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 3 architecture diagram
    shapes = title_block("Architecture Diagram")
    shapes += [
        textbox_xml(4, "Cloud", emu(4.85), emu(1.05), emu(3.6), emu(0.75), [
            {"text": "OTA Cloud Server", "size": 1800, "bold": True, "color": "0F172A"},
            {"text": "HTTPS artifacts + MQTT notify/status", "size": 1200},
        ], fill="DBEAFE", line="60A5FA", radius=True),
        textbox_xml(5, "TCU", emu(4.15), emu(2.0), emu(5.0), emu(1.0), [
            {"text": "TCU Orchestrator", "size": 1800, "bold": True, "color": "0F172A"},
            {"text": "campaign validation, trust, dependency plan, transport selection", "size": 1200},
        ], fill="E0E7FF", line="818CF8", radius=True),
        textbox_xml(6, "DoIP", emu(0.65), emu(3.35), emu(3.6), emu(0.95), [
            {"text": "DoIP Backbone", "size": 1700, "bold": True},
            {"text": "UDP discovery + TCP diagnostics", "size": 1200},
        ], fill="DCFCE7", line="4ADE80", radius=True),
        textbox_xml(7, "VCAN", emu(4.65), emu(3.35), emu(3.0), emu(0.95), [
            {"text": "VCAN / CAN FD / ISO-TP", "size": 1600, "bold": True},
            {"text": "diagnostic path for CAN-based update", "size": 1200},
        ], fill="FEF3C7", line="FBBF24", radius=True),
        textbox_xml(8, "Zones", emu(8.0), emu(3.1), emu(4.0), emu(1.25), [
            {"text": "Zone Controllers", "size": 1700, "bold": True},
            {"text": "health, policy, heartbeat, request forwarding", "size": 1200},
        ], fill="FCE7F3", line="F472B6", radius=True),
        textbox_xml(9, "Gateway ECU", emu(0.75), emu(4.95), emu(3.6), emu(0.9), [
            {"text": "Gateway ECU", "size": 1600, "bold": True},
            {"text": "A/B slot + flash model", "size": 1200},
        ], fill="F8FAFC", line="94A3B8", radius=True),
        textbox_xml(10, "BCM ECU", emu(4.6), emu(4.95), emu(3.0), emu(0.9), [
            {"text": "BCM ECU", "size": 1600, "bold": True},
            {"text": "UDS server + flash target", "size": 1200},
        ], fill="F8FAFC", line="94A3B8", radius=True),
        textbox_xml(11, "Cluster ECU", emu(8.1), emu(4.95), emu(3.8), emu(0.9), [
            {"text": "Cluster ECU", "size": 1600, "bold": True},
            {"text": "UDS server + flash target", "size": 1200},
        ], fill="F8FAFC", line="94A3B8", radius=True),
    ]
    slides.append(slide_xml(shapes))

    # Slide 4 architecture detail
    shapes = title_block("Architecture Flow In Detail")
    shapes.append(
        textbox_xml(
            4,
            "Flow",
            emu(0.7),
            emu(1.3),
            emu(11.7),
            emu(4.9),
            [
                {"text": "1. Cloud publishes campaign/job and hosts artifacts over HTTPS.", "size": 1450},
                {"text": "2. TCU receives trigger by MQTT or Mender deployment, then downloads campaign and firmware.", "size": 1450},
                {"text": "3. TCU verifies repository state, metadata trust, inventory, compatibility, and dependency order.", "size": 1450},
                {"text": "4. TCU selects transport: DoIP backbone or VCAN/CAN FD path.", "size": 1450},
                {"text": "5. Zone controllers enforce ECU heartbeat availability and service/programming policy.", "size": 1450},
                {"text": "6. ECU programming follows UDS-oriented flow: session -> security -> erase -> download -> transfer -> verify -> activate -> reset.", "size": 1450},
                {"text": "7. ECU installs into inactive A/B slot; post-install validation commits or rolls back.", "size": 1450},
                {"text": "8. Final result is reported back through status APIs / MQTT / Mender view.", "size": 1450},
            ],
            fill="F8FAFC",
            line="CBD5E1",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 5 scenario 1
    shapes = title_block("Scenario 1: All ECUs Healthy And Eligible")
    shapes.append(
        textbox_xml(
            4,
            "Input",
            emu(0.65),
            emu(1.35),
            emu(3.75),
            emu(4.7),
            [
                {"text": "Setup", "size": 1750, "bold": True},
                {"text": "Topology: default", "size": 1450},
                {"text": "Dependency: topology default", "size": 1450},
                {"text": "Offline ECUs: none", "size": 1450},
                {"text": "ECU state: fresh baseline", "size": 1450},
                {"text": "Transport: DoIP or VCAN", "size": 1450},
            ],
            fill="DCFCE7",
            line="4ADE80",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "Behavior",
            emu(4.65),
            emu(1.35),
            emu(3.7),
            emu(4.7),
            [
                {"text": "Expected behavior", "size": 1750, "bold": True},
                {"text": "Discovery finds all 3 ECUs.", "size": 1450},
                {"text": "Compatibility passes.", "size": 1450},
                {"text": "Topological order is built.", "size": 1450},
                {"text": "Gateway, BCM, and Cluster are flashed and verified.", "size": 1450},
                {"text": "All move to target version and committed slot.", "size": 1450},
            ],
            fill="E0E7FF",
            line="818CF8",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            6,
            "Presenter",
            emu(8.65),
            emu(1.35),
            emu(3.0),
            emu(4.7),
            [
                {"text": "Presenter message", "size": 1750, "bold": True},
                {"text": "This is the reference happy-path OTA execution.", "size": 1450},
                {"text": "It proves orchestration, transport, flashing, and commit flow end-to-end.", "size": 1450},
            ],
            fill="FEF3C7",
            line="FBBF24",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 6 scenario 2
    shapes = title_block("Scenario 2: Some ECUs Already At Target Version")
    shapes.append(
        textbox_xml(
            4,
            "Input",
            emu(0.65),
            emu(1.35),
            emu(3.9),
            emu(4.85),
            [
                {"text": "Setup", "size": 1750, "bold": True},
                {"text": "Use ECU-state presets such as:", "size": 1450},
                {"text": "Gateway + BCM already updated", "size": 1450},
                {"text": "Gateway + Cluster already updated", "size": 1450},
                {"text": "BCM + Cluster already updated", "size": 1450},
            ],
            fill="DBEAFE",
            line="60A5FA",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "DynamicDecision",
            emu(4.8),
            emu(1.35),
            emu(3.8),
            emu(4.85),
            [
                {"text": "Expected behavior", "size": 1750, "bold": True},
                {"text": "TCU discovers live ECU versions.", "size": 1450},
                {"text": "ECUs already at target are classified as ALREADY_SATISFIED and skipped.", "size": 1450},
                {"text": "Only remaining compatible ECUs are updated.", "size": 1450},
                {"text": "This is dynamic skip/update, not a hardcoded replay.", "size": 1450},
            ],
            fill="DCFCE7",
            line="4ADE80",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            6,
            "Presenter",
            emu(8.95),
            emu(1.35),
            emu(2.7),
            emu(4.85),
            [
                {"text": "Presenter message", "size": 1750, "bold": True},
                {"text": "This demonstrates production-style delta targeting: do not reflash ECUs that already satisfy campaign target.", "size": 1450},
            ],
            fill="FFF7ED",
            line="FDBA74",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 7 scenario 3
    shapes = title_block("Scenario 3: Some ECUs Are Not Running / Offline")
    shapes.append(
        textbox_xml(
            4,
            "OfflineSetup",
            emu(0.65),
            emu(1.35),
            emu(3.8),
            emu(4.85),
            [
                {"text": "How we trigger it", "size": 1750, "bold": True},
                {"text": "Dynamic launcher offline menu", "size": 1450},
                {"text": "or live fault injection:", "size": 1450},
                {"text": "ecu_fault_control.py <ecu> heartbeat off", "size": 1450},
                {"text": "Zone controller then marks ECU OFFLINE after heartbeat timeout.", "size": 1450},
            ],
            fill="FCE7F3",
            line="F472B6",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "OfflineBehavior",
            emu(4.8),
            emu(1.35),
            emu(3.8),
            emu(4.85),
            [
                {"text": "Expected behavior", "size": 1750, "bold": True},
                {"text": "Cluster offline: may be skipped if campaign policy allows it.", "size": 1450},
                {"text": "BCM offline: may abort if BCM is mandatory or dependency-critical.", "size": 1450},
                {"text": "Gateway offline: typically abort because the main dependency path is unavailable.", "size": 1450},
            ],
            fill="FEF3C7",
            line="FBBF24",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            6,
            "Realism",
            emu(8.95),
            emu(1.35),
            emu(2.75),
            emu(4.85),
            [
                {"text": "Presenter message", "size": 1750, "bold": True},
                {"text": "The fault injection is manual, but the detection and OTA reaction are automatic.", "size": 1450},
            ],
            fill="F8FAFC",
            line="94A3B8",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 8 scenario 4
    shapes = title_block("Scenario 4: Condition Mismatched / Campaign Rejected")
    shapes.append(
        textbox_xml(
            4,
            "MismatchTypes",
            emu(0.65),
            emu(1.35),
            emu(4.2),
            emu(4.85),
            [
                {"text": "Typical mismatch cases", "size": 1750, "bold": True},
                {"text": "Transport unsupported for selected target.", "size": 1450},
                {"text": "Bootloader minimum not satisfied.", "size": 1450},
                {"text": "Mandatory ECU not found or not reachable.", "size": 1450},
                {"text": "Runtime ECU state preset does not match actual live version state.", "size": 1450},
            ],
            fill="FEE2E2",
            line="F87171",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "MismatchBehavior",
            emu(5.1),
            emu(1.35),
            emu(3.5),
            emu(4.85),
            [
                {"text": "Expected behavior", "size": 1750, "bold": True},
                {"text": "TCU fails validation early.", "size": 1450},
                {"text": "Campaign is rejected or narrowed before flashing.", "size": 1450},
                {"text": "Unsafe or inconsistent rollout does not proceed.", "size": 1450},
            ],
            fill="FFF7ED",
            line="FDBA74",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            6,
            "Presenter",
            emu(9.0),
            emu(1.35),
            emu(2.7),
            emu(4.85),
            [
                {"text": "Presenter message", "size": 1750, "bold": True},
                {"text": "This slide proves the system does not blindly push firmware when safety or consistency checks fail.", "size": 1450},
            ],
            fill="F8FAFC",
            line="94A3B8",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    # Slide 9 trigger screen
    shapes = title_block("Trigger Paths For The Demo")
    shapes.append(
        textbox_xml(
            4,
            "LocalTrigger",
            emu(0.65),
            emu(1.35),
            emu(5.4),
            emu(4.9),
            [
                {"text": "Local dynamic trigger", "size": 1750, "bold": True},
                {"text": "run_dynamic_demo.sh", "size": 1450},
                {"text": "Choose topology, dependency, offline case, ECU state, and transport.", "size": 1450},
                {"text": "Backend job is then published over MQTT and artifacts are downloaded over HTTPS.", "size": 1450},
                {"text": "This is the cleanest live operator path for local presentation.", "size": 1450},
            ],
            fill="DBEAFE",
            line="60A5FA",
            radius=True,
        )
    )
    shapes.append(
        textbox_xml(
            5,
            "MenderTrigger",
            emu(6.2),
            emu(1.35),
            emu(5.1),
            emu(4.9),
            [
                {"text": "Mender trigger", "size": 1750, "bold": True},
                {"text": "run_dynamic_mender_demo.sh", "size": 1450},
                {"text": "Build scenario-specific .mender artifact from selected runtime scenario.", "size": 1450},
                {"text": "Hosted Mender deploys to TCU host.", "size": 1450},
                {"text": "Mender client invokes tcu-ota-module -> TCU OTA orchestration starts.", "size": 1450},
            ],
            fill="DCFCE7",
            line="4ADE80",
            radius=True,
        )
    )
    slides.append(slide_xml(shapes))

    return slides


def content_types_xml(slide_count: int) -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for index in range(1, slide_count + 1):
        overrides.append(
            f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  {overrides}
</Types>""".replace("{overrides}", "".join(overrides))


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def presentation_xml(slide_count: int) -> str:
    sld_ids = []
    for index in range(1, slide_count + 1):
        sld_ids.append(f'<p:sldId id="{255 + index}" r:id="rId{index + 1}"/>')
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{cx}" cy="{cy}"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>""".format(slide_ids="".join(sld_ids), cx=SLIDE_W, cy=SLIDE_H)


def presentation_rels_xml(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for index in range(1, slide_count + 1):
        rels.append(
            f'<Relationship Id="rId{index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        )
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {rels}
</Relationships>""".replace("{rels}", "".join(rels))


def slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="Master">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle/>
    <p:bodyStyle/>
    <p:otherStyle/>
  </p:txStyles>
</p:sldMaster>"""


def slide_master_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Custom Theme">
  <a:themeElements>
    <a:clrScheme name="Custom">
      <a:dk1><a:srgbClr val="000000"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F2937"/></a:dk2>
      <a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>
      <a:accent1><a:srgbClr val="2563EB"/></a:accent1>
      <a:accent2><a:srgbClr val="7C3AED"/></a:accent2>
      <a:accent3><a:srgbClr val="16A34A"/></a:accent3>
      <a:accent4><a:srgbClr val="EA580C"/></a:accent4>
      <a:accent5><a:srgbClr val="DB2777"/></a:accent5>
      <a:accent6><a:srgbClr val="0891B2"/></a:accent6>
      <a:hlink><a:srgbClr val="2563EB"/></a:hlink>
      <a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont>
        <a:latin typeface="Aptos Display"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="Aptos"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>"""


def core_xml() -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Virtual Automotive OTA Demo Slides</dc:title>
  <dc:creator>OpenAI Codex</dc:creator>
  <cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>OpenAI Codex</Application>
  <Slides>{slide_count}</Slides>
  <Notes>0</Notes>
  <HiddenSlides>0</HiddenSlides>
  <MMClips>0</MMClips>
  <PresentationFormat>Custom</PresentationFormat>
  <Company>OpenAI</Company>
  <SharedDoc>false</SharedDoc>
  <LinksUpToDate>false</LinksUpToDate>
  <ScaleCrop>false</ScaleCrop>
</Properties>"""


def generate_pptx(out_path: Path) -> None:
    slides = build_slides()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(out_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(len(slides)))
        zf.writestr("_rels/.rels", root_rels_xml())
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("docProps/app.xml", app_xml(len(slides)))
        zf.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(len(slides)))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels_xml())
        zf.writestr("ppt/theme/theme1.xml", theme_xml())

        for index, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{index}.xml", slide)
            zf.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", slide_rels_xml())


def main() -> int:
    generate_pptx(OUT_PATH)
    print(f"[OK] Generated PowerPoint deck: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
