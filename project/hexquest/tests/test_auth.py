from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

class LoginTests(TestCase):
    def test_login_page_status_code(self):
        response = self.client.get(reverse('hexquest:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hexquest/login_page.html')

    def test_login_functionality(self):
        user = User.objects.create_user(username='testuser', password='testpassword')
        response = self.client.post(reverse('hexquest:login'), {
            'username': 'testuser',
            'password': 'testpassword'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertRedirects(response, reverse('hexquest:home'))

    def test_logout_functionality(self):
        user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(reverse('hexquest:logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_login_from_registration_page(self):
        response = self.client.get(reverse('hexquest:register'))
        self.assertContains(response, reverse('hexquest:login'))
