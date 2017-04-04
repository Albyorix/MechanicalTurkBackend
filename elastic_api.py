from __future__ import unicode_literals
from logging import NullHandler
from datetime import datetime, timedelta
from random import shuffle

from django.conf import settings
from elasticsearch import Elasticsearch, RequestsHttpConnection

from servicematcher import queries as eq
from servicematcher.utils import get_logging, get_unix_time

tracer = get_logging('elasticsearch.trace')
tracer.addHandler(NullHandler())
log = get_logging(__name__)

country_to_index = settings.SERVICEMATCHER_COUNTRY_TO_INDEX
PARENT_DOC_TYPE = "index_element"
CHILD_DOC_TYPE = "service"
NEGATIVE_CHILD_DOC_TYPE = "negative_service"
SEARCHED_CHILD_DOC_TYPE = "searched_service"


def format_service_for_frontend_from_elastic_hit(hit):
    """
    :param hit: dict, from elastic
    :return: dict, service payload for frontend
    """
    data = {
        "service": {
            "description": hit["_source"]["product_description"],
            "category": hit["_source"]["product_category"],
            "key": hit["_source"]["product_key"],
            "elastic_service_id": hit["_id"],
            "elastic_index_element_id": hit["_parent"],
        },
        "venue": {
            "key": hit["_source"]["subdomain_key"],
            "name": hit["_source"]["venue_name"],
            "category_name": hit["_source"]["venue_category"],
            "category_id": hit["_source"]["venue_category_id"],
        },
        "origin": "elastic",
    }
    return data


def format_index_element_from_elastic_hit(hit):
    """
    :param hit: dict, from elasticsearch
    :return: dict, index_element payload for frontend
    """
    index_element = {
        "id": hit['_id'],
        "score": hit.get('_score', 0),
        "level1": hit["_source"]["level1"],
        "level2": hit["_source"]["level2"],
        "level3": hit["_source"]["level3"],
        "level4": hit["_source"]["level4"],
        "level5": hit["_source"]["level5"],
        "wizard": hit["_source"]["wizard"],
        "pictures": [hit["_source"]["picture1"],
                     hit["_source"]["picture2"]]
    }
    return index_element


def format_service_for_elastic_from_request(service, venue, user, time_spent):
    """
    :param service: dict, from frontend
    :param venue: dict, from frontend
    :param user: user obj,
    :param time_spent: str,
    :return: dict, service to store in elastic
    """
    new = {
        "user_email": user.email,
        "user_id": user.id,
        "product_key": service['key'],
        "subdomain_key": venue['key'],
        "product_category": service["category"],
        "product_description": service["description"],
        "venue_category": venue["category_name"],
        "venue_name": venue["name"],
        "venue_category_id": venue["category_id"],
        "time_spent": time_spent,
    }
    return new


class ElasticServices(object):

    def __init__(self):
        self.es = Elasticsearch(
            hosts=[{'host': settings.ELASTIC_HOST, 'port': settings.ELASTIC_PORT}],
            use_ssl=settings.ELASTIC_SSL,
            http_auth=(settings.ELASTIC_USER, settings.ELASTIC_PASSWD),
            connection_class=RequestsHttpConnection,
            send_get_body_as='POST')
        log.info("Using Elastic {}".format(self.es))

    def autocompleter(self, country, search_string, range_size=10, skip=0, level1_id=""):
        """
        auto-complete search for frontend
        :param country: str, name of the country to map to the index
        :param search_string: str, search string filled by the matcher in the box
        :param range_size: int, size of the batch
        :param skip: int, number of results to skip
        :param level1_id: str, for filter in elastic, e.g. "Hair & Beauty"
        :return: list of dict, index_elements
        """
        query = eq.query_get_index_elements_from_search_string(search_string, size=range_size, skip=skip, level1_id=level1_id)
        index = country_to_index[country]
        res = self.es.search(index=index, doc_type=PARENT_DOC_TYPE, body=query)
        hits = [format_index_element_from_elastic_hit(hit) for hit in res['hits']['hits']]
        return hits

    def get_top3_index_elements_from_service(self, data, level1_id, country, get_1st_match=True):
        """
        This send top 3 matched parents to the frontend and frontend should
        :param data: dict, containing "service" and "venue", and "wizard" if the service is for 2nd matcher
        :param level1_id: str, for filter in elastic, e.g. "01000"
        :param country: str,
        :param get_1st_match: boolean, get the match of the 1st matcher if it's the second matcher fetching
        :return: dict, parent, triplet and the user_dictionary
        """
        query = eq.query_get_index_elements_from_service(data["service"], data["venue"], level1_id)
        index = country_to_index[country]
        hits = []
        log.info("START fetching top3")
        time = get_unix_time()
        if get_1st_match and "wizard" in data:
            # 2nd matcher - fetch the 1st matcher result
            hit = self.es.get(index=index, id=data["wizard"], doc_type=PARENT_DOC_TYPE)
            hits += [format_index_element_from_elastic_hit(hit)]
        try:
            res = self.es.search(index=index, body=query, doc_type=PARENT_DOC_TYPE)
            if res['hits']['total'] > 0:
                hits += [format_index_element_from_elastic_hit(hit) for hit in res['hits']['hits']]
            log.info("Elastic returned top3 for: {} {}".format(data["service"]["key"], data["venue"]["key"]))
        except:
            log.warning("No service were found for this service: {} {}".format(data["service"]["key"], data["venue"]["key"]))
        log.info("STOP fetching top3. It took: {}ms".format(get_unix_time() - time))
        if len(hits) > 3:
            # delete duplicate or last match
            hit1_wizard = hits[0]["id"]
            for i in range(1, 4):
                if hits[i]["id"] == hit1_wizard:
                    hits.pop(i)
                    break
            hits = hits[:3]
        shuffle(hits)
        return hits

    def get_batch_unmatched_service(self, country, level1_id, user_id, size=10):
        """
        Search the child index for the 2nd junior
        :param country: str
        :param level1_id: str, "01000"
        :param user_id: int, dont retrieve from this user
        :param size: int, size of the batch to return
        :return: list of dic, containing query, child and parent documents.
        """
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        query_before = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        query = eq.query_get_unmatched_service(user_id=user_id,
                                               before_time=query_before,
                                               level1_id=level1_id,
                                               size=size)
        index = country_to_index[country]
        res = self.es.search(index=index, body=query, doc_type=CHILD_DOC_TYPE)
        hits = res['hits']['hits']
        for hit in hits:
            # idea to improve : use elastic script to update all docs at once
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-update-by-query.html
            service_id = hit["_id"]
            index_element_id = hit["_parent"]
            update_service = {
                "doc": {
                    "last_fetch_date": current_time,
                },
                "_source": True
            }
            self.es.update(index=index, doc_type=CHILD_DOC_TYPE, id=service_id, body=update_service, routing=index_element_id)
        hits = [format_service_for_frontend_from_elastic_hit(hit) for hit in hits]
        return hits

    def save_service(self, service, venue, user, country, matched_index_element_id="", unmatched_index_element_ids=(),
                     time_spent="0", used_search=False, not_enough_info=False, check_flag=False):
        """
        :param service: dict,
        :param venue: dict,
        :param user: user obj,
        :param country: str,
        :param matched_index_element_id: str,
        :param unmatched_index_element_ids: list of str,
        :param used_search: Boolean, True if the search box was used
        :param not_enough_info: Boolean, True if the button was used
        :param time_spent: str, time spent for the matcher to match the service
        :param check_flag: Boolean, True for the 1st matcher, False for the second
        :return:
        """
        new = format_service_for_elastic_from_request(service, venue, user, time_spent)
        index = country_to_index[country]
        for unmatched_index_element_id in unmatched_index_element_ids:
            # save negative service
            self.es.index(index=index, body=new, parent=unmatched_index_element_id, doc_type=NEGATIVE_CHILD_DOC_TYPE)
        if used_search:
            # save searched service
            self.es.index(index=index, body=new, parent=matched_index_element_id, doc_type=SEARCHED_CHILD_DOC_TYPE)
        if not not_enough_info:
            # save service
            new["check_flag"] = check_flag
            new["last_fetch_date"] = "2011-11-11 11:11:11"  # Random date to not leave emtpy
            self.es.index(index=index, body=new, parent=matched_index_element_id, doc_type=CHILD_DOC_TYPE)

    def get_wizard_from_index_element_id(self, index_element_id, country):
        """
        :param index_element_id: str,
        :param country: str,
        :return: str, wizard
        """
        index = country_to_index[country]
        res = self.es.get(index=index, id=index_element_id)
        return res["_source"]["wizard"]

    def update_1st_match_flag(self, service_id, index_element_id, country):
        """
        :param service_id: str,
        :param index_element_id: str,
        :param country: str,
        :return:
        """
        update_service = {
            "doc": {
                "check_flag": False,
            },
            "_source": True
        }
        index = country_to_index[country]
        try:
            self.es.update(index=index, doc_type=CHILD_DOC_TYPE, id=service_id, body=update_service, routing=index_element_id)
            return True
        except:
            return False