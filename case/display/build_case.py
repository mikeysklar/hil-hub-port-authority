# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
Display case for the Smart HIL Hub Rev C: a sandwich-style top plate that
carries a QT Py ESP32-S3 and a 0.96" 128x64 STEMMA QT OLED, over a SKADIS
rail frame.

Run headless:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_case.py

Writes next to this file:
    display_case.FCStd         parametric model, every setting in the Params sheet
    top_plate.step/.stl        STL laid outer face down for printing
    qtpy_cradle.step/.stl      STL laid floor down for printing
    frame.step/.stl            STL laid back face down for printing

Frame: PCB coordinates from the Rev C gerbers, board back face on Z=0,
components up. Same frame and hub stand-in as case/sandwich.

The top plate sits on M2.5 standoffs (bought, not printed) at the four mount
holes, top_gap above the board. Screws go down through clearance holes into
the standoffs. Everything taller than top_gap pokes through snug cutouts;
cutouts on the board edge run out through the plate edge. The left edge stays
open so both STEMMA QT ports can be plugged in under the plate overhang.

OLED: on M2.5 x ol_standoff standoffs screwed into heat-set inserts, centred
between the X10 JST-XH and the DC jack. Its STEMMA QT ports are on the back
and face sideways; at this height the right one's plug clears the DC jack.
The board is taller than the plate, so the top two inserts sit on a tab past
the top edge. Bosses hang boss_drop under the plate to give the inserts depth.

QT Py: no mounting holes, so it rides in a printed cradle with its USB-C out
the left edge. It slides in from the STEMMA end under lips on the castellated
edges until it meets stops at the USB-C end; plugging in the STEMMA cable
pushes it further home. Two M2.5 screws sit in counterbores under the QT Py
and go down into plate inserts. The cradle's right end stops short of the X10
plug and the QT Py's STEMMA plug lands below the X10 cutout.

Back frame: two rails through the mount-hole rows and two ties at the hole
columns, bot_standoff behind the board on M2.5 standoffs, with a flush
heat-set insert at each hole. No hook notches: the rails run rail_len so
your own hooks can grab them.
"""

import os
import struct
import zipfile

import FreeCAD as App
import Part

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()

DOC_PATH = os.path.join(HERE, "display_case.FCStd")

PARAMS = [
    ("# board, Rev C gerbers. Facts, not design choices", None, ""),
    ("board_w", 91.44, "outline X"),
    ("board_h", 35.56, "outline Y"),
    ("board_t", 1.6, "PCB thickness"),
    ("board_r", 2.54, "outline corner radius"),
    ("hole_inset", 2.54, "mount hole centre from left and bottom edge"),
    ("hole_dx", 86.36, "mount hole pitch X"),
    ("hole_dy", 30.48, "mount hole pitch Y"),
    ("band_y1", 13.06, "top of the USB-A / JST-XH / cap band"),
    ("# stack", None, ""),
    ("plate_t", 2.0, "plate thickness"),
    ("border", 1.5, "plate overhang past the board outline"),
    ("top_gap", 5.0, "PCB top to plate underside. M2.5 x 5 standoff"),
    ("standoff_d", 5.0, "standoff across flats, for the clash check"),
    ("screw_d", 2.7, "M2.5 clearance hole"),
    ("# cutouts", None, ""),
    ("cut_margin", 0.5, "clearance around each part poking through"),
    ("# heat-set inserts, M2.5", None, ""),
    ("insert_d", 3.3, "insert pocket diameter"),
    ("insert_depth", 3.3, "insert pocket depth from the top face"),
    ("insert_wall", 1.0, "boss wall around the pocket"),
    ("boss_drop", 2.0, "boss below the plate underside, for insert depth"),
    ("insert_screw_d", 2.8, "screw clearance past the insert"),
    ("# OLED 0.96in 128x64 STEMMA QT (Adafruit 326), Adafruit CAD", None, ""),
    ("ol_w", 29.21, "outline X"),
    ("ol_l", 31.75, "outline Y including the bottom tabs"),
    ("ol_t", 1.6, "PCB thickness, assumed"),
    ("ol_standoff", 8.0, "M2.5 standoff, plate top to OLED back"),
    ("ol_cx", 46.3, "centre X. X10 on the left, the DC jack plug on the right"),
    ("ol_y0", "=band_y1 + cut_margin + 0.5", "OLED bottom edge Y, clear of the band"),
    ("# QT Py ESP32-S3 (Adafruit 5426), Adafruit CAD", None, ""),
    ("qt_w", 17.78, "width across the castellated edges (world Y)"),
    ("qt_l", 20.70, "length, STEMMA end to USB-C end (world X)"),
    ("qt_t", 1.6, "PCB thickness, assumed"),
    ("qt_usb_over", 1.02, "USB-C overhang past the PCB edge"),
    ("qt_x0", -3.5, "USB-C end X. Right end clears the X10 plug"),
    ("# QT Py cradle", None, ""),
    ("cr_floor", 3.0, "floor thickness"),
    ("cr_wall", 1.2, "side wall thickness"),
    ("cr_clear", 0.2, "PCB to wall"),
    ("cr_lip", 0.5, "lip reach over the castellated edge"),
    ("cr_lip_t", 0.8, "lip thickness"),
    ("cr_stop", 1.2, "end stop length past the USB-C end"),
    ("cr_stop_w", 2.4, "end stop width, clear of the USB-C"),
    ("cr_relief", 1.2, "relief under the ESP32-S3 on the QT Py's underside"),
    ("cr_screw_d", 2.7, "M2.5 clearance hole"),
    ("cr_cbore_d", 5.0, "counterbore for the screw head"),
    ("cr_cbore_h", 2.0, "counterbore depth"),
    ("# back frame", None, ""),
    ("bot_standoff", 5.0, "PCB back to rail face. M2.5 x 5 standoff, clears THT leads"),
    ("rail_w", 8.0, "rail width (Y)"),
    ("rail_t", 4.0, "rail thickness (Z)"),
    ("rail_len", 140.0, "rail length, centred on the board. Room for hooks"),
    ("tie_w", 6.0, "tie width (X) at the mount-hole columns"),
    ("# derived, do not edit", None, ""),
    ("plate_w", "=board_w + 2 * border", "plate outline X"),
    ("plate_h", "=board_h + 2 * border", "plate outline Y"),
    ("plate_r", "=board_r + border", "plate corner radius"),
    ("top_z0", "=board_t + top_gap", "plate underside Z"),
    ("top_z1", "=board_t + top_gap + plate_t", "plate outer face Z"),
    ("boss_d", "=insert_d + 2 * insert_wall", "insert boss diameter"),
    ("ol_x0", "=ol_cx - ol_w / 2", "OLED left edge X"),
    ("ol_z0", "=top_z1 + ol_standoff", "OLED back face Z"),
    ("rail_z1", "=-bot_standoff", "rail front face Z"),
    ("rail_z0", "=-bot_standoff - rail_t", "rail back face Z"),
    ("rail_x0", "=board_w / 2 - rail_len / 2", "rail start X"),
    ("qt_x1", "=qt_x0 + qt_l", "QT Py STEMMA end X"),
    ("qt_y0", "=band_y1 + cut_margin + cr_wall + cr_clear", "QT Py lower edge Y"),
    ("qt_z0", "=top_z1 + cr_floor", "QT Py back face Z"),
]

# Plate cutouts: (name, x0, x1, y0, y1) in PCB mm at the part bodies.
# cut_margin is added on every closed side. None = open through that plate edge.
# Only parts taller than top_gap need one, plus SW2 for access.
CUTS = [
    # X1-X8 USB-A + JST XH stacks and caps C24 C27 C30: webs between them are
    # all under 3 mm, so one notch.
    ("usbA_band", 7.31, 84.02, None, 13.06),
    ("cap_C3", 1.16, 6.46, 5.48, 10.78),
    # X9 sits under the plate; this notch clears the plug overmold
    # (12.35 x 6.5 max, USB-IF) where it meets the plate edge.
    ("plug_X9", 7.79, 20.15, 35.45, None),
    ("xh_X10", 19.20, 31.60, 30.02, None),
    ("dcjack_X11", 61.61, 70.61, 22.06, None),
    ("term_J1", 72.95, 79.95, 28.28, None),
    # SW2 body (6.66 x 5.4, DSHP 1.27-4P drawing) so the switches can be set
    # with the case closed.
    ("dip_SW2", 84.17, 90.83, 23.21, 28.61),
]
# OLED mount holes, OLED-local mm from its lower-left corner (Adafruit CAD).
# The top two land on a tab past the plate's top edge.
OLED_HOLES = (("bl", 2.54, 2.54), ("br", 26.67, 2.54), ("tl", 2.54, 29.21),
              ("tr", 26.67, 29.21))

# QT Py cradle screws into plate inserts, QT Py-local mm: x across the
# castellated edges, y from the STEMMA end. Clear of the ESP32-S3 underneath.
QT_SCREWS = (("a", 4.0, 3.0), ("b", 10.0, 15.5))
# ESP32-S3 QFN on the QT Py's underside, local centre and size.
QT_QFN = (10.33, 9.20, 7.0)


def qt_world(lx, ly):
    """QT Py-local point to world sheet expressions. USB-C points to -X."""
    return ("%sqt_x1 - %g" % (P, ly), "%sqt_y0 + %g" % (P, lx))


# Body-to-body fills where the web between two cuts is too thin to print.
WEBS = [
    ("web_X11_J1", 70.61, 72.95, 28.28, None),
]

# Hub stand-in, PCB mm. (name, x0, x1, y0, y1, h above the top face).
PARTS = [
    ("X1_usbA", 7.31, 20.41, -0.2, 9.8, 6.5),
    ("X3_usbA", 29.01, 42.11, -0.2, 9.8, 6.5),
    ("X5_usbA", 49.33, 62.43, -0.2, 9.8, 6.5),
    ("X7_usbA", 70.92, 84.02, -0.2, 9.8, 6.5),
    ("X2_xh4", 7.77, 20.17, 6.53, 12.28, 7.0),
    ("X4_xh4", 29.36, 41.76, 6.40, 12.15, 7.0),
    ("X6_xh4", 49.68, 62.08, 6.40, 12.15, 7.0),
    ("X8_xh4", 71.27, 83.67, 6.40, 12.15, 7.0),
    ("X10_xh4", 19.20, 31.60, 30.02, 35.77, 7.0),
    ("C3_100u", 1.16, 6.46, 5.48, 10.78, 5.8),
    ("C24_100u", 23.51, 28.81, 7.76, 13.06, 5.8),
    ("C27_100u", 43.96, 49.26, 7.38, 12.68, 5.8),
    ("C30_100u", 65.80, 71.10, 7.76, 13.06, 5.8),
    ("X9_usbC", 9.50, 18.44, 28.60, 35.95, 3.26),
    ("X11_dcjack", 61.61, 70.61, 22.06, 36.06, 11.0),
    ("J1_term", 72.95, 79.95, 28.28, 35.48, 8.5),
    ("D1_sma", 65.09, 70.29, 18.89, 21.49, 2.3),
    ("STEMMA1", -0.3, 4.0, 11.48, 17.48, 2.9),
    ("STEMMA2", -0.3, 4.0, 20.88, 26.88, 2.9),
    ("SW1_slide", 88.01, 92.4, 5.40, 13.40, 1.4),
    ("SW2_dip4", 84.17, 90.83, 23.21, 28.61, 2.3),
]
THT = ["X1_usbA", "X3_usbA", "X5_usbA", "X7_usbA", "X2_xh4", "X4_xh4",
       "X6_xh4", "X8_xh4", "X10_xh4", "X11_dcjack", "J1_term"]
LEAD_LEN = 2.5
SMD_FLOOR = 1.5      # tallest ordinary SMD part (SOT-23), for the clash check

EPS = 0.1
P = "Params."


def build_sheet(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "parameter")
    sheet.set("B1", "value")
    sheet.set("C1", "note")
    for row, (name, value, note) in enumerate(PARAMS, start=2):
        sheet.set("A%d" % row, name)
        if value is not None:
            sheet.set("B%d" % row, str(value))
            sheet.setAlias("B%d" % row, name)
            sheet.set("C%d" % row, note)
    sheet.setColumnWidth("A", 130)
    sheet.setColumnWidth("B", 130)
    sheet.setColumnWidth("C", 400)
    doc.recompute()
    return sheet


def bind(obj, prop, expr):
    obj.setExpression(prop, expr)


def box(doc, name, x, y, z, length, width, height):
    o = doc.addObject("Part::Box", name)
    for prop, expr in (("Length", length), ("Width", width), ("Height", height),
                       ("Placement.Base.x", x), ("Placement.Base.y", y),
                       ("Placement.Base.z", z)):
        bind(o, prop, expr)
    return o


def cyl(doc, name, x, y, z, radius, height):
    o = doc.addObject("Part::Cylinder", name)
    for prop, expr in (("Radius", radius), ("Height", height),
                       ("Placement.Base.x", x), ("Placement.Base.y", y),
                       ("Placement.Base.z", z)):
        bind(o, prop, expr)
    return o


def rounded_plate(doc, prefix, z):
    """Board outline grown by border, as 2 boxes + 4 corner cylinders."""
    x0, y0 = "-" + P + "border", "-" + P + "border"
    r = P + "plate_r"
    objs = [
        box(doc, prefix + "_spanX", "%s + %s" % (x0, r), y0, z,
            "%splate_w - 2 * %s" % (P, r), P + "plate_h", P + "plate_t"),
        box(doc, prefix + "_spanY", x0, "%s + %s" % (y0, r), z,
            P + "plate_w", "%splate_h - 2 * %s" % (P, r), P + "plate_t"),
    ]
    for tag, cx, cy in (("bl", "0", "0"), ("br", "1", "0"),
                        ("tl", "0", "1"), ("tr", "1", "1")):
        objs.append(cyl(
            doc, "%s_corner_%s" % (prefix, tag),
            "%s + %s + %s * (%splate_w - 2 * %s)" % (x0, r, cx, P, r),
            "%s + %s + %s * (%splate_h - 2 * %s)" % (y0, r, cy, P, r),
            z, r, P + "plate_t"))
    return objs


HOLES = (("bl", "0", "0"), ("br", "1", "0"), ("tl", "0", "1"), ("tr", "1", "1"))


def hole_xy(ix, iy):
    return ("%shole_inset + %s * %shole_dx" % (P, ix, P),
            "%shole_inset + %s * %shole_dy" % (P, iy, P))


def cut_box(doc, name, x0, x1, y0, y1, z0, z1, margin=True):
    m = " - %scut_margin" % P if margin else ""
    mp = " + %scut_margin" % P if margin else ""
    far = "%sborder + 1" % P
    xa = "%g%s" % (x0, m)
    xb = "%g%s" % (x1, mp)
    ya = "-(%s)" % far if y0 is None else "%g%s" % (y0, m)
    yb = "%sboard_h + %s" % (P, far) if y1 is None else "%g%s" % (y1, mp)
    return box(doc, name, xa, ya, z0, "(%s) - (%s)" % (xb, xa),
               "(%s) - (%s)" % (yb, ya), "(%s) - (%s)" % (z1, z0))



def build_top(doc):
    z0, z1 = P + "top_z0", P + "top_z1"
    adds = rounded_plate(doc, "Top", z0)
    cuts = []
    for tag, ix, iy in HOLES:
        hx, hy = hole_xy(ix, iy)
        cuts.append(cyl(doc, "TopScrew_" + tag, hx, hy, "%s - %g" % (z0, EPS),
                        P + "screw_d / 2", "%splate_t + %g" % (P, 2 * EPS)))
    # Tab past the top edge for the OLED's upper holes.
    adds.append(box(doc, "OledTab", P + "ol_x0", "%splate_h - %sborder - 1" % (P, P),
                    z0, P + "ol_w",
                    "%sol_y0 + %sol_l + 0.5 - (%splate_h - %sborder - 1)"
                    % (P, P, P, P), P + "plate_t"))
    for tag, hx, hy in OLED_HOLES:
        x = "%sol_x0 + %g" % (P, hx)
        y = "%sol_y0 + %g" % (P, hy)
        adds.append(cyl(doc, "OledBoss_" + tag, x, y,
                        "%s - %sboss_drop" % (z0, P), P + "boss_d / 2",
                        "%sboss_drop + %splate_t" % (P, P)))
        cuts.append(cyl(doc, "OledInsert_" + tag, x, y,
                        "%s - %sinsert_depth" % (z1, P), P + "insert_d / 2",
                        "%sinsert_depth + %g" % (P, EPS)))
        cuts.append(cyl(doc, "OledScrew_" + tag, x, y,
                        "%s - %sboss_drop - %g" % (z0, P, EPS),
                        P + "insert_screw_d / 2",
                        "%sboss_drop + %splate_t" % (P, P)))
    for tag, lx, ly in QT_SCREWS:
        x, y = qt_world(lx, ly)
        adds.append(cyl(doc, "QtBoss_" + tag, x, y,
                        "%s - %sboss_drop" % (z0, P), P + "boss_d / 2",
                        "%sboss_drop + %splate_t" % (P, P)))
        cuts.append(cyl(doc, "QtInsert_" + tag, x, y,
                        "%s - %sinsert_depth" % (z1, P), P + "insert_d / 2",
                        "%sinsert_depth + %g" % (P, EPS)))
        cuts.append(cyl(doc, "QtScrew_" + tag, x, y,
                        "%s - %sboss_drop - %g" % (z0, P, EPS),
                        P + "insert_screw_d / 2",
                        "%sboss_drop + %splate_t" % (P, P)))
    za, zb = "%s - %g" % (z0, EPS), "%s + %g" % (z1, EPS)
    for name, x0, x1, y0, y1 in CUTS:
        cuts.append(cut_box(doc, "TopCut_" + name, x0, x1, y0, y1, za, zb))
    for name, x0, x1, y0, y1 in WEBS:
        cuts.append(cut_box(doc, "TopCut_" + name, x0, x1, y0, y1, za, zb,
                            margin=False))
    return finish(doc, "TopPlate", adds, cuts)


def finish(doc, name, adds, cuts):
    body = doc.addObject("Part::MultiFuse", name + "_body")
    body.Shapes = adds
    body.Refine = True
    tool = doc.addObject("Part::MultiFuse", name + "_cuts")
    tool.Shapes = cuts
    out = doc.addObject("Part::Cut", name)
    out.Base = body
    out.Tool = tool
    out.Refine = True
    for o in adds + cuts + [body, tool]:
        o.Visibility = False
    return out


def build_hub(doc):
    bw, bh, bt, r = 91.44, 35.56, 1.6, 2.54
    plate = Part.makeBox(bw - 2 * r, bh, bt, App.Vector(r, 0, 0))
    plate = plate.fuse(Part.makeBox(bw, bh - 2 * r, bt, App.Vector(0, r, 0)))
    for cx, cy in ((r, r), (bw - r, r), (r, bh - r), (bw - r, bh - r)):
        plate = plate.fuse(Part.makeCylinder(r, bt, App.Vector(cx, cy, 0)))
    for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02), (88.9, 33.02)):
        plate = plate.cut(Part.makeCylinder(1.25, bt + 1, App.Vector(cx, cy, -0.5)))
    parts, leads = [], []
    for name, x0, x1, y0, y1, h in PARTS:
        parts.append(Part.makeBox(x1 - x0, y1 - y0, h, App.Vector(x0, y0, bt)))
        if name in THT:
            leads.append(Part.makeBox(x1 - x0, y1 - y0, LEAD_LEN,
                                      App.Vector(x0, y0, -LEAD_LEN)))
    objs = []
    for name, shape in (("HubPCB", plate.removeSplitter()),
                        ("HubParts", Part.makeCompound(parts)),
                        ("HubLeads", Part.makeCompound(leads))):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        objs.append(o)
    return objs


# View state. FreeCAD 1.1 has no ViewObject headless, so GuiDocument.xml is
# written into the saved FCStd directly. Layout from kicad2freecad-enclosures.

VIEW_PROP = """        <ViewProvider name="%s" expanded="0">
            <Properties Count="6" TransientCount="0">
                <Property name="LineColor" type="App::PropertyColor" status="1">
                    <PropertyColor value="%d"/>
                </Property>
                <Property name="LineWidth" type="App::PropertyFloatConstraint" status="1">
                    <Float value="%.4f"/>
                </Property>
                <Property name="PointColor" type="App::PropertyColor" status="1">
                    <PropertyColor value="%d"/>
                </Property>
                <Property name="ShapeAppearance" type="App::PropertyMaterialList" status="1">
                    <MaterialList file="%s" version="3"/>
                </Property>
                <Property name="Transparency" type="App::PropertyPercent" status="1">
                    <Integer value="%d"/>
                </Property>
                <Property name="Visibility" type="App::PropertyBool" status="1">
                    <Bool value="%s"/>
                </Property>
            </Properties>
        </ViewProvider>
"""


def _rgb(spec):
    h = spec.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (r << 24) | (g << 16) | (b << 8) | 0xFF


def _material_blob(diffuse, transparency):
    return (struct.pack("<I", 1)
            + struct.pack("<I", _rgb("#333333"))
            + struct.pack("<I", diffuse)
            + struct.pack("<I", 0x000000FF)
            + struct.pack("<I", 0x000000FF)
            + struct.pack("<ff", 0.2, transparency / 100.0)
            + struct.pack("<III", 0, 0, 0))


def write_view_state(doc_path, styles, hidden):
    entries, blobs = [], {}
    for i, name in enumerate(list(styles) + hidden):
        color, line, transp = styles.get(name, ("#808080", "#000000", 0))
        blob = "ShapeAppearance" if i == 0 else "ShapeAppearance%d" % i
        blobs[blob] = _material_blob(_rgb(color), transp)
        entries.append(VIEW_PROP % (name, _rgb(line), 2.0, _rgb(line), blob,
                                    transp, "false" if name in hidden else "true"))
    xml = ("<?xml version='1.0' encoding='utf-8'?>\n"
           '<Document SchemaVersion="1">\n'
           '    <ViewProviderData Count="%d">\n%s    </ViewProviderData>\n'
           "</Document>\n" % (len(entries), "".join(entries)))
    with zipfile.ZipFile(doc_path, "r") as z:
        keep = [(n, z.read(n)) for n in z.namelist()
                if n != "GuiDocument.xml" and n not in blobs]
    with zipfile.ZipFile(doc_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in keep:
            z.writestr(n, data)
        z.writestr("GuiDocument.xml", xml)
        for n, data in blobs.items():
            z.writestr(n, data)




def corner_box(doc, name, x0, x1, y0, y1, z0, z1):
    return box(doc, name, x0, y0, z0, "(%s) - (%s)" % (x1, x0),
               "(%s) - (%s)" % (y1, y0), "(%s) - (%s)" % (z1, z0))


def build_cradle(doc):
    """QT Py cradle: floor, side walls with lips over the castellated edges,
    end stops at the USB-C end. The QT Py slides in from the STEMMA end."""
    e = lambda expr: " ".join(P + t if t[0].isalpha() else t
                              for t in expr.split())
    ya, yb = e("qt_y0 - cr_clear - cr_wall"), e("qt_y0 + qt_w + cr_clear + cr_wall")
    fz0, fz1 = P + "top_z1", P + "qt_z0"
    wz1 = e("qt_z0 + qt_t + 0.1 + cr_lip_t")
    adds = [corner_box(doc, "CrFloor", P + "qt_x0", P + "qt_x1",
                       ya, yb, fz0, fz1)]
    for tag, y0, y1 in (("lo", ya, e("qt_y0 - cr_clear")),
                        ("hi", e("qt_y0 + qt_w + cr_clear"), yb)):
        adds.append(corner_box(doc, "CrWall_" + tag, P + "qt_x0",
                               P + "qt_x1", y0, y1, fz1, wz1))
    lz0 = e("qt_z0 + qt_t + 0.1")
    for tag, y0, y1 in (("lo", e("qt_y0 - cr_clear - 0.1"), e("qt_y0 + cr_lip")),
                        ("hi", e("qt_y0 + qt_w - cr_lip"),
                         e("qt_y0 + qt_w + cr_clear + 0.1"))):
        adds.append(corner_box(doc, "CrLip_" + tag, P + "qt_x0", P + "qt_x1",
                               y0, y1, lz0, wz1))
    for tag, y0, y1 in (("lo", ya, e("qt_y0 + cr_stop_w")),
                        ("hi", e("qt_y0 + qt_w - cr_stop_w"), yb)):
        adds.append(corner_box(doc, "CrStop_" + tag, e("qt_x0 - cr_stop"),
                               P + "qt_x0", y0, y1, fz0, e("qt_z0 + qt_t")))
    cuts = []
    qx, qy = qt_world(QT_QFN[0], QT_QFN[1])
    half = QT_QFN[2] / 2 + 0.5
    cuts.append(corner_box(doc, "CrRelief", "%s - %g" % (qx, half),
                           "%s + %g" % (qx, half), "%s - %g" % (qy, half),
                           "%s + %g" % (qy, half), e("qt_z0 - cr_relief"),
                           e("qt_z0 + 0.1")))
    for tag, lx, ly in QT_SCREWS:
        x, y = qt_world(lx, ly)
        cuts.append(cyl(doc, "CrScrew_" + tag, x, y, e("top_z1 - 0.1"),
                        P + "cr_screw_d / 2", e("cr_floor + 0.2")))
        cuts.append(cyl(doc, "CrCbore_" + tag, x, y, e("qt_z0 - cr_cbore_h"),
                        P + "cr_cbore_d / 2", e("cr_cbore_h + 0.1")))
    return finish(doc, "QtCradle", adds, cuts)


def build_frame(doc):
    """Two rails through the mount-hole rows, two ties at the hole columns,
    a flush heat-set insert at each hole for the back standoffs."""
    z0 = P + "rail_z0"
    adds = []
    for tag, iy in (("bot", "0"), ("top", "1")):
        _x, hy = hole_xy("0", iy)
        adds.append(box(doc, "Rail_" + tag, P + "rail_x0",
                        "%s - %srail_w / 2" % (hy, P), z0, P + "rail_len",
                        P + "rail_w", P + "rail_t"))
    for tag, ix in (("l", "0"), ("r", "1")):
        hx, _y = hole_xy(ix, "0")
        adds.append(box(doc, "Tie_" + tag, "%s - %stie_w / 2" % (hx, P),
                        P + "hole_inset", z0, P + "tie_w", P + "hole_dy",
                        P + "rail_t"))
    cuts = []
    for tag, ix, iy in HOLES:
        hx, hy = hole_xy(ix, iy)
        cuts.append(cyl(doc, "FrameInsert_" + tag, hx, hy,
                        "%srail_z1 - %sinsert_depth" % (P, P),
                        P + "insert_d / 2", "%sinsert_depth + %g" % (P, EPS)))
        cuts.append(cyl(doc, "FrameScrew_" + tag, hx, hy,
                        "%s - %g" % (z0, EPS), P + "insert_screw_d / 2",
                        "%srail_t + %g" % (P, 2 * EPS)))
    return finish(doc, "Frame", adds, cuts)


def build_qtpy(doc, s):
    """QT Py stand-in in its cradle: PCB, USB-C, STEMMA QT and its plug on
    top, ESP32-S3 underneath, USB-C plug overmold. Adafruit CAD positions."""
    zb, zt = s.qt_z0, s.qt_z0 + s.qt_t

    def b(lx0, lx1, ly0, ly1, z0, z1):
        return Part.makeBox(ly1 - ly0, lx1 - lx0, z1 - z0,
                            App.Vector(s.qt_x1 - ly1, s.qt_y0 + lx0, z0))
    qx, qy, qs = QT_QFN
    board = [b(0, s.qt_w, 0, s.qt_l, zb, zt),
             b(4.42, 13.36, 14.37, 21.72, zt, zt + 3.2),
             b(8.07, 14.17, 0.49, 4.74, zt, zt + 2.95),
             b(qx - qs / 2, qx + qs / 2, qy - qs / 2, qy + qs / 2, zb - 0.9, zb)]
    stemma_plug = b(11.07 - 3.0, 11.07 + 3.0, 0.49 - 6.0, 0.49, zt, zt + 2.95)
    usb_plug = b(8.89 - 6.175, 8.89 + 6.175, 21.72, 40.0,
                 zt + 1.6 - 3.25, zt + 1.6 + 3.25)
    objs = []
    for name, shapes in (("QtPy", board + [stemma_plug]),
                         ("QtPlug", [usb_plug])):
        o = doc.addObject("Part::Feature", name)
        o.Shape = Part.makeCompound(shapes)
        objs.append(o)
    return objs


def build_oled(doc, s):
    """OLED stand-in on its standoffs: PCB, glass, back JST SH ports, right
    STEMMA QT plug. Adafruit CAD positions, OLED-local mm."""
    ox, oy, zb, zt = s.ol_x0, s.ol_y0, s.ol_z0, s.ol_z0 + s.ol_t

    def b(x0, x1, y0, y1, z0, z1):
        return Part.makeBox(x1 - x0, y1 - y0, z1 - z0,
                            App.Vector(ox + x0, oy + y0, z0))
    pcb = Part.makeBox(s.ol_w, s.ol_l, s.ol_t, App.Vector(ox, oy, zb))
    for _t, hx, hy in OLED_HOLES:
        pcb = pcb.cut(Part.makeCylinder(1.25, 5, App.Vector(ox + hx, oy + hy,
                                                            zb - 1)))
    shapes = [pcb, b(1.26, 27.96, 7.67, 26.93, zt, zt + 1.4),
              b(0.45, 4.7, 13.51, 19.51, zb - 2.95, zb),
              b(24.51, 28.76, 13.51, 19.51, zb - 2.95, zb),
              b(28.76, 34.26, 14.26, 18.76, zb - 2.95, zb)]
    o = doc.addObject("Part::Feature", "Oled")
    o.Shape = Part.makeCompound(shapes)
    return o


def check(top, cradle, frame, hub, oled, qtpy, sheet):
    pcb, parts, leads = (o.Shape for o in hub)
    t, c, f = top.Shape, cradle.Shape, frame.Shape
    qt, qt_plug = (o.Shape for o in qtpy)
    ok = True

    def report(label, good, detail=""):
        nonlocal ok
        ok = ok and good
        print("%-5s %-28s %s" % ("ok" if good else "FAIL", label, detail))

    for label, x in (("top", t), ("cradle", c), ("frame", f)):
        report(label + " valid", x.isValid())
        report(label + " solids", len(x.Solids) == 1, "%d" % len(x.Solids))
    for label, a, other in (("top vs pcb", t, pcb), ("top vs parts", t, parts),
                            ("top vs OLED", t, oled.Shape),
                            ("top vs QT Py", t, qt), ("top vs cradle", t, c),
                            ("cradle vs QT Py", c, qt),
                            ("top vs QT Py USB plug", t, qt_plug),
                            ("cradle vs QT Py USB plug", c, qt_plug),
                            ("frame vs pcb", f, pcb),
                            ("frame vs leads", f, leads)):
        v = a.common(other).Volume
        report(label + " clash", v < 1e-3, "%.4f mm3" % v)
    # Host USB-C plug overmold, 12.35 x 6.5, centred on the X9 receptacle.
    plug = Part.makeBox(12.35, 15.0, 6.5,
                        App.Vector(13.97 - 6.175, 35.95, 1.6 + 1.63 - 3.25))
    v = t.common(plug).Volume
    report("top vs host USB-C plug", v < 1e-3, "%.4f mm3" % v)
    standoffs = [Part.makeCylinder(sheet.standoff_d / 2, sheet.top_gap,
                                   App.Vector(cx, cy, sheet.board_t))
                 for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02),
                                (88.9, 33.02))]
    for s in standoffs:
        v = s.common(parts).Volume
        report("standoff %.2f,%.2f vs parts" % (s.BoundBox.Center.x,
                                                s.BoundBox.Center.y),
               v < 1e-3, "%.4f mm3" % v)
        report("plate sits on standoff", t.distToShape(s)[0] < 1e-3)
    # DC jack plug goes in from the top edge: keep its path clear.
    dc_plug = Part.makeBox(9.0, 20.0, 11.0, App.Vector(61.61, 36.06, 1.6))
    v = t.common(dc_plug).Volume
    report("top vs DC jack plug path", v < 1e-3, "%.4f mm3" % v)
    # X10 plug and wires go straight up from the header.
    x10_up = Part.makeBox(12.4, 5.75, 40.0, App.Vector(19.2, 30.02, 1.6))
    report("cradle sits on plate", c.distToShape(t)[0] < 1e-3)
    report("QT Py sits in cradle", qt.distToShape(c)[0] < 1e-3)
    for label, shp in (("top", t), ("OLED", oled.Shape), ("cradle", c),
                       ("QT Py", qt)):
        v = shp.common(x10_up).Volume
        report("%s vs X10 plug and wires" % label, v < 1e-3, "%.4f mm3" % v)
    for tag, hx, hy in OLED_HOLES:
        x, y = sheet.ol_x0 + hx, sheet.ol_y0 + hy
        ring = Part.makeCylinder(sheet.boss_d / 2 - 0.01, sheet.plate_t,
                                 App.Vector(x, y, sheet.top_z0))
        ring = ring.cut(Part.makeCylinder(sheet.insert_d / 2 + 0.01,
                                          sheet.plate_t,
                                          App.Vector(x, y, sheet.top_z0)))
        v = ring.cut(t).Volume
        report("OLED boss %s in plate" % tag, v < 1e-3, "%.4f mm3 missing" % v)
        stand = Part.makeCylinder(2.5, sheet.ol_standoff,
                                  App.Vector(x, y, sheet.top_z1))
        report("OLED standoff %s on plate" % tag,
               t.distToShape(stand)[0] < 1e-3)
    for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02), (88.9, 33.02)):
        so = Part.makeCylinder(sheet.standoff_d / 2, sheet.bot_standoff,
                               App.Vector(cx, cy, -sheet.bot_standoff))
        v = so.common(leads).Volume
        report("back standoff %.2f,%.2f vs leads" % (cx, cy), v < 1e-3,
               "%.4f mm3" % v)
        report("frame under standoff %.2f,%.2f" % (cx, cy),
               f.distToShape(so)[0] < 1e-3)
        pocket = Part.makeCylinder(sheet.insert_d / 2 - 0.05, sheet.insert_depth,
                                   App.Vector(cx, cy, sheet.rail_z1 - sheet.insert_depth))
        v = pocket.common(f).Volume
        report("frame insert pocket %.2f,%.2f" % (cx, cy), v < 1e-3,
               "%.4f mm3" % v)
    gap = -sheet.bot_standoff + LEAD_LEN
    report("lead clearance to rails", gap < 0, "%.2f mm" % -gap)
    through = [n for n, *_r, h in PARTS if h > sheet.top_gap]
    print("parts through the top plate:", ", ".join(through))
    return ok


doc = App.newDocument("display_case")
sheet = build_sheet(doc)
top = build_top(doc)
cradle = build_cradle(doc)
frame = build_frame(doc)
hub = build_hub(doc)
doc.recompute()
oled = build_oled(doc, sheet)
qtpy = build_qtpy(doc, sheet)
doc.recompute()

ok = check(top, cradle, frame, hub, oled, qtpy, sheet)

doc.saveAs(DOC_PATH)
hidden = [o.Name for o in doc.Objects
          if hasattr(o, "Visibility") and not o.Visibility
          and o.TypeId != "Spreadsheet::Sheet"]
write_view_state(DOC_PATH, {
    "TopPlate": ("#1A1A1F", "#D9FF00", 45),
    "HubPCB": ("#0E3A2C", "#00E5C7", 0),
    "HubParts": ("#B0B0B8", "#404040", 0),
    "HubLeads": ("#FF8C00", "#FF8C00", 0),
    "Oled": ("#101010", "#40C0FF", 0),
    "QtCradle": ("#1A1A1F", "#FF2D9B", 30),
    "Frame": ("#1A1A1F", "#FF2D9B", 45),
    "QtPy": ("#2A2A6E", "#8080FF", 0),
    "QtPlug": ("#808080", "#404040", 70),
}, hidden)

for obj, stem, flip in ((top, "top_plate", True), (cradle, "qtpy_cradle", False),
                        (frame, "frame", False)):
    obj.Shape.exportStep(os.path.join(HERE, stem + ".step"))
    s = obj.Shape.copy()
    if flip:
        s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.translate(App.Vector(0, 0, -s.BoundBox.ZMin))
    s.exportStl(os.path.join(HERE, stem + ".stl"))

print("wrote", DOC_PATH)
print("CHECKS PASS" if ok else "CHECKS FAIL")
