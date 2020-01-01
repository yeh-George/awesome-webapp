import logging;
import asyncio
import aiomysql

async def create_pool(loop, **kw):
    logging.info('create a mysql connnection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw.get('user'),
        password=kw.get('password'),
        db=kw.get('db'),
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )    
    
async def query(sql, args, size=None):
    ''' 
        SELECT rowname FROM tablename WHERE 
    '''
    logging.info('SELECT SQL: %s args: %s' % (sql, args))
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else: 
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs

async def execute(sql, args, autocommit=True):
    '''
        INSERT INTO tablename [rowname] VALUES (,,);
        UPDATE tablename SET rouname=value WHERE 
        DELETE FROM tablename WHERE      
    '''
    logging.info('EXECUTE SQL: %s args: %s' % (sql, args))
    global __pool
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected

def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ','.join(L)
  
  
class Field(object):
    
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
        
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class_.__name__, self.column_type, self.name)
        

class StringField(Field):
    
    def __init__(self, name=None, column_type='varchar(100)', primary_key=False, default=None):
        super().__init__(name, column_type, primary_key, default)
    
    
class TextField(Field):
    
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)
    
    
class IntegerField(Field):
    
    def __init__(self, name=None, primary_key=False, default=0):
        super.__init__(name, 'bigint', primary_key, default)
    
    
class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

    
class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class ModelMetaclass(type):
    
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        mappings = dict()
        fields = []
        primaryKey = None
        
        # mappings = fields + primaryKey
        for k, v in attrs.items():
            if isinstance(v, Field):
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise StandardError('Duplicate primary key for mappings[ %s ]' % k)
                    primaryKey = (k) 
                else:
                    fields.append(k)
        if not primaryKey:
            raise StandardError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        
        attrs['__mappings__'] = mappings #保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        #SQL
        escaped_primaryKey = '`%s`' % primaryKey
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__select__'] = 'SELECT %s, %s FROM %s' % (escaped_primaryKey, ', '.join(escaped_fields), tableName) 
        attrs['__insert__'] = 'INSERT INTO %s (%s, %s) VALUES (%s)' % (tableName, escaped_primaryKey, ', '.join(escaped_fields), create_args_string(len(fields) + 1))
        attrs['__update__'] = 'UPDATE %s SET %s WHERE %s=?' % (tableName, ', '.join(map(lambda f: ' %s=?' % f, escaped_fields)), escaped_primaryKey)
        attrs['__delete__'] = 'DELETE FROM %s WHERE %s=?' % (tableName, escaped_primaryKey)
        return type.__new__(cls, name, bases, attrs)
        
        
class Model(dict, metaclass=ModelMetaclass):
    
    def __init__(self, **kw):
        super().__init__(**kw)
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)
            
    def __setattr__(self, key, value):
        self[key] = value
    
    def getValue(self, key):
        value = getattr(self, key ,None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                # default()是因存在default=time.time，所以在使用getValue的时候再计算
                # default=next_id, 创建任务是需要uid=next_id()直接传入，所以这一段用处不大
                value = field.default() if callable(field.default) else field.default 
                logging.debug('using default value: %s for key: %s' % (value, key))
                setattr(self, key, value)
        return value
     
    @classmethod
    async def find(cls, pk):
        'find object by primary key or email'
        "'SELECT %s, %s FROM %s' % (primaryKey, ', '.join(fields), tableName) "
        sql = '%s where %s=?' % (cls.__select__, cls.__primary_key__)
        rs = await query(sql, [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])
    
    @classmethod
    async def findNumber(cls, column_name, where=None, args=None):
        sql = ['SELECT COUNT(%s) AS num FROM %s' % (column_name, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await query(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['num']
        
    @classmethod
    async def findAll(cls, where=None, args=None,**kw):
        ' find all objects by where clause.'
        "'SELECT %s, %s FROM %s' % (primaryKey, ', '.join(fields), tableName) "
        sql = [cls.__select__]
        if where:
            sql.append('where %s' % where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', 'created_at desc')
        if orderBy:
            sql.append('order by %s' % orderBy)
        limit = kw.get('limit', None)
        if limit:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % limit)
        rs = await query(' '.join(sql), args)
        return [cls(**r) for r in rs]
        
    async def insert(self):
        "'INSERT INTO %s (%s, %s) VALUES (%s)' "
        values = [self.getValue(self.__primary_key__)]
        values.extend(list(map(self.getValue, self.__fields__)))
        affected = await execute(self.__insert__, values)
        if affected != 1:
            logging.warn('failed to insert record: affected rows: %s' % affected)
        
    async def update(self):
        'UPDATE %s SET %s WHERE %s=?'
        values = list(map(self.getValue, self.__fields__))
        values.append(self.getValue(self.__primary_key__))
        affected = await execute(self.__update__, values)
        if affected != 1:
            logging.warn('failed to update record by primary key.')
        
    async def delete(self):
        'DELETE FROM %s WHERE %s=?'
        affected = await execute(self.__delete__, self.getValue(self.__primary_key__))
        if affected != 1:
            logging.warn('failed to delete record by primary key.')
        
        
        
        
        
  
    
    
    
        















                
    