from django.conf.urls import url

from servicematcher import views

urlpatterns = [
    url(r'^business_types', views.FetchBusinessType.as_view()),
    url(r'^fetch_batch', views.FetchBatchService.as_view()),
    url(r'^submit', views.SubmitService.as_view()),
    url(r'^index_elements', views.SearchService.as_view()),
]
