from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('shells-library/', views.shells_library, name='shells_library'),
    path('shell-quiz/', views.shell_quiz, name='shell_quiz'),
    path(
        'shells-library/<int:shell_id>/',
        views.shell_detail,
        name='shell_detail',
    ),
    path('history/', views.history, name='history'),
    path('about-us/', views.about_us, name='about_us'),
    path('benchmark/', views.benchmark_results, name='benchmark'),
    path('', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('signout/', views.signout, name='signout'),
]
