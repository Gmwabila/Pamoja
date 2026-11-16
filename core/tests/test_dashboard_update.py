from datetime import date, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from core.forms import TaskForm
from core.models import Profile, Task, User
from core.time_fields import FriendlyTimeField


class TimeSelectorTests(SimpleTestCase):
    def test_noon_midnight_and_evening_conversion(self):
        field = FriendlyTimeField()
        for parts, expected in [(['12', '00', 'AM'], time(0)),
                                (['12', '00', 'PM'], time(12)),
                                (['6', '30', 'PM'], time(18, 30)),
                                (['11', '59', 'AM'], time(11, 59))]:
            with self.subTest(parts=parts):
                self.assertEqual(field.clean(parts), expected)

    def test_blank_time_is_optional_but_partial_and_invalid_times_are_rejected(self):
        field = FriendlyTimeField()
        self.assertIsNone(field.clean(['', '', '']))
        for parts in [['6', '', 'PM'], ['', '30', 'PM'], ['13', '00', 'AM'], ['6', '65', 'PM']]:
            with self.subTest(parts=parts), self.assertRaises(ValidationError):
                field.clean(parts)

    def test_existing_model_time_populates_all_three_controls(self):
        for value, selected in [(time(0, 5), ['12', '05', 'AM']), (time(12, 30), ['12', '30', 'PM']),
                                (time(18, 30), ['6', '30', 'PM'])]:
            widget = FriendlyTimeField().widget
            self.assertEqual(widget.decompress(value), selected)
        form = TaskForm(instance=Task(due_time=time(18, 30)))
        html = str(form['due_time'])
        self.assertNotIn('type="time"', html)
        for name in ['due_time_0', 'due_time_1', 'due_time_2']:
            self.assertIn('name="' + name + '"', html)
        self.assertIn('value="6" selected', html)
        self.assertIn('value="30" selected', html)
        self.assertIn('value="PM" selected', html)


class UpdatedDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('me@example.com', 'MyFreshStart!9384', first_name='Gloire')
        self.other = User.objects.create_user('someone@example.com', 'MyFreshStart!9384')
        Profile.objects.create(user=self.user, onboarded=True, timezone='America/Chicago')
        self.client.force_login(self.user)
        self.today = date(2026, 11, 15)
        self.now = patch('core.views.timezone.now', return_value=__import__('datetime').datetime(
            2026, 11, 16, 2, tzinfo=dt_timezone.utc))
        self.now.start()
        self.addCleanup(self.now.stop)

    def task(self, title, days, **kwargs):
        return Task.objects.create(user=kwargs.pop('user', self.user), title=title,
                                   due_date=self.today + timedelta(days=days), **kwargs)

    def test_upcoming_has_only_own_unfinished_future_tasks_in_next_week(self):
        self.task('Today complete', 0, completed=True)
        self.task('Today pending', 0)
        self.task('Overdue task', -1)
        first = self.task('Tomorrow reading', 1, due_time=time(18, 30))
        last = self.task('Seven days ahead', 7)
        self.task('Too far ahead', 8)
        self.task('Future already complete', 2, completed=True)
        self.task('PRIVATE OTHER UPCOMING', 1, user=self.other)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(list(response.context['upcoming_tasks']), [first, last])
        self.assertEqual(response.context['upcoming_count'], 2)
        self.assertEqual(response.context['done'], 1)
        self.assertEqual(response.context['total'], 2)
        self.assertEqual(response.context['progress'], 50)
        self.assertContains(response, 'Tomorrow reading')
        self.assertContains(response, 'Tomorrow')
        self.assertNotContains(response, 'PRIVATE OTHER UPCOMING')
        self.assertNotContains(response, 'Too far ahead')

    def test_upcoming_is_limited_to_five_ordered_tasks_and_counts_all(self):
        self.task('No time yet', 1)
        earlier = self.task('Morning first', 1, due_time=time(8))
        self.task('Afternoon second', 1, due_time=time(14))
        for day in range(2, 7):
            self.task('Later day ' + str(day), day)
        response = self.client.get(reverse('dashboard'))
        tasks = list(response.context['upcoming_tasks'])
        self.assertEqual(len(tasks), 5)
        self.assertEqual(tasks[0], earlier)
        self.assertEqual(response.context['upcoming_count'], 8)
        self.assertContains(response, 'See all 8 upcoming tasks')

    def test_dropdown_time_saves_round_trips_and_can_be_cleared(self):
        data = {'title': 'Reading', 'space': 'planning', 'due_date': '2026-11-16',
                'due_time_0': '6', 'due_time_1': '30', 'due_time_2': 'PM', 'priority': 'normal'}
        self.assertRedirects(self.client.post(reverse('task_add'), data), reverse('dashboard'))
        task = Task.objects.get(title='Reading')
        self.assertEqual(task.due_time, time(18, 30))
        response = self.client.get(reverse('task_edit', args=[task.pk]))
        self.assertContains(response, 'value="PM" selected')
        self.assertContains(response, 'value="30" selected')
        data.update(due_time_0='', due_time_1='', due_time_2='')
        self.client.post(reverse('task_edit', args=[task.pk]), data)
        task.refresh_from_db()
        self.assertIsNone(task.due_time)

    def test_partial_time_shows_server_error_and_preserves_other_inputs(self):
        response = self.client.post(reverse('task_add'), {'title': 'Keep this text', 'space': 'career',
            'due_date': '2026-11-16', 'due_time_0': '6', 'due_time_1': '', 'due_time_2': 'PM', 'priority': 'normal'})
        self.assertContains(response, 'Choose an hour, minute, and AM or PM')
        self.assertContains(response, 'Keep this text')
        self.assertEqual(Task.objects.count(), 0)

    def test_rescheduling_tomorrows_task_to_today_moves_it_into_daily_progress(self):
        task = self.task('Move to today', 1)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['total'], 0)
        self.assertEqual(response.context['upcoming_count'], 1)
        self.client.post(reverse('task_edit', args=[task.pk]), {'title': task.title, 'space': 'planning',
            'due_date': self.today.isoformat(), 'due_time_0': '', 'due_time_1': '', 'due_time_2': '',
            'priority': 'normal'})
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['total'], 1)
        self.assertEqual(response.context['upcoming_count'], 0)

    def test_brand_is_pamoja_on_all_pages_and_in_install_manifest(self):
        for route in ['welcome', 'dashboard', 'onboarding', 'profile', 'chat', 'planner', 'task_add']:
            response = self.client.get(reverse(route))
            self.assertNotContains(response, 'PAMOJA AI')
            self.assertNotContains(response, '<small>AI</small>')
            self.assertContains(response, '<span>PAMOJA</span>')
