## Background 
 
> **N.B. The terms *venue categories*, *service categories* and *index element categories* are all different entities** 
 
The purpose of the Service Matcher (SM) is to match services to index elements. 
 
Venue information and the services they provide are obtained through a variety of means, such as from data scrapes and walkers. These venue and service data are stored in the warehouse. 
 
The service names provided by the venue are likely to be different from each other, even though they mean the same thing. For example, "Ladies Cut & Blow Dry" from TONI&GUY means the same as "Supercut" from supercuts. 
 
The service matcher takes these arbitrary service names, and try to match them to a large pre-defined, curated list of services, which we call index elements. 
 
To be absolutely clear, when we say 'services', we mean 'unmatched services with arbitrary names'; when we say 'index elements', we mean 'an element from the list of services that have been curated, and for which we are trying to match *to*`. 
 
## Endpoints 

### Get a list of venue categories

#### Request

* HTTP Method: `GET` 
* Endpoint URL Path: `/matcher/business_types`
* Payload Properties
  * `city` *String* - key of the city as obtained from `/interfaces/wh_cities` endpoint

#### Response

* Payload:
  * An array of venue categories, each array element is an object containing the following properties:
    * `id` *String*  - ID of the venue category
    * `name` *String* - Name of the venue category
    * `venue_count` *Int* - Number of venue with unmatched product


**N.B. The `id` for business type must never be `0` (integer)**

### Fetch Services & Most relevant Index Elements 
 
This should be called after the user has selected a city and a service category. 
 
#### Request 

* HTTP Method: `POST` 
* Endpoint URL Path: `/matcher/fetch_batch` 
* Payload Properties: 
  * `search_data` *[Object]* 
    * `city*` *String* - name of the city as obtained from `/interfaces/wh_cities` endpoint
    * `country*` *String* - ISO-3166-1 code for the country the city belongs to
    * `level1_id*` *String* - ID of the level1 index of service
    * `level1` *String* - Name the level1 index of the service 
  * `requested_at` *Integer* - A UNIX timestamp, used to track old requests which may still be in transit after the parameters have changed in the UI
  * `batch_size` *int* - Size of batch to return

 
#### Response 
 
* HTTP Status Code: `200 OK` 
* Payload properties: 
  * `requested_at` *Integer*: The `requested_at` UNIX timestamp sent with the request
  * `results` *[Object]*: An array of services
      * `search_data` *[Object]* 
        * cf above
      * `service` *[Object]* - Information about the service we are matching
        * `key` *String* - The primary key used in the warehouse for this service
        * `category` *String* - The name of the *service category* of this service
        * `description` *String* - The name of the service
        * `elastic_service_id` *String* - The primary key of the service in elasticsearch. (optional, must be passed back)
        * `elastic_index_element_id` *String* - The primary key of the index element in elasticsearch. (optional, must be passed back)
      * `venue` *[Object]* - Information about the venue we are matching
        * `key` *String* - The primary key used in the warehouse for the venue
        * `name` *String* - The name of the venue.
        * `category_name` *String* - The name of the *venue category*
        * `category_id` *int* - The id of the *venue category*
      * `index_elements` *[Object]* - An array of index element objects we are matching the service to. Each index element object would have the following properties: 
        * `id` *String* - The primary key used in elasticsearch for the index element 
        * `score` *Float* - A indication of how relevant this index element is to the service being a match 
        * `wizard` *String* - A string used by the backend to quickly determine the level 1-5 categorization of this index element 
        * `level[n]` *String* - Name of the grouping, for each level: 1 (business), 2 (category), 3 (sub-category), 4 (service), 5 (name) 
        * `pictures` *[String]* - An array of image URLs representing the index element. The first image should be the default image 

 
#### Request 

* HTTP Method: `POST` 
* Endpoint URL Path: `/matcher/fetch_batch` 
* Payload Properties: 
  * Same as `match/fetch`
  
#### Response 
 

### Search for relevant index elements 
 
This should be called when the user cannot find a relevant match after querying 'Fetch Services & Most relevant Index Elements' 
 
#### Request 
 
* HTTP Method: `GET` 
* Endpoint URL Path: `/matcher/index_elements` 
* Query Paramters: 
  * `search_string` *String* - Search term 
  * `country*` *String* - ISO-3166-1 code for the country the city belongs to
  * `level1*` *String* - Level 1 to limit the search to. If unspecified, do not limit the search to a particular category. 
  * `skip` *Number* - Number of entries to skip from the results. If unspecified, the backend defaults this to 0. 
  * `range_size` *Number* - The number of results being requested. If unspecified, the backend defaults this to 10. 


#### Response 
 
* HTTP Status Code: `200 OK` 
* Payload properties: 
  * `skip` *Number* - The number of entries skipped 
  * `range_size` *Number* - The range requested. If this number is more than the number of results, we can determine that there are no more results 
  * `index_elements` *[Object]* - An array of index element objects returned from the search. Each index element object should have the following properties: 
    * cf above
    

### Submit a match 
 
This is called when confirming a match 
 
#### Request 
 
* HTTP Method: `POST` 
* Endpoint URL Path: `/matcher/submit` 
* Payload Properties: 
  * `country*` *String* - Country code
  * `search_data` *[Object]* 
    * cf above
  * `service*` *[Object]* 
    * cf above
  * `venue*` *[Object]*
    * cf above
  * `match_data` + [Object]*
    * `matched_index_element_id*` *String* - The primary key used in elasticsearch for the index element 
    * `unmatched_index_element_ids*` *List of String*
    * `used_search*` *Boolean* - Whether the `matched_index_element_id` index element was from the search results
    * `search_string` *String* - What is in the search box if the matcher used it, not defined if not used
    * `wizard*` *String* - the 25 digits to which the product was matched
    * `not_enough_info*` *Boolean* - Wether the matcher click on `Not enough info` button
    * `time_spent` *String* - Time it took to match the service
  

 
#### Response 
 
* HTTP Status Code: `200 OK` 
* Payload: None


## Environements

### local elasticsearch

if you have a local elasticsearch for development, add these lines to `settings_override.py` :
    ELASTIC_HOST = "localhost"
    ELASTIC_PORT = 9200
    ELASTIC_SSL = False
    SERVICEMATCHER_IN_TEST_MODE = True
    SERVICEMATCHER_COUNTRY_TO_INDEX = defaultdict(lambda: "new_english_test")

### local warehouse

if you have a local warehouse add these:
    WAREHOUSE_HOST = 'http://localhost'
    WAREHOUSE_PORT = 8099
    WAREHOUSE_LOCAL_TOKEN = 'debug'
and make sure you add arguments --port=8099 and --admin_port=8090 to `develop.py` in the back-end

### dev1 online dev/test

We push the servicematcher to test it on the appengine to dev1, with live elasticsearch at elastic.ueni.com
we add:
    SERVICEMATCHER_IN_TEST_MODE = True 
To make sure nothing will be pushed to the warehouse
and:
    SERVICEMATCHER_COUNTRY_TO_INDEX = defaultdict(lambda: "new_english_test")
to make sure we use the test index and not the prod index

### prod 

use live elasticsearch with production index :
    SERVICEMATCHER_IN_TEST_MODE = False
    SERVICEMATCHER_COUNTRY_TO_INDEX = defaultdict(lambda: "new_english")
    SERVICEMATCHER_COUNTRY_TO_INDEX["en"] = "new_english"
