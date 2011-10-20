
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

# '''bold'''
# ''italic''

class state(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def clone(self, **kw):
        s=state(**self.__dict__)
        s.__dict__.update(kw)
        return s
    
    def __repr__(self):
        res = ["<state "]
        res.append(" %s " % self.apocount)
        if self.is_bold:
            res.append("bold ")
        if self.is_italic:
            res.append("italic ")
        
        res.append(">")
        return "".join(res)
    
    def get_next(self, count, res=None, previous=None):
        if previous is None:
            previous = self
            
        if res is None:
            res=[]

        def nextstate(**kw):
            cl = self.clone(previous=previous, **kw)
            res.append(cl)

        assert count>=2, "internal error"
        
        if count==2:
            nextstate(is_italic=not self.is_italic)
            
        if count==3:
            nextstate(is_bold=not self.is_bold)

            s=self.clone(apocount=self.apocount+1, previous=previous)
            
            s.get_next(2, res, previous=previous)
            

        if count==4:
            s=self.clone(apocount=self.apocount+1)
            s.get_next(3, res, previous=previous)
            
        if count==5:
            for x in self.get_next(2):
                x.get_next(3, res, previous=previous)
            for x in self.get_next(3):
                x.get_next(2, res, previous=previous)

            
            s=self.clone(apocount=self.apocount)
            s.get_next(4, res, previous=previous)


        if count>5:
            s = self.clone(apocount=self.apocount+(count-5))
            s.get_next(5, res, previous=previous)
            
        return res

def sort_states(states):
    tmp = [((x.apocount+x.is_bold+x.is_italic), x) for x in states]
    tmp.sort()
    return [x[1] for x in tmp]
    
def compute_path(counts):
    states = [state(is_bold=False, is_italic=False, previous=None, apocount=0)]
    
    for count in counts:
        new_states = []
        for s in states:
            s.get_next(count, new_states)
        states = new_states
        states = sort_states(states)
        best = states[0]
        #print "STATES:", states
        if best.apocount==0 and not best.is_italic and not best.is_bold:
            #print "CHOOSING PERFECT STATE"
            states = [best]
        else:
            states = states[:32]
            
    tmp = states[0]

    res = []
    while tmp.previous is not None:
        res.append(tmp)
        tmp = tmp.previous

    res.reverse()
    assert len(res)==len(counts)
    return res
