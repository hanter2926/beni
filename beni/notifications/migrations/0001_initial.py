import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=200)),
                ('title', models.CharField(max_length=160)),
                ('message', models.CharField(max_length=500)),
                ('destination_url', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', '-pk'),
            },
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(fields=('recipient', 'event_key'), name='notification_recipient_event_unique'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'read_at', 'created_at'], name='notification_inbox_idx'),
        ),
    ]
