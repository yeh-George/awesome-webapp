﻿# -*- coding: utf-8 -*-
import asyncio, hashlib, json, time, logging, re

from aiohttp import web

from coroweb import get, post

from models import User, Blog, Comment, next_id

from config import configs
import markdown2

from errors import APIError, APIValueError, APIResourceNotFoundError

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
    
#   登录页:    GET /signin
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
    
#后端API
# 登录signin验证用户
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
  
# 注册register用户 / 创建create用户
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1_PASSWD = re.compile(r'^[0-9a-f]{40}$')

@post('/api/user/register')
async def api_user_register(*, email, name, passwd):
    #check 
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
     
    
    
        
    
    
    
    
    
    
    
    
    