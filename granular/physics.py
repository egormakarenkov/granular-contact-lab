"""Frictionless disc contact, velocity QP, and checked implicit time stepping.

Lengths, time and forces are dimensionless. epsilon multiplies the reference
inertial mass only: the externally prescribed body-force field stays fixed.
"""
from dataclasses import dataclass, asdict, replace
from typing import Callable
import math
import numpy as np
import osqp
from scipy import sparse
from scipy.optimize import linprog, minimize, lsq_linear


@dataclass
class Settings:
    particles: int = 36
    seed: int = 2027
    gravity: float = 1.0
    damping: float = 1.0
    epsilon: float = 0.0
    dt: float = .015
    duration: float = .6
    amplitude: float = .02
    frequency: float = 1.0
    waveform: str = 'sway'
    stroke: float = .03
    aspect: float = 1.0
    angle: float = 0.0
    width: float = 2.7
    intruder_x: float = 1.35
    intruder_y: float = .78
    intruder_radius: float = .32

    def __post_init__(self):
        for k,v in asdict(self).items():
            if isinstance(v,(float,int)) and not math.isfinite(v):
                raise ValueError(f'{k} must be finite')
        if not 1 <= self.particles <= 150: raise ValueError('particles must be 1–150')
        if not .0005 <= self.dt <= .04: raise ValueError('dt must be .0005–.04')
        if not .03 <= self.duration <= 8: raise ValueError('duration must be .03–8')
        if not .1 <= self.damping <= 8: raise ValueError('damping must be .1–8')
        if not 0 <= self.epsilon <= 1: raise ValueError('epsilon must be 0–1')
        if not 0 <= self.amplitude <= .08: raise ValueError('amplitude must be 0–.08')
        if not .1 <= self.frequency <= 4: raise ValueError('frequency must be .1–4')
        if not 0 <= self.gravity <= 4: raise ValueError('gravity must be 0–4')
        if not 0 <= self.stroke <= .3: raise ValueError('stroke must be 0–.3')
        if not 1 <= self.aspect <= 1.7: raise ValueError('aspect must be 1–1.7')
        if self.waveform not in ('sway','translate','hold'):
            raise ValueError('unknown waveform')
        if self.width != 2.7 or self.intruder_x != 1.35 or self.intruder_y != .78 or self.intruder_radius != .32:
            # Non-default geometry is used by analytic tests; service constrains it.
            if self.width <= .5 or self.intruder_radius <= 0: raise ValueError('invalid geometry')


@dataclass
class State:
    q: np.ndarray
    r: np.ndarray
    v: np.ndarray

    def copy(self): return State(self.q.copy(), self.r.copy(), self.v.copy())
    def json(self): return {'q':self.q.tolist(),'r':self.r.tolist(),'v':self.v.tolist()}
    @staticmethod
    def load(d): return State(np.array(d['q'],float),np.array(d['r'],float),np.array(d['v'],float))


def intruder(c: Settings, t: float):
    phase=2*math.pi*c.frequency*t
    fraction=min(max(t/c.duration,0),1)
    envelope=math.sin(math.pi*fraction)**2
    radius=c.intruder_radius
    x,y=c.intruder_x,c.intruder_y
    # A rigid intruder: optional lateral sinusoid with a smooth time window.
    if c.waveform=='sway':
        x+=c.amplitude*math.sin(phase)*envelope
    if c.waveform not in ('hold',): y-=c.stroke*min(max(t/c.duration,0),1)
    return {'x':x,'y':y,'a':radius*c.aspect,'b':radius/c.aspect,'angle':c.angle}


def surface(q, shape):
    """Exact exterior closest-point gap/normal to an ellipse (Newton/bisection).

    Grains are required to remain outside the intruder. An inside center is
    rejected by stepping checks rather than being given a fictitious normal.
    """
    ang=shape['angle']; co,si=math.cos(ang),math.sin(ang)
    rot=np.array([[co,si],[-si,co]])
    local=(q-np.array([shape['x'],shape['y']]))@rot.T
    a,b=shape['a'],shape['b']
    if abs(a-b)<1e-12:
        length=np.linalg.norm(local,axis=1)
        normal=local/np.maximum(length[:,None],1e-12)
        return length-a,normal@rot
    inside=(local[:,0]/a)**2+(local[:,1]/b)**2 < 1
    lo=np.zeros(len(q)); hi=np.maximum(a*np.abs(local[:,0])+b*np.abs(local[:,1]),1.)
    for _ in range(48):
        mid=(lo+hi)*.5
        f=(a*local[:,0]/(mid+a*a))**2+(b*local[:,1]/(mid+b*b))**2-1
        lo=np.where(f>0,mid,lo);hi=np.where(f>0,hi,mid)
    lam=(lo+hi)*.5
    foot=np.column_stack((a*a*local[:,0]/(lam+a*a),b*b*local[:,1]/(lam+b*b)))
    delta=local-foot
    distance=np.linalg.norm(delta,axis=1)
    normal=delta/np.maximum(distance[:,None],1e-12)
    distance[inside]=-min(a,b)
    return distance,normal@rot


def constraints(s,c,t,h):
    q,r=s.q,s.r;n=len(r);rows=[];gs=[];gt=[];meta=[]
    def add(i,j,norm,g,kind,rate=0.):
        row=np.zeros((n,2));row[i]=norm
        if j>=0:row[j]=-norm
        rows.append(row.ravel());gs.append(g);gt.append(rate)
        meta.append({'i':int(i),'j':int(j),'kind':kind,'normal':list(map(float,norm))})
    ii,jj=np.triu_indices(n,1)
    delta=q[ii]-q[jj];dist=np.linalg.norm(delta,axis=1)
    g=dist-r[ii]-r[jj]
    # The .14 neighbour skin exceeds twice the accepted .045 displacement;
    # exact all-pair gap validation below independently guards tunnelling.
    for i,j,d,l,gap in zip(ii,jj,delta,dist,g):
        if l < 1e-10:raise RuntimeError('coincident grain centers')
        if gap < .14: add(i,j,d/l,gap,'grain')
    for i in range(n):
        add(i,-1,[0,1],q[i,1]-r[i],'floor')
        add(i,-1,[1,0],q[i,0]-r[i],'left')
        add(i,-1,[-1,0],c.width-q[i,0]-r[i],'right')
    shape=intruder(c,t);future=intruder(c,t+h)
    gd,norm=surface(q,shape); gd_next,_=surface(q,future)
    for i in range(n):
        if gd[i]-r[i]<.2:
            add(i,-1,norm[i],gd[i]-r[i],'intruder',(gd_next[i]-gd[i])/h)
    return np.array(rows),np.array(gs),np.array(gt),meta


def gaps(s,c,t):
    q,r=s.q,s.r;ii,jj=np.triu_indices(len(r),1)
    pair=np.linalg.norm(q[ii]-q[jj],axis=1)-r[ii]-r[jj]
    gd,_=surface(q,intruder(c,t))
    return np.concatenate((pair,q[:,1]-r,q[:,0]-r,c.width-q[:,0]-r,gd-r))


def advance(s: State,c: Settings,t:float,h:float,depth=0):
    G,g,gt,meta=constraints(s,c,t,h)
    mass=(s.r/.12)**2
    H=np.repeat(mass*(c.damping+c.epsilon/h),2)
    F=np.zeros_like(s.q);F[:,1]=-mass*c.gravity
    b=F.ravel()+np.repeat(mass*c.epsilon/h,2)*s.v.ravel()
    lower=-g/h-gt
    solver=osqp.OSQP()
    solver.setup(P=sparse.diags(H,format='csc'),q=-b,A=sparse.csc_matrix(G),l=lower,u=np.full(len(g),np.inf),
                 verbose=False,eps_abs=1e-6,eps_rel=1e-6,max_iter=50000,polishing=True,
                 polish_refine_iter=5,adaptive_rho=True)
    solver.warm_start(x=s.v.ravel())
    res=solver.solve(raise_error=False)
    solved_x=res.x;solved_y=res.y;status=res.info.status
    if res.info.status_val not in (1,2):
        # Independent primal active-set fallback for nearly dependent, tightly
        # wedged contact sets. Accept only after the same residual checks below.
        opt=minimize(lambda x: .5*np.dot(H*x,x)-np.dot(b,x),res.x,
                     jac=lambda x:H*x-b,method='SLSQP',
                     constraints={'type':'ineq','fun':lambda x:G@x-lower,'jac':lambda x:G},
                     options={'ftol':1e-11,'maxiter':300})
        if not opt.success:
            raise RuntimeError(f'Contact solver: {res.info.status}; independent primal solve: {opt.message}')
        solved_x=opt.x
        active=(G@solved_x-lower)<2e-6
        solved_y=np.zeros(len(g))
        if active.any():
            dual=lsq_linear(G[active].T,H*solved_x-b,bounds=(0,np.inf),method='bvls',tol=1e-11,max_iter=1000)
            solved_y[active]=-dual.x
        status='solved · independent active-set fallback'
    v=solved_x.reshape((-1,2));out=State(s.q+h*v,s.r.copy(),v)
    exact=gaps(out,c,t+h); penetration=max(0.,-float(exact.min()))
    # Nonlinear moving-boundary errors and large grain displacements must be
    # resolved, not hidden with position clipping or an unreported soft spring.
    if penetration>2e-6 or np.max(np.linalg.norm(h*v,axis=1))>.045:
        if depth>=9:raise RuntimeError(f'Step rejected: geometric error {penetration:.3g}; reduce motion or timestep')
        mid,d1=advance(s,c,t,h/2,depth+1);out,d2=advance(mid,c,t+h/2,h/2,depth+1)
        d2['substeps']+=d1['substeps'];d2['step_work']+=d1['step_work']
        d2['positive_step_work']+=d1['positive_step_work']
        return out,d2
    lam=np.maximum(-solved_y,0)
    slack=G@solved_x-lower
    balance=float(np.max(np.abs(H*solved_x-b-G.T@lam)))
    comp=float(np.max(np.abs(lam*slack)))
    if balance>3e-4 or comp>3e-4:
        raise RuntimeError(f'Numerical residual too large: balance={balance:.2g}, complementarity={comp:.2g}')
    net=np.zeros(2);power=0.;contacts=[]
    for k,m in enumerate(meta):
        if g[k]>.002 and lam[k]<1e-5:continue
        z=dict(m,gap=float(g[k]),force=float(lam[k]),impulse=float(h*lam[k]),
               relative_velocity=float(G[k]@solved_x+gt[k]),slack=float(slack[k]))
        z['status']='loaded' if lam[k]>1e-4 else ('touching' if abs(g[k])<2e-4 else 'open')
        contacts.append(z)
        if m['kind']=='intruder':
            net-=lam[k]*np.array(m['normal']);power+=lam[k]*(-gt[k])
    return out,{'contacts':contacts,'balance':balance,'complementarity':comp,'penetration':penetration,
                'reaction':net.tolist(),'actuator_power':float(power),'step_work':float(power*h),'positive_step_work':float(max(0,power*h)),
                'iterations':int(res.info.iter),'status':status,'substeps':1,
                'target_reaction':(H*solved_x-b).tolist(),'force_scale':'force; impulse = force × accepted substep'}


def prepare(c:Settings,progress:Callable|None=None,cancel:Callable|None=None):
    rng=np.random.default_rng(c.seed)
    rs=rng.choice([.105,.137],size=c.particles)
    coords=[];row=0;shape=intruder(c,0)
    while len(coords)<c.particles:
        for col in range(9):
            x=.155+col*.295+(.145 if row%2 else 0)
            if x>c.width-.145:continue
            p=np.array([[x+rng.uniform(-.004,.004),.15+row*.259+rng.uniform(-.003,.003)]])
            r=rs[len(coords)]
            gd,_=surface(p,shape)
            if gd[0]<r+.008:continue
            if any(np.linalg.norm(p[0]-a)<r+rs[k]+.001 for k,a in enumerate(coords)):continue
            coords.append(p[0])
            if len(coords)==c.particles:break
        row+=1
        if row>80:raise RuntimeError('Cannot generate requested packing')
    state=State(np.array(coords),rs,np.zeros((c.particles,2)))
    hold=replace(c,waveform='hold',epsilon=0)
    diag=None
    for k in range(150):
        if cancel and cancel():raise InterruptedError('Packing cancelled')
        state,diag=advance(state,hold,0,.025)
        if progress and k%10==0:progress(k/150)
    state.v[:]=0
    state,diag=advance(state,hold,0,.01)
    state.v[:]=0
    return state,diag


def metrics(frames):
    if not frames:return {}
    forces=np.array([f['reaction'] for f in frames]);work=float(frames[-1]['work'])
    return {'mean_reaction':float(np.mean(np.linalg.norm(forces,axis=1))),
            'mean_vertical_resistance':float(np.mean(np.maximum(forces[:,1],0))),
            'work':work,'positive_work':float(frames[-1]['positive_work']),
            'max_penetration':max(f['penetration'] for f in frames),
            'max_balance':max(f['balance'] for f in frames),
            'max_complementarity':max(f['complementarity'] for f in frames)}


def simulate(c:Settings,initial:State,progress:Callable|None=None,cancel:Callable|None=None):
    s=initial.copy();frames=[];t=0.;work=positive=0.;steps=math.ceil(c.duration/c.dt)
    # Same t=0 frame for every branch; solve stationary initial reactions.
    _,d0=advance(s,replace(c,waveform='hold',epsilon=0),0,c.dt)
    def record(d):
        return dict(t=float(t),q=s.q.tolist(),v=s.v.tolist(),intruder=intruder(c,t),
                    work=work,positive_work=positive,**{k:v for k,v in d.items() if k not in ('step_work','positive_step_work')})
    frames.append(record(d0))
    for k in range(steps):
        if cancel and cancel():raise InterruptedError('Experiment cancelled')
        h=min(c.dt,c.duration-t)
        s,d=advance(s,c,t,h);t+=h;work+=d['step_work'];positive+=d['positive_step_work']
        frames.append(record(d))
        if progress and k%4==0:progress((k+1)/steps)
    return {'settings':asdict(c),'initial':initial.json(),'r':s.r.tolist(),
            'frames':frames,'metrics':metrics(frames),'method':'normal-contact velocity QP public v1 · rigid translation/sway'}


def force_range(frame,index):
    contacts=frame['contacts']
    if not 0<=index<len(contacts):raise ValueError('Contact index out of range')
    active=[k for k,z in enumerate(contacts) if z['status']!='open' and z['slack']<2e-4]
    if index not in active:return {'min':0.,'max':0.,'note':'Inactive contact: reaction constrained to zero.'}
    target=np.array(frame['target_reaction'])
    G=contact_matrix([contacts[k] for k in active],len(target))
    objective=np.zeros(len(active));objective[active.index(index)]=1
    # Explicit force-balance tolerance makes the LP consistent with the recorded
    # QP tolerances. Other contacts are constrained nonnegative and inactive=0.
    A=np.vstack((G.T,-G.T));b=np.concatenate((target+3e-5,-target+3e-5))
    low=linprog(objective,A_ub=A,b_ub=b,bounds=(0,None),method='highs')
    high=linprog(-objective,A_ub=A,b_ub=b,bounds=(0,None),method='highs')
    return {'min':float(low.fun) if low.success else None,
            'max':float(-high.fun) if high.success else None,'unbounded':high.status==3,
            'note':'Nonnegative normal-force distributions matching this step’s balance within 3e-5; history/compliance not selected.',
            'min_status':low.message,'max_status':high.message}


def contact_matrix(contacts,ndof):
    G=np.zeros((len(contacts),ndof))
    for k,z in enumerate(contacts):
        G[k,2*z['i']:2*z['i']+2]=z['normal']
        if z['j']>=0:G[k,2*z['j']:2*z['j']+2]=-np.array(z['normal'])
    return G
