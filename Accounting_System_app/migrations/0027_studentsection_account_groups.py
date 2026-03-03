from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0026_studentsection_userprofile_section'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentsection',
            name='account_groups',
            field=models.ManyToManyField(blank=True, related_name='sections', to='Accounting_System_app.accountgroups'),
        ),
    ]
