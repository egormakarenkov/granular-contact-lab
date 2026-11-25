"""Local service and bounded experiment workers. No external AI calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace, fields
from pathlib import Path
from threading import Lock, Event
import csv, gzip, hashlib, io, json, math, os, platform, sys, time, uuid, zipfile
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from .physics import Settings, State, prepare, simulate, force_range, contact_matrix

ROOT=Path(os.environ['GRANULAR_LAB_HOME']).resolve() if os.environ.get('GRANULAR_LAB_HOME') else Path(__file__).resolve().parents[1]
DATA=ROOT/'experiments';DATA.mkdir(exist_ok=True)
app=FastAPI(title='Granular Lab',docs_url=None,redoc_url=None)
app.add_middleware(GZipMiddleware,minimum_size=1000)
POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='granular-worker')
JOBS={};RUNS={};CACHE={};LOCK=Lock()


@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin','')
    port=os.environ.get('GRANULAR_LAB_PORT','8765')
    if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
        return Response('This application accepts local-origin requests only.',status_code=403)
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost','testserver'):
        return Response('Local host required',status_code=403)
    if int(request.headers.get('content-length','0'))>20_000_000:
        return Response('Request too large',status_code=413)
    return await call_next(request)


def config(d):
    try:
        allowed={f.name for f in fields(Settings)}
        if set(d)-allowed:raise ValueError('Unknown model setting')
        for k in ('width','intruder_x','intruder_y','intruder_radius'):
            if k=='width' and k in d and d[k]!=2.7:raise ValueError('Container width is fixed at 2.7')
        if not .1<=float(d.get('intruder_radius',.32))<=.6:raise ValueError('Intruder radius out of range')
        if not .4<=float(d.get('intruder_x',1.35))<=2.3 or not .2<=float(d.get('intruder_y',.78))<=4:
            raise ValueError('Intruder position out of range')
        c=Settings(**d)
        if not isinstance(c.particles,int) or not isinstance(c.seed,int):raise ValueError('Particle count and seed must be integers')
        if c.dt<.003:raise ValueError('Interactive jobs require dt ≥ .003')
        if c.duration/c.dt>1000:raise ValueError('Job exceeds 1000 time steps; shorten duration or increase dt')
        return c
    except (ValueError,TypeError) as e:raise HTTPException(422,str(e))


def public(job):
    clean=job.copy();clean.pop('cancel',None);return clean
def getrun(rid):
    if rid in RUNS:return RUNS[rid]
    if len(rid)!=12 or not rid.isalnum():raise HTTPException(404,'Experiment not found')
    p=DATA/f'{rid}.json.gz'
    if not p.exists():p=ROOT/'examples'/'runs'/f'{rid}.json.gz'
    if not p.exists():raise HTTPException(404,'Experiment not found')
    return json.loads(gzip.decompress(p.read_bytes()))


def persist(run):
    rid=uuid.uuid4().hex[:12];run['id']=rid;run['created']=time.time()
    run['initial_hash']=hashlib.sha256(json.dumps(run['initial'],sort_keys=True).encode()).hexdigest()[:16]
    run['versions']={'python':platform.python_version(),'numpy':np.__version__,'method':2}
    import osqp,scipy
    run['versions'].update(osqp=osqp.__version__,scipy=scipy.__version__)
    tmp=DATA/f'{rid}.tmp'
    tmp.write_bytes(gzip.compress(json.dumps(run,allow_nan=False).encode()))
    tmp.replace(DATA/f'{rid}.json.gz')
    RUNS[rid]=run
    while len(RUNS)>10:RUNS.pop(next(iter(RUNS)))
    return {'id':rid,'settings':run['settings'],'metrics':run['metrics'],'initial_hash':run['initial_hash']}


def worker(jid,payload):
    job=JOBS[jid];job.update(status='running',message='Preparing the same packed bed for every branch')
    try:
        c=config(payload.get('settings',{}))
        mode=payload.get('mode','run')
        key=(c.particles,c.seed,c.aspect,c.angle,c.gravity,c.damping)
        if payload.get('fork'):
            origin=getrun(payload['fork']);idx=int(payload.get('frame',0))
            if not 0<=idx<len(origin['frames']):raise ValueError('Fork frame out of range')
            frame=origin['frames'][idx]
            if c.particles!=len(origin['r']):
                raise ValueError('Fork geometry must match its original experiment')
            shape=frame['intruder']
            c=replace(c,intruder_x=shape['x'],intruder_y=shape['y'],
                      intruder_radius=math.sqrt(shape['a']*shape['b']),
                      aspect=math.sqrt(shape['a']/shape['b']),angle=shape['angle'])
            initial=State(np.array(frame['q']),np.array(origin['r']),np.array(frame['v'])) if idx else State.load(origin['initial'])
        elif key in CACHE:initial=CACHE[key].copy()
        elif key==(36,2027,1.0,0.0,1.0,1.0) and (ROOT/'examples'/'default-packing.json').exists():
            initial=State.load(json.loads((ROOT/'examples'/'default-packing.json').read_text()))
            CACHE[key]=initial.copy()
        else:
            initial,_=prepare(c,lambda p:job.update(progress=.15*p),job['cancel'].is_set)
            CACHE[key]=initial.copy()
            if len(CACHE)>6:CACHE.pop(next(iter(CACHE)))
        if job['cancel'].is_set():raise InterruptedError()
        variants=[]
        if mode=='compare':
            if set(payload.get('alternative',{}))-{'waveform','epsilon','amplitude','frequency','stroke','duration','dt'}:
                raise ValueError('Alternative control cannot change packing geometry')
            variants=[('A · baseline',c),('B · alternative',replace(c,**payload.get('alternative',{'waveform':'translate'})))]
            for _,cc in variants:config(asdict(cc))
        elif mode=='map':
            amps=payload.get('amplitudes',[0,.025,.05]);freqs=payload.get('frequencies',[.5,1,2])
            if not 1<=len(amps)*len(freqs)<=16:raise ValueError('Map is limited to 16 experiments')
            variants=[(f'A={a:.3f}, f={f:.2f}',replace(c,waveform='sway',amplitude=float(a),frequency=float(f))) for a in amps for f in freqs]
            for _,cc in variants:config(asdict(cc))
        elif mode=='search':
            # Every candidate has the same translation, duration and amplitude
            # bound; no stationary/shrinking-to-escape candidate can win.
            if c.stroke<=0:raise ValueError('Search requires a positive translation stroke')
            if c.waveform=='hold':raise ValueError('Search requires a translating baseline; choose pulse, orbit or translation')
            c=replace(c,waveform='translate',amplitude=0.)
            variants=[('Baseline translation',c)]
            for amplitude in (.01,.02,.03):
                for frequency in (.5,1.,2.):
                    if amplitude<=config(payload.get('settings',{})).amplitude+1e-12:
                        variants.append((f'Sway A={amplitude:g}, f={frequency:g}',
                                         replace(c,waveform='sway',amplitude=amplitude,frequency=frequency)))
        elif mode=='refine':variants=[('Original timestep',c),('Half timestep',replace(c,dt=c.dt/2))]
        elif mode=='probe':
            # Prescribed-displacement resistance, explicitly not a freely
            # responding intruder under a probe force.
            variants=[('Small displacement probe',replace(c,waveform='translate',stroke=.025,amplitude=0,duration=.5))]
        else:variants=[('Experiment',c)]
        results=[]
        for i,(label,cc) in enumerate(variants):
            job.update(message=f'{label} · {i+1}/{len(variants)}')
            try:
                run=simulate(cc,initial,lambda p:job.update(progress=.15+.8*(i+p)/len(variants)),job['cancel'].is_set)
                if payload.get('fork'):
                    run['fork_origin']={'run':payload['fork'],'frame':int(payload.get('frame',0)),
                                        'time':origin['frames'][int(payload.get('frame',0))]['t']}
                entry=persist(run);entry['label']=label;entry['status']='solved';results.append(entry)
            except InterruptedError:raise
            except Exception as e:
                if mode in ('map','search'):results.append({'label':label,'settings':asdict(cc),'status':'failed','error':str(e)})
                else:raise
            job['results']=list(results)
        if mode=='search':
            good=[r for r in results if r['status']=='solved']
            if not good:raise RuntimeError('No candidate met numerical checks')
            best=min(good,key=lambda z:z['metrics']['positive_work'])
            job['best']=best['id'];job['objective']='Least positive actuator work among tested rigid motions; same stroke, duration, amplitude bound.'
            job.update(message='Checking selected motion on two additional packing seeds')
            validations=[]
            bestc=Settings(**best['settings'])
            refined=[]
            for label,cc in [('baseline',replace(c,dt=c.dt/2)),('selected',replace(bestc,dt=c.dt/2))]:
                try:refined.append({'label':label,**persist(simulate(cc,initial,cancel=job['cancel'].is_set))})
                except InterruptedError:raise
                except Exception as e:refined.append({'label':label,'error':str(e)})
            job['refinement']=refined
            for seed in (c.seed+1,c.seed+2):
                if job['cancel'].is_set():raise InterruptedError()
                vc=replace(c,seed=seed);st,_=prepare(vc,cancel=job['cancel'].is_set)
                pair=[]
                for label,cc in [('baseline',vc),('selected',replace(bestc,seed=seed))]:
                    try:pair.append({'label':label,**persist(simulate(cc,st,cancel=job['cancel'].is_set))})
                    except InterruptedError:raise
                    except Exception as e:pair.append({'label':label,'error':str(e)})
                validations.append({'seed':seed,'runs':pair})
            job['validation']=validations
        job.update(status='complete',progress=1.,message='Computed and saved',results=results)
    except InterruptedError:job.update(status='cancelled',message='Cancelled; completed results remain available')
    except Exception as e:job.update(status='failed',error=str(e),message='Experiment stopped; inspect the reported numerical failure')
    finally:
        folder=DATA/'jobs';folder.mkdir(exist_ok=True)
        (folder/f'{jid}.json').write_text(json.dumps(public(job),allow_nan=False),encoding='utf-8')


@app.get('/api/health')
def health():return {'status':'ready','model':'frictionless normal-contact QP','version':'1.0',
                     'home':str(ROOT),'portable':bool(getattr(sys,'frozen',False))}

@app.get('/api/default')
def default_run():
    marker=ROOT/'examples'/'default-run-id.txt'
    if marker.exists():return getrun(marker.read_text().strip())
    raise HTTPException(404,'No bundled experiment')

@app.get('/api/jobs')
def list_jobs():
    recent={}
    folder=DATA/'jobs'
    if folder.exists():
        for p in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            try:
                j=json.loads(p.read_text(encoding='utf-8'));j.setdefault('created',p.stat().st_mtime);recent[j['id']]=j
            except (ValueError,KeyError):continue
    recent.update({k:public(v) for k,v in list(JOBS.items())})
    return sorted(recent.values(),key=lambda j:j.get('created',0),reverse=True)

@app.post('/api/jobs')
def start(payload:dict):
    config(payload.get('settings',{}))
    with LOCK:
        if sum(j['status'] in ('running','queued') for j in JOBS.values())>=3:
            raise HTTPException(429,'Three jobs are already queued; finish or cancel one first')
        jid=uuid.uuid4().hex[:12]
        JOBS[jid]={'id':jid,'created':time.time(),'status':'queued','progress':0.,'message':'Queued','cancel':Event(),'results':[],'mode':payload.get('mode','run')}
        POOL.submit(worker,jid,payload)
    return public(JOBS[jid])

@app.get('/api/jobs/{jid}')
def job_status(jid:str):
    if jid not in JOBS:raise HTTPException(404,'Job not found')
    return public(JOBS[jid])

@app.post('/api/jobs/{jid}/cancel')
def cancel(jid:str):
    if jid not in JOBS:raise HTTPException(404,'Job not found')
    JOBS[jid]['cancel'].set();return {'status':'cancellation requested'}

@app.get('/api/runs')
def list_runs():
    summaries=[]
    paths={p.name:p for p in (ROOT/'examples'/'runs').glob('*.json.gz')}
    paths.update({p.name:p for p in DATA.glob('*.json.gz')})
    for p in sorted(paths.values(),key=lambda x:x.stat().st_mtime,reverse=True)[:40]:
        r=getrun(p.name.split('.')[0])
        summaries.append({k:r[k] for k in ('id','settings','metrics','initial_hash','created')})
    return summaries

@app.get('/api/runs/{rid}')
def read_run(rid:str):return getrun(rid)

@app.get('/api/runs/{rid}/frame/{idx}/matrix')
def matrix(rid:str,idx:int):
    r=getrun(rid)
    if not 0<=idx<len(r['frames']):raise HTTPException(404,'Frame not found')
    f=r['frames'][idx];zs=[z for z in f['contacts'] if z['status']!='open']
    G=contact_matrix(zs,2*len(r['r']));sing=np.linalg.svd(G,compute_uv=False)
    tol=max(G.shape)*np.finfo(float).eps*(float(sing[0]) if len(sing) else 1)*100
    rank=int(np.sum(sing>tol))
    return {'G':G.tolist(),'singular_values':sing.tolist(),'rank':rank,'nullity':G.shape[1]-rank,'tolerance':tol,
            'note':'Equality nullity of touching-contact Jacobian; unilateral feasible velocities form a cone. Not a fluidization criterion.'}

@app.get('/api/runs/{rid}/frame/{idx}/force/{contact}')
def ambiguity(rid:str,idx:int,contact:int):
    r=getrun(rid)
    if not 0<=idx<len(r['frames']):raise HTTPException(404,'Frame not found')
    try:return force_range(r['frames'][idx],contact)
    except ValueError as e:raise HTTPException(422,str(e))


@app.get('/api/runs/{rid}/export/{kind}')
def export(rid:str,kind:str):
    r=getrun(rid)
    if kind=='json':return Response(json.dumps(r),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="granular-{rid}.json"'})
    def csvdata():
        out=io.StringIO();writer=csv.writer(out)
        writer.writerow(['time','reaction_x','reaction_y','signed_actuator_work','positive_actuator_work','max_penetration','balance_residual','complementarity_residual'])
        for f in r['frames']:writer.writerow([f['t'],*f['reaction'],f['work'],f['positive_work'],f['penetration'],f['balance'],f['complementarity']])
        return out.getvalue()
    if kind=='csv':return Response(csvdata(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="granular-{rid}.csv"'})
    if kind=='bundle':
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('experiment.json',json.dumps(r));z.writestr('metrics.csv',csvdata())
            z.writestr('requirements.txt',(ROOT/'requirements.txt').read_text())
            for name in ('__init__.py','physics.py'):z.writestr('granular/'+name,(ROOT/'granular'/name).read_text())
            z.writestr('reproduce.py','import json\nfrom granular.physics import Settings,State,simulate\nr=json.load(open("experiment.json"))\ns=simulate(Settings(**r["settings"]),State.load(r["initial"]))\njson.dump(s,open("reproduced.json","w"))\nprint(s["metrics"])\n')
            z.writestr('README.txt','Install requirements, then run python reproduce.py in this folder. The exact initial arrays are included. Floating-point variation across platforms is possible.\n'+json.dumps(r['versions']))
        return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="granular-{rid}-reproduce.zip"'})
    raise HTTPException(404,'Unknown export format')


UI=ROOT/'ui'/'dist'
if UI.exists():app.mount('/',StaticFiles(directory=UI,html=True),name='ui')
