import csv
from io import TextIOWrapper

from django import forms


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace("-", " ").replace("_", " ")


class GoodreadsImportForm(forms.Form):
    """Form for importing a Goodreads library export CSV."""

    file = forms.FileField(
        required=True,
        label="Goodreads export (.csv)",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "file-input file-input-bordered w-full",
                "accept": ".csv,text/csv",
            }
        ),
        help_text=(
            "Export your library from Goodreads (My Books > Import/Export), "
            "then upload the CSV here."
        ),
    )

    def clean_file(self):
        file_obj = self.cleaned_data.get("file")
        if not file_obj:
            return file_obj

        file_obj.seek(0)
        wrapper = TextIOWrapper(file_obj, encoding="utf-8-sig")
        try:
            reader = csv.reader(wrapper)
            header = next(reader, None)
            if not header:
                raise forms.ValidationError("File is empty.")

            normalized = {_normalize_header(value) for value in header if value}
            if "book id" not in normalized:
                raise forms.ValidationError(
                    "Missing required 'Book Id' column. "
                    "Please upload the Goodreads library export CSV."
                )
        except forms.ValidationError:
            raise
        except Exception as exc:
            raise forms.ValidationError(f"Could not read file: {exc}")
        finally:
            try:
                wrapper.detach()
            except Exception:
                pass
            file_obj.seek(0)

        return file_obj
