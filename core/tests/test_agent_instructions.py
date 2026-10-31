"""`CLAUDE.md` has to stay a link to `AGENTS.md`.

`/code-review`'s conventions check reads only `CLAUDE.md` files, so deleting the
link stops the review checking the repo's rules, and a regular copy lets the
two drift. Nothing else would fail. A Windows clone without
`core.symlinks=true` fails here too: the link arrives as a text file.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ClaudeMdIsALinkTests(SimpleTestCase):
    def test_claude_md_links_to_agents_md(self):
        link = Path(settings.BASE_DIR) / "CLAUDE.md"
        self.assertTrue(link.is_symlink(), "CLAUDE.md must be a symlink")
        self.assertEqual(link.readlink(), Path("AGENTS.md"))
