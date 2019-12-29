import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, datetime

from aiohttp import web

import orm
from coroweb import add_routes, add_static

from jinja2 import Environment, FileSystemLoader 

#源码里对于middleware__factory的处理
#for factory in app._middlewares: 
#     handler = yield from factory(app, handler)
# resp = yield from handler(request)
async def logger_factory(app, handler):
    async def logger_handler(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))
    return logger_handler
    
async def response_factory(app, handler):   
    async def response_handler(request):
        logging.info('response handler...')
        resp = await handler(request)
        # 处理resp
        if isinstance(resp, web.StreamResponse):
            return resp
        if isinstance(resp, bytes):
            resp = web.Response(body=resp)
            resp.conten_type = 'application/octet-stream'
            return  resp
        if isinstance(resp, str):
            if resp.startswith('redirect:'):
                #@get('/manage') return 'redirect:/manage/comments'
                return web.HTTPFound(resp[9:])
            resp = web.Response(body=resp.encode('utf-8'))
            resp.conten_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(resp, dict):
            template = resp.get('__template__')
            if template is None:
                #@get('/api/users') return dict(page=p, users=users)
                resp = web.Response(body=json.dumps(resp, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                #@get('/manage/comments') 
                #   return {
                #      '__template__': 'manage_comments.html',
                #      'page_index': get_page_index(page)
                #   }
                resp = web.Response(body=app['__jinja2_env__'].get_template(template).render(**resp).encode('utf-8'))
                resp.conten_type = 'text/html;charset=utf-8'
                return resp
        # 返回状态 200 ok
        if isinstance(resp, int) and resp >= 100 and resp < 600:
            return web.Response(resp)
        if isinstance(resp, tuple) and len(resp) == 2:
            t, m = r 
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        #default:
        #@get('/api/blogs/{id}') return blog
        resp = web.Response(body=str(resp).encode('utf-8'))
        resp.conten_type = 'text/plain;charset=utf-8'
        return resp 
    return response_handler
    
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    # template path 
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    # filters
    filters = kw.get('filters', None)
    if filters is not None:
        for name, filter in filters.items():
            env.filters[name] = filter
    app['__jinja2_env__'] = env
  
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)
 
async def init(loop):
    await orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_static(app)
    add_routes(app, 'handlers')
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server start at http://127.0.0.1:9000...')
    return srv
    
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()