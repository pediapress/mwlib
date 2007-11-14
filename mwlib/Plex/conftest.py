
import py
class DoNotTest(py.test.collect.Directory):
    def run(self):
        pass

Directory = DoNotTest
