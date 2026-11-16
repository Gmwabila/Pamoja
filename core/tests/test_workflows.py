from datetime import date, timedelta
from unittest.mock import patch
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import User, Profile, Task

class AccountWorkflowTests(TestCase):
    def test_signup_onboarding_and_personal_dashboard(self):
        response = self.client.post(reverse('signup'), {'first_name': 'Gloire', 'email': 'GLOIRE@example.com',
            'password1': 'MyFreshStart!9384', 'password2': 'MyFreshStart!9384'})
        self.assertRedirects(response, reverse('onboarding'))
        user = User.objects.get(email='gloire@example.com')
        self.assertTrue(user.check_password('MyFreshStart!9384'))
        response = self.client.post(reverse('onboarding'), {'spaces': ['planning', 'career', 'fitness'],
            'goal': 'Make time for coding', 'timezone': 'America/Chicago', 'reminders': 'on'})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertContains(response.client.get(reverse('dashboard')), 'Gloire')
        profile = user.profile
        self.assertTrue(profile.onboarded)
        self.assertEqual(profile.spaces, ['planning', 'career', 'fitness'])
        self.assertTrue(profile.reminders)

    def test_email_is_case_insensitive_for_signup_and_login(self):
        User.objects.create_user('person@example.com', 'MyFreshStart!9384')
        response = self.client.post(reverse('signup'), {'first_name': 'Other', 'email': 'PERSON@example.com',
            'password1': 'MyFreshStart!9384', 'password2': 'MyFreshStart!9384'})
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.count(), 1)
        self.assertRedirects(self.client.post(reverse('login'),
            {'username': 'PERSON@example.com', 'password': 'MyFreshStart!9384'}), reverse('dashboard'), fetch_redirect_response=False)

    def test_invalid_timezone_is_rejected(self):
        user = User.objects.create_user('person@example.com', 'MyFreshStart!9384')
        self.client.force_login(user)
        response = self.client.post(reverse('onboarding'), {'timezone': 'Moon/Crater', 'spaces': ['career']})
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(user.profile.onboarded)

    def test_guest_cannot_read_private_pages_or_mutate(self):
        for route in ['dashboard', 'planner', 'profile', 'chat', 'onboarding', 'task_add']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 302)

class TaskAndPrivacyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner@example.com', 'MyFreshStart!9384', first_name='Gloire')
        self.other = User.objects.create_user('other@example.com', 'MyFreshStart!9384')
        Profile.objects.create(user=self.owner, onboarded=True, timezone='America/Chicago',
                               spaces=['planning', 'career', 'fitness'], reminders=True)
        Profile.objects.create(user=self.other, onboarded=True)
        self.task = Task.objects.create(user=self.owner, title='Apply for a job', space='career',
                                       due_date=timezone.localdate(timezone=__import__('zoneinfo').ZoneInfo('America/Chicago')))
        self.other_task = Task.objects.create(user=self.other, title='PRIVATE OTHER USER TASK', due_date=self.task.due_date)
        self.client.force_login(self.owner)

    def test_task_create_edit_complete_delete(self):
        response = self.client.post(reverse('task_add'), {'title': 'Gym session', 'space': 'fitness',
            'due_date': self.task.due_date.isoformat(), 'due_time_0': '6', 'due_time_1': '00', 'due_time_2': 'PM', 'priority': 'normal'})
        self.assertRedirects(response, reverse('dashboard'))
        task = Task.objects.get(title='Gym session')
        self.assertEqual(task.user, self.owner)
        self.client.post(reverse('task_toggle', args=[task.pk]))
        task.refresh_from_db()
        self.assertTrue(task.completed)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['done'], 1)
        self.assertEqual(response.context['total'], 2)
        self.assertEqual(response.context['progress'], 50)
        self.client.post(reverse('task_edit', args=[task.pk]), {'title': 'Short gym session', 'space': 'fitness',
            'due_date': task.due_date.isoformat(), 'due_time_0': '6', 'due_time_1': '30', 'due_time_2': 'PM', 'priority': 'high'})
        task.refresh_from_db()
        self.assertEqual(task.title, 'Short gym session')
        self.client.post(reverse('task_delete', args=[task.pk]))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_edit_form_preserves_an_existing_future_due_date(self):
        self.task.due_date += timedelta(days=12)
        self.task.save()
        response = self.client.get(reverse('task_edit', args=[self.task.pk]))
        self.assertEqual(response.context['form']['due_date'].value(), self.task.due_date)

    def test_other_users_data_is_not_visible_or_mutable(self):
        for route in ['dashboard', 'planner']:
            self.assertNotContains(self.client.get(reverse(route)), self.other_task.title)
        for route in ['task_edit', 'task_toggle', 'task_delete']:
            response = self.client.post(reverse(route, args=[self.other_task.pk]), {'title': 'Changed'})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(reverse('task_edit', args=[self.other_task.pk])).status_code, 404)
        self.other_task.refresh_from_db()
        self.assertFalse(self.other_task.completed)
        self.assertEqual(self.other_task.title, 'PRIVATE OTHER USER TASK')

    def test_custom_order_is_saved_and_disabling_space_keeps_data(self):
        self.client.post(reverse('move_space', args=['fitness']), {'direction': 'up'})
        profile = Profile.objects.get(user=self.owner)
        self.assertEqual(profile.spaces, ['planning', 'fitness', 'career'])
        self.client.post(reverse('onboarding'), {'spaces': ['fitness'], 'timezone': 'America/Chicago'})
        profile.refresh_from_db()
        self.assertEqual(profile.spaces, ['fitness'])
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_csrf_protection_and_post_only_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('task_toggle', args=[self.task.pk])).status_code, 403)
        self.assertEqual(client.get(reverse('task_toggle', args=[self.task.pk])).status_code, 405)
        self.assertEqual(client.get(reverse('task_delete', args=[self.task.pk])).status_code, 405)

    def test_day_boundary_uses_profile_timezone_and_reminders(self):
        # 02:00 UTC on Nov 16 is still Nov 15 in Chicago.
        instant = timezone.datetime(2026, 11, 16, 2, 0, tzinfo=__import__('datetime').timezone.utc)
        Task.objects.create(user=self.owner, title='Older unfinished task', due_date=date(2026, 11, 14))
        with patch('core.views.timezone.now', return_value=instant):
            response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['today'], date(2026, 11, 15))
        self.assertGreaterEqual(response.context['overdue'], 1)
        self.assertContains(response, 'from earlier')

    def test_routes_render_and_user_text_is_escaped(self):
        self.task.title = '<script>alert(1)</script>'
        self.task.save()
        for route in ['welcome', 'dashboard', 'planner', 'profile', 'chat', 'onboarding', 'task_add']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200, route)
        response = self.client.get(reverse('planner'))
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
