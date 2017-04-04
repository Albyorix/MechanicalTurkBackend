from collections import namedtuple
from datetime import datetime, timedelta

from rest_framework import serializers
from django.db import transaction
from django.conf import settings

from servicematcher import models
from utils import get_logging


log = get_logging(__name__)
MATCH_BACKEND_VERSION = 2


class ServiceSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=200, default="", allow_blank=True)
    category = serializers.CharField(max_length=200, default="", allow_blank=True)
    elastic_service_id = serializers.CharField(max_length=200, required=False)
    elastic_index_element_id = serializers.CharField(max_length=200, required=False)
    waiting_2nd_match = serializers.BooleanField(required=False)
    last_fetch_date = serializers.DateTimeField(required=False)


class VenueSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=200)
    name = serializers.CharField(max_length=200, default="", allow_blank=True)
    category_id = serializers.CharField(max_length=5, default=1000)
    category_name = serializers.CharField(max_length=200, default="other", allow_blank=True)
    is_chain = serializers.IntegerField(default=-1, allow_null=True)


class FetchBusinessTypeSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=200, default="")


class InitialSearchSerializer(serializers.Serializer):
    country = serializers.CharField(max_length=200)
    level1 = serializers.CharField(max_length=200)
    level1_id = serializers.CharField(max_length=5)
    city = serializers.CharField(max_length=200)


class FetchServiceSerializer(serializers.Serializer):
    search_data = InitialSearchSerializer()
    batch_size = serializers.IntegerField(default=10)
    requested_at = serializers.IntegerField()

    def get_batch_unmatch_service(self, country, level1_id, user_id, size):
        """
        Return service in the process that are saved in SQL
        :param country: str,
        :param level1_id: str, "01000"
        :param user_id: int,
        :param size: int,
        :return: list
        """
        with transaction.atomic():
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            if settings.SERVICEMATCHER_IN_TEST_MODE:
                query_before = (datetime.utcnow() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                query_before = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

            matchs = models.Match.objects\
                .all()\
                .exclude(user__id=user_id)\
                .filter(service__search_country=country)\
                .filter(service__search_level1_id=level1_id)\
                .filter(service__waiting_2nd_match=True)\
                .filter(service__last_fetch_date__lte=query_before)

            matchs = matchs[:size]
            fetched_service_keys = [match.service.id for match in matchs]

            models.Service.objects\
                .filter(pk__in=fetched_service_keys)\
                .update(last_fetch_date=current_time)

        if not matchs:
            return []

        datas = [self.format_service_for_frontend_from_sql(match) for match in matchs]
        return datas

    def format_service_for_frontend_from_sql(self, match):
        """
        :param match: QuerySet, from SQL
        :return: dict, service payload for frontend
        """
        data = {
            "service": {
                "description": match.service.description,
                "category": match.service.category,
                "key": match.service.wh_key,
                "sql_id": match.service.id,
                "wizard": match.match_index.wizard,
            },
            "venue": {
                "key": match.service.venue.wh_key,
                "name": match.service.venue.name,
                "category_name": match.service.venue.category_name,
                "category_id": match.service.venue.category_id,
                "venue_country": match.service.search_country,
                "sql_id": match.service.venue.id,
            },
            "wizard": match.match_index.wizard,
            "origin": "sql",
        }
        return data


class SearchServiceSerializer(serializers.Serializer):
    range_size = serializers.IntegerField(default=10)
    skip = serializers.IntegerField(default=0)
    country = serializers.CharField(max_length=3, default="gb")
    search_string = serializers.CharField(max_length=200)
    level1 = serializers.CharField(max_length=200, default="All")


class MatchDataSerializer(serializers.Serializer):
    matched_index_element_id = serializers.CharField(max_length=30, default="")
    unmatched_index_element_ids = serializers.ListField(default=[])
    used_search = serializers.BooleanField(default=False)
    wizard = serializers.CharField(max_length=29, default="")
    not_enough_info = serializers.BooleanField(default=False)
    time_spent = serializers.CharField(max_length=200)
    search_string = serializers.CharField(max_length=200, default="")


class SubmitServiceSerializer(serializers.Serializer):
    service = ServiceSerializer()
    venue = VenueSerializer()
    country = serializers.CharField(max_length=3, default="gb")
    search_data = InitialSearchSerializer()
    match_data = MatchDataSerializer()

    def save_match_to_sql(self, venue_dict, service_dict, search_data_dict, match_data_dict, user):
        with transaction.atomic():
            log.info("START saving to sql")
            venue = get_or_create_venue(venue_dict)
            service, previous_match_wizard = get_or_create_service(venue, service_dict, search_data_dict)
            session = update_or_create_session(user)
            create_or_increment_smprofile(user)
            create_match(service, session, user, match_data_dict)
            log.info("STOP saving to sql")
        return previous_match_wizard


def get_or_create_venue(venue_dict):
    try:
        venue = models.Venue.objects.get(wh_key=venue_dict["key"])
    except models.Venue.DoesNotExist:
        venue = models.Venue.objects.create(
            wh_key=venue_dict["key"],
            category_id=venue_dict["category_id"],
            category_name=venue_dict["category_name"],
            name=venue_dict["name"],
            is_chain=venue_dict["is_chain"],
        )
    log.info("Saved the venue")
    return venue


def get_or_create_service(venue, service_dict, search_data):
    try:
        service = models.Service.objects.get(wh_key=service_dict["key"])
        service.waiting_2nd_match = False
        service.save()
        previous_match = service.match_set.all()[0]
        previous_match_wizard = previous_match.match_index.wizard
    except models.Service.DoesNotExist:
        service = models.Service.objects.create(
            venue=venue,
            description=service_dict["description"],
            category=service_dict["category"],
            wh_key=service_dict["key"],
            search_level1_id=search_data["level1_id"],
            search_level1=search_data["level1"],
            search_city=search_data["city"],
            search_country=search_data["country"],
            waiting_2nd_match=True,
            last_fetch_date="2011-11-11 11:11:11",
        )
        previous_match_wizard = None
    log.info("Saved the service")
    return service, previous_match_wizard


def update_or_create_session(user):
    try:
        one_hour_before = models.timezone.now() - models.timezone.timedelta(hours=1)
        session = models.SessionMetric.objects \
            .filter(user=user) \
            .filter(end_time__gt=one_hour_before)[0]
    except IndexError:
        session = models.SessionMetric.objects.create(user=user)
    session.set_end_time()
    log.info("Saved the session")
    return session


def create_or_increment_smprofile(user):
    try:
        profile = models.ServiceMatcherProfile.objects.get(user=user)
    except models.ServiceMatcherProfile.DoesNotExist:
        profile = models.ServiceMatcherProfile.objects.create(user=user)
    profile.increment()
    log.info("Saved the profile")


def create_match(service, session, user, match_data):
    not_enough_info = match_data["not_enough_info"]
    if not_enough_info:
        wizard = "00000_00000_00000_00000_00000"
        service.waiting_2nd_match=False
        service.save()
    else:
        wizard = match_data["wizard"]
    index_element = models.IndexElement.objects.filter(wizard=wizard).get()
    match = models.Match.objects.create(
        service=service,
        match_index=index_element,
        not_enough_info=match_data["not_enough_info"],
        used_search=match_data["used_search"],
        time_spent=match_data["time_spent"],
        session=session,
        user=user,
        match_backend_version=MATCH_BACKEND_VERSION,
        search_string=match_data["search_string"],
    )
    for wizard in match_data["unmatched_index_element_ids"]:
        index_element = models.IndexElement.objects.get(wizard=wizard)
        match.negative_index.add(index_element)
    match.save()
    log.info("Saved the match")
