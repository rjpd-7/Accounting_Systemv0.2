from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0034_tasksubmission_tasksubmissionattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskassignment',
            name='batch_key',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
