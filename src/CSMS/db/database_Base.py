from sqlalchemy.orm import declarative_base
from sqlalchemy.inspection import inspect

Base = declarative_base()

class CustomBase(Base):
    """Base extender
    In sqlalchemy we can init an obj and pass a relation throw passing another object in the init
    This extender allows to also pass a dict with the correct fields for creating that object
    """
    __abstract__ = True

    def __init__(self, **kwargs):

        for arg in kwargs:
            if arg in self.__mapper__.relationships.keys():
                rel = self.__mapper__.relationships[arg] 

                if rel.uselist:                    
                    o = [rel.mapper.class_(**d_l) if not isinstance(d_l, rel.mapper.class_) else d_l for d_l in kwargs[arg]]
                else:
                    if isinstance(kwargs[arg], rel.mapper.class_):
                        continue
                    o = rel.mapper.class_(**kwargs[arg])
                
                kwargs[arg] = o


        super().__init__(**kwargs)

    """
    OLD
    {
        "relationships": {
            "evse" : {
                "describe":False,
                "relationships" : {
                    "connector":{}
                }
            }
        }
    }

    NEW
    {
        "describe":False,
        "evse" : {
            "connector:{}
        }
    }
    """
    
    def get_dict_obj(self, mode={}, **kwargs):
        
        mode_copy={**mode}
        describe = mode_copy.pop("describe") if "describe" in mode_copy else True

        if describe:
            base_dict= { attr:value 
                for attr, value in self.__dict__.items()
                if not attr.startswith("_") and attr not in self.__mapper__.relationships.keys() }
        else:
            primary_key_name = inspect(self.__class__).primary_key[0].name 
            base_dict = {primary_key_name : self.__dict__[primary_key_name]}


        for rel_name, rel_mode in mode_copy.items():
            if rel_name in self.__mapper__.relationships.keys():

                rel = self.__mapper__.relationships[rel_name] 
                obj = getattr(self, rel_name)

                if rel.uselist:
                    base_dict[rel_name] = [o.get_dict_obj(rel_mode, **kwargs) for o in obj]
                else:
                    base_dict[rel_name] = obj.get_dict_obj(rel_mode, **kwargs) if obj is not None else None
        
        return base_dict
