"""Build a source-first inventory from explicit application ownership decisions."""
from observer_runtime.code_structure import scan
from observer_runtime.implementation_coverage import functional_symbols
from observer_runtime.observation_scope import endpoint_paths, observer_route

HTTP_GROUPS={
    'sessions':('账号与登录','session login logout'),
    'file_access':('文件列表与下载','files upload download review'),
    'messages':('消息中心','messages read_message'),
    'interface':('工作台与页面','index favicon health asset'),
}


def make_inventory(root, code):
    index=scan(root,code)
    assert not index['errors'],index['errors']
    symbols=functional_symbols(index)
    features=[
        {'id':'upload','label':'上传暂存与通知','business_node':'upload',
         'nodes':['upload','notify','pending'],'sources':['app/service.py::ReviewService.upload'],
         'parameters':[], 'cases':[
             {'case':'upload','node':'upload','phase':'commit','values':[
                 {'direction':'in','field':'filename','path':['saved_filename']},
                 {'direction':'in','field':'note','path':['saved_note']},
                 {'direction':'in','field':'size','path':['saved_size']},
                 {'direction':'out','field':'state','path':['status']}]},
             {'case':'upload','node':'notify','phase':'commit'},
             {'case':'upload','node':'pending','phase':'wait'}]},
        {'id':'review','label':'通过与驳回','business_node':'review',
         'nodes':['review','review_guard'],'sources':['app/service.py::ReviewService.review'],
         'parameters':[], 'cases':[
             {'case':'approve','node':'review','phase':'commit','values':[
                 {'direction':'in','field':'entity','path':['saved_id']},
                 {'direction':'in','field':'note','path':['saved_review_note']},
                 {'direction':'out','field':'state','path':['status']}]},
             {'case':'reject','node':'review','phase':'commit','values':[
                 {'direction':'out','field':'state','path':['status']}]},
             {'case':'approve','node':'review_guard','phase':'decision'},
             {'case':'forbidden','node':'review_guard','phase':'decision'}]},
    ]
    for feature in features:
        source=feature['sources'][0]
        for parameter in symbols[source]['parameters']:
            name=parameter['name']
            if name=='self':
                continue
            field={'content':'size','ident':'entity'}.get(name,name)
            policy='derived' if name in ('actor','content') else 'value'
            disposition={'source':source,'name':name,'node':feature['business_node'],
                         'direction':'in','field':field,'policy':policy}
            if policy=='derived':
                disposition['reason']='主体以实际账号ID表示' if name=='actor' else '文件内容以实际字节长度表示，不记录文件正文'
            feature['parameters'].append(disposition)
    nodes=[]
    for node_id,(label,names) in HTTP_GROUPS.items():
        entries=['integrations/server.py::create_app.'+name for name in names.split()]
        for source in entries:
            assert source in symbols,'Missing declared HTTP implementation: '+source
        parameters=[]
        cases=[]
        for source in entries:
            for parameter in symbols[source]['parameters']:
                name=parameter['name']
                parameters.append({'source':source,'name':name,'node':node_id,'direction':'in',
                    'field':'request' if name=='request' else 'arguments','policy':'derived',
                    'reason':'实际HTTP方法和路径摘要；请求正文、密码和cookie不写入观测' if name=='request'
                             else '实际路径和查询参数的JSON表示；未提供的可选查询参数保持缺失'})
            phase=source.rsplit('.',1)[-1]
            cases.append({'case':'http','node':node_id,'phase':phase,
                'values':[{'direction':'out','field':'status','path':['http_codes',phase]}]})
        features.append({'id':'http-'+node_id,'label':label,'business_node':node_id,
                         'nodes':[node_id],'sources':entries,'parameters':parameters,'cases':cases})
        first=symbols[entries[0]]
        nodes.append({'id':node_id,'label':label,'kind':'action','layer':'business','summary':label,
            'source':{'path':first['path'],'symbol':first['symbol']},'basis_fields':['param_version','epoch'],
            'capture':{'in':{'request':'string','arguments':'string'},'out':{'status':'number'}}})
    classified={source for f in features for source in f['sources']}
    support={}
    excluded={}
    for sid,symbol in symbols.items():
        if sid in classified:
            continue
        path,name=symbol['path'],symbol['symbol'].split('.')[-1]
        routes=endpoint_paths(symbol)
        if routes and all(observer_route(p) for p in routes):
            excluded[sid]={'category':'observer','routes':routes,'reason':'图展示与记录控制，不是业务操作'}
        elif name in ('__init__','__enter__','__exit__'):
            excluded[sid]={'category':'construction','reason':'对象构造；其业务效果由所属功能和真实场景验证'}
        elif path in ('integrations/bo_observer.py','app/ports.py') or name in ('bo_trace','bo_view'):
            excluded[sid]={'category':'observer','reason':'可选观测适配或失败隔离的中立接口，不执行领域规则'}
        elif path=='bo_stategraph/query.py':
            excluded[sid]={'category':'observer','reason':'读取已存在的状态快照；真实迁移函数仍保留业务映射'}
        else:
            assert not symbol.get('entrypoints'),'Unowned application endpoint: '+sid
            if path=='app/storage.py':
                owner='sessions' if name in ('password_hash','authenticate') else 'upload'
            elif path=='app/service.py':
                owner='messages' if name in ('messages','read_message') else 'file_access' if name in ('detail','list_files') else 'upload'
            elif path.startswith('bo_stategraph/'):
                owner='review'
            else:
                owner='sessions' if name=='user' else 'interface'
            support[sid]={'node':owner,'reason':'该功能调用的实际辅助实现；保留源码节点与静态调用关系'}
    return {'schema':'bo-implementation/v1','features':features,'support':support,'excluded':excluded},nodes
