"""
URLconf for app Blog
"""

from django.conf.urls.defaults import *
from blog.models import Post
from blog.feeds import RssBlogFeed
import blog.views

info_dict = {
    'queryset' : Post.objects.all(),
    'date_field' : 'pub_date',
    'extra_context': {
        'section': 'blog',
    }
}

urlpatterns = patterns('django.views.generic.date_based',
   (r'^$', 'archive_index', info_dict, 'blog_index'),
   (r'^new/$', blog.views.new),
   (r'^archive/$', 'archive_index', info_dict, 'blog_archive'),
   (r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\w{1,2})/(?P<slug>[A-Za-z0-9-_]+)/$', 'object_detail', dict(info_dict, slug_field='slug', month_format='%m')),
   (r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\w{1,2})/$', 'archive_day', dict(info_dict, month_format='%m')),
   (r'^(?P<year>\d{4})/(?P<month>\d{2})/$', 'archive_month', dict(info_dict, month_format='%m')),
   (r'^(?P<year>\d{4})/$', 'archive_year', info_dict),
   (r'^rss/latest/$', RssBlogFeed),
)
