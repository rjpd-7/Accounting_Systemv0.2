from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0035_taskassignment_batch_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskassignment',
            name='deadline',
            field=models.DateTimeField(),
        ),
    ]
