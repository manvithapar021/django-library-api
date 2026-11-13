"""URL routing: DRF router for the viewsets, plus the token endpoint."""

from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from catalog.views import BookViewSet, LoanViewSet, MemberViewSet, StatsViewSet

router = DefaultRouter()
router.register(r"books", BookViewSet, basename="book")
router.register(r"members", MemberViewSet, basename="member")
router.register(r"loans", LoanViewSet, basename="loan")
router.register(r"stats", StatsViewSet, basename="stats")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/token/", obtain_auth_token, name="api-token"),
]
