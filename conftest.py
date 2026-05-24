import sys
import os

root = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(root, 'compiler', 'lexical'))
sys.path.insert(0, os.path.join(root, 'compiler', 'semantic'))
sys.path.insert(0, os.path.join(root, 'compiler', 'codegen'))
sys.path.insert(0, os.path.join(root, 'compiler', 'validation'))