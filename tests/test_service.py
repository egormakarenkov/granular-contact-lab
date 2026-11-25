import io,time,zipfile,json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from granular.server import app
import granular.server as service

client=TestClient(app)

@pytest.fixture(autouse=True)
def isolated_experiments(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'DATA',tmp_path)

def finish(payload):
    res=client.post('/api/jobs',json=payload)
    assert res.status_code==200,res.text
    jid=res.json()['id']
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        job=client.get('/api/jobs/'+jid).json()
        if job['status'] not in ('running','queued'):
            assert job['status']=='complete',job
            return job
        time.sleep(.1)
    raise AssertionError('Worker timeout')

def test_compare_exports_matrix_and_force_bounds():
    job=finish({'mode':'compare','settings':{'particles':20,'duration':.15,'seed':21},'alternative':{'waveform':'translate'}})
    ra,rb=[client.get('/api/runs/'+r['id']).json() for r in job['results']]
    assert ra['initial_hash']==rb['initial_hash']
    assert ra['initial']==rb['initial']
    assert ra['frames'][len(ra['frames'])//2]['intruder']!=rb['frames'][len(rb['frames'])//2]['intruder']
    assert ra['frames'][-1]['intruder']==rb['frames'][-1]['intruder']
    matrix=client.get(f'/api/runs/{ra["id"]}/frame/0/matrix').json()
    assert matrix['rank']+matrix['nullity']==40
    bundle=client.get(f'/api/runs/{ra["id"]}/export/bundle')
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
        assert 'reproduce.py' in z.namelist()
        assert json.loads(z.read('experiment.json'))['initial']==ra['initial']
    csv=client.get(f'/api/runs/{ra["id"]}/export/csv')
    assert 'balance_residual' in csv.text
    assert len(csv.text.strip().splitlines())==len(ra['frames'])+1
    loaded=next(k for k,z in enumerate(ra['frames'][0]['contacts']) if z['status']=='loaded')
    bounds=client.get(f'/api/runs/{ra["id"]}/frame/0/force/{loaded}').json()
    assert bounds['min'] is not None
    assert bounds['unbounded'] or bounds['max']>=bounds['min']-1e-8

def test_map_saves_real_runs():
    job=finish({'mode':'map','settings':{'particles':20,'duration':.12,'seed':21},'amplitudes':[0,.035],'frequencies':[.5,1]})
    assert len(job['results'])==4
    assert all(r['status']=='solved' for r in job['results'])
    assert len({r['initial_hash'] for r in job['results']})==1

def test_invalid_input_and_remote_origins():
    assert client.post('/api/jobs',json={'settings':{'dt':0}}).status_code==422
    assert client.post('/api/jobs',json={'settings':{'damping':0}}).status_code==422
    assert client.post('/api/jobs',headers={'Origin':'https://unrelated.example'},json={}).status_code==403
    assert client.get('/api/runs/nonexistent').status_code==404

def test_cancel_job():
    r=client.post('/api/jobs',json={'settings':{'particles':24,'seed':31,'duration':1}}).json()
    assert client.post('/api/jobs/'+r['id']+'/cancel',json={}).status_code==200
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        j=client.get('/api/jobs/'+r['id']).json()
        if j['status'] not in ('running','queued'):break
        time.sleep(.1)
    assert j['status']=='cancelled'


def test_fork_preserves_paused_positions_velocities_and_intruder_shape():
    source=finish({'settings':{'particles':20,'duration':.3,'seed':21}})['results'][0]
    r=client.get('/api/runs/'+source['id']).json();idx=6
    fork=finish({'mode':'compare','fork':source['id'],'frame':idx,
                 'settings':{'particles':20,'duration':.12,'seed':21},'alternative':{'waveform':'translate'}})
    branches=[client.get('/api/runs/'+e['id']).json() for e in fork['results']]
    assert branches[0]['initial']==branches[1]['initial']
    assert branches[0]['initial']['q']==r['frames'][idx]['q']
    assert branches[0]['initial']['v']==r['frames'][idx]['v']
    for b in branches:
        for key in ('x','y','a','b','angle'):
            assert b['frames'][0]['intruder'][key]==pytest.approx(r['frames'][idx]['intruder'][key])


def test_synthetic_default_is_readable_without_mutating_fixture():
    run=client.get('/api/default')
    assert run.status_code==200
    r=run.json()
    assert r['settings']['seed']==2027
    assert client.get('/api/runs/'+r['id']).json()['initial']==r['initial']
    assert any(x['id']==r['id'] for x in client.get('/api/runs').json())


def test_bounded_rigid_motion_search_and_independent_checks():
    job=finish({'mode':'search','settings':{'particles':20,'duration':.12,'seed':2030,'amplitude':.02}})
    assert len(job['results'])==7
    assert all(x['status']=='solved' for x in job['results'])
    assert len({x['initial_hash'] for x in job['results']})==1
    assert job['results'][0]['settings']['waveform']=='translate'
    assert all(x['settings']['amplitude']<=.02 for x in job['results'])
    assert job['best'] in {x['id'] for x in job['results']}
    assert len(job['refinement'])==2 and all('error' not in x for x in job['refinement'])
    assert [x['seed'] for x in job['validation']]==[2031,2032]
    assert all('error' not in r for x in job['validation'] for r in x['runs'])
