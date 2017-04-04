from __future__ import unicode_literals

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import permission_classes

from servicematcher.warehouse_api import WarehouseServiceMatcherAPI
from servicematcher.elastic_api import ElasticServices
from servicematcher import validation
from servicematcher.mappings import level1_to_warehouse_category_id, level1s, level1_to_level1_id
from servicematcher.utils import get_logging, get_unix_time


log = get_logging(__name__)
es = ElasticServices()
wh = WarehouseServiceMatcherAPI()


@permission_classes((IsAuthenticated,))
class FetchBusinessType(APIView):
    serializer_class = validation.FetchBusinessTypeSerializer

    def get(self, request):
        """
        The matcher logs in the servicematcher - automatic request for the level1s and count per city
        """
        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        city = payload["city"]
        total = 0
        for level1 in level1s:
            try:
                count = wh.get_venue_count(city, level1["id"])
                level1["venue_count"] = count
                total += count
            except:
                level1["venue_count"] = -1
        level1s[-1]["venue_count"] = total
        log.info("Returning business types")
        return Response(level1s)


@permission_classes((IsAuthenticated,))
class FetchBatchService(APIView):
    serializer_class = validation.FetchServiceSerializer

    def post(self, request):
        """
        New function to make the fetch quicker with batch of services
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        batch_size = payload["batch_size"]
        search_data = payload["search_data"]
        level1_id = level1_to_level1_id[search_data['level1']]

        log.info("START fetching batch of size {} from SQL".format(batch_size))
        time = get_unix_time()
        datas = serializer.get_batch_unmatch_service(
            search_data['country'],
            level1_id=level1_id,
            user_id=request.user.id,
            size=batch_size,
        )
        log.info("STOP fetching SQL. It took: {}ms to find {} services".format(get_unix_time() - time, len(datas)))

        # log.info("START fetching batch of size {} from elastic".format(batch_size))
        # time = get_unix_time()
        # datas = es.get_batch_unmatched_service(
        #     search_data['country'],
        #     level1_id=level1_id,
        #     user_id=request.user.id,
        #     size=batch_size,
        # )
        # log.info("STOP fetching elastic. It took: {}ms to find {} services".format(get_unix_time() - time, len(datas)))
        #
        if len(datas) < batch_size:
            batch_size -= len(datas)
            log.info("START fetching batch of size {} from the Warehouse".format(batch_size))
            time = get_unix_time()
            wh_datas = wh.get_batch_unmatched_service(
                search_data['country'],
                search_data['city'],
                category_ids=level1_to_warehouse_category_id[search_data['level1_id']],
                size=batch_size,
            )
            log.info("STOP fetching the Warehouse. It took: {}ms to find {} services".format(
                get_unix_time() - time,
                len(wh_datas))
            )
            datas += wh_datas

        if not datas:
            log.info("No batch service were found in SQL or in the warehouse")
            return Response("No batch service were found in SQL or in the warehouse")

        # Get the top3 match from the corresponding service
        log.info("START fetching top3 from batch of size {}".format(len(datas)))
        time = get_unix_time()
        for data in datas:
            hits = es.get_top3_index_elements_from_service(data, level1_id, search_data['country'])
            data["index_elements"] = hits
            data["search_data"] = search_data
        log.info("STOP fetching top3 from batch. It took: {total}ms or {average}ms/service".format(
            total=get_unix_time() - time,
            average=(get_unix_time() - time)/float(len(datas)))
        )
        res = {
            "requested_at": payload["requested_at"],
            "results": datas,
        }
        return Response(res)


@permission_classes((IsAuthenticated,))
class SearchService(APIView):
    serializer_class = validation.SearchServiceSerializer

    def get(self, request):
        """
        The matcher uses the search box in the frontend to search for an index_element
        """
        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        level1_id = level1_to_level1_id[payload['level1']]
        range_size = payload['range_size']
        skip = payload['skip']
        hits = es.autocompleter(
            payload['country'],
            payload['search_string'],
            range_size,
            skip,
            level1_id=level1_id
        )
        res = {
            "index_elements": hits,
            "range_size": range_size,
            "skip": skip,
        }
        log.info("Returning {} index elements from the search query".format(len(hits)))
        return Response(res)


@permission_classes((IsAuthenticated,))
class SubmitService(APIView):
    serializer_class = validation.SubmitServiceSerializer

    def post(self, request):
        """
        The matcher sends data back to save in the database
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        service = payload["service"]
        venue = payload["venue"]
        match_data = payload["match_data"]
        user = request.user

        # Save to SQL DB
        previous_match_wizard = serializer.save_match_to_sql(venue,
                                                             service,
                                                             payload["search_data"],
                                                             match_data,
                                                             user)
        # Save to elastic
        es.save_service(service, venue, user, payload["country"],
                        matched_index_element_id=match_data["matched_index_element_id"],
                        unmatched_index_element_ids=match_data["unmatched_index_element_ids"],
                        time_spent=match_data["time_spent"],
                        used_search=match_data["used_search"],
                        not_enough_info=match_data["not_enough_info"])
        # Save to warehouse
        return wh.submit_to_warehouse(match_data["not_enough_info"],
                                      service["key"],
                                      venue["key"],
                                      match_data["wizard"],
                                      venue["category_id"],
                                      user,
                                      previous_match_wizard)



