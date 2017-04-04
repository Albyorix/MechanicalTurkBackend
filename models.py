from django.db import models
from django.utils import timezone
from django.db.models import F

from backend.models.users import Profile


class ServiceMatcherProfile(models.Model):
    user = models.OneToOneField(Profile)
    general_counter = models.IntegerField(default=0)

    def increment(self):
        self.general_counter = F('general_counter') + 1
        self.save()


class IndexElement(models.Model):
    wizard = models.CharField(max_length=29, unique=True)
    level1_id = models.CharField(max_length=5)
    level1 = models.CharField(max_length=50)
    level2 = models.CharField(max_length=100)
    level3 = models.CharField(max_length=100)
    level4 = models.CharField(max_length=100)
    level5 = models.CharField(max_length=100)


class Venue(models.Model):
    name = models.CharField(max_length=100)
    category_name = models.CharField(max_length=100)
    category_id = models.CharField(max_length=4)
    wh_key = models.CharField(max_length=200, unique=True)
    is_chain = models.IntegerField(null=True)


class Service(models.Model):
    venue = models.ForeignKey(Venue)
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=200)
    wh_key = models.CharField(max_length=200, unique=True)
    search_level1_id = models.CharField(max_length=5)
    search_level1 = models.CharField(max_length=50)
    search_city = models.CharField(max_length=50)
    search_country = models.CharField(max_length=50)
    waiting_2nd_match = models.BooleanField(default=True)
    last_fetch_date = models.DateTimeField(default="2011-11-11 11:11:11")


class SessionMetric(models.Model):
    user = models.ForeignKey(Profile)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(auto_now_add=True)
    match_counter = models.IntegerField(default=0)

    def set_end_time(self):
        self.match_counter += 1
        self.end_time = timezone.now()
        self.save()


class Match(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.PROTECT)
    session = models.ForeignKey(SessionMetric, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    match_index = models.ForeignKey(IndexElement, on_delete=models.PROTECT)
    negative_index = models.ManyToManyField(IndexElement, related_name='negative_match')
    created_time = models.DateTimeField(auto_now_add=True)
    not_enough_info = models.BooleanField(default=False)
    used_search = models.BooleanField(default=False)
    search_string = models.CharField(blank=True, default="", max_length=200)
    time_spent = models.IntegerField()
    match_backend_version = models.IntegerField()

