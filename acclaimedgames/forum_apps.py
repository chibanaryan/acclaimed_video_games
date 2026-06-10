"""
django-machina AppConfig compatibility patch.

machina's apps predate Django's DEFAULT_AUTO_FIELD setting and ship
migrations built on AutoField primary keys. Without this patch, our
global BigAutoField default makes `makemigrations` try to write
AlterField migrations into machina's site-packages directory - files
that would be lost on every fresh install and break deploys.

We pin each machina AppConfig to AutoField by setting the attribute on
the config classes before Django populates the app registry (called
from settings.py). The INSTALLED_APPS entries must stay as plain
"machina.apps.*" strings because machina's dynamic class loader
(machina.core.loading) resolves apps by matching those module paths.
"""


def pin_machina_auto_fields():
    from machina.apps.forum.apps import ForumAppConfig
    from machina.apps.forum_conversation.apps import ForumConversationAppConfig
    from machina.apps.forum_conversation.forum_attachments.apps import (
        ForumAttachmentsAppConfig,
    )
    from machina.apps.forum_conversation.forum_polls.apps import ForumPollsAppConfig
    from machina.apps.forum_feeds.apps import ForumFeedsAppConfig
    from machina.apps.forum_member.apps import ForumMemberAppConfig
    from machina.apps.forum_moderation.apps import ForumModerationAppConfig
    from machina.apps.forum_permission.apps import ForumPermissionAppConfig
    from machina.apps.forum_search.apps import ForumSearchAppConfig
    from machina.apps.forum_tracking.apps import ForumTrackingAppConfig

    machina_configs = [
        ForumAppConfig,
        ForumConversationAppConfig,
        ForumAttachmentsAppConfig,
        ForumPollsAppConfig,
        ForumFeedsAppConfig,
        ForumMemberAppConfig,
        ForumModerationAppConfig,
        ForumPermissionAppConfig,
        ForumSearchAppConfig,
        ForumTrackingAppConfig,
    ]
    for config in machina_configs:
        config.default_auto_field = "django.db.models.AutoField"
