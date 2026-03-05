# Generated migration for JournalAuditTrail model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Accounting_System_app', '0028_subject'),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalAuditTrail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(choices=[('created', 'Created'), ('updated', 'Updated'), ('deleted', 'Deleted')], default='updated', max_length=20)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('field_name', models.CharField(blank=True, max_length=100, null=True)),
                ('old_value', models.TextField(blank=True, null=True)),
                ('new_value', models.TextField(blank=True, null=True)),
                ('entry_id', models.IntegerField(blank=True, null=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('journal_header', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audit_trails', to='Accounting_System_app.journalheader')),
                ('journal_header_draft', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audit_trails', to='Accounting_System_app.journalheaderdrafts')),
            ],
            options={
                'db_table': 'journal_audit_trail',
                'ordering': ['-changed_at'],
            },
        ),
    ]
