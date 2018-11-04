#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
            Based on project:
            https://github.com/Bertrand256/dash-masternode-tool
"""
import threading
import traceback
from functools import partial

from workerThread import WorkerThread


class ThreadFuns:
    _global_thread_pool = []

    @classmethod
    @property
    def get_last_thread(cls):
        return cls._global_thread_pool[-1] if cls._global_thread_pool else None

    @classmethod
    def runInThread(cls,
                    worker_fun, worker_fun_args,
                    on_thread_finish=None, on_thread_exception=None,
                    skip_raise_exception=False):
            """
            Run a function inside a thread.
            :param worker_fun: reference to function to be executed inside a thread
            :param worker_fun_args: arguments passed to a thread function
            :param on_thread_finish: function to be called after thread finishes its execution
            :param skip_raise_exception: Exception raised inside the 'worker_fun' will be passed to the calling thread if:
                - on_thread_exception is a valid function (it's exception handler)
                - skip_raise_exception is False
            :return: reference to a thread object
            """
            
            def on_thread_finished_int(thread_arg, on_thread_finish_arg, skip_raise_exception_arg, on_thread_exception_arg):
                if thread_arg.worker_exception:
                    if on_thread_exception_arg:
                        on_thread_exception_arg(thread_arg.worker_exception)
                    else:
                        if not skip_raise_exception_arg:
                            raise thread_arg.worker_exception
                else:
                    if on_thread_finish_arg:
                        on_thread_finish_arg()
    
            if threading.current_thread() != threading.main_thread():
                # starting thread from another thread causes an issue of not passing arguments'
                # values to on_thread_finished_int function, so on_thread_finish is not called
                st = traceback.format_stack()
                print('Running thread from inside another thread. Stack: \n' + ''.join(st))
            
            thread = WorkerThread(worker_fun=worker_fun, worker_fun_args=worker_fun_args)
    
            # in Python 3.5 local variables sometimes are removed before calling on_thread_finished_int
            # so we have to bind that variables with the function ref
            bound_on_thread_finished = partial(on_thread_finished_int, thread, on_thread_finish, skip_raise_exception,
                                               on_thread_exception)
    
            thread.finished.connect(bound_on_thread_finished)
            thread.started.connect(lambda: cls._global_thread_pool.append(thread))
            thread.finished.connect(lambda: cls._global_thread_pool.remove(thread))
            thread.start()
            return thread
        