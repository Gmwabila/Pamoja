# PAMOJA AI Chat 2.0: persisted, approval-only task proposals.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0016_profile_daily_planning_time")]

    operations = [
        migrations.CreateModel(
            name="AITaskProposal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("space", models.CharField(max_length=16, default="planning", choices=[
                    ("planning", "Daily Planning"), ("career", "Career & Jobs"),
                    ("fitness", "Fitness"), ("education", "Education"),
                    ("sports", "Sports"), ("finance", "Personal Finance"),
                    ("budgeting", "Savings & Budgeting"), ("business", "Business & Entrepreneurship"),
                    ("technology", "Technology & AI"), ("health", "Health & Wellness"),
                    ("wellbeing", "Mental Wellbeing"), ("faith", "Faith & Spirituality"),
                    ("family", "Family"), ("relationships", "Relationships"),
                    ("cooking", "Food & Cooking"), ("travel", "Travel"),
                    ("languages", "Languages"), ("reading", "Books & Reading"),
                    ("music", "Music"), ("creativity", "Art & Creativity"),
                    ("photography", "Photography"), ("community", "Community & Volunteering"),
                    ("lifestyle", "Home & Lifestyle"), ("productivity", "Productivity & Habits"),
                    ("growth", "Personal Growth"),
                ])),
                ("due_date", models.DateField()),
                ("due_time", models.TimeField(blank=True, null=True)),
                ("priority", models.CharField(max_length=8, default="normal", choices=[("normal", "Normal"), ("high", "High") ])),
                ("saved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="task_proposal", to="core.aimessage")),
                ("task", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.task")),
            ],
        ),
    ]
