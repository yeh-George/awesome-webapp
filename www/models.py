# -*- coding:utf-8 -*-

'''
Models for user, blog, comment
'''

import time, uuid

from orm import Model, StringField, TextField, IntegerField, FloatField, BooleanField

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
    

class User(Model):
    __table__ = 'users'
    
    id = StringField(primary_key=True, default=next_id)
    email = StringField()
    passwd = StringField()
    admin = BooleanField()
    name = StringField()
    image = StringField()
    created_at = FloatField(default=time.time)
    
class Blog(Model):
    __table__ = 'blogs'
    
    id = StringField(primary_key=True, default=next_id)
    name = StringField()
    summary = StringField()
    content = TextField()
    created_at = FloatField(default=time.time)
    user_id = StringField()
    user_name = StringField()
    user_image = StringField()
    
class Comment(Model):
    __table__ = 'comments'
    
    id = StringField(primary_key=True, default=next_id)
    content = StringField()
    created_at = FloatField(default=time.time)
    blog_id = StringField()
    user_id = StringField()
    user_name = StringField()
    user_image = StringField()
    
    
    
    
    
    
    
    