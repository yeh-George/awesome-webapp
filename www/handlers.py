# -*- coding: utf-8 -*-
import asyncio

from aiohttp import web

from coroweb import get, post

from models import User, Blog

@get('/')
async def index(request):
    blogs = await Blog.findAll()
    print(blogs)
    return {
        '__template__': 'index.html',
        'blogs': blogs
    }