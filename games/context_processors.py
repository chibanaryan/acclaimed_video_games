"""
Custom template context processors.
"""


def feature_flags(request):
    """
    Add feature flags to template context.
    """
    import os

    from music import config as music_config

    return {
        # Books feature is hidden until ready for public release
        "BOOKS_ENABLED": os.environ.get("BOOKS_ENABLED", "").lower() == "true",
        # The "Beta" badge on music pages
        "MUSIC_BETA": music_config.MUSIC_BETA,
    }


def media_type(request):
    """
    Add the current site and media type to template context.

    ``site_key`` is the site the host names (core/sites.py): ``"root"`` for
    the landing page, ``"games"`` or ``"music"``; ``site_home_url`` is that
    site's front page. ``media_type`` follows it,
    except that the staff-only books section, which lives on the games host,
    is told apart by its URL namespace. Every page on a site is that site's,
    the shared ones (About, Contact, sign-in) included, so they keep the
    sidebar of the site the visitor is on.
    """
    from core import sites

    site = sites.request_site(request)
    resolver_match = getattr(request, "resolver_match", None)
    namespace = getattr(resolver_match, "namespace", "") or ""
    if site == sites.GAMES and namespace.startswith("books"):
        kind = "books"
    else:
        kind = site
    return {
        "site_key": site,
        "media_type": kind,
        "site_home_url": sites.site_reverse(site, sites.HOME_VIEWS[site]),
    }


def canonical_origin(request):
    """
    Add the current site's public origin, for canonical links and structured
    data.
    """
    from core import sites

    return {"canonical_origin": sites.canonical_origin(sites.request_site(request))}
