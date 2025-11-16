"""
URL configuration for KORA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def root_view(request):
    """Rediriger la racine vers l'interface d'administration comme auparavant."""
    return redirect('admin:index')

urlpatterns = [
    path('', root_view, name='api_root'),
    path('admin/', admin.site.urls),
    path('api/', include('pac.urls')),  # API intégrée dans pac
    path('api/parametre/', include('parametre.urls')),  # API des paramètres
    path('api/dashboard/', include('dashboard.urls')),  # API du tableau de bord
    path('api/cartographie-risque/', include('cartographie_risque.urls')),  # API cartographie de risque
]

# Servir les fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
