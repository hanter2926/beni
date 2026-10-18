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
            name='RepairBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_category', models.CharField(max_length=100)),
                ('problem_description', models.TextField()),
                ('service_address', models.TextField(max_length=500)),
                ('preferred_at', models.DateTimeField()),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('assigned', 'Assigned'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('in_progress', 'In progress'), ('completed', 'Completed')], default='requested', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_worker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_repair_bookings', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_bookings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', '-id'),
            },
        ),
        migrations.CreateModel(
            name='BookingAssignmentEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_repair_assignment_events', to=settings.AUTH_USER_MODEL)),
                ('assigned_worker', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_assignment_events', to=settings.AUTH_USER_MODEL)),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignment_events', to='bookings.repairbooking')),
                ('previous_worker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='previous_repair_assignment_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('created_at', 'pk'),
            },
        ),
        migrations.AddIndex(
            model_name='repairbooking',
            index=models.Index(fields=['customer', 'created_at'], name='booking_customer_created_idx'),
        ),
        migrations.AddIndex(
            model_name='repairbooking',
            index=models.Index(fields=['assigned_worker', 'status'], name='bookings_re_assigne_2d1b47_idx'),
        ),
        migrations.AddIndex(
            model_name='repairbooking',
            index=models.Index(fields=['status', 'preferred_at'], name='bookings_re_status_5eb4dc_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingassignmentevent',
            index=models.Index(fields=['booking', 'created_at'], name='booking_assign_history_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingassignmentevent',
            index=models.Index(fields=['assigned_worker', 'created_at'], name='booking_assign_worker_idx'),
        ),
    ]
