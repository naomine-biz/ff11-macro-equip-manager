"""Shared modal overlays rendered inside the application's own windows."""
import tkinter as tk
from tkinter import ttk, font as tkfont


class Modal:
    def __init__(self,parent,title,message,kind='notice',initialvalue='',accept_label=None):
        self.parent=parent.winfo_toplevel()
        self.previous_focus=self.parent.focus_get()
        self.previous_grab=self.parent.grab_current()
        self.previous_grab_status=self.previous_grab.grab_status() if self.previous_grab else None
        self.result=False if kind=='confirm' else None
        self.layer=tk.Frame(self.parent,bg='#080f22')
        self.layer.place(x=0,y=0,relwidth=1,relheight=1);self.layer.lift()
        self.message=str(message)
        self._layout_job=None;self._measure_job=None
        panel=self.panel=tk.Frame(self.layer,bg='#101b38',highlightbackground='#8491b2',highlightthickness=2,padx=18,pady=14)
        panel.place(relx=.5,rely=.5,anchor='center',width=400,height=160)
        panel.rowconfigure(1,weight=1);panel.columnconfigure(0,weight=1)
        color={'error':'#ef9994','warning':'#f3ce77'}.get(kind,'#fff1c0')
        self.heading=tk.Label(panel,text=title,bg='#101b38',fg=color,font=('MS Gothic',14,'bold'),anchor='w')
        self.heading.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,12))
        self.body=tk.Text(panel,wrap='word',bg='#101b38',fg='#edf1fa',selectbackground='#354b7a',relief='flat',height=1,width=1,takefocus=True)
        self.body.insert('1.0',str(message));self.body.configure(state='disabled')
        self.body.grid(row=1,column=0,sticky='nsew')
        scroll=self.scroll=ttk.Scrollbar(panel,command=self.body.yview);scroll.grid(row=1,column=1,sticky='ns')
        self.body.configure(yscrollcommand=scroll.set)
        self.entry=None
        if kind=='input':
            self.entry=tk.Entry(panel,bg='#182b53',fg='#edf1fa',insertbackground='white')
            self.entry.insert(0,initialvalue);self.entry.grid(row=2,column=0,columnspan=2,sticky='ew',pady=10)
        bar=self.bar=ttk.Frame(panel);bar.grid(row=3,column=0,columnspan=2,sticky='ew',pady=(12,0))
        copy=ttk.Button(bar,text='本文をコピー',command=lambda:self.copy(str(message)));copy.pack(side='left')
        self.cancel_button=None
        if kind in ('confirm','input'):
            self.cancel_button=ttk.Button(bar,text='取消',command=self.cancel);self.cancel_button.pack(side='right',padx=(8,0))
        self.ok_button=ttk.Button(bar,text=accept_label or ('適用' if kind in ('confirm','input') else '閉じる'),command=lambda:self.finish(self.entry.get() if self.entry else True))
        self.ok_button.pack(side='right')
        self.focusables=[self.body]+([self.entry] if self.entry else [])+[copy,self.ok_button]+([self.cancel_button] if self.cancel_button else [])
        for widget in [self.layer,*self.focusables]:
            widget.bind('<Escape>',self.cancel)
            widget.bind('<Tab>',lambda e:self.cycle(1))
            widget.bind('<Shift-Tab>',lambda e:self.cycle(-1))
            widget.bind('<ISO_Left_Tab>',lambda e:self.cycle(-1))
        # Enter is accepted only on an explicit button, not in an IME input field.
        for button in (self.ok_button,self.cancel_button,copy):
            if button:button.bind('<Return>',lambda e,b=button:(b.invoke(),'break')[1])
        self.layer.bind('<Configure>',self.schedule_layout)
        self.layer.bind('<Destroy>',self.cancel_layout)
        self.layer.grab_set()
        (self.entry or self.cancel_button or self.ok_button).focus_set()

    def cancel_layout(self,event):
        if event.widget is not self.layer:return
        for job in (self._layout_job,self._measure_job):
            if job:self.layer.after_cancel(job)
        self._layout_job=self._measure_job=None

    def schedule_layout(self,event=None):
        if self._layout_job:self.layer.after_cancel(self._layout_job)
        if self._measure_job:self.layer.after_cancel(self._measure_job)
        self._measure_job=None
        self._layout_job=self.layer.after_idle(self.layout)

    def layout(self):
        self._layout_job=None
        font=tkfont.Font(root=self.parent,font=self.body.cget('font'))
        text_width=max((font.measure(line) for line in self.message.splitlines()),default=0)
        gutter=self.scroll.winfo_reqwidth()
        # Reserve the same gutter with/without the scrollbar to keep wrapping stable.
        self.panel.columnconfigure(1,minsize=gutter)
        maximum=max(100,min(720,self.layer.winfo_width()-40))
        width=min(maximum,max(360,text_width+48+gutter,self.heading.winfo_reqwidth()+40,self.bar.winfo_reqwidth()+40))
        self.heading.configure(wraplength=max(40,width-40))
        self.panel.place_configure(width=width)
        self._measure_job=self.layer.after_idle(self.fit_height)

    def fit_height(self):
        self._measure_job=None
        # Tk measures actual wrapped display lines after the width has been laid out.
        pixels=self.body.count('1.0','end','update','ypixels')
        content=(pixels[0] if isinstance(pixels,tuple) else pixels) or tkfont.Font(root=self.parent,font=self.body.cget('font')).metrics('linespace')
        padding=2*(int(self.body.cget('pady'))+int(self.body.cget('borderwidth'))+int(self.body.cget('highlightthickness')))
        overhead=self.panel.winfo_reqheight()-self.body.winfo_reqheight()
        maximum=max(overhead+24,int(self.layer.winfo_height()*.85))
        height=min(maximum,overhead+content+padding)
        self.panel.place_configure(height=height)
        if overhead+content+padding>maximum:self.scroll.grid()
        else:
            self.scroll.grid_remove()
            self.body.yview_moveto(0)

    def copy(self,message):
        self.layer.clipboard_clear();self.layer.clipboard_append(message)

    def cycle(self,direction):
        current=self.parent.focus_get()
        index=self.focusables.index(current) if current in self.focusables else 0
        self.focusables[(index+direction)%len(self.focusables)].focus_set()
        return 'break'

    def cancel(self,event=None):
        self.layer.destroy()
        return 'break'

    def finish(self,result):
        self.result=result;self.layer.destroy()

    def wait(self):
        try:
            self.parent.wait_window(self.layer)
            return self.result
        finally:
            try:
                if self.layer.winfo_exists():self.layer.destroy()
                if self.previous_grab and self.previous_grab.winfo_exists():
                    if self.previous_grab_status=='global':self.previous_grab.grab_set_global()
                    else:self.previous_grab.grab_set()
                if self.previous_focus and self.previous_focus.winfo_exists():self.previous_focus.focus_set()
            except tk.TclError:pass  # Parent window may have been closed.


def showwarning(title,message,*,parent):return Modal(parent,title,message,'warning').wait()
def showerror(title,message,*,parent):return Modal(parent,title,message,'error').wait()
def askyesno(title,message,*,parent,accept_label=None):return Modal(parent,title,message,'confirm',accept_label=accept_label).wait()
def askstring(title,message,*,parent,initialvalue=''):return Modal(parent,title,message,'input',initialvalue).wait()


def when_visible(parent,callback):
    """Run once after the first mapping; nested waits in an idle mapper block Tk."""
    window=parent.winfo_toplevel()
    def invoke():
        if window.winfo_exists():callback()
    if window.winfo_viewable():
        window.after_idle(invoke)
        return
    def mapped(event):
        if event.widget is window:
            window.unbind('<Map>',binding)
            window.after_idle(invoke)
    binding=window.bind('<Map>',mapped,add='+')
