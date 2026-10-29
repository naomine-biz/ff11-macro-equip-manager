"""Explicit busy actions for heavy UI operations."""
from contextlib import contextmanager
import tkinter as tk
from tkinter import ttk


class BusyState:
    def __init__(self,root):
        self.root=root;self.depth=0;self.cursors=[]

    def show(self):
        def visit(widget):
            try:
                if 'cursor' in widget.keys():
                    self.cursors.append((widget,widget.cget('cursor')))
                    widget.configure(cursor='wait')
                for child in widget.winfo_children():visit(child)
            except tk.TclError:pass
        visit(self.root)
        # Flush drawing only. Do not dispatch another click/key while the action runs.
        try:self.root.update_idletasks()
        except tk.TclError:pass

    def restore(self):
        cursors,self.cursors=self.cursors,[]
        for widget,cursor in reversed(cursors):
            try:widget.configure(cursor=cursor)
            except tk.TclError:pass  # The callback may destroy its window.

    @contextmanager
    def handling(self):
        outer=self.depth==0;self.depth+=1
        try:
            if outer:self.show()
            yield
        finally:
            self.depth-=1
            if outer:self.restore()

    @contextmanager
    def waiting(self):
        """A nested event loop waits for a user, so it must have normal cursors."""
        depth=self.depth
        self.restore();self.depth=0
        try:yield
        finally:
            self.depth=depth
            if depth:self.show()


def state(widget):
    root=widget._root()
    if not hasattr(root,'_busy_actions'):root._busy_actions=BusyState(root)
    return root._busy_actions


@contextmanager
def input_wait(widget):
    busy=getattr(widget._root(),'_busy_actions',None)
    if busy is None:
        yield
    else:
        with busy.waiting():yield


class ActionButton(ttk.Button):
    """Declare busy=True at construction; the action itself stays UI-independent."""
    def __init__(self,master=None,*,command=None,busy=False,**kwargs):
        self._action=command;self._busy=busy
        super().__init__(master,command=self._run,**kwargs)

    def _run(self):
        if self._action is None:return
        if not self._busy:return self._action()
        with state(self).handling():return self._action()

    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs};cnf=None
        if 'command' in kwargs:
            self._action=kwargs['command'];kwargs['command']=self._run
        if 'busy' in kwargs:self._busy=kwargs.pop('busy')
        return super().configure(cnf,**kwargs)

    config=configure
