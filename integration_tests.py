from walker_app.configs.settings_override import *

from pprint import pprint
import requests
import json
import subprocess
import os
import psutil
import time
import datetime

from copy import deepcopy

from servicematcher.utils import get_logging
from queries import query_get_unmatched_service

log = get_logging(__name__)
BASE_URL = "http://localhost:8080"
AUTH_TOKEN_1 = "XXX"
AUTH_TOKEN_2 = "XXX"
AUTH_TOKEN_3 = "XXX"
HEADERS_1 = {'Content-Type': 'application/json', 'Authorization': 'Token {}'.format(AUTH_TOKEN_1)}
HEADERS_2 = {'Content-Type': 'application/json', 'Authorization': 'Token {}'.format(AUTH_TOKEN_2)}
HEADERS_3 = {'Content-Type': 'application/json', 'Authorization': 'Token {}'.format(AUTH_TOKEN_3)}
INITIAL_INPUT = {
    "search_data": {
        "city": "London",
        "level1_id": "01000",
        "level1": "Hair & Beauty",
        "country": "gb",
    },
    "requested_at": 0,
    "batch_size": 10,
}
MATCHED_SERVICE = {
    "service": {
        "category": "Semi Permanent Eyelash Extensions",
        "description": "Blue or Purple Ombre lashes",
        "key": "XXX"
    },
    "venue": {
        "category_name": "Tanning",
        "key": "XXX",
        "category_id": "1085",
        "name": "Amy's Beauty Obsession"
    },
    "search_data": INITIAL_INPUT["search_data"],
    "country": "gb",
    "match_data": {
        "matched_index_element_id": "01000_00100_01000_00100_00800",
        "unmatched_index_element_ids": [
            "01100_00100_00200_00100_01600",
            "02000_00300_05200_00200_00200",
        ],
        "used_search": False,
        "wizard": "01000_00100_01000_00100_00800",
        "time_spent": "666",
    }
}
MATCHED_SERVICE_2 = deepcopy(MATCHED_SERVICE)
MATCHED_SERVICE_2["wizard"] = "01400_00100_00400_00100_00400"
SEARCH = {
    "search_string": "Hair cu",
    "country": "gb",
    "skip": 10,
    "range_size": 10,
    "level1": "Hair & Beauty"
}
TEST_INDEX = "new_english_test"
CHILD_DOC_TYPE = "service"


class ServiceMatcherTest:

    def __init__(self):
        pass

    def junior1_can_fetch_service_from_warehouse(self):
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "warehouse":
            log.error("The data is not coming from the warehouse as it should be")
            return

    def junior1_cannot_fetch_his_service_from_elastic(self):
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "warehouse":
            log.error("The data is not coming from the warehouse as it should be")
            return

    def junior2_can_fetch_junior1_service_from_elastic(self):
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "elastic":
            log.error("The data is not coming from the elastic as it should be")
            return

    def junior3_cannot_fetch_service_matched_by_junior1_and_fetched_by_junior2(self):
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "elastic":
            log.error("The data is not coming from the elastic as it should be")
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_3)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "warehouse":
            log.error("The service in elastic is not locked as it should be")
            return

    def junior1_and_junior2_agree(self):
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "elastic":
            log.error("The should not be fetchable after being submitted")
            return

    def junior1_and_junior2_disagree(self):
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE), headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        response = requests.post('{}/matcher/submit'.format(BASE_URL), data=json.dumps(MATCHED_SERVICE_2), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        time.sleep(1)
        response = requests.post('{}/matcher/fetch_batch'.format(BASE_URL), data=json.dumps(INITIAL_INPUT), headers=HEADERS_2)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return
        payload = json.loads(response.text)
        if payload["results"][0]["origin"] != "elastic":
            log.error("The should not be fetchable after being submitted")
            return

    def junior1_use_search_box(self):
        response = requests.get('{}/matcher/index_elements'.format(BASE_URL), params=SEARCH, headers=HEADERS_1)
        if response.status_code != 200:
            log.error("'{}' with code '{}'".format(response.text, response.status_code))
            return


if __name__ == "__main__":
    smt = ServiceMatcherTest()
    smt.junior1_can_fetch_service_from_warehouse()
    # smt.junior2_can_fetch_junior1_service_from_elastic()
    # smt.junior1_cannot_fetch_his_service_from_elastic()
    # smt.junior3_cannot_fetch_service_matched_by_junior1_and_fetched_by_junior2()
    # smt.junior1_and_junior2_agree()
    # smt.junior1_and_junior2_disagree()
    # smt.junior1_use_search_box()
