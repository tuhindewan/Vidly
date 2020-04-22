from django.shortcuts import render
from django.http import HttpResponse
from .models import Movie

# Create your views here.


def index(request):
    movies = Movie.objects.all()
    title_list = [movie.title for movie in movies]
    separator = ', '
    result = separator.join(title_list)
    return HttpResponse(result)
