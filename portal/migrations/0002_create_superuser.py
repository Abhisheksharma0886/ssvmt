from django.db import migrations

def create_superuser(apps, schema_editor):
    User = apps.get_model('portal', 'User')
    
    if not User.objects.filter(username='abhisheksharma0886').exists():
        # Precreate the root tech admin superuser account only
        User.objects.create_superuser(
            username='abhisheksharma0886',
            email='admin@ssvmt.org',
            password='AbhiAbhi#1234',
            first_name='Abhishek',
            last_name='Sharma'
        )

def remove_superuser(apps, schema_editor):
    User = apps.get_model('portal', 'User')
    User.objects.filter(username='abhisheksharma0886').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(create_superuser, reverse_code=remove_superuser),
    ]
