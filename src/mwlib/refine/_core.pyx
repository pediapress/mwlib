# -*- mode: cython -*-

cdef class token_walker(object):
    cdef object skip_tags

    def __init__(self, skip_tags=set()):
        self.skip_tags = skip_tags
        
    def __call__(self, list tokens):
        cdef set skip_tags =  self.skip_tags
        
        cdef list res =  [tokens]
        cdef list todo = [tokens]
        cdef list children
        
        while todo:
            for x in todo.pop():
                children = x.children
                if children:
                    todo.append(children)
                    if x.tagname not in skip_tags:
                        res.append(children)
        return res
