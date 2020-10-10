from django.shortcuts import render,get_object_or_404,render_to_response
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator,PageNotAnInteger,EmptyPage
from django.contrib.postgres.search import SearchQuery,SearchRank,SearchVector
from django.contrib.postgres.search import TrigramSimilarity
from django.core.mail import send_mail
from django.forms import ValidationError
from django.db.models import Count
from django.views.generic.list import ListView
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.core.mail.message import EmailMessage  #send an email containing some data e.g a file
from taggit.models import Tag  #tagging module for tagging posts
from .models import Post
from .forms import EmailPostForm,CommentForm,SearchForm,ContactForm

class AboutPage(TemplateView):
    template_name = 'blog/about.html'

class  ProjectsPage(TemplateView):
    template_name = 'blog/projects.html'

class GalleryPage(TemplateView):
    template_name = 'blog/gallery.html'

class DownloadsPage(TemplateView):
    template_name = 'blog/downloads.html'        

class ContactUs(FormView):
    template_name = 'blog/contacts.html'
    form_class =  ContactForm
    success_url = '/blog/thanks/'

    def form_valid(self,form):
        form.send_mail()
        return super().form_valid(form)

def thanks(request):
    return render(request,'blog/thanks.html',{})



"""
The view below gets the all posts, and gets paginator object for the posts 
across pages.
The get_object_or_404() function takes a Django model as its first argument and an arbitrary number of keyword arguments,
which it passes to the get() function of the model's manager and raises Http404 if the object doesn't exist.
The get_list_or_404() works the same only that it gets a list instead of an object.
"""
def post_list(request,tag_slug=None):
    posts = Post.published.all()

     # get the object_list to use in pagination and tagging the content with a similar post
    object_list = Post.published.all()
    
    # tagging the posts,filtering a post using a given tag_slug in the url
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag,slug=tag_slug)
        object_list = object_list.filter(tags__in=[tag])

    paginator = Paginator(object_list,4)   #initialize the paginator and assign number of objects per page
    page = request.GET.get('page')    # get the first page 
    #posts = paginator.get_page(page) also does the trick and handles exceptions too ie no need to write
    try:
        posts = paginator.page(page)    # deliver the pages
    except PageNotAnInteger:
        # If the page is not an integer then deliver the first page
        posts =  paginator.page(1)
    except EmptyPage:
        # If page out of range,deliver last page of results
        posts = paginator.page(paginator.num_pages)      
    return render(request,'blog/post/list.html',{'posts':posts,'page':page,'tag':tag})


def post_detail(request,year,month,day,post):
    post = get_object_or_404(Post,status='published',slug=post,publish__year=year,publish__month=month,publish__day=day)
    
    #get a list of similar posts
    post_tags_ids = post.tags.values_list('id',flat=True)  # retrieve all tag id's
    similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id) #get ids matching the ids in this post,excluding this one
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags','-publish')[:4]
    
    """
    Process the comment form  here:::
    """
    #get the list of active comments for this post
    comments = post.comments.filter(active=True)
    new_comment = None

    #when server receives a POST request
    if request.method == 'POST':
        commment_form = CommentForm(data=request.POST)   # initialize the form with the data submitted
        commment_form.checkMail()   # run this function to check for validity
        if commment_form.is_valid():
            #create a comment object and don't save yet,this is because we want to modify it
            #save method is available to ModelForms only not Forms
            new_comment = commment_form.save(commit=False)
            
            #Modify it by Assigning this comment to this specific post
            new_comment.post = post

            #finally save the data to the database
            new_comment.save()
    else:
        commment_form = CommentForm() #Render the form if the server receives a GET request        

    return render(request,'blog/post/detail.html',{'post':post,
                'comments':comments,
                'new_comment':new_comment,
                'comment_form':commment_form,
                'similar_posts':similar_posts })


#Share the posts via email
def post_share(request,post_id):
    #Retrieve post by ID
    post = get_object_or_404(Post,id=post_id,status='published')
    sent = False    
    if request.method == 'POST':
        #The form has been submitted
        form = EmailPostForm(request.POST)   # initialize the form using its data
        form.checkMail() #check if email is valid
        
        if form.is_valid():
            cd = form.cleaned_data           # the validated data in a dictionary
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = '{} ({}) recommends you reading "{}"'.format(cd['name'],cd["email"],post.title)
            message = 'Read "{}" at {} \n\n{}\'s comments:{}'.format(post.title,post_url,cd["name"],cd["comments"])
            sender = 'billyfranks98@gmail.com'
            send_mail(subject,message,sender,[cd['to']],fail_silently=True) #set to False to get the error message
            sent = True
    else:
        form = EmailPostForm()
    return render(request,'blog/post/share.html',{'post':post,'form':form,'sent':sent})        


# Full text search using contrib.postgres.search
def post_search(request):
    se_form = SearchForm()     #initialize the form
    query = None               # set the seacrh query to none
    results = []               # set results to an empty list
    if 'find_posts' in request.GET:   #check for query string in the request.GET dictionary
        se_form = SearchForm(request.GET)    #When submitted,instantiate the form with submitted GET data and check for validity
        if se_form.is_valid():
            query = se_form.cleaned_data['find_posts']
            """
            In the search we could use a simple filter,SearchVector or a more complex TrigramSimilarity,which uses weights 
            """
            search_vector = SearchVector('title',weight='A') + SearchVector('body',weight='B')
            search_query = SearchQuery(query)
            results = Post.objects.annotate(similarity=TrigramSimilarity('title',query)).filter(similarity__gt=0.3).order_by('-similarity')
    return render(request,'blog/base.html',{'se_form':se_form,'query':query,'results':results})        




    
