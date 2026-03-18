# Generated manually for task time fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_treasuretask_completion_proof'),
    ]

    operations = [
        migrations.AddField(
            model_name='treasuretask',
            name='publish_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='发布时间'),
        ),
        migrations.AddField(
            model_name='treasuretask',
            name='expire_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='过期时间'),
        ),
        migrations.AddField(
            model_name='treasuretask',
            name='penalty_days_applied',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
