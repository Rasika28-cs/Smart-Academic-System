from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('department', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Gallery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200)),
                ('image', models.ImageField(upload_to='gallery/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Gallery Image',
                'verbose_name_plural': 'Gallery Images',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NewsItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField()),
                ('date', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'News Item',
                'verbose_name_plural': 'News Items',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='UpcomingEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('date', models.DateField()),
                ('venue', models.CharField(blank=True, max_length=200)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Upcoming Event',
                'verbose_name_plural': 'Upcoming Events',
                'ordering': ['date'],
            },
        ),
    ]
