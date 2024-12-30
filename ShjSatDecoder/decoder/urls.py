from django.urls import path
from . import views

app_name = "decoder"

urlpatterns = [
    path('', views.decoder_view, name='decoder_view'),
    path('fetch_and_decode', views.fetch_and_decode, name='fetch_and_decode'),
    path('visualize/', views.visualize_data, name='visualize_data'),
    path('trend-analysis/', views.trend_analysis, name='trend_analysis'),

]