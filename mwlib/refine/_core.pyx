cdef class token_walker(object):
    cdef object skip_tags
    
    def __init__(self, skip_tags=set()):
        self.skip_tags = skip_tags
        
    def __call__(self, list tokens):
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
                if x.tagname not in skip_tags:
                    if children is not None:
                        res.append(children)
                        todo.append(children)
                else:
                    # print "skip", x, x.children
                    if children is not None:
                        todo.append(children)
        return res
