"""RecordPrep-owned shared Pi + active classification connection, not OCR."""
from ._model_store import serve
from ._model_schema import raw,pi_slot,direct_slot
from decimal import Decimal

def boolean(value,default=False):
    if isinstance(value,(bool,int,float,Decimal)): return bool(value)
    if isinstance(value,str):
        if value.strip().lower() in ('1','true','yes','on'): return True
        if value.strip().lower() in ('0','false','no','off'): return False
    return default

def resolve():
    from .paths import application_config_path,pi_settings_path
    paths={'config':application_config_path(),'pi':pi_settings_path()}; data=raw(paths['config'])
    profile={k:str(data.get('classifier_'+k) or '').strip() for k in ('api_url','model_id','api_key')}
    profile['disable_reasoning']=(boolean(data['classifier_disable_reasoning']) if 'classifier_disable_reasoning' in data else not boolean(data.get('classifier_thinking_enabled'),True))
    def replace(raw,target): raw['classifier_model_id']=target['model']
    return paths,[pi_slot(paths),direct_slot('classification','config',profile,replace,image=True,local=boolean(data.get('classifier_local_vision_enabled')))]

def main(): return serve('recordprep',resolve)
