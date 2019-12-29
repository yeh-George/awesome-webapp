import asyncio
import orm
from models import User, Blog, Comment

async def test(loop):
    await orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')

    #u = User(name='Test12', email='test12@example.com', passwd='1234567890', image='about:blank')
    #await u.insert()
    u = await User.findAll()
    print(u)
    u = await User.find('00157724757983438e36e85bf3745b0907429aacdb0571c000')
    print(u)
    u.name = 'Test12 update time2'
    await u.update()
    u = await User.find('00157724757983438e36e85bf3745b0907429aacdb0571c000')
    print(u)
    await u.delete()
    u = await User.findAll()
    print(u)
    

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.run_forever()
