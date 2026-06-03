from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group

@receiver(post_save, sender=User)
def asignar_rol_superusuario(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        grupo_admin, _ = Group.objects.get_or_create(name='Administrador')
        instance.groups.add(grupo_admin)