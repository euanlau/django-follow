from django.contrib.auth.models import User, AnonymousUser
from django.db import models
from django.db.models.signals import post_save, post_delete
from follow.registry import model_map
from follow.signals import followed, unfollowed
import inspect

class FollowManager(models.Manager):
    def fname(self, model_or_obj):
        cls = model_or_obj if inspect.isclass(model_or_obj) else model_or_obj.__class__
        _, fname = model_map[cls]
        return fname
    
    def create(self, user, obj, **kwargs):
        """
        Create a new follow link between a user and an object
        of a registered model type.
        
        """
        follow = Follow(user=user)
        follow.target = obj
        follow.save()
        return follow
            
    def get_or_create(self, user, obj, **kwargs):
        """ 
        Almost the same as `FollowManager.objects.create` - behaves the same 
        as the normal `get_or_create` methods in django though. 

        Returns a tuple with the `Follow` and either `True` or `False`

        """
        if not self.is_following(user, obj):
            return self.create(user, obj, **kwargs), True
        return self.get_follows(obj).get(user=user), False
    
    def is_following(self, user, obj):
        """ Returns `True` or `False` """
        if isinstance(user, AnonymousUser):
            return False        
        return 0 < self.get_follows(obj).filter(user=user).count()

    def get_follows(self, model_or_object):
        """
        Returns all the followers of a model or object
        """
        fname = self.fname(model_or_object)
        if inspect.isclass(model_or_object):
            return self.exclude(**{fname:None})
        return self.filter(**{fname:model_or_object})
    
class Follow(models.Model):
    """
    This model allows a user to follow any kind of object. The followed
    object is accessible through `Follow.target`.
    """
    user = models.ForeignKey(User, related_name='following')

    datetime = models.DateTimeField(auto_now_add=True)

    objects = FollowManager()

    def __unicode__(self):
        return '%s' % self.target

    def _get_target(self):
        for _, fname in model_map.values():
            if hasattr(self, fname) and getattr(self, fname):
                return getattr(self, fname)
    
    def _set_target(self, obj):
        for _, fname in model_map.values():
            setattr(self, fname, None)
        if obj is None:
            return
        _, fname = model_map[obj.__class__]
        setattr(self, fname, obj)
        
    target = property(fget=_get_target, fset=_set_target)

def follow_dispatch(sender, instance, created=False, **kwargs):
    if created:
        followed.send(instance.target.__class__, user=instance.user, target=instance.target, instance=instance)

def unfollow_dispatch(sender, instance, **kwargs):
    unfollowed.send(instance.target.__class__, user=instance.user, target=instance.target, instance=instance)
    
    
post_save.connect(follow_dispatch, dispatch_uid='follow.follow_dispatch', sender=Follow)
post_delete.connect(unfollow_dispatch, dispatch_uid='follow.unfollow_dispatch', sender=Follow)
