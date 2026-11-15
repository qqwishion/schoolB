from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts.views import register
from museum import views as m
from quizzes import views as q

urlpatterns = [
    path('', m.home, name='home'), path('eras/', m.eras, name='eras'), path('eras/<slug:slug>/', m.era_detail, name='era'),
    path('topics/<int:pk>/', m.topic_detail, name='topic'), path('cards/', m.catalog, name='cards'), path('cards/<int:pk>/', m.card_detail, name='card'), path('cards/<int:pk>/progress/', m.mark_card, name='mark_card'),
    path('quizzes/', q.catalog, name='quizzes'), path('quizzes/<int:pk>/', q.quiz_detail, name='quiz'), path('attempts/<int:pk>/', q.attempt_detail, name='attempt'), path('attempts/<int:pk>/submit/', q.submit, name='submit_attempt'),
    path('profile/', m.profile, name='profile'), path('sources/', m.sources, name='sources'), path('accounts/register/', register, name='register'), path('accounts/', include('django.contrib.auth.urls')), path('admin/', admin.site.urls),
] + (static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) if settings.DEBUG else [])
handler404 = 'config.views.not_found'
handler403 = 'config.views.forbidden'
