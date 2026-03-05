# Generated migration to add teachers field to StudentSection

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Accounting_System_app', '0030_delete_subject'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentsection',
            name='teachers',
            field=models.ManyToManyField(blank=True, related_name='managed_sections', to=settings.AUTH_USER_MODEL),
        ),
    ]
