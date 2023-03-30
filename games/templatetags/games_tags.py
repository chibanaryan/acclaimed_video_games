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
