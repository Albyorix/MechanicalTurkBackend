from __future__ import unicode_literals
import json
from unidecode import unidecode

from rest_framework.response import Response
from django.conf import settings
import requests

from backend.models import get_token
from servicematcher.utils import get_logging, get_wizard_for_wh
from servicematcher.mappings import id_to_industry, level1_to_warehouse_category_id

log = get_logging(__name__)


def format_service_for_frontend_from_warehouse_data(data_from_wh, country):
    """
    :param data_from_wh: dict, from warehouse
    :param country: str,
    :return: dict, service for frontend
    """
    venue_category = data_from_wh.get('venue_category', "")
    venue_category_id = data_from_wh.get('venue_category_id')
    if not venue_category_id:
        venue_category_id = "other"
        venue_category = "1000"
    if not venue_category:
        if country == "en":
            venue_category = id_to_industry[venue_category_id]
        else:
            venue_category = ""
    data = {
        "service": {
            "description": unidecode(data_from_wh.get("description", "")),
            "category": unidecode(data_from_wh.get("category", "")),
            "key": data_from_wh["key"],
        },
        "venue": {
            "category_name": unidecode(venue_category),
            "category_id": venue_category_id,
            "name": unidecode(data_from_wh.get("venue_name", "")),
            "key": data_from_wh["subdomain"],
        },
        "origin": "warehouse",
    }
    return data


class WarehouseServiceMatcherAPI:

    def __init__(self):
        pass

    def submit_to_warehouse(self, not_enough_info, service_key, venue_key, wizard, venue_category_id, user, previous_match_wizard):
        if not_enough_info:
            # Not enough info flag
            return self.save_flagged_service(
                service_key,
                venue_key,
                venue_category_id,
                user.email)
        if previous_match_wizard:
            # 2nd matcher - save match to warehouse
            return self.save_matched_service(
                service_key,
                venue_key,
                wizard,
                venue_category_id,
                user.email,
                previous_match_wizard)
        else:
            # 1st matcher - lock service in warehouse
            return self.lock_service_matched(service_key)

    def get_venue_count(self, city, level1):
        if level1 == "-1":
            return 0
        url = settings.BUILD_URL(
            settings.WAREHOUSE_HOST,
            settings.WAREHOUSE_PORT,
            settings.WAREHOUSE_UNMATCHED_VENUE_COUNT_PATH,
        )
        category_ids = [str(category_id) for category_id in level1_to_warehouse_category_id[level1]]
        params = {
            'ueni_token': get_token(),
            'major_city': city,
            'category_id': ",".join(category_ids),
            'limit': 100,
            'model': 'protodomain',
        }
        r = requests.get(url, params=params, timeout=1)
        venue_count = int(r.content)
        return venue_count

    def get_batch_unmatched_service(self, country, city, category_ids=None, size=10):
        """
        Fetch a service from the frontend
        :param country: str,
        :param city: str,
        :param category_ids: list of int, e.g. [1077, 1078. 1099 ...]
        :param size: int, size of the batch to return
        :return: dict or None, service for frontend
        """
        url = settings.BUILD_URL(
            settings.WAREHOUSE_HOST,
            settings.WAREHOUSE_PORT,
            settings.WAREHOUSE_UNMATCHED_SERVICES_PATH,
        )
        params = {
            'ueni_token': get_token(),
            'major_city': city,
            'batch_size': size,
            'model': 'protodomain',
        }
        if settings.SERVICEMATCHER_IN_TEST_MODE:
            # shorter temporary lock during test mode because nothing is saved anyway
            params["time_limit"] = 1
        if category_ids:
            params['category_id'] = ",".join([str(category_id) for category_id in category_ids])
        r = requests.get(url, params=params, timeout=60)
        if r.status_code != 200:
            log.warning("Connection with the warehouse {} returned code {}".format(url, r.status_code))
            return []
        if r.content:
            datas = json.loads(r.content)
            datas = [format_service_for_frontend_from_warehouse_data(data, country) for data in datas]
            return datas
        return []

    def save_matched_service(self, service_key, venue_key, venue_category_id, wizard, user_email, previous_match_wizard):
        """
        :param service_key: str,
        :param venue_key: str,
        :param venue_category_id: int,
        :param wizard: str, the wizard found by the 2nd matcher
        :param user_email: str,
        :param previous_match_wizard: str, the wizard found by the 1st matcher
        :return: Boolean, did everything go well
        """
        if wizard != previous_match_wizard:
            # The two juniors don't agree
            source = "matcher"
        else:
            # The two juniors agree
            source = "matcher_qc"
        data = {
            "wizard_index": get_wizard_for_wh(venue_category_id, wizard, previous_match_wizard)
        }
        if self.save_data(service_key, venue_key, user_email, source, data):
            rep = "Service from 2nd matcher saved in the warehouse"
            log_level = log.info
        else:
            rep = "Service could not be saved in the warehouse"
            log_level = log.warning
        log_level(rep)
        return Response(rep)

    def save_flagged_service(self, service_key, venue_key, venue_category_id, user):
        """
        :param service_key: str,
        :param venue_key: str,
        :param venue_category_id, int,
        :param user: user obj,
        :return: Boolean, did everything go well
        """
        source = "matcher"
        data = {
            "matcher_flags": ["not_enough_info"],
            "wizard_index": get_wizard_for_wh(venue_category_id),
        }
        # if the flag is chosen, we match to a level1 in the warehouse with the flag
        if self.save_data(service_key, venue_key, user.email, source, data):
            rep = "Service {} saved in warehouse".format(service_key)
            log_level = log.info
        else:
            rep = "Locking service {} in warehouse returned error code".format(service_key)
            log_level = log.warning
        log_level(rep)
        return Response(rep)

    def save_data(self, service_key, venue_key, user_email, source, data):
        """
        :param service_key: str,
        :param venue_key: str,
        :param user_email: str,
        :param source: str, the ref for warehouse
        :param data: str, the datasource for warehouse
        :return: Boolean, did everything go well
        """
        datasource = {
            'source': source,
            'source_ref': user_email,
            'data': data,
            'informs': [service_key, venue_key],  # venu_key -> GUID ? GUID is more robust, key can be deleted
            'data_kind': 'service'
        }
        if settings.SERVICEMATCHER_IN_TEST_MODE:
            log.info("Dont send to warehouse as it is in test mode")
            return True
        headers = {'X_UENI_TOKEN': get_token()}
        params = {'priority': 1}
        data = json.dumps([datasource], encoding='utf-8')
        url = settings.BUILD_URL(
            settings.WAREHOUSE_HOST,
            settings.WAREHOUSE_PORT,
            settings.WAREHOUSE_UPLOAD_PATH
        )
        r = requests.put(url, data=data, headers=headers, params=params, timeout=60)
        if r.status_code != 200:
            return False
        else:
            return True

    def lock_service_matched(self, service_key):
        """
        If the service has been matched by the 1st matcher, we want to lock it in the warehouse to
        make sure it wont be fetched again by another matcher
        :param service_key: dict, from the frontend
        :return: Boolean, did everything go well
        """
        url = settings.BUILD_URL(
            settings.WAREHOUSE_HOST,
            settings.WAREHOUSE_PORT,
            settings.WAREHOUSE_LOCK_SERVICE_PATH
        )
        params = {
            'ueni_token': get_token(),
            'product_key': service_key,
        }
        if settings.SERVICEMATCHER_IN_TEST_MODE:
            rep = "Dont send to warehouse as it is in test mode"
            log_level = log.info
        else:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code != 200:
                rep = "Locking service {} in warehouse returned error code {}".format(service_key, r.status_code)
                log_level = log.warning
            else:
                rep = "Service {} locked in the warehouse".format(service_key)
                log_level = log.info
        log_level(rep)
        return Response(rep)
