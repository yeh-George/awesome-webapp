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
            #���overrider����k����ô�ж����v�ǲ���dict���ǵĻ����ٵݹ����merge����
            if isinstance(v, dict):
                r[k] = merge(v, overrider[k])
            else:
                r[k] = overrider[k]
        else:
            r[k] = v
    return r
 
#toDict��Ϊ��֧��x.y, ������Ҳ�ǿ��Եģ� 
def toDict(d):
    D = Dict()
    for k, v in d.items():
        # d.item()��v�����dict��ݹ飬֪������dict����ֵ��D{k}
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D 
    
configs = config_default.configs

# configsĬ��Ϊconfig_default.configs
#���config_override���ڣ���merge()
try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)           