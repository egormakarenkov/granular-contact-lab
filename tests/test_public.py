from dataclasses import replace
import numpy as np
import pytest
from granular.physics import Settings, State, intruder, advance, gaps


def test_sway_is_rigid_bounded_and_returns_to_commanded_endpoint():
    c=Settings(waveform="sway", amplitude=.03, frequency=1, duration=1, stroke=.04)
    shapes=[intruder(c,t) for t in np.linspace(0,1,101)]
    assert max(abs(s["x"]-c.intruder_x) for s in shapes)>.005
    assert max(abs(s["x"]-c.intruder_x) for s in shapes)<=c.amplitude+1e-12
    assert all(s["a"]==shapes[0]["a"] and s["b"]==shapes[0]["b"] for s in shapes)
    assert shapes[-1]["x"]==pytest.approx(shapes[0]["x"])
    assert shapes[-1]["y"]==pytest.approx(shapes[0]["y"]-c.stroke)


def test_translating_boundary_pushes_without_expansion():
    c=Settings(waveform="sway",gravity=0,stroke=0,amplitude=.05,duration=1)
    shape=intruder(c,.125)
    st=State(np.array([[shape["x"]+shape["a"]+.1,shape["y"]]]),np.array([.1]),np.zeros((1,2)))
    out,d=advance(st,c,.125,.01)
    assert out.q[0,0]>st.q[0,0]
    assert min(gaps(out,c,.135))>-2e-6


def test_shipped_synthetic_fixtures_share_arrays_and_preserve_rigid_shape():
    import gzip
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'examples/manifest.json').read_text())
    assert len(manifest['runs'])==8
    for pair in manifest['comparisons']:
        runs=[json.loads(gzip.decompress((root/'examples/runs'/f"{r['id']}.json.gz").read_bytes())) for r in pair['runs']]
        assert runs[0]['initial']==runs[1]['initial']
        assert runs[0]['frames'][-1]['intruder']['x']==pytest.approx(runs[1]['frames'][-1]['intruder']['x'])
        for r in runs:
            shape=r['frames'][0]['intruder']
            assert all(f['intruder']['a']==shape['a'] and f['intruder']['b']==shape['b'] for f in r['frames'])
            assert r['metrics']['max_penetration']<=2e-6
