from django.contrib.auth.models import User
from django.test import TestCase

from accounts.media_paths import brand_logo_upload, property_gallery_upload, user_avatar_upload
from accounts.models import Brand, UserProfile


class MediaPathTests(TestCase):
    def test_brand_logo_path_uses_slug_and_id(self):
        brand = Brand(name='PropKeep', slug='propkeep', pk=3)
        path = brand_logo_upload(brand, 'Company Logo.png')
        self.assertTrue(path.startswith('propkeep/brand-3/logo/'))
        self.assertTrue(path.endswith('.png'))

    def test_user_avatar_path(self):
        brand = Brand(name='CheckPro', slug='checkpro-data', pk=2)
        user = User(pk=9, username='owner1')
        profile = UserProfile(user=user, brand=brand, pk=1)
        path = user_avatar_upload(profile, 'me.jpg')
        self.assertTrue(path.startswith('checkpro-data/user-9/avatar/'))
        self.assertIn('.jpg', path)

    def test_property_gallery_uses_property_account(self):
        from properties.models import Property, PropertyImage

        brand = Brand(name='PropKeep', slug='propkeep', pk=1)
        prop = Property(pk=55, brand=brand, title='Flat', owner_id=1)
        img = PropertyImage(property=prop, pk=10)
        path = property_gallery_upload(img, 'living-room.png')
        self.assertTrue(path.startswith('propkeep/property-55/gallery/'))
