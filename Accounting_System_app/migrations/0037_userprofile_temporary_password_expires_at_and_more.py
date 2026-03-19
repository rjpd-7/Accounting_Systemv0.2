from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0036_alter_taskassignment_deadline'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='requires_password_change',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='temporary_password_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]