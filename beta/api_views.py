"""
API views for beta app - provides JSON endpoints for HTMX/Alpine.js interactions
"""

from django.http import JsonResponse
from django.views import View
from games import models


class GameSearchAPIView(View):
    """
    API endpoint for navbar search - returns JSON list of games matching query.
    Used by GameSearchComponent in navbar.
    """

    def get(self, request):
        q = request.GET.get("q", "").strip()
        limit = int(request.GET.get("limit", 5))

        if len(q) < 2:
            return JsonResponse({"results": [], "count": 0})

        # Search games by name
        games = (
            models.Game.objects.filter(name__icontains=q)
            .prefetch_related(
                "developers",
                "developers__developer",
            )
            .order_by("rank")[:limit]
        )

        results = []
        for game in games:
            results.append(
                {
                    "id": game.id,
                    "name": game.name,
                    "slug": game.slug,
                    "year_of_release": game.year_of_release,
                    "rank": game.rank,
                    "thumbnail": game.thumbnail,
                }
            )

        return JsonResponse({"results": results, "count": len(results)})
