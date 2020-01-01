import asyncio, functools
import logging

import inspect
from aiohttp import web
from urllib import parse # https://www.jianshu.com/p/fb1010c77bda

import os 

from errors import APIError

# 定义handlers的@get @post
def get(path):
    '''
    Decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__path__ = path
        return wrapper
    return decorator
        
def post(path):
    '''
    Decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__path__ = path
        return wrapper
    return decorator
    
# 用RequestHandler获取request的数据，传入handler中    
# 定义RequestHandler,主要是接受request传来的数据json(),post(),query_string, match_info，在通过inspect获取handler的参数组装kw，最后_func(**kw)
# required_kw KEYWORD_ONLY中的default=empty 
# kw_only  KEYWORD_ONLY,default=empty or  aValue
# var_kw VAR_KEYWORD
# request
# 关于inspect.Signature,Paramters的分析，参照https://blog.csdn.net/weixin_35955795/article/details/53053762      
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)
        
def get_kw_only_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_kw_only_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
    
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found =False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            #request之后的参数必须不是位置参数POSITIONAL，为什么这么设计呢？（因为，这些参数可能不是必须的
            raise ValueError('request paramter must be the last named parameter in function: %s %s' % (fn.__name__, str(sig)))
    return found
    

class RequestHandler(object):
    
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_kw_only_args = has_kw_only_args(fn)
        self._kw_only_args = get_kw_only_args(fn)
        self._required_kw_args = get_required_kw_args(fn)
        
    async def __call__(self, request):
        kw = None
        # 如果fn有关键字参数：
        if self._has_var_kw_arg or self._has_kw_only_args or self._required_kw_args:
            # GET 取出querystring中的参数
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
            # POST 通过content_type判断类型取出参数
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBasRequest('JSON body must be object.')
                    kw = params 
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Upsupported Content-Type: %s' % request.content_type)
        if kw is None:
            # 取出path中{}中的数值，例如@get('/blog/{id}')
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._kw_only_args:
                copy = dict()
                for name in self._kw_only_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warn('Duplicate arg name in named arg and kw arg: %s' % k)
                kw[k] = v 
        if self._has_request_arg:
            kw['request'] = request
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try: 
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)
 
# 添加static文件 js，css 
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s %s' % ('/static/', path))

# 添加route        
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__path__', None)
    if method is None or path is None:
        raise ValueError('@get or @post not define in %s' % fn.__name__)
    if not asyncio.iscoroutine(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s %s' % (method, path, fn.__name__))
    
    app.router.add_route(method, path, RequestHandler(app, fn))
    # path: 通过request.match_info，可以导入参数
    # RequestHandler(app, fn) = handler: 之后调用的将是handler(request)也就是RequestHander(request)，即RequestHandler.__call__(request)，
    # 会自动获取request中参数形成kw，在调用fn(**kw)
    
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__path__', None)
            if method and path:
                add_route(app, fn)