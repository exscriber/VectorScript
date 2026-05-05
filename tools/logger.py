# This code is freely distributable under the terms of the [MIT license]
# Copyright (c) 2026 Nick N. Zinovenko


import inspect


class Logger:
    obj = None

    @classmethod
    def log(self, *args, **kwds):
        frame = inspect.currentframe().f_back.f_back
        obj = frame.f_locals.get('self') or '__main__'
        if obj is not self.obj:
            self.obj = obj
            print('\x1b[31m', self.obj, '\x1b[0m', sep='')
        print(*args, **kwds)


def log(*args, **kwds):
    Logger.log(*args, **kwds)
