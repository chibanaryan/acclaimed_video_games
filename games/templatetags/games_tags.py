import markdown as md
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from ..models import Snippet

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


@register.inclusion_tag('games/_pagination.html', takes_context=True)
def pagination(context, number_adjacent=1):

    args = context.get('args', '')

    pages = []
    current_page_number = context['page_obj'].number
    paginator = context['page_obj'].paginator
    last_page_visible = True

    for i in paginator.page_range:
        show_page = False
        classes = ['pagination-link']

        if current_page_number == i:
            classes.append('is-current')
            show_page = True
        elif abs(current_page_number - i) <= number_adjacent:
            classes.append('is-adjacent')
            show_page = True
        if i == 1:
            classes.append('is-first')
            show_page = True
        if i == paginator.num_pages:
            classes.append('is-last')
            show_page = True

        if show_page:
            page = {
                'text': str(i),
                'class': ' '.join(classes),
                'href': f"?{args}&page={i}",
                'visible': show_page,
            }
            pages.append(page)
            last_page_visible = True
        elif last_page_visible:
            page = {'visible': False}
            pages.append(page)
            last_page_visible = False

    return {
        'pages': pages,
    }
