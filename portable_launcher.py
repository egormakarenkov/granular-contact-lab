"""Self-contained USB launcher. Runtime and data stay alongside the executable."""
import argparse
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk


HOME=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent


def ready(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.5) as r:
            d=json.load(r)
            return d.get('status')=='ready' and Path(d.get('home','')).resolve()==HOME
    except Exception:return False


def browser(url):
    candidates=[Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
                Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
                Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe',
                Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    exe=next((p for p in candidates if p.exists()),None)
    if exe:
        # A dedicated profile keeps the app separate from personal browser tabs
        # and lets Chromium apply app-window flags even when Chrome is open.
        profile=Path(os.environ.get('LOCALAPPDATA',str(HOME)))/'GranularLab'/'AppWindow'
        profile.mkdir(parents=True,exist_ok=True)
        # Avoid leaking the frozen app's DLL search directory into the browser.
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:subprocess.Popen([str(exe),'--app='+url,'--user-data-dir='+str(profile),
                              '--no-first-run','--no-default-browser-check'],close_fds=True)
        finally:
            if getattr(sys,'frozen',False):ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
    else:messagebox.showerror('Browser engine needed','Install Google Chrome or Microsoft Edge to open the Granular Lab app window.')


def self_test(report):
    import gzip
    import numpy as np
    import scipy
    import osqp
    from granular.physics import Settings,State,advance,force_range,simulate
    s=State(np.array([[1.,.1]]),np.array([.1]),np.zeros((1,2)))
    out,d=advance(s,Settings(intruder_y=4),0,.01)
    assert abs(out.q[0,1]-.1)<1e-6
    idx=next(i for i,z in enumerate(d['contacts']) if z['kind']=='floor')
    bounds=force_range(d,idx)
    assert abs(bounds['min']-(.1/.12)**2)<1e-4
    rid=(HOME/'examples'/'default-run-id.txt').read_text().strip()
    sample=json.loads(gzip.decompress((HOME/'examples'/'runs'/f'{rid}.json.gz').read_bytes()))
    run=simulate(Settings(**{**sample['settings'],'duration':.12,'epsilon':.05}),State.load(sample['initial']))
    assert run['metrics']['max_penetration']<2e-6
    assert (HOME/'ui'/'dist'/'index.html').is_file()
    result={'passed':True,'frozen':bool(getattr(sys,'frozen',False)),'home':str(HOME),
            'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'osqp':osqp.__version__,
            'support_force':d['contacts'][idx]['force'],'force_bounds':bounds,
            'finite_inertia_steps':len(run['frames'])-1,'metrics':run['metrics']}
    Path(report).write_text(json.dumps(result,indent=2),encoding='utf-8')


def configure(port):
    os.environ['GRANULAR_LAB_HOME']=str(HOME)
    os.environ['GRANULAR_LAB_PORT']=str(port)
    os.chdir(HOME)
    # Windowed builds have no stdout; C and Python numerical diagnostics get a
    # local log instead of failing on a None stream.
    stream=open(HOME/'runtime.log','a',encoding='utf-8',buffering=1)
    sys.stdout=sys.stderr=stream
    logging.basicConfig(stream=stream,level=logging.WARNING)


def server_for(port):
    import uvicorn
    from granular.server import app
    return uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,
                          loop='asyncio',http='h11',ws='none',lifespan='off',
                          log_config=None,log_level='warning',access_log=False))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',metavar='REPORT_JSON')
    parser.add_argument('--serve-only',action='store_true')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if args.self_test:
        configure(args.port)
        try:self_test(args.self_test)
        except Exception:
            Path(args.self_test).write_text(json.dumps({'passed':False,'error':traceback.format_exc()}),encoding='utf-8')
            raise
        return
    if args.serve_only:
        configure(args.port);server_for(args.port).run();return
    port=args.port
    if ready(port):browser(f'http://127.0.0.1:{port}');return
    for candidate in range(port,port+12):
        probe=socket.socket()
        try:probe.bind(('127.0.0.1',candidate));port=candidate;break
        except OSError:continue
        finally:probe.close()
    configure(port)
    window=tk.Tk();window.title('Granular Lab');window.geometry('470x265');window.resizable(False,False)
    window.configure(background='#f4f3ed')
    label=tk.Label(window,text='Granular Lab',font=('Georgia',24),fg='#155f63',bg='#f4f3ed')
    label.pack(pady=(26,12))
    status=tk.StringVar(value='Starting the bundled numerical solver…')
    tk.Label(window,textvariable=status,font=('Segoe UI',10),bg='#f4f3ed',fg='#334c3e',wraplength=420).pack(pady=5)
    tk.Label(window,text='Runs from this folder. No Python installation or internet needed.',
             font=('Segoe UI',9),bg='#f4f3ed',fg='#59695d').pack(pady=8)
    buttons=tk.Frame(window,bg='#f4f3ed');buttons.pack(pady=13)
    url=f'http://127.0.0.1:{port}'
    open_button=ttk.Button(buttons,text='Open Granular Lab',command=lambda:browser(url),state='disabled')
    open_button.pack(side='left',padx=7)
    srv=server_for(port)
    failure=[]
    def run():
        try:srv.run()
        except BaseException:failure.append(traceback.format_exc())
    thread=threading.Thread(target=run,daemon=True);thread.start()
    closing=False
    def close():
        nonlocal closing
        if closing:return
        closing=True;status.set('Stopping jobs. Keep the USB connected until this window closes.')
        open_button.configure(state='disabled')
        from granular.server import JOBS
        for j in list(JOBS.values()):j['cancel'].set()
        srv.should_exit=True
        stopped=threading.Event()
        def stop_workers():
            thread.join()
            from granular.server import POOL
            POOL.shutdown(wait=True,cancel_futures=True)
            stopped.set()
        threading.Thread(target=stop_workers,daemon=True).start()
        def finish():
            if not stopped.is_set():
                window.after(150,finish)
            else:window.destroy()
        finish()
    ttk.Button(buttons,text='Quit',command=close).pack(side='left',padx=7)
    window.protocol('WM_DELETE_WINDOW',close)
    started=time.monotonic()
    def check():
        if closing:return
        if ready(port):
            status.set('Ready · '+url+'\nClose this window to stop the app before removing the USB.')
            open_button.configure(state='normal');browser(url)
        elif failure or time.monotonic()-started>60:
            status.set('The solver could not start. Details are in runtime.log beside the EXE.')
            if failure:print(failure[0])
        else:window.after(250,check)
    window.after(250,check);window.mainloop()


if __name__=='__main__':
    try:main()
    except Exception:
        try:
            (HOME/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            if '--self-test' not in sys.argv and '--serve-only' not in sys.argv:
                messagebox.showerror('Granular Lab could not start','See startup-error.txt beside the EXE. Make sure the full GranularLab folder is on a writable drive.')
        finally:sys.exit(1)
