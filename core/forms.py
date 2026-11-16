from zoneinfo import available_timezones
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Profile, Task, SPACES
from .time_fields import FriendlyTimeField

class SignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label='What should we call you?')
    class Meta:
        model = User
        fields = ['first_name', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists. Try logging in.')
        return email

class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email')

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

class PreferencesForm(forms.ModelForm):
    spaces = forms.MultipleChoiceField(choices=SPACES, widget=forms.CheckboxSelectMultiple, required=False)
    timezone = forms.ChoiceField(choices=[(z, z.replace('_', ' ')) for z in sorted(available_timezones())])
    class Meta:
        model = Profile
        fields = ['spaces', 'goal', 'timezone', 'reminders']
        widgets = {'goal': forms.Textarea(attrs={'rows': 2, 'placeholder': 'One thing you would like to make time for…'})}

    def clean_spaces(self):
        selected = self.cleaned_data['spaces']
        previous = self.instance.spaces or []
        return [s for s in previous if s in selected] + [s for s in selected if s not in previous]

class TaskForm(forms.ModelForm):
    due_time = FriendlyTimeField(label='Due time')

    class Meta:
        model = Task
        fields = ['title', 'space', 'due_date', 'due_time', 'priority']
        widgets = {'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
                   'title': forms.TextInput(attrs={'placeholder': 'What would you like to get done?'})}
