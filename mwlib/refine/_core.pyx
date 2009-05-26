cdef class token_walker(object):
    cdef object skip_types
    cdef object skip_tags
    
    def __init__(self, skip_types=set(), skip_tags=set()):
        self.skip_types =  skip_types
        self.skip_tags = skip_tags
        
    def __call__(self, list tokens):
        cdef set skip_types =  self.skip_types
        cdef set skip_tags =  self.skip_tags
        
        res =  []
        cdef list todo = [tokens]
        res.append(tokens)
        cdef list tmp
        cdef object children
        
        while todo:
            tmp = todo.pop()
            for x in tmp:
                children = x.children
                if x.type not in skip_types and x.tagname not in skip_tags:
                    if children is not None:
                        res.append(children)
                        todo.append(children)
                else:
                    # print "skip", x, x.children
                    if children is not None:
                        todo.append(children)
        return res
