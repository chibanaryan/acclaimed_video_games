"""
Developer hierarchy caching service.

Precomputes and caches developer hierarchy data to avoid expensive recursive
queries on the developers page. The cache is invalidated when Developer or
Game.developers relationships change.
"""

from collections import defaultdict
from typing import Any, Dict, Optional, Set

from django.core.cache import cache

from games import config


# Cache key for developer hierarchy data
DEVELOPER_HIERARCHY_CACHE_KEY = f"{config.CACHE_VERSION}:developer_hierarchy"


def get_developer_hierarchy() -> Dict[str, Any]:
    """
    Get cached developer hierarchy data.

    Returns a dictionary containing precomputed hierarchy information:
    - subsidiary_ids: {dev_id: set of all descendant ids}
    - root_developer_id: {dev_id: root developer id}
    - games_by_dev: {dev_id: set of direct game ids}
    - recursive_game_counts: {dev_id: count of games including subsidiaries}
    - recursive_game_ids: {dev_id: set of game ids including subsidiaries}
    - recursive_subsidiary_counts: {dev_id: count of all nested subsidiaries}
    - top_game_id: {dev_id: id of best ranked game across subsidiaries}

    The data is cached for 24 hours and invalidated via signals when
    Developer or Game.developers relationships change.
    """
    cached = cache.get(DEVELOPER_HIERARCHY_CACHE_KEY)
    if cached is not None:
        return cached

    data = _compute_hierarchy()
    cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, data, config.CACHE_TIMEOUT_24_HOURS)
    return data


def invalidate_developer_cache() -> None:
    """
    Invalidate the developer hierarchy cache.

    Call this after Developer save/delete or Game.developers M2M changes.
    """
    cache.delete(DEVELOPER_HIERARCHY_CACHE_KEY)


def _compute_hierarchy() -> Dict[str, Any]:
    """
    Compute full hierarchy with minimal database queries.

    This builds all hierarchy data in a single pass using bulk queries,
    avoiding the recursive N+1 pattern of the original implementation.
    """
    from games.models import Developer, Game

    # Query 1: Fetch all developers with parent relationships
    developers = list(Developer.objects.values("id", "parent_id", "name", "slug"))

    # Query 2: Fetch all developer-game relationships
    dev_game_links = list(
        Developer.objects.filter(developed_games__isnull=False).values_list(
            "id", "developed_games__id"
        )
    )

    # Query 3: Fetch game ranks for top game calculation
    game_ranks = dict(Game.objects.filter(rank__isnull=False).values_list("id", "rank"))

    # Build lookup structures
    dev_by_id = {d["id"]: d for d in developers}
    children_by_parent: Dict[int, Set[int]] = defaultdict(set)
    games_by_dev: Dict[int, Set[int]] = defaultdict(set)

    for dev in developers:
        if dev["parent_id"]:
            children_by_parent[dev["parent_id"]].add(dev["id"])

    for dev_id, game_id in dev_game_links:
        if game_id is not None:
            games_by_dev[dev_id].add(game_id)

    # Compute root developer for each developer (walking up the tree)
    root_developer_id: Dict[int, int] = {}
    for dev in developers:
        root_developer_id[dev["id"]] = _find_root(dev["id"], dev_by_id)

    # Compute all subsidiary IDs for each developer (walking down the tree)
    subsidiary_ids: Dict[int, Set[int]] = {}
    for dev in developers:
        subsidiary_ids[dev["id"]] = _collect_all_descendants(
            dev["id"], children_by_parent
        )

    # Compute recursive game counts and IDs
    recursive_game_ids: Dict[int, Set[int]] = {}
    recursive_game_counts: Dict[int, int] = {}

    for dev in developers:
        dev_id = dev["id"]
        # Collect games from this dev and all subsidiaries
        all_game_ids = set(games_by_dev.get(dev_id, set()))
        for sub_id in subsidiary_ids[dev_id]:
            all_game_ids.update(games_by_dev.get(sub_id, set()))

        recursive_game_ids[dev_id] = all_game_ids
        recursive_game_counts[dev_id] = len(all_game_ids)

    # Compute recursive subsidiary counts
    recursive_subsidiary_counts: Dict[int, int] = {
        dev["id"]: len(subsidiary_ids[dev["id"]]) for dev in developers
    }

    # Compute top game ID (best ranked) for each developer
    top_game_id: Dict[int, Optional[int]] = {}
    for dev in developers:
        dev_id = dev["id"]
        game_ids = recursive_game_ids.get(dev_id, set())
        if game_ids:
            # Find the game with the best (lowest) rank
            best_game_id = None
            best_rank = float("inf")
            for gid in game_ids:
                rank = game_ranks.get(gid)
                if rank is not None and rank < best_rank:
                    best_rank = rank
                    best_game_id = gid
            top_game_id[dev_id] = best_game_id
        else:
            top_game_id[dev_id] = None

    return {
        "subsidiary_ids": subsidiary_ids,
        "root_developer_id": root_developer_id,
        "games_by_dev": games_by_dev,
        "recursive_game_counts": recursive_game_counts,
        "recursive_game_ids": recursive_game_ids,
        "recursive_subsidiary_counts": recursive_subsidiary_counts,
        "top_game_id": top_game_id,
    }


def _find_root(dev_id: int, dev_by_id: Dict[int, Dict]) -> int:
    """Find the root developer ID by walking up the parent chain."""
    visited = set()
    current_id = dev_id

    while True:
        if current_id in visited:
            # Circular reference, return current
            break
        visited.add(current_id)

        dev = dev_by_id.get(current_id)
        if not dev or not dev["parent_id"]:
            break
        current_id = dev["parent_id"]

    return current_id


def _collect_all_descendants(
    dev_id: int, children_by_parent: Dict[int, Set[int]]
) -> Set[int]:
    """Collect all descendant IDs recursively."""
    descendants = set()
    to_visit = list(children_by_parent.get(dev_id, set()))

    while to_visit:
        child_id = to_visit.pop()
        if child_id not in descendants:
            descendants.add(child_id)
            to_visit.extend(children_by_parent.get(child_id, set()))

    return descendants
