import numpy as np
import pytest
from granular.physics import Settings, State, advance, gaps, prepare, simulate, force_range, surface, intruder


def one(x=1.0, y=1.0):
    return State(np.array([[x, y]], dtype=float), np.array([.1]), np.zeros((1, 2)))


def test_unconstrained_drift():
    c = Settings(gravity=1, damping=2, epsilon=0, intruder_y=4)
    s, d = advance(one(), c, 0, .01)
    assert s.q[0, 1] == pytest.approx(.995, abs=1e-7)
    assert d['balance'] < 1e-6


def test_floor_support_and_force():
    c = Settings(gravity=1, intruder_y=4)
    s, d = advance(one(y=.1), c, 0, .01)
    assert s.q[0, 1] == pytest.approx(.1, abs=1e-6)
    floor = next(z for z in d['contacts'] if z['kind'] == 'floor')
    assert floor['force'] == pytest.approx((.1/.12)**2, abs=1e-4)
    assert d['penetration'] < 1e-6


def test_finite_inertia_implicit_euler():
    c = Settings(gravity=1, damping=2, epsilon=.1, intruder_y=4)
    s, _ = advance(one(), c, 0, .01)
    assert s.v[0, 1] == pytest.approx(-1/12, abs=1e-6)


def test_exact_gap_guards_and_deterministic_packing():
    c = Settings(particles=24, seed=7)
    a, da = prepare(c)
    b, db = prepare(c)
    assert np.array_equal(a.q, b.q)
    assert min(gaps(a, c, 0)) > -2e-6
    assert np.isfinite(a.q).all()
    assert any(z['kind']=='intruder' and z['force']>1e-4 for z in da['contacts'])


def test_recorded_fork_is_reproducible():
    c = Settings(particles=20, duration=.12)
    state, _ = prepare(c)
    a = simulate(c, state)
    b = simulate(c, state)
    assert a['initial'] == b['initial']
    assert a['frames'][-1]['q'] == b['frames'][-1]['q']


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        Settings(damping=0)
    with pytest.raises(ValueError):
        Settings(dt=-.1)


def test_force_range_for_supported_grain():
    c = Settings(gravity=1, intruder_y=4)
    state, d = advance(one(y=.1), c, 0, .01)
    floor = next(i for i,z in enumerate(d['contacts']) if z['kind']=='floor')
    result = force_range(d, floor)
    assert result['min'] == pytest.approx((.1/.12)**2, abs=1e-4)
    assert result['max'] == pytest.approx((.1/.12)**2, abs=1e-4)


def test_redundant_support_has_nonunique_forces():
    z={'i':0,'j':-1,'kind':'floor','normal':[0,1],'status':'loaded','slack':0}
    f={'contacts':[z.copy(),z.copy()],'target_reaction':[0,1]}
    r=force_range(f,0)
    assert r['min']==pytest.approx(0,abs=1e-5)
    assert r['max']==pytest.approx(1,abs=1e-4)


def test_ellipse_distance_on_axes_and_rotated():
    shape={'x':0,'y':0,'a':2,'b':1,'angle':0}
    d,n=surface(np.array([[3.,0],[0,2.]]),shape)
    assert np.allclose(d,[1,1],atol=1e-10)
    assert np.allclose(n,[[1,0],[0,1]],atol=1e-10)
    shape['angle']=np.pi/2
    d,_=surface(np.array([[0,3.]]),shape)
    assert d[0]==pytest.approx(1,abs=1e-10)


def test_refinement_improves_free_inertial_drift():
    c=Settings(gravity=1,epsilon=.1,intruder_y=4,duration=.12)
    start=one()
    from dataclasses import replace
    coarse=simulate(replace(c,dt=.03),start)['frames'][-1]['q'][0][1]
    fine=simulate(replace(c,dt=.0075),start)['frames'][-1]['q'][0][1]
    exact=1-(.12-.1*(1-np.exp(-.12/.1)))
    assert abs(fine-exact)<abs(coarse-exact)


@pytest.mark.parametrize('waveform',['sway','translate'])
@pytest.mark.parametrize('frequency',[.5,1,2])
def test_every_search_motion_has_identical_endpoints(waveform,frequency):
    c=Settings(waveform=waveform,frequency=frequency,duration=1,stroke=.08)
    start,end=intruder(c,0),intruder(c,c.duration)
    assert end['x']==pytest.approx(start['x'],abs=1e-12)
    assert end['y']==pytest.approx(start['y']-.08,abs=1e-12)
    assert end['a']==pytest.approx(start['a'],abs=1e-12)
    assert end['b']==pytest.approx(start['b'],abs=1e-12)
