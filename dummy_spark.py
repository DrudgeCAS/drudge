"""
Minimal dummy_spark module for testing.
"""

class SparkConf:
    def __init__(self):
        pass

class Broadcast:
    def __init__(self, value):
        self.value = value

class SparkContext:
    def __init__(self, master='', conf=None):
        self.master = master
        self.conf = conf
        
    def broadcast(self, value):
        return Broadcast(value)