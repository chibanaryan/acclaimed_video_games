import markdown as md
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from ..models import Snippet, Platform, Genre

register = template.Library()


@register.filter
@stringfilter
def markdown(content):
    return md.markdown(content)


def get_snippet(slug, create=True):
    snippet = Snippet.objects.filter(slug=slug)
    if snippet.exists():
        return snippet.first().text
    else:
        if create:
            placeholder_text = slug.replace('-', ' ').upper()
            snippet = Snippet.objects.create(slug=slug, text=placeholder_text)
            return snippet.text


@register.simple_tag
def snippet(name):
    return mark_safe(get_snippet(name))


@register.inclusion_tag('games/_search_form.html', takes_context=True)
def search_form(context):
    return {
        'platforms': Platform.objects.all(),
        'genres': Genre.objects.all(),
    }


@register.inclusion_tag('games/_pagination.html', takes_context=True)
def pagination(context, max_pages=10):

    args = context.get('args', '')
    pages = []
    current_page_number = context['page_obj'].number
    paginator = context['page_obj'].paginator

    for i in paginator.page_range:
        classes = ['pagination-link']
        distance_from_current = abs(current_page_number - i)

        is_current = current_page_number == i
        if is_current:
            classes.append('is-current')

        page = {
            'text': str(i),
            'class': ' '.join(classes),
            'href': f"?{args}&page={i}",
            'first': i == 1,
            'last': i == paginator.num_pages,
            'current': is_current,
            'order': i,
            'distance_from_current': distance_from_current,
        }

        pages.append(page)

    if len(pages) > max_pages:
        min_pages = [x for x in pages if x['current']
                     or x['first'] or x['last']]
        min_page_orders = [x['order'] for x in min_pages]
        num_extra_pages_required = max_pages - len(min_pages)
        available_pages = [
            x for x in pages if x['order'] not in min_page_orders]
        extra_pages = sorted(available_pages, key=lambda x: x['distance_from_current'])[
            :num_extra_pages_required]
        raw_pages = min_pages + extra_pages
        raw_pages.sort(key=lambda x: x['order'])

        pages = []
        for i in range(0, len(raw_pages)):
            this_page = raw_pages[i]
            pages.append(this_page)
            try:
                next_page = raw_pages[i + 1]
                if next_page['order'] - this_page['order'] > 1:
                    pages.append({})
            except IndexError:
                break

    return {
        'pages': pages,
    }
