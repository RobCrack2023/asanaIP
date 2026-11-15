"""The quote as a PDF, built only from what the client is allowed to see.

The builder takes the payload of ClientQuoteSerializer, never a Quote object.
That is the whole point: there is no cost or margin in scope here, so no
future edit to this file can print one by accident.
"""

import unicodedata
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

#: Room for the footer band, so the flowables never sit on top of it.
BOTTOM_MARGIN = 22 * mm


def _decimal(value):
    return Decimal(str(value or '0'))


def format_date(value):
    """'2026-08-26' as '26 de agosto de 2026'."""
    if not value:
        return '—'
    year, month, day = (int(part) for part in str(value)[:10].split('-'))
    return f'{day} de {MONTHS[month - 1]} de {year}'


def format_money(amount, currency, rate):
    """A CLP figure shown in the currency the quote is expressed in.

    Amounts are stored in pesos; `rate` is what one unit of `currency` was
    worth when the quote was issued, so the document keeps reading the same
    however the dollar moves afterwards.
    """
    value = _decimal(amount) / (_decimal(rate) or Decimal('1'))
    if currency == 'CLP':
        return '$ ' + f'{value:,.0f}'.replace(',', '.')
    whole = f'{value:,.2f}'.replace(',', '@').replace('.', ',').replace('@', '.')
    return f'{currency} {whole}'


def _quantity(value):
    """Quantities are decimal in the model but whole in practice."""
    number = _decimal(value)
    if number == number.to_integral_value():
        return f'{number:.0f}'
    return f'{number:.2f}'.replace('.', ',')


class _Styles:
    def __init__(self, accent):
        base = getSampleStyleSheet()
        self.accent = accent
        self.normal = ParagraphStyle('ipNormal', parent=base['Normal'],
                                     fontName='Helvetica', fontSize=8.5, leading=12,
                                     textColor=colors.HexColor('#333333'))
        self.small = ParagraphStyle('ipSmall', parent=self.normal, fontSize=7.5, leading=10,
                                    textColor=colors.HexColor('#666666'))
        self.right = ParagraphStyle('ipRight', parent=self.normal, alignment=TA_RIGHT)
        self.company = ParagraphStyle('ipCompany', parent=self.normal, fontSize=13,
                                      leading=16, fontName='Helvetica-Bold',
                                      textColor=accent)
        self.title = ParagraphStyle('ipTitle', parent=self.normal, fontSize=15, leading=18,
                                    fontName='Helvetica-Bold', alignment=TA_RIGHT,
                                    textColor=colors.white)
        self.title_meta = ParagraphStyle('ipTitleMeta', parent=self.normal, fontSize=9,
                                         leading=13, alignment=TA_RIGHT, textColor=colors.white)
        self.section = ParagraphStyle('ipSection', parent=self.normal, fontSize=9,
                                      fontName='Helvetica-Bold', textColor=accent,
                                      spaceAfter=3)
        self.cell = ParagraphStyle('ipCell', parent=self.normal, fontSize=8)
        self.cell_right = ParagraphStyle('ipCellRight', parent=self.cell, alignment=TA_RIGHT)
        self.cell_center = ParagraphStyle('ipCellCenter', parent=self.cell, alignment=TA_CENTER)
        self.header_cell = ParagraphStyle('ipHeadCell', parent=self.cell,
                                          fontName='Helvetica-Bold', textColor=colors.white)
        self.header_right = ParagraphStyle('ipHeadRight', parent=self.header_cell,
                                           alignment=TA_RIGHT)
        self.header_center = ParagraphStyle('ipHeadCenter', parent=self.header_cell,
                                            alignment=TA_CENTER)
        self.footer = ParagraphStyle('ipFooter', parent=self.small, alignment=TA_CENTER)


def _letterhead(template, styles, width):
    """Logo on the left, company details on the right."""
    lines = [f'<b>{template.company_name or template.organization.name}</b>']
    if template.tax_id:
        lines.append(f'RUT {template.tax_id}')
    for value in (template.address, template.phone, template.email, template.website):
        if value:
            lines.append(str(value))
    details = Paragraph('<br/>'.join(lines), styles.small)

    logo = ''
    if template.logo:
        try:
            logo = Image(template.logo.path)
            # Fit inside the box without distorting whatever shape it has.
            ratio = logo.imageHeight / float(logo.imageWidth)
            logo.drawWidth = min(45 * mm, 45 * mm)
            logo.drawHeight = logo.drawWidth * ratio
            if logo.drawHeight > 20 * mm:
                logo.drawHeight = 20 * mm
                logo.drawWidth = logo.drawHeight / ratio
            logo.hAlign = 'LEFT'
        except Exception:
            # A missing or unreadable file must not cost the company its quote.
            logo = Paragraph(template.company_name or template.organization.name, styles.company)

    table = Table([[logo, details]], colWidths=[width * 0.5, width * 0.5])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def _title_band(quote, template, styles, width):
    left = Paragraph(template.document_title, styles.title)
    meta = [f'N° {quote["number"] or "—"}',
            f'Fecha: {format_date(quote["issue_date"])}']
    if quote.get('valid_until'):
        meta.append(f'Válida hasta: {format_date(quote["valid_until"])}')
    right = Paragraph('<br/>'.join(meta), styles.title_meta)

    band = Table([[left, right]], colWidths=[width * 0.45, width * 0.55])
    band.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), styles.accent),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (0, 0), 10),
        ('RIGHTPADDING', (-1, 0), (-1, 0), 10),
    ]))
    return band


def _client_block(quote, styles, width):
    lines = [f'<b>{quote.get("client_name") or ""}</b>']
    for value in (quote.get('client_contact'), quote.get('client_email'),
                  quote.get('client_phone')):
        if value:
            lines.append(str(value))
    left = Paragraph('<br/>'.join(lines), styles.normal)

    right_lines = []
    if quote.get('opportunity_name'):
        right_lines.append(f'<b>Referencia:</b> {quote["opportunity_name"]}')
    if quote.get('owner_name'):
        right_lines.append(f'<b>Preparado por:</b> {quote["owner_name"]}')
    right = Paragraph('<br/>'.join(right_lines), styles.normal)

    table = Table([[left, right]], colWidths=[width * 0.45, width * 0.55])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def _items_table(quote, template, styles, width):
    """The columns the template asked for — none of which is a cost."""
    currency, rate = quote['display_currency'], quote['display_rate']

    columns = []
    if template.show_item_number:
        columns.append(('N°', 0.05, 'center'))
    columns.append(('Descripción', 0.42, 'left'))
    if template.show_unit:
        columns.append(('Unidad', 0.10, 'center'))
    columns.append(('Cant.', 0.08, 'center'))
    columns.append(('P. unitario', 0.16, 'right'))
    if template.show_discount:
        columns.append(('Desc.', 0.07, 'center'))
    columns.append(('Subtotal', 0.18, 'right'))

    # Descripción absorbs whatever the optional columns left behind.
    spare = 1 - sum(share for _, share, _ in columns)
    columns = [(label, share + spare if label == 'Descripción' else share, align)
               for label, share, align in columns]

    head_style = {'left': styles.header_cell, 'right': styles.header_right,
                  'center': styles.header_center}
    rows = [[Paragraph(label, head_style[align]) for label, _, align in columns]]

    for index, item in enumerate(quote['items'], start=1):
        row = []
        if template.show_item_number:
            row.append(Paragraph(str(index), styles.cell_center))
        row.append(Paragraph(item['description'], styles.cell))
        if template.show_unit:
            row.append(Paragraph(item.get('unit') or '—', styles.cell_center))
        row.append(Paragraph(_quantity(item['quantity']), styles.cell_center))
        row.append(Paragraph(format_money(item['unit_price'], currency, rate), styles.cell_right))
        if template.show_discount:
            discount = _decimal(item.get('discount_percent'))
            row.append(Paragraph(f'{discount:.0f}%' if discount else '—', styles.cell_center))
        row.append(Paragraph(format_money(item['subtotal'], currency, rate), styles.cell_right))
        rows.append(row)

    table = Table(rows, colWidths=[width * share for _, share, _ in columns],
                  repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), styles.accent),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, colors.HexColor('#E4E4E4')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
    ]))
    return table


def _totals_table(quote, styles, width):
    currency, rate = quote['display_currency'], quote['display_rate']
    tax_rate = _decimal(quote['tax_rate'])
    rows = [
        ['Neto', format_money(quote['subtotal'], currency, rate)],
        [f'IVA {tax_rate:.0f}%', format_money(quote['tax_amount'], currency, rate)],
        ['TOTAL', format_money(quote['total_amount'], currency, rate)],
    ]
    cells = [[Paragraph(label, styles.cell_right), Paragraph(value, styles.cell_right)]
             for label, value in rows]

    table = Table(cells, colWidths=[width * 0.22, width * 0.22], hAlign='RIGHT')
    table.setStyle(TableStyle([
        ('LINEABOVE', (0, 2), (-1, 2), 0.8, styles.accent),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#F2F2F2')),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def _signature_block(template, styles, width):
    lines = ['_' * 34]
    if template.signature_name:
        lines.append(f'<b>{template.signature_name}</b>')
    if template.signature_title:
        lines.append(template.signature_title)
    if template.company_name:
        lines.append(template.company_name)
    block = Paragraph('<br/>'.join(lines),
                      ParagraphStyle('ipSign', parent=styles.small, alignment=TA_CENTER))
    table = Table([[block]], colWidths=[width * 0.4], hAlign='RIGHT')
    table.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 18)]))
    return table


def _page_furniture(template, styles):
    """Footer text and page numbers, drawn on every page."""
    footer = template.footer_text

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(styles.accent)
        canvas.setLineWidth(1.2)
        y = BOTTOM_MARGIN - 6 * mm
        canvas.line(doc.leftMargin, y, A4[0] - doc.rightMargin, y)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#777777'))
        if footer:
            canvas.drawCentredString(A4[0] / 2, y - 4.5 * mm, footer)
        canvas.drawRightString(A4[0] - doc.rightMargin, y - 4.5 * mm,
                               f'Página {canvas.getPageNumber()}')
        canvas.restoreState()

    return draw


def build_quote_pdf(quote, template):
    """Render `quote` (a ClientQuoteSerializer payload) onto `template`.

    Returns the PDF bytes. Nothing is written to disk: the document is
    regenerated from current data every time it is asked for.
    """
    accent = colors.HexColor(template.accent_color or template.DEFAULT_ACCENT)
    styles = _Styles(accent)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=BOTTOM_MARGIN,
        title=f'{template.document_title} N° {quote["number"] or ""}'.strip(),
        author=template.company_name or template.organization.name,
    )
    width = doc.width

    story = [
        _letterhead(template, styles, width),
        Spacer(1, 8 * mm),
        _title_band(quote, template, styles, width),
        Spacer(1, 7 * mm),
        _client_block(quote, styles, width),
        Spacer(1, 6 * mm),
    ]

    if template.intro_text:
        story += [Paragraph(template.intro_text.replace('\n', '<br/>'), styles.normal),
                  Spacer(1, 5 * mm)]

    story += [_items_table(quote, template, styles, width), Spacer(1, 5 * mm),
              _totals_table(quote, styles, width)]

    if quote['display_currency'] != 'CLP':
        story += [Spacer(1, 3 * mm),
                  Paragraph(f'Valores expresados en {quote["display_currency"]} al tipo de '
                            f'cambio de la fecha de emisión.', styles.small)]

    if template.show_quote_notes and quote.get('notes'):
        story += [Spacer(1, 6 * mm),
                  KeepTogether([Paragraph('Observaciones', styles.section),
                                Paragraph(quote['notes'].replace('\n', '<br/>'), styles.normal)])]

    if template.terms:
        story += [Spacer(1, 6 * mm),
                  KeepTogether([Paragraph('Condiciones comerciales', styles.section),
                                Paragraph(template.terms.replace('\n', '<br/>'), styles.small)])]

    story.append(_signature_block(template, styles, width))

    draw = _page_furniture(template, styles)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()


def quote_filename(quote, template):
    """Cotizacion-N12-Cliente.pdf — safe on every filesystem."""
    parts = [template.document_title.replace(' ', '-'),
             f'N{quote["number"]}' if quote['number'] else '',
             (quote.get('client_name') or '').replace(' ', '-')]
    name = unicodedata.normalize('NFKD', '-'.join(part for part in parts if part))
    # ASCII only: a Content-Disposition header carrying 'Ó' arrives mangled.
    keep = [c for c in name if (c.isalnum() and c.isascii()) or c in '-_']
    return (''.join(keep) or 'cotizacion') + '.pdf'
