# -*- coding: utf-8 -*-
import asyncio

from aiohttp import web

from coroweb import get, post

@get('/')
def index(request):
    return web.Response(body=b'Awesome')