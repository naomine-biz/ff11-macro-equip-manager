"""Startup preparation off the Tk thread; one-way ownership handoff to the UI."""
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
import tkinter as tk
from tkinter import ttk


def prepare(root, report):
    from .application import installations, load_snapshot
    from .edit_application import Editor
    from .tracing import configure, span
    configure(Path(__file__).resolve().parent.parent/'work'/'logs'/'timings.jsonl')
    with span('startup.prepare'):
        report('ゲームデータを読み込んでいます…')
        roots=installations() if root is None else [root]
        if len(roots)!=1:raise ValueError('FF11のインストール先を特定できません。--rootで指定してください。')
        with span('startup.read'):snapshot=load_snapshot(Path(roots[0]).resolve())
        report('編集履歴を復元しています…')
        with span('startup.restore'):
            editor=Editor(snapshot)
            snapshot=editor.snapshot()
        return snapshot,editor


class Startup:
    def __init__(self, app, prepare_work, ready):
        self.app=app;self.prepare_work=prepare_work;self.ready=ready
        self.messages=Queue();self.closed=False;self.started=False;self.poll_id=None
        app.title('FF11 ワークスペース — 起動中');app.geometry('480x180');app.configure(bg='#080f22')
        self.panel=tk.Frame(app,bg='#080f22',padx=24,pady=24);self.panel.pack(fill='both',expand=True)
        tk.Label(self.panel,text='FF11 ワークスペースを起動しています',bg='#080f22',fg='#edf1fa',font=('MS Gothic',13,'bold')).pack(anchor='w')
        self.status=tk.Label(self.panel,text='準備しています…',bg='#080f22',fg='#edf1fa',wraplength=430,justify='left');self.status.pack(anchor='w',pady=12)
        self.progress=ttk.Progressbar(self.panel,mode='indeterminate');self.progress.pack(fill='x');self.progress.start(40)
        app.protocol('WM_DELETE_WINDOW',self.close)
        self.binding=app.bind('<Map>',self.mapped,add='+')

    def mapped(self,event):
        if event.widget is not self.app or self.started:return
        self.started=True;self.app.unbind('<Map>',self.binding)
        self.app.after_idle(self.start)

    def start(self):
        if self.closed:return
        def work():
            try:self.messages.put(('ready',self.prepare_work(lambda text:self.messages.put(('status',text)))))
            except Exception as exc:self.messages.put(('error',str(exc)))
        # Finish any application-owned draft recovery even if the window is closed.
        self.worker=Thread(target=work,name='ff11-startup',daemon=False);self.worker.start()
        self.poll_id=self.app.after(40,self.poll)

    def poll(self):
        self.poll_id=None
        if self.closed:return
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='status':self.status.configure(text=value)
                else:
                    self.progress.stop()
                    if kind=='error':self.fail(value);return
                    try:
                        self.panel.destroy();self.app.protocol('WM_DELETE_WINDOW',self.app.destroy)
                        self.ready(value)
                    except Exception as exc:
                        from . import dialogs
                        dialogs.showerror('起動できませんでした',str(exc),parent=self.app)
                        self.app.destroy()
                    return
        except Empty:pass
        self.poll_id=self.app.after(40,self.poll)

    def fail(self,message):
        self.app.title('FF11 ワークスペース — 起動エラー')
        self.status.configure(text='起動できませんでした。')
        self.progress.pack_forget()
        detail=tk.Text(self.panel,height=6,bg='#101b38',fg='#edf1fa',wrap='word')
        detail.insert('1.0',message);detail.configure(state='disabled');detail.pack(fill='both',expand=True)
        ttk.Button(self.panel,text='閉じる',command=self.close).pack(pady=8)
        self.app.geometry('600x340')

    def close(self):
        self.closed=True
        if self.poll_id:self.app.after_cancel(self.poll_id)
        self.progress.stop();self.app.destroy()


def launch(root=None):
    app=tk.Tk()
    def ready(result):
        from .ui import ReaderWindow
        snapshot,editor=result
        app.view=ReaderWindow(app,snapshot,editor=editor)
    app.startup=Startup(app,lambda report:prepare(root,report),ready)
    app.mainloop()
