# Generated by Django 5.1.6 on 2025-04-06 09:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solsub', '0002_cluster_api_key_alter_cluster_cluster_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='cluster',
            name='trial_period',
            field=models.IntegerField(default=0),
        ),
    ]
