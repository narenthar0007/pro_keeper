from django.db import migrations, models


def migrate_brands(apps, schema_editor):
    Brand = apps.get_model('accounts', 'Brand')
    # Existing theme row(s) become PropKeep if slug empty/default
    for brand in Brand.objects.all():
        if not getattr(brand, 'slug', None) or brand.slug in ('', 'default'):
            brand.slug = 'propkeep'
        if brand.name in ('Default', ''):
            brand.name = 'PropKeep'
        brand.tagline = brand.tagline or 'Property Management'
        brand.footer_text = brand.footer_text or 'PropKeep — rent, advance, and listings in one place.'
        brand.hostnames = brand.hostnames or 'localhost,127.0.0.1,testserver'
        brand.base_url = brand.base_url or 'http://127.0.0.1:8000'
        brand.is_default = True
        brand.is_active = True
        if not brand.header_color:
            brand.header_color = '#0f2744'
        brand.save()

    if not Brand.objects.filter(slug='propkeep').exists():
        Brand.objects.create(
            name='PropKeep',
            slug='propkeep',
            tagline='Property Management',
            footer_text='PropKeep — rent, advance, and listings in one place.',
            hostnames='localhost,127.0.0.1,testserver',
            base_url='http://127.0.0.1:8000',
            is_default=True,
            is_active=True,
        )
    else:
        Brand.objects.filter(slug='propkeep').update(is_default=True)

    Brand.objects.filter(is_default=True).exclude(slug='propkeep').update(is_default=False)

    if not Brand.objects.filter(slug='checkpro-data').exists():
        Brand.objects.create(
            name='CheckPro Data',
            slug='checkpro-data',
            tagline='Property Intelligence',
            footer_text='CheckPro Data — verify, track, and report property performance.',
            hostnames='checkpro.localhost,checkpro.local',
            base_url='http://checkpro.localhost:8000',
            is_default=False,
            is_active=True,
            primary_color='#0f766e',
            secondary_color='#134e4a',
            button_color='#0d9488',
            button_text_color='#ffffff',
            background_color='#f0fdfa',
            surface_color='#ffffff',
            text_color='#134e4a',
            header_color='#042f2e',
            header_text_color='#ccfbf1',
            header_active_color='#2dd4bf',
            footer_bg_color='#042f2e',
            footer_text_color='#99f6e4',
            font_style='inter_system',
            table_format='striped',
            border_radius='sharp',
        )


def apply_brand_slug_unique(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS accounts_brand_slug_key '
            'ON accounts_brand (slug)'
        )
        schema_editor.execute(
            'CREATE INDEX IF NOT EXISTS accounts_brand_slug_21841905_like '
            'ON accounts_brand (slug varchar_pattern_ops)'
        )
    else:
        schema_editor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS accounts_brand_slug_key '
            'ON accounts_brand (slug)'
        )


def reverse_brand_slug_unique(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP INDEX IF EXISTS accounts_brand_slug_21841905_like')
    schema_editor.execute('DROP INDEX IF EXISTS accounts_brand_slug_key')


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_sitetheme_roleprivilege_userprofile'),
    ]

    operations = [
        migrations.RenameModel(old_name='SiteTheme', new_name='Brand'),
        migrations.AlterModelOptions(
            name='brand',
            options={'ordering': ['-is_default', 'name'], 'verbose_name': 'Brand'},
        ),
        migrations.AddField(
            model_name='brand',
            name='slug',
            # CharField first: SlugField on Postgres can create a _like index
            # before we add the unique constraint (duplicate index error).
            field=models.CharField(default='propkeep', max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='brand',
            name='tagline',
            field=models.CharField(blank=True, default='Property Management', max_length=120),
        ),
        migrations.AddField(
            model_name='brand',
            name='footer_text',
            field=models.CharField(
                blank=True,
                default='PropKeep — rent, advance, and listings in one place.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='brand',
            name='hostnames',
            field=models.CharField(
                blank=True,
                default='localhost,127.0.0.1',
                help_text='Comma-separated hosts that activate this brand (e.g. checkpro.localhost)',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='brand',
            name='base_url',
            field=models.CharField(
                blank=True,
                default='http://127.0.0.1:8000',
                help_text='Public base URL shown for this brand',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='brand',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='brand',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='brand',
            name='header_color',
            field=models.CharField(default='#0f2744', max_length=20),
        ),
        migrations.AddField(
            model_name='brand',
            name='header_text_color',
            field=models.CharField(default='#e8eef7', max_length=20),
        ),
        migrations.AddField(
            model_name='brand',
            name='header_active_color',
            field=models.CharField(default='#12b886', max_length=20),
        ),
        migrations.AddField(
            model_name='brand',
            name='footer_bg_color',
            field=models.CharField(default='#ffffff', max_length=20),
        ),
        migrations.AddField(
            model_name='brand',
            name='footer_text_color',
            field=models.CharField(default='#6b7280', max_length=20),
        ),
        migrations.AlterField(
            model_name='brand',
            name='name',
            field=models.CharField(default='PropKeep', help_text='Brand display name', max_length=80),
        ),
        migrations.RunPython(migrate_brands, migrations.RunPython.noop),
        # Avoid Django/Postgres double-creating the varchar_pattern_ops
        # "_like" index when flipping SlugField unique=False -> unique=True.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='brand',
                    name='slug',
                    field=models.SlugField(default='propkeep', max_length=80, unique=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    apply_brand_slug_unique,
                    reverse_brand_slug_unique,
                ),
            ],
        ),
    ]
