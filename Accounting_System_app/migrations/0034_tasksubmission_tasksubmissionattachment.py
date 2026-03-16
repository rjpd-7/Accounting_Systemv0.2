from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0033_taskassignment_taskattachment'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_submissions', to=settings.AUTH_USER_MODEL)),
                ('task', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='submission', to='Accounting_System_app.taskassignment')),
            ],
            options={
                'db_table': 'task_submissions_table',
            },
        ),
        migrations.CreateModel(
            name='TaskSubmissionAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='task_submission_attachments/%Y/%m/%d/')),
                ('filename', models.CharField(max_length=255)),
                ('file_size', models.IntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='Accounting_System_app.tasksubmission')),
            ],
            options={
                'db_table': 'task_submission_attachments_table',
            },
        ),
    ]
