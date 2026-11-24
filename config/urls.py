from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from apps.dashboard.forms import LoginForm

urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("login/", LoginView.as_view(template_name="auth/login.html", authentication_form=LoginForm), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("admin/", admin.site.urls),
    path("catalog/", include("apps.catalog.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("reports/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
