# Generated migration to add account_groups field to UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0031_studentsection_teachers'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='account_groups',
            field=models.ManyToManyField(blank=True, related_name='assigned_users', to='Accounting_System_app.accountgroups'),
        ),
    ]
