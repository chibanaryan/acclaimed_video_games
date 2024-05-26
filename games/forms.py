from django import forms

from . import constants


class ImportForm(forms.Form):
    type = forms.ChoiceField(choices=constants.TYPES, required=False)
    file = forms.FileField(required=False)
    delete = forms.BooleanField(required=False)
