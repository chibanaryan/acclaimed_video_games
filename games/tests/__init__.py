import logging

# Silence games.models logger noise (e.g., ranking warnings) during tests
logger = logging.getLogger("games.models")
logger.addHandler(logging.NullHandler())
logger.propagate = False
