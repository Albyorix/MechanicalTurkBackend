def query_get_index_elements_from_search_string(search_string, size=10, skip=0, level1_id=""):
    query = {
        "query": {
            "bool": {
                "should": {
                    "multi_match": {
                        "query": search_string,
                        "type": "best_fields",
                        "tie_breaker": 0.7,
                        "fields": ["level5.search"]
                    }
                }
            }
        },
        "from": skip,
        "size": size,
    }
    if level1_id:
        query["query"]["bool"]["filter"] = {"match": {"level1_id": level1_id}}
    return query


def query_get_index_elements_from_service(service, venue, level1_id="", size=3):
    query = {
        "query": {
            "bool": {
                "should": [
                    {
                        "dis_max": {
                            "tie_breaker": 0.7,
                            "boost": 10.1,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        # "score_mode": "sum",
                                        "query": {
                                            "match": {
                                                "product_description.search_analyzer": service['description']
                                            }
                                        }
                                    }},
                                {
                                    "match": {
                                        "level5.search_analyzer": service['description']
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "dis_max": {
                            "tie_breaker": 0.2,
                            # "boost": 1.0,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        "query": {
                                            "multi_match": {
                                                "query": service['description'],
                                                "fields": ["product_category", "product_description", "venue_category"]
                                            },
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "full_wizard": service['description']
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "dis_max": {
                            # "tie_breaker": 0.1,
                            # "boost": 0.5,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        # "score_mode": "sum",
                                        "query": {
                                            "match": {
                                                "product_description.search_analyzer": service['category']
                                            }
                                        }
                                    }},
                                {
                                    "match": {
                                        "level5.search_analyzer": service['category']
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "dis_max": {
                            # "tie_breaker": 0.2,
                            # "boost": 1.0,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        "query": {
                                            "multi_match": {
                                                "query": service['category'],
                                                "fields": ["product_category", "product_description", "venue_category"]
                                            }
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "full_wizard": service['category']
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "dis_max": {
                            "tie_breaker": 0.1,
                            "boost": 0.5,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        # "score_mode": "sum",
                                        "query": {
                                            "match": {
                                                "product_description.search_analyzer": venue['category_name']
                                            }
                                        }
                                    }},
                                {
                                    "match": {
                                        "level5.search_analyzer": venue['category_name']
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "dis_max": {
                            "tie_breaker": 0.2,
                            "boost": 1.0,
                            "queries": [
                                {
                                    "has_child": {
                                        "type": "service",
                                        "query": {
                                            "multi_match": {
                                                "query": venue['category_name'],
                                                "fields": ["product_category", "product_description", "venue_category"]
                                            }
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "full_wizard": venue['category_name']
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        },
        "size": size
    }
    if level1_id:
        query["query"]["bool"]["filter"] = {
            "match": {
                "level1_id": level1_id
            }
        }
    return query


def query_get_unmatched_service(user_id, before_time, level1_id="", size=1):
    query = {
        "query": {
            "constant_score": {
                "filter": {
                    "bool": {
                        "must": [
                            {"range": {"last_fetch_date": {
                                "lte": before_time
                            }}},
                            {"term": {"check_flag": True}},
                            {"term": {"_type": "service"}},
                        ],
                        "must_not": {"term": {"user_id": user_id}},
                    }
                }
            }
        },
        "size": size
    }
    if level1_id:
        query["query"]["constant_score"]["filter"]["bool"]["filter"] = {
            "has_parent": {
                "type": "index_element",
                "query": {"match": {"level1_id": level1_id}},
            },
        }
    return query


# Test the queries
if __name__ == "__main__":
    from elasticsearch import Elasticsearch
    from pprint import pprint

    es = Elasticsearch(hosts=[{'host': "localhost", 'port': 9200}])
    new_date = "2016-05-05 22:22:55"
    user_id = 777
    update_dico = {
        "script": {
            "inline": "ctx._source.last_fetch_date = params.last_fetch_date; ctx._source.lock_user_id= params.lock_user_id",
            "lang": "painless",
            "params": {
                "last_fetch_date": new_date,
                "lock_user_id": user_id,
            }
        },
        "query": {
            "constant_score": {
                "filter": {
                    "bool": {
                        "must": [
                            {"range": {"last_fetch_date": {
                                    "lte": "2018-11-11 11:11:11"
                                }}},
                            {"term": {"check_flag": True}},
                            {"term": {"_type": "service"}}
                        ],
                        "must_not": {"term": {"user_id": -1}},
                        "filter": {"has_parent": {"type": "index_element", "query": {"match": {"level1": "Hair & Beauty"}}}}
                    }
                }
            }
        }
    }
    query_dico = {
        "query": {
            "constant_score": {
                "filter": {
                    "bool": {
                        "must": [
                            {"match": {"last_fetch_date": new_date}},
                            {"match": {"lock_user_id": user_id}}
                        ]
                    }
                }
            },
        },
        "_version": True,
    }
    r = es.update_by_query(index="new_english_test", doc_type="service", body=update_dico, wait_for_completion=True, size=2)
    # r = es.reindex(body={})
    r = es.search(index="new_english_test", doc_type="service", body=query_dico, size=2)
    pprint(r)


