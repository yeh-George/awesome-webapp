# -*- coding: utf-8 -*-
import asyncio, hashlib, json, time, logging, re

from aiohttp import web

from coroweb import get, post

from models import User, Blog, Comment, next_id

from config import configs
import markdown2

from errors import APIError, APIValueError, APIResourceNotFoundError, APIPermissionError

COOKIE_NAME = 'aweseesion'
_COOKIE_KEY = configs.session.secret

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError:
        pass 
    if p < 1:
        p = 1
    return p


class Page(object):
    '''
    Page object for display pages.
    '''
    
    def __init__(self, item_count, page_index=1, page_size=5):
        '''
        Init Pagination by item_count, page_index and page_size.
        '''
        # item_count, page_size, page_count, page_index, has_next, has_previous是给Pagination使用的
        # offset(page_size*(page_index-1)), limit(page_size) 是SQL的判断条件
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        
        if (item_count == 0) or (page_index > self.page_count):
            self.page_index = 1
            self.offset = 0
            self.limit = 0
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1
  
  
def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    生成一串验证字符串：user.id + 过期时间expires + sha1（用户ID，用户密码，过期时间，SecretKey）
    '''
    expires = str(int(time.time()) + max_age)
    sha1 = hashlib.sha1(('%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)).encode('utf-8')).hexdigest()
    L = [user.id, expires, sha1]
    return '-'.join(L)
 
async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1_cookie = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        sha1_user = hashlib.sha1(('%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)).encode('utf-8')).hexdigest()
        if sha1_cookie != sha1_user:
            return None
        user.passwd = '******'
        return user
    except Except as e:
        return None
            
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()
    
#用户浏览页面
#   首页（日志展示页面）： GET /
@get('/')
async def index(*, page='1'):
    page_index = get_page_index(page)
    item_count = await Blog.findNumber('id')
    page = Page(item_count, page_index)
    
    if item_count == 0:
        blogs = []  
    else:
        blogs = await Blog.findAll(limit=(page.offset, page.limit))

    return {
        '__template__': 'index.html',
        'blogs': blogs,
        'page': page
    }
    
#   日志详情页： GET /blog/blog_id
@get('/blog/{blog_id}')
async def blog(blog_id):
    blog = await Blog.find(blog_id)
    blog.html_content = markdown2.markdown(blog.content.replace('<script>', '&lt;script&gt;').replace('</script>', '&lt;/script&gt;').replace('"', '&quot;').replace('_', '&#95;'))
    comments = await Comment.findAll('blog_id=?', [blog_id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)        
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }
              
#   注册页： GET /register
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }
    
#   登录页:  GET /signin
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }
    
#   登出页： GET /signout
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    resp = web.HTTPFound(referer or '/')
    resp.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user %s signed out.' % request.__user__.name)
    return resp
    
#管理页面: GET /manage
@get('/manage')
def manage():
    return 'redirect:/manage/comments'
    
#   评论列表页面： GET /manage/comments
@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }  

#   日志列表页面： GET /manage/blogs
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }
    
#       日志创建页面： GET /manage/blogs/create
@get('/manage/blogs/create')
def manage_blogs_create():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }
    
#       日志修改页面： GET /manage/blogs/edit 
#        在manage_blogs.html中有location.assign('/manage/blogs/edit?id=' + blog.id)      
#        所以参数id是通过querystring传入的
@get('/manage/blogs/edit')
def manage_blogs_edit(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }

#   用户列表页面： GET /manage/users
@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }
    
#用户浏览页面后端API
#   登录signin验证用户: POST /api/athenticate
@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check password: id:passwd
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # if ok, set cookie
    resp = web.Response()
    resp.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    resp.content_type = 'application/json'
    resp.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return resp
  
#   注册register用户/创建create用户:  POST /api/user/register
@post('/api/users')
async def api_users_register(*, email, name, passwd):    
    #check 
    _RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
    _RE_SHA1_PASSWD = re.compile(r'^[0-9a-f]{40}$')
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1_PASSWD.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register failed', 'email', 'Email existed.')
    # create user
    uid = next_id()
    sha1_passwd = hashlib.sha1(('%s:%s' % (uid, passwd)).encode('utf-8')).hexdigest()
    user = User(id=uid, name=name.strip(), email=email, passwd=sha1_passwd, image='about:blank')
    await user.insert()
    # make cookie
    resp = web.Response()
    resp.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    resp.content_type = 'application/json'
    resp.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return resp
  
#   创建评论： POST /api/blogs/blog_id/comments
@post('/api/blogs/{blog_id}/comments')
async def api_commments_create(blog_id,request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please sigin.')
    blog = await Blog.find(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    if not content or not content.strip():
        raise APIValueError('content', 'comment content can\'t be empty.')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,
                        content=content.strip())
    await comment.insert()
    return comment 
  
#管理页面后端API  
# manage_comments 获取评论：GET /api/comments
@get('/api/comments')
async def api_comments_get(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)
    
# manage_comments 删除评论：POST /api/comments/comment_id/delete 
@post('/api/comments/{comment_id}/delete')
async def api_comments_delete(comment_id, request):
    check_admin(request)
    comment = await Comment.find(comment_id)
    await comment.delete()
    return dict(id=comment_id)
    
# manage_users 获取用户：GET /api/users
@get('/api/users')
async def api_users_get(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)
       
# manage_blogs 获取日志： GET /api/blogs
@get('/api/blogs')
async def api_blogs_get(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)
    
# manage_blogs 获取单条日志： GET /api/blogs/blog_id
#   这和日志详情页： GET /blog/blog_id 不一样，是因为是getJSON，通过vue展示出去的
@get('/api/blogs/{blog_id}')
async def api_blogs_getOne(blog_id):
    blog = await Blog.find(blog_id)
    return blog
    
# manage_blogs 创建日志： POST /api/blogs
@post('/api/blogs')
async def api_blogs_create(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'blog name can\'t be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'blog summary can\'t be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'blog content can\'t be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, 
                    name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.insert()
    return blog
  
# manage_blogs 修改日志： POST /api/blogs/blog_id
@post('/api/blogs/{blog_id}')
async def api_blogs_update(blog_id, request, *, name, summary, content):
    check_admin(request)
    blog = await Blog.find(blog_id)
    if not name or not name.strip():
        raise APIValueError('name', 'blog name can\'t be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'blog summary can\'t be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'blog content can\'t be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

# manage_blogs 删除日志： POST /api/blogs/blog_id/delete
@post('/api/blogs/{blog_id}/delete')
async def api_blogs_delete(blog_id, request):
    check_admin(request)
    blog = await Blog.find(blog_id)
    await blog.delete()
    return dict(id=blog_id)
    