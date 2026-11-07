"""Minimal stdlib xlsx reader (fallback when openpyxl is unavailable).

Reads cached cell values only (equivalent of openpyxl data_only=True):
numbers, shared strings, inline strings, booleans. No formula
evaluation, formatting, or charts. Only what the importer needs:
wb[name] -> ws; ws.cell(row, column); ws["B4"] -> cell with .value.
"""
import re
import zipfile
import xml.etree.ElementTree as ET


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _col_to_index(ref):
    letters = re.sub("[^A-Z]", "", ref.upper())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


class Cell:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class WorkSheet:
    def __init__(self, grid):
        self._grid = grid

    def cell(self, row, column):
        return Cell(self._grid.get((int(row), int(column))))

    def __getitem__(self, ref):
        m = re.match(r"([A-Za-z]+)([0-9]+)", ref)
        return self.cell(int(m.group(2)), _col_to_index(m.group(1)))


class WorkBook:
    def __init__(self, sheets):
        self._sheets = sheets

    def __getitem__(self, name):
        return self._sheets[name]

    @property
    def sheetnames(self):
        return list(self._sheets.keys())
def _shared_strings(zf):
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root:
        if _local(si.tag) != "si":
            continue
        parts = []
        for node in si.iter():
            if _local(node.tag) == "t" and node.text:
                parts.append(node.text)
        out.append("".join(parts))
    return out


def _sheet_grid(zf, path, strings):
    try:
        root = ET.fromstring(zf.read(path))
    except KeyError:
        return {}
    grid = {}
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        r = int(row.get("r", "0") or 0)
        for c in row:
            if _local(c.tag) != "c":
                continue
            ref = c.get("r", "")
            m = re.match(r"([A-Za-z]+)([0-9]+)", ref)
            if not m:
                continue
            col = _col_to_index(m.group(1))
            typ = c.get("t")
            val = None
            if typ == "inlineStr":
                buf = []
                for node in c.iter():
                    if _local(node.tag) == "t" and node.text:
                        buf.append(node.text)
                val = "".join(buf) or None
            else:
                vnode = None
                for node in c:
                    if _local(node.tag) == "v":
                        vnode = node
                        break
                if vnode is not None and vnode.text is not None:
                    raw = vnode.text
                    if typ == "s":
                        try:
                            val = strings[int(raw)]
                        except (ValueError, IndexError):
                            val = None
                    elif typ == "b":
                        val = (raw != "0")
                    elif typ == "e":
                        val = None
                    else:
                        try:
                            num = float(raw)
                        except ValueError:
                            val = raw
                        else:
                            val = int(num) if num.is_integer() else num
            grid[(r, col)] = val
    return grid


def load_workbook(path, data_only=True):
    zf = zipfile.ZipFile(path)
    wbroot = ET.fromstring(zf.read("xl/workbook.xml"))
    try:
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        rels = None
    targets = {}
    if rels is not None:
        for rel in rels:
            if _local(rel.tag) == "Relationship":
                targets[rel.get("Id")] = rel.get("Target")
    sheets = []
    for node in wbroot.iter():
        if _local(node.tag) != "sheet":
            continue
        name = node.get("name")
        rid = None
        for k, v in node.attrib.items():
            if _local(k) == "id":
                rid = v
        target = targets.get(rid, "")
        if target.startswith("/"):
            target = target[1:]
        elif not target.startswith("xl/"):
            target = "xl/" + target
        sheets.append((name, target))
    strings = _shared_strings(zf)
    out = {}
    for name, target in sheets:
        out[name] = WorkSheet(_sheet_grid(zf, target, strings))
    zf.close()
    return WorkBook(out)
