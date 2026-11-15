"""The general summary of a project: what was sold, what was done, what it cost
and what was left. It is the page read when the work is over, so it gathers in
one place what otherwise lives in the quote, the expenses and the files.

Nothing here is stored. The summary is computed from the project every time, so
it can never disagree with the records it summarises — closing a project only
marks the day it stopped moving.
"""

from decimal import Decimal

from .models import Task


def _two_places(value):
    return Decimal(value).quantize(Decimal('0.01'))


def build_summary(project):
    opportunity = project.opportunities.select_related('client').first()
    quote = opportunity.winning_quote if opportunity else None
    expenses = list(project.expenses.all())

    return {
        'project': _project_block(project),
        'deal': _deal_block(project, opportunity, quote),
        'period': _period_block(expenses),
        'result': project.cost_summary,
        'expenses': _expenses_block(project, expenses),
        'documents': [
            {'id': asset.id, 'name': asset.name, 'category': asset.category,
             'file_size': asset.file_size, 'uploaded_at': asset.created_at}
            for asset in project.assets.all()
        ],
        'tasks': _tasks_block(project),
    }


def _project_block(project):
    closer = project.closed_by
    return {
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'team': project.team.name,
        'area': project.team.area.name,
        'created_at': project.created_at,
        'is_closed': project.is_closed,
        'closed_on': project.closed_on,
        # A user with no full name set still has to be named.
        'closed_by_name': (closer.get_full_name() or closer.username) if closer else None,
        'closing_notes': project.closing_notes,
    }


def _deal_block(project, opportunity, quote):
    """Who bought it and under which document. None for a project with no deal."""
    if opportunity is None:
        return None

    block = {
        'client': opportunity.client.name,
        'opportunity_id': opportunity.id,
        'opportunity_name': opportunity.name,
        'quote': None,
    }
    if quote is not None:
        rate = quote.display_rate
        in_pesos = quote.display_currency == 'CLP'
        block['quote'] = {
            'number': quote.number,
            'reference': quote.reference,
            'status_display': quote.get_status_display(),
            'issue_date': quote.issue_date,
            'display_currency': quote.display_currency,
            'display_rate': rate,
            # The sale as the client reads it: a purchase order in UF is 280 UF,
            # whatever that came to in pesos on the day.
            'sale_in_display_currency': None if in_pesos else _two_places(project.budget_sale / rate),
            'notes': quote.notes,
        }
    return block


def _period_block(expenses):
    """The days money was spent: the closest thing to when the work happened."""
    dates = [expense.incurred_on for expense in expenses]
    if not dates:
        return {'from': None, 'to': None, 'days': 0}
    first, last = min(dates), max(dates)
    return {'from': first, 'to': last, 'days': (last - first).days + 1}


def _expenses_block(project, expenses):
    by_day = {}
    for expense in expenses:
        day = by_day.setdefault(expense.incurred_on, {'total': Decimal('0'), 'count': 0})
        day['total'] += expense.amount
        day['count'] += 1

    largest = sorted(expenses, key=lambda expense: expense.amount, reverse=True)[:5]
    return {
        'count': len(expenses),
        'total': project.expense_total,
        'by_day': [{'date': date, 'total': values['total'], 'count': values['count']}
                   for date, values in sorted(by_day.items())],
        'largest': [{'description': expense.description,
                     'category_display': expense.get_category_display(),
                     'amount': expense.amount, 'incurred_on': expense.incurred_on}
                    for expense in largest],
    }


def _tasks_block(project):
    tasks = Task.objects.filter(section__project=project)
    return {'total': tasks.count(),
            'completed': tasks.filter(status=Task.Status.COMPLETED).count()}
