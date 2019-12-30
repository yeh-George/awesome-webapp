'''
Configuration merge config_default with config_override.
'''

import config_default

class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        super().__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute key '%s'" % key)
            
    def __setattr__(self, key, value):
        self[key] = value
        
def merge(defaultor, overrider):
    r = {}
    for k, v in defaultor.items():
        if k in overrider:
            #如果overrider存在k，那么判断这个v是不是dict，是的话，再递归调用merge（）
            if isinstance(v, dict):
                r[k] = merge(v, overrider[k])
            else:
                r[k] = overrider[k]
        else:
            r[k] = v
    return r
 
#toDict是为了支持x.y, 不进行也是可以的？ 
def toDict(d):
    D = Dict()
    for k, v in d.items():
        # d.item()的v如果是dict则递归，知道不是dict，赋值给D{k}
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D 
    
configs = config_default.configs

# configs默认为config_default.configs
#如果config_override存在，则merge()
try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)           