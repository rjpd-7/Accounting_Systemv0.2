from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting_System_app', '0025_journalcollaborator_journaldraftcollaborator'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'student_sections',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='userprofile',
            name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='Accounting_System_app.studentsection'),
        ),
    ]
