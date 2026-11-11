"""A small, dependency-free PDF writer for text reports: A4 pages, Helvetica (regular/bold), word wrapping,
clickable links, page numbers. Enough for the weekly report, without pulling a PDF library (and its native
image dependencies) into the API image.

Text uses the PDF standard 14 fonts with WinAnsiEncoding (cp1252): Latin scripts render as is; other
characters are replaced with "?" (the report links every item to its original source).
"""

import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

PAGE_W, PAGE_H = 595.0, 842.0  # A4 in points
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 50.0, 56.0, 60.0

# Advance widths (1/1000 em) of Helvetica and Helvetica-Bold for ASCII 32..126 (Adobe AFM).
_REG = [
    int(w)
    for w in (
        "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
        "556 556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 "
        "778 667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 "
        "556 556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 500 334 260 334 584 "
    ).split()
]
_BOLD = [
    int(w)
    for w in (
        "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 "
        "556 556 333 333 584 584 584 611 975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
        "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 333 556 611 556 611 556 333 611 "
        "611 278 278 556 278 889 611 611 611 611 389 556 333 611 556 778 556 556 500 389 280 389 584 "
    ).split()
]
assert len(_REG) == len(_BOLD) == 95


def _encode(text: str) -> bytes:
    return text.encode("cp1252", errors="replace")


def text_width(text: str, size: float, bold: bool = False) -> float:
    table = _BOLD if bold else _REG
    total = 0
    for b in _encode(text):
        total += table[b - 32] if 32 <= b <= 126 else 556
    return total * size / 1000


def wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    lines: list[str] = []
    for para in (text or "").splitlines() or [""]:
        line = ""
        for word in para.split():
            while text_width(word, size, bold) > width:  # a URL or token longer than a line: hard-break it
                cut = len(word)
                while cut > 1 and text_width(word[:cut], size, bold) > width:
                    cut -= 1
                if line:
                    lines.append(line)
                    line = ""
                lines.append(word[:cut])
                word = word[cut:]
            candidate = f"{line} {word}" if line else word
            if text_width(candidate, size, bold) <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _esc(raw: bytes) -> bytes:
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)").replace(b"\r", b"")


@dataclass
class _Page:
    ops: list[bytes] = field(default_factory=list)
    links: list[tuple[float, float, float, float, str]] = field(default_factory=list)


class PdfDocument:
    def __init__(self, title: str, footer: str = "AI Pulse") -> None:
        self.title = title
        self.footer = footer
        self.pages: list[_Page] = []
        self.y = 0.0
        self._new_page()

    @property
    def width(self) -> float:
        return PAGE_W - 2 * MARGIN_X

    def _new_page(self) -> None:
        self.pages.append(_Page())
        self.y = PAGE_H - MARGIN_TOP

    def _need(self, h: float) -> None:
        if self.y - h < MARGIN_BOTTOM:
            self._new_page()

    def space(self, h: float) -> None:
        self.y -= h
        if self.y < MARGIN_BOTTOM:
            self._new_page()

    def text(
        self,
        text: str,
        *,
        size: float = 10,
        bold: bool = False,
        color: tuple[float, float, float] = (0.1, 0.1, 0.12),
        indent: float = 0,
        link: str | None = None,
        leading: float = 1.35,
        keep_with_next: float = 0,
    ) -> None:
        line_h = size * leading
        lines = wrap(text, size, self.width - indent, bold)
        self._need(line_h * min(len(lines), 2) + keep_with_next)
        font = b"/F2" if bold else b"/F1"
        for line in lines:
            self._need(line_h)
            self.y -= line_h
            x = MARGIN_X + indent
            page = self.pages[-1]
            r, g, b = color
            page.ops.append(
                b"BT %s %.1f Tf %.3f %.3f %.3f rg %.2f %.2f Td (%s) Tj ET"
                % (font, size, r, g, b, x, self.y + size * 0.25, _esc(_encode(line)))
            )
            if link and line:
                w = text_width(line, size, bold)
                page.links.append((x, self.y, x + w, self.y + line_h, link))

    def rule(self, gap: float = 8) -> None:
        self.space(gap)
        y = self.y
        self.pages[-1].ops.append(
            b"0.8 0.8 0.84 RG 0.6 w %.2f %.2f m %.2f %.2f l S" % (MARGIN_X, y, PAGE_W - MARGIN_X, y)
        )
        self.space(gap)

    def render(self, created: datetime | None = None) -> bytes:
        created = created or datetime.now(UTC)
        objs: list[bytes] = []

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        catalog = add(b"")  # placeholders, filled below
        pages_id = add(b"")
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        stamp = created.strftime("D:%Y%m%d%H%M%SZ").encode()
        info = add(
            b"<< /Title (%s) /Producer (AI Pulse) /CreationDate (%s) >>" % (_esc(_encode(self.title)), stamp)
        )
        kids: list[int] = []
        total = len(self.pages)
        for i, page in enumerate(self.pages, start=1):
            footer = f"{self.footer}  -  page {i} of {total}"
            ops = [
                *page.ops,
                b"BT /F1 8 Tf 0.45 0.45 0.5 rg %.2f %.2f Td (%s) Tj ET"
                % (MARGIN_X, MARGIN_BOTTOM / 2, _esc(_encode(footer))),
            ]
            data = zlib.compress(b"\n".join(ops))
            content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream" % (len(data), data))
            annots = b" ".join(
                b"<< /Type /Annot /Subtype /Link /Rect [%.2f %.2f %.2f %.2f] /Border [0 0 0] "
                b"/A << /S /URI /URI (%s) >> >>" % (x1, y1, x2, y2, _esc(url.encode("ascii", "ignore")))
                for x1, y1, x2, y2, url in page.links
                if url.startswith(("https://", "http://"))
            )
            kids.append(
                add(
                    b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.0f %.0f] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Annots [%s] >>"
                    % (pages_id, PAGE_W, PAGE_H, content, f1, f2, annots)
                )
            )
        objs[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
        objs[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
            b" ".join(b"%d 0 R" % k for k in kids),
            len(kids),
        )

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for n, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
        out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objs) + 1,
            catalog,
            info,
            xref,
        )
        return bytes(out)
