from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [path('healthz/', views.health, name='health'),
 path('', views.welcome, name='welcome'), path('signup/', views.signup, name='signup'),
 path('login/', views.PamojaLoginView.as_view(), name='login'), path('logout/', LogoutView.as_view(), name='logout'),
 path('onboarding/', views.onboarding, name='onboarding'), path('dashboard/', views.dashboard, name='dashboard'),
 path('planner/', views.planner, name='planner'), path('tasks/new/', views.task_edit, name='task_add'),
 path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
 path('tasks/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
 path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
 path('spaces/<str:key>/move/', views.move_space, name='move_space'),
 path('profile/', views.profile, name='profile'), path('chat/', views.chat, name='chat'),
 path('sw.js', views.service_worker, name='service_worker')]
