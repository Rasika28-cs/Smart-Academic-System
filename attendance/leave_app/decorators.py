# Authentication is now fully handled by Django's built-in @login_required.
# This file is kept for import compatibility but no longer contains
# custom session-based decorators.

from django.contrib.auth.decorators import login_required  # noqa: F401
