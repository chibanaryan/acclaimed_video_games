from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from django import forms
from django.urls import reverse

from . import constants, models


class ImportForm(forms.Form):
    type = forms.ChoiceField(choices=constants.TYPES, required=False)
    file = forms.FileField(required=False)
    delete = forms.BooleanField(required=False)


class SearchForm(forms.Form):
    start = forms.IntegerField(
        required=False,
        label='Start year'
    )
    end = forms.IntegerField(
        required=False,
        label='End year'
    )
    genre_option = forms.ChoiceField(
        required=False,
        choices=[
            (constants.SEARCH_ALL, 'All of'),
            (constants.SEARCH_ANY, 'Any of'),
            (constants.SEARCH_EXACTLY, 'Exactly'),
            (constants.SEARCH_NONE, 'None of'),
        ],
        initial='ANY', label='')
    genres = forms.ModelMultipleChoiceField(
        required=False,
        queryset=models.Genre.objects.all(),
        label='')
    platforms = forms.ModelMultipleChoiceField(
        required=False,
        queryset=models.Platform.objects.all(),
        label='')

    def __init__(self,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'GET'
        self.helper.form_action = reverse('games-search')
        reset_url = reverse('games-search')
        has_data = args and args[0]
        self.helper.layout = Layout(
            Div(
                Div('start', css_class="column"),
                Div('end', css_class="column"),
                Div(
                    HTML('<label class="label">Genres</label>'),
                    'genre_option',
                    'genres',
                    css_class="column"),
                Div(
                    HTML('<label class="label">Platforms</label>'),
                    'platforms',
                    css_class="column"),
                Div(
                    Submit('submit', 'Submit', css_class='button is-link'),
                    HTML(
                        f'<a href="{reset_url}" class="button">Reset</a>') if has_data else '',
                    css_class="column"),
                css_class="columns"
            )
        )
