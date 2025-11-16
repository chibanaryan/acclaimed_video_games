from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from unittest import mock

from games import constants


class ImportViewIntegrationTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client = Client()

    def test_requires_authentication(self):
        response = self.client.get(reverse("import"))
        self.assertEqual(response.status_code, 302)

    @mock.patch("games.views.utils.import_data", return_value=(True, "Done"))
    def test_success_message_on_successful_import(self, mock_import):
        self.client.login(username="tester", password="pass")
        fake_file = SimpleUploadedFile("data.txt", b"payload")
        response = self.client.post(
            reverse("import"),
            {
                "type": constants.TYPE_PLATFORM,
                "file": fake_file,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("import"))

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertEqual(messages[0].message, "Done")
        mock_import.assert_called_once()

    @mock.patch("games.views.utils.import_data", return_value=(False, "Error"))
    def test_error_message_when_import_fails(self, mock_import):
        self.client.login(username="tester", password="pass")
        fake_file = SimpleUploadedFile("data.txt", b"payload")
        response = self.client.post(
            reverse("import"),
            {
                "type": constants.TYPE_PLATFORM,
                "file": fake_file,
            },
        )

        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, "Error")
        mock_import.assert_called_once()
