"""The sign-in modal's HTMX partials, which call allauth's forms directly."""

import logging
from urllib.parse import urlparse

from allauth.core import ratelimit
from django.db import transaction
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from core.models import User
from games import models
from games.services import playtime
from games.services.percentile_service import calculate_percentile
from music.services.listening_stats import listening_stats

logger = logging.getLogger(__name__)


def _referer_redirect_url(request):
    """Where to send someone after logging in or out: back where they were.

    Only a page on this site counts - the Referer is the client's to set, so
    redirecting to it unchecked is an open redirect - and never back to an
    auth page.
    """
    redirect_url = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(
        redirect_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return "/"
    if urlparse(redirect_url).path.startswith(("/auth/", "/accounts/")):
        return "/"
    return redirect_url


def _rate_limited_form(request, template_name, form, **context):
    """Re-render an auth form with allauth's rate-limit message.

    A 429 would be the natural answer, but HTMX does not swap a 4xx, so the
    modal would sit there looking as if nothing happened.
    """
    from allauth.account.adapter import get_adapter

    form.is_valid()  # populate errors so add_error has somewhere to go
    form.add_error(None, get_adapter().error_messages["rate_limited"])
    response = TemplateResponse(request, template_name, {"form": form, **context})
    response["HX-Push-Url"] = "false"
    return response


def _send_confirmation(request, email_address, *, signup):
    """Send a verification email unless this address was sent one recently.

    The modal views call ``send_confirmation`` themselves, which skips the
    ``confirm_email`` cooldown allauth's own views apply (one email per
    address per three minutes), so the resend button could mail an address
    as fast as it was pressed. Skipping silently is allauth's own behaviour:
    the link in the email already sent still works.
    """
    if ratelimit.consume(
        request, action="confirm_email", key=email_address.email.lower()
    ):
        email_address.send_confirmation(request, signup=signup)


class AuthModalLoginView(View):
    """Handle email login form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_login_form.html"

    def get(self, request):
        from allauth.account.forms import LoginForm

        form = LoginForm(request=request)
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import LoginForm
        from allauth.account.models import EmailAddress
        from django.contrib.auth import login

        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.user

            # Check if email is verified (mandatory verification)
            # Look for user's email in EmailAddress table
            email_address = EmailAddress.objects.filter(
                user=user, email__iexact=user.email
            ).first()

            # If no EmailAddress record or not verified, block login
            if not email_address or not email_address.verified:
                # User exists but email not verified - show resend option
                response = TemplateResponse(
                    request,
                    "auth/partials/_unverified_email.html",
                    {"email": user.email},
                )
                response["HX-Push-Url"] = "false"
                return response

            # Email verified - proceed with login
            login(
                request,
                user,
                backend="allauth.account.auth_backends.AuthenticationBackend",
            )
            response = HttpResponse()
            response["HX-Redirect"] = _referer_redirect_url(request)
            return response

        # Re-render form with errors
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response


class AuthModalSignupView(View):
    """Handle email signup form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_signup_form.html"

    def get(self, request):
        from allauth.account.forms import SignupForm

        form = SignupForm()
        # Hide back button when accessed directly (not from auth options)
        show_back = request.GET.get("direct") != "1"
        response = TemplateResponse(
            request, self.template_name, {"form": form, "show_back": show_back}
        )
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import SignupForm
        from allauth.account.models import EmailAddress

        if not ratelimit.consume(request, action="signup"):
            return _rate_limited_form(
                request,
                self.template_name,
                SignupForm(request.POST),
                username_value=request.POST.get("username", "").strip(),
            )

        form = SignupForm(request.POST)
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        username_error = None

        # Validate username if provided (skip if it matches email - that's the default)
        if username and username.lower() != email.lower():
            if len(username) < 3:
                username_error = "Username must be at least 3 characters."
            elif len(username) > 30:
                username_error = "Username must be 30 characters or fewer."
            elif not username.replace("_", "").replace("-", "").isalnum():
                username_error = (
                    "Username can only contain letters, numbers, "
                    "underscores, and hyphens."
                )
            elif User.username_claimed(username):
                username_error = "This username is already taken."

        if form.is_valid() and not username_error:
            # Reclaim the username/email from any abandoned, never-verified
            # account before creating the new one, then create the user
            # (and EmailAddress) atomically so the unique constraint holds.
            with transaction.atomic():
                User.reclaim_username(username or email)
                user = form.save(request)

            # Set email subscription preference from checkbox
            email_subscribed = request.POST.get("email_subscribed") == "on"
            if email_subscribed:
                user.email_subscribed = True
                user.date_subscribed = timezone.now()
                user.generate_unsubscribe_token()
                user.save()

            # Send verification email (form.save doesn't do this automatically)
            email_address = EmailAddress.objects.filter(
                user=user, email__iexact=user.email
            ).first()
            if email_address and not email_address.verified:
                _send_confirmation(request, email_address, signup=True)

            # Don't log in - show verification screen instead
            response = TemplateResponse(
                request,
                "auth/partials/_verification_sent.html",
                {"email": user.email},
            )
            response["HX-Push-Url"] = "false"
            return response

        # Check if email already exists with unverified account
        email = request.POST.get("email", "").strip()
        if email and form.errors.get("email"):
            existing_email = EmailAddress.objects.filter(email__iexact=email).first()
            if existing_email and not existing_email.verified:
                # Show resend verification option instead of error
                response = TemplateResponse(
                    request,
                    "auth/partials/_unverified_email.html",
                    {"email": existing_email.email},
                )
                response["HX-Push-Url"] = "false"
                return response

        # Re-render form with errors
        response = TemplateResponse(
            request,
            self.template_name,
            {
                "form": form,
                "username_error": username_error,
                "username_value": username,
            },
        )
        response["HX-Push-Url"] = "false"
        return response


class AuthModalForgotPasswordView(View):
    """Handle forgot password form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_forgot_password_form.html"

    def get(self, request):
        from allauth.account.forms import ResetPasswordForm

        form = ResetPasswordForm()
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import ResetPasswordForm

        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            if not ratelimit.consume(
                request,
                action="reset_password",
                key=form.cleaned_data["email"].lower(),
            ):
                return _rate_limited_form(request, self.template_name, form)
            form.save(request)
            # Show success message
            response = TemplateResponse(
                request, "auth/partials/_forgot_password_sent.html", {}
            )
            response["HX-Push-Url"] = "false"
            return response

        # Re-render form with errors
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response


class AuthModalResendVerificationView(View):
    """Handle resending verification email from the auth modal."""

    def post(self, request):
        from allauth.account.models import EmailAddress

        email = request.POST.get("email", "").strip()

        if email:
            try:
                email_address = EmailAddress.objects.get(email__iexact=email)
                if not email_address.verified:
                    _send_confirmation(request, email_address, signup=False)
            except EmailAddress.DoesNotExist:
                pass  # Don't reveal if email exists

        # Always show success (prevents email enumeration)
        response = TemplateResponse(
            request,
            "auth/partials/_verification_resent.html",
            {"email": email},
        )
        response["HX-Push-Url"] = "false"
        return response


class EmailConfirmationView(TemplateView):
    """Custom email confirmation page matching the site style."""

    template_name = "account/email_confirmed.html"

    def get(self, request, key):
        """Process email confirmation key."""
        from allauth.account.models import EmailConfirmationHMAC
        from django.contrib.auth import login

        try:
            # Validate the confirmation key
            email_confirmation = EmailConfirmationHMAC.from_key(key)
            # from_key() finds only unverified addresses, so a link works
            # once. confirm() returns None when the address cannot be
            # verified - another account has verified it, say - and then
            # nobody is logged in.
            if email_confirmation and email_confirmation.confirm(request):
                email_address = email_confirmation.email_address

                # Log the user in (matches ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION)
                user = email_address.user
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                return self.render_to_response(
                    {
                        "success": True,
                        "email": email_address.email,
                    }
                )
        except Exception:
            logger.exception("Email confirmation failed")

        # Invalid or expired key
        return self.render_to_response({"success": False})


def _profile_stats(user):
    """The Account modal's stats, games' and music's."""
    # Only count non-orphaned games
    played_count = user.played_games.filter(game__isnull=False).count()
    want_to_play_count = user.want_to_play_games.filter(game__isnull=False).count()
    return {
        "profile": user,
        "played_count": played_count,
        "want_to_play_count": want_to_play_count,
        "backlog_playtime": playtime.backlog_hours(user, want_to_play_count),
        "total_games": models.Game.objects.count(),
        "percentile_message": calculate_percentile(played_count)["message"],
        "music_stats": listening_stats(user),
    }


@method_decorator(never_cache, name="get")
class AuthModalProfileView(View):
    """Handle profile editing form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_profile_form.html"

    def get(self, request):
        if not request.user.is_authenticated:
            # Redirect to login form via HTMX
            response = HttpResponse()
            response["HX-Redirect"] = reverse("auth-modal-login")
            return response

        response = TemplateResponse(
            request,
            self.template_name,
            {"form": {}, **_profile_stats(request.user)},
        )
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        if not request.user.is_authenticated:
            response = HttpResponse()
            response["HX-Redirect"] = "/"
            return response

        user = request.user
        new_username = request.POST.get("username", "").strip()

        # Validate username (if changed, skip validation if it matches user's email)
        username_error = None
        if (
            new_username
            and new_username != user.username
            and new_username.lower() != user.email.lower()
        ):
            if len(new_username) < 3:
                username_error = "Username must be at least 3 characters."
            elif len(new_username) > 30:
                username_error = "Username must be 30 characters or fewer."
            elif not new_username.replace("_", "").replace("-", "").isalnum():
                username_error = (
                    "Username can only contain letters, numbers, "
                    "underscores, and hyphens."
                )
            elif User.username_claimed(new_username, exclude_pk=user.pk):
                username_error = "This username is already taken."

            if username_error:
                # Re-render with full context including stats
                return render(
                    request,
                    self.template_name,
                    {
                        "form": {"username": {"errors": [username_error]}},
                        **_profile_stats(user),
                    },
                )
            # Free the name from any abandoned, never-verified account first.
            User.reclaim_username(new_username)
            user.username = new_username

        email_subscribed = request.POST.get("email_subscribed") == "on"

        if email_subscribed and not user.email_subscribed:
            # Subscribing - logged in user already has verified email
            user.email_subscribed = True
            user.generate_unsubscribe_token()
            if not user.date_subscribed:
                from django.utils import timezone

                user.date_subscribed = timezone.now()
        elif not email_subscribed:
            user.email_subscribed = False

        user.save()

        # Refresh page to show updated name in sidebar
        response = HttpResponse()
        response["HX-Refresh"] = "true"
        return response


class AuthLogoutView(View):
    """Handle logout and redirect back to previous page."""

    def post(self, request):
        from django.contrib.auth import logout

        logout(request)
        return redirect(_referer_redirect_url(request))
