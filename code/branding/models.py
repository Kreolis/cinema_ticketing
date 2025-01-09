from django.db import models

import os

# model for contact form emails
class Contact(models.Model):
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.firstname} {self.lastname}"
    

# model for logos and other branding images
class Branding(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to=os.path.join('branding', 'images'))
    favicon = models.ImageField(upload_to=os.path.join('branding', 'images'))
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    
    # make sure only one image is active at a time
    def save(self, *args, **kwargs):
        if self.is_active:
            Branding.objects.all().update(is_active=False)
        super(Branding, self).save(*args, **kwargs)

    # delete image files when object is deleted
    def delete(self, *args, **kwargs):
        self.logo.delete()
        self.favicon.delete()
        super(Branding, self).delete(*args, **kwargs)