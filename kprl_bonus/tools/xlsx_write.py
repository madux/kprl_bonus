"""Minimal stdlib xlsx WRITER (no third-party dependency).

Writes styled workbooks the Accounts ledger needs: title block, header
row, data rows (numbers stay numeric, strings via shared strings),
TOTAL row with live SUM formulas, frozen header, auto-filter, column
widths, money number format. Read back verified with openpyxl.
"""
import io
import zipfile
from xml.sax.saxutils import escape as _escape


def _col_letter(n):
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _styles_xml():
    f = []
    f.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
    f.append("<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">")
    f.append("<numFmts count=\"1\"><numFmt numFmtId=\"164\" formatCode=\"#,##0.00\"/></numFmts>")
    f.append("<fonts count=\"5\">")
    f.append("<font><sz val=\"11\"/><name val=\"Calibri\"/></font>")
    f.append("<font><b/><sz val=\"14\"/><color rgb=\"FF1A3C6E\"/><name val=\"Calibri\"/></font>")
    f.append("<font><b/><sz val=\"9\"/><color rgb=\"FFFFFFFF\"/><name val=\"Calibri\"/></font>")
    f.append("<font><sz val=\"9\"/><name val=\"Calibri\"/></font>")
    f.append("<font><b/><sz val=\"10\"/><name val=\"Calibri\"/></font>")
    f.append("</fonts>")
    f.append("<fills count=\"3\">")
    f.append("<fill><patternFill patternType=\"none\"/></fill>")
    f.append("<fill><patternFill patternType=\"gray125\"/></fill>")
    f.append("<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF1A3C6E\"/><bgColor indexed=\"64\"/></patternFill></fill>")
    f.append("</fills>")
    f.append("<borders count=\"2\">")
    f.append("<border><left/><right/><top/><bottom/><diagonal/></border>")
    f.append("<border><left style=\"thin\"><color rgb=\"FF999999\"/></left><right style=\"thin\"><color rgb=\"FF999999\"/></right><top style=\"thin\"><color rgb=\"FF999999\"/></top><bottom style=\"thin\"><color rgb=\"FF999999\"/></bottom><diagonal/></border>")
    f.append("</borders>")
    f.append("<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>")
    f.append("<cellXfs count=\"7\">")
    f.append("<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/>")
    f.append("<xf numFmtId=\"0\" fontId=\"2\" fillId=\"2\" borderId=\"1\" xfId=\"0\" applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\"><alignment horizontal=\"center\" vertical=\"center\" wrapText=\"1\"/></xf>")
    f.append("<xf numFmtId=\"164\" fontId=\"3\" fillId=\"0\" borderId=\"1\" xfId=\"0\" applyNumberFormat=\"1\" applyFont=\"1\" applyBorder=\"1\"><alignment horizontal=\"right\"/></xf>")
    f.append("<xf numFmtId=\"164\" fontId=\"4\" fillId=\"0\" borderId=\"1\" xfId=\"0\" applyNumberFormat=\"1\" applyFont=\"1\" applyBorder=\"1\"><alignment horizontal=\"right\"/></xf>")
    f.append("<xf numFmtId=\"0\" fontId=\"1\" fillId=\"0\" borderId=\"0\" xfId=\"0\" applyFont=\"1\"/>")
    f.append("<xf numFmtId=\"0\" fontId=\"3\" fillId=\"0\" borderId=\"0\" xfId=\"0\" applyFont=\"1\"/>")
    f.append("<xf numFmtId=\"0\" fontId=\"3\" fillId=\"0\" borderId=\"1\" xfId=\"0\" applyFont=\"1\" applyBorder=\"1\"/>")
    f.append("</cellXfs>")
    f.append("<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>")
    f.append("<dxfs count=\"0\"/><tableStyles count=\"0\" defaultTableStyle=\"TableStyleMedium9\" defaultPivotStyle=\"PivotTableStyle1\"/>")
    f.append("</styleSheet>")
    return "".join(f)
CELL_DEFAULT = 0
CELL_HEADER = 1
CELL_MONEY = 2
CELL_MONEY_BOLD = 3
CELL_TITLE = 4
CELL_TEXT = 5
CELL_TEXT_BORDER = 6


def _cell(ref, style, inner, ctype=None):
    tag = "<c r=\"" + ref + "\" s=\"" + str(style) + "\""
    if ctype:
        tag += " t=\"" + ctype + "\""
    return tag + ">" + inner + "</c>"


class _SheetBuilder(object):
    def __init__(self):
        self._strings = []
        self._index = {}

    def _scell(self, ref, style, text):
        text = "" if text is None else str(text)
        if text not in self._index:
            self._index[text] = len(self._strings)
            self._strings.append(text)
        return _cell(ref, style, "<v>" + str(self._index[text]) + "</v>", "s")

    def _num(self, value):
        if value is None:
            return ""
        return "<v>" + repr(float(value)) + "</v>"

    def build_ledger(self, title, subtitle_lines, headers, widths, rows, amount_cols, with_total=True):
        ncols = len(headers)
        last_col = _col_letter(ncols)
        header_row = 3 + len(subtitle_lines) + 2
        first_data = header_row + 1
        out = []
        out.append("<row r=\"1\">" + self._scell("A1", CELL_TITLE, title) + "</row>")
        for i, sub in enumerate(subtitle_lines):
            r = 2 + i
            out.append("<row r=\"" + str(r) + "\">" + self._scell("A" + str(r), CELL_TEXT, sub) + "</row>")
        head = []
        for idx in range(ncols):
            head.append(self._scell(_col_letter(idx + 1) + str(header_row), CELL_HEADER, headers[idx]))
        out.append("<row r=\"" + str(header_row) + "\">" + "".join(head) + "</row>")
        for i, row in enumerate(rows):
            r = first_data + i
            cells = []
            for idx in range(ncols):
                ref = _col_letter(idx + 1) + str(r)
                val = row[idx] if idx < len(row) else None
                if idx in amount_cols:
                    cells.append(_cell(ref, CELL_MONEY, self._num(val)))
                else:
                    cells.append(self._scell(ref, CELL_TEXT_BORDER, val))
            out.append("<row r=\"" + str(r) + "\">" + "".join(cells) + "</row>")
        total_row = first_data + len(rows)
        if with_total:
            cells = [self._scell("A" + str(total_row), CELL_TEXT, "TOTAL")]
            for idx in range(1, ncols):
                ref = _col_letter(idx + 1) + str(total_row)
                if idx in amount_cols:
                    col = _col_letter(idx + 1)
                    cells.append('<c r="' + ref + '" s="' + str(CELL_MONEY_BOLD) + '"><f>SUM(' + col + str(first_data) + ':' + col + str(total_row - 1) + ')</f><v>0</v></c>')
                else:
                    cells.append(self._scell(ref, CELL_TEXT_BORDER, ""))
            out.append("<row r=\"" + str(total_row) + "\">" + "".join(cells) + "</row>")
            last_row = total_row
        else:
            last_row = total_row - 1
        cols = "".join("<col min=\"" + str(i + 1) + "\" max=\"" + str(i + 1) + "\" width=\"" + str(widths[i]) + "\" customWidth=\"1\"/>" for i in range(ncols))
        parts = []
        parts.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
        parts.append("<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">")
        parts.append("<dimension ref=\"A1:" + last_col + str(last_row) + "\"/>")
        parts.append("<sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"" + str(header_row) + "\" topLeftCell=\"A" + str(first_data) + "\" activePane=\"bottomLeft\" state=\"frozen\"/></sheetView></sheetViews>")
        parts.append("<sheetFormat defaultRowHeight=\"15\"/>")
        parts.append("<cols>" + cols + "</cols>")
        parts.append("<sheetData>" + "".join(out) + "</sheetData>")
        bottom = last_row - (1 if with_total else 0)
        if bottom < header_row:
            bottom = header_row
        parts.append("<autoFilter ref=\"A" + str(header_row) + ":" + last_col + str(bottom) + "\"/>")
        parts.append("</worksheet>")
        return "".join(parts), self._strings


def _shared_strings_xml(strings):
    items = "".join("<si><t>" + _escape_text(s) + "</t></si>" for s in strings)
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"" + str(len(strings)) + "\" uniqueCount=\"" + str(len(strings)) + "\">" + items + "</sst>"


def _escape_text(text):
    return _escape(text, {'"': "&quot;"})


def build_ledger_workbook(title, subtitle_lines, headers, widths, rows, amount_cols, with_total=True):
    """Assemble a complete .xlsx file (bytes) for the bonus ledger."""
    import io
    import zipfile
    builder = _SheetBuilder()
    sheet_xml, strings = builder.build_ledger(title, subtitle_lines, headers, widths, rows, set(amount_cols), with_total)
    content_types = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">" + "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>" + "<Default Extension=\"xml\" ContentType=\"application/xml\"/>" + "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>" + "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>" + "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>" + "<Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>" + "</Types>"
    rels = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">" + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>" + "</Relationships>"
    workbook = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">" + "<sheets><sheet name=\"Bonus Ledger\" sheetId=\"1\" r:id=\"rId1\"/></sheets>" + "</workbook>"
    wb_rels = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">" + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>" + "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>" + "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" Target=\"sharedStrings.xml\"/>" + "</Relationships>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/styles.xml", _styles_xml())
        zf.writestr("xl/sharedStrings.xml", _shared_strings_xml(strings))
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()
