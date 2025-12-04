import csv
from io import TextIOWrapper

from django import forms

from . import constants


class ContactForm(forms.Form):
    """Form for users to contact the site administrators."""

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Your name",
            }
        ),
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "your.email@example.com (optional)",
            }
        ),
    )

    category = forms.ChoiceField(
        choices=constants.CONTACT_CATEGORIES,
        required=True,
        widget=forms.Select(
            attrs={
                "class": "select select-bordered w-full",
            }
        ),
    )

    message = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered w-full",
                "placeholder": "Tell us what's on your mind...",
                "rows": 6,
            }
        ),
    )

    # Honeypot field for spam protection (should remain empty)
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "style": "display:none;",
                "tabindex": "-1",
                "autocomplete": "off",
            }
        ),
    )

    def clean_website(self):
        """Honeypot validation - this field should always be empty."""
        honeypot = self.cleaned_data.get("website")
        if honeypot:
            raise forms.ValidationError(
                "Spam detected. Please try again or contact us directly."
            )
        return honeypot


class SubscribeForm(forms.Form):
    """Form for users to subscribe to post notifications."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "your.email@example.com",
            }
        ),
    )

    # Honeypot field for spam protection (should remain empty)
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "style": "display:none;",
                "tabindex": "-1",
                "autocomplete": "off",
            }
        ),
    )

    def clean_website(self):
        """Honeypot validation - this field should always be empty."""
        honeypot = self.cleaned_data.get("website")
        if honeypot:
            raise forms.ValidationError(
                "Spam detected. Please try again or contact us directly."
            )
        return honeypot


class ImportForm(forms.Form):
    """Form for batch importing game data files."""

    platforms_file = forms.FileField(
        required=False,
        label="Platforms (PlatformDB.txt)",
        help_text="Tab-separated file with platform codes and names",
    )
    lists_file = forms.FileField(
        required=False,
        label="Source Lists (SourceLists.txt)",
        help_text="Tab-separated file with critic lists and rankings",
    )
    games_file = forms.FileField(
        required=False,
        label="Games (Top1000.txt)",
        help_text="Tab-separated file with game data",
    )
    memberships_file = forms.FileField(
        required=False,
        label="Game Positions (GamePositions.txt)",
        help_text="Tab-separated file with game positions in lists",
    )
    delete = forms.BooleanField(
        required=False, label="Delete existing data before importing"
    )
    igdb = forms.BooleanField(
        required=False,
        label="Fetch IGDB data after import (cover art, descriptions, etc.)",
    )
    seed_test_data = forms.BooleanField(
        required=False,
        label=(
            "Load bundled test data "
            "(PlatformDB, SourceLists, Top1000, GamePositions)"
        ),
    )

    def _validate_tsv_file(self, file_obj, expected_columns):
        """
        Validate that a file is valid TSV format with expected column count.

        Args:
            file_obj: Django UploadedFile object
            expected_columns: int or tuple of ints for valid column counts

        Raises:
            forms.ValidationError: If file format is invalid
        """
        if not file_obj:
            return

        try:
            # Reset file pointer to beginning
            file_obj.seek(0)
            f = TextIOWrapper(file_obj, encoding="utf-8")

            # Read first line to check format
            rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
            first_row = next(rows, None)

            if not first_row:
                raise forms.ValidationError("File is empty.")

            # Validate column count
            if isinstance(expected_columns, int):
                expected_columns = (expected_columns,)

            if len(first_row) not in expected_columns:
                expected_str = (
                    f"exactly {expected_columns[0]}"
                    if len(expected_columns) == 1
                    else f"one of: {expected_columns}"
                )
                raise forms.ValidationError(
                    f"Invalid format: expected {expected_str} columns, "
                    f"got {len(first_row)}. Ensure the file is tab-separated "
                    f"and all columns are present."
                )

            # Detach wrapper to prevent it from closing the underlying file
            f.detach()

            # Reset file pointer for later processing
            file_obj.seek(0)

        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError(f"Could not read file: {e}")

    def clean_platforms_file(self):
        """Validate platforms file format."""
        file_obj = self.cleaned_data.get("platforms_file")
        if file_obj:
            self._validate_tsv_file(file_obj, 2)
        return file_obj

    def clean_lists_file(self):
        """Validate source lists file format."""
        file_obj = self.cleaned_data.get("lists_file")
        if file_obj:
            self._validate_tsv_file(file_obj, 5)
        return file_obj

    def clean_games_file(self):
        """Validate games file format."""
        file_obj = self.cleaned_data.get("games_file")
        if file_obj:
            self._validate_tsv_file(file_obj, 6)
        return file_obj

    def clean_memberships_file(self):
        """Validate game positions file format."""
        file_obj = self.cleaned_data.get("memberships_file")
        if file_obj:
            # Game positions have variable columns (pairs of listID:position)
            # Each row can have different numbers of columns (1-500+)
            # Only validate that the file is not empty
            try:
                file_obj.seek(0)
                f = TextIOWrapper(file_obj, encoding="utf-8")
                rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
                first_row = next(rows, None)

                if not first_row:
                    raise forms.ValidationError("File is empty.")

                if len(first_row) < 1:
                    raise forms.ValidationError("File has no columns.")

                # Detach wrapper to prevent it from closing the underlying file
                f.detach()

                # Reset file pointer for later processing
                file_obj.seek(0)
            except forms.ValidationError:
                raise
            except Exception as e:
                raise forms.ValidationError(f"Could not read file: {e}")

        return file_obj

    def clean(self):
        """Validate that at least one file is provided for batch imports."""
        cleaned_data = super().clean()

        # Special operations (delete/igdb/seed_test_data) don't require files
        if (
            cleaned_data.get("delete")
            or cleaned_data.get("igdb")
            or cleaned_data.get("seed_test_data")
        ):
            return cleaned_data

        files = [
            cleaned_data.get("platforms_file"),
            cleaned_data.get("lists_file"),
            cleaned_data.get("games_file"),
            cleaned_data.get("memberships_file"),
        ]

        if not any(files):
            raise forms.ValidationError("Please select at least one file to import.")

        return cleaned_data
