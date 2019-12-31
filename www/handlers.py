# -*- coding: utf-8 -*-
import asyncio

from aiohttp import web

from coroweb import get, post

from models import User

@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }